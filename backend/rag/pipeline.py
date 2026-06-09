"""
AthleteCare RAG pipeline — AWS Bedrock Agent backend.

RAGEngine is the single public surface used by the Flask web app.
It wraps a single boto3 call to Bedrock's invoke_agent API, which handles
retrieval, generation, and conversational context management internally.

Classes
-------
RAGEngine -- instantiate once at startup; call .ask() per user question
"""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

_AWS_ACCESS_KEY_ID     = os.environ.get("AWS_ACCESS_KEY_ID", "")
_AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
_AWS_REGION            = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
_AGENT_ID              = os.environ.get("BEDROCK_AGENT_ID", "")
_AGENT_ALIAS_ID        = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "")


def _log(msg: str) -> None:
    print(f"[pipeline] {msg}", flush=True)


def _source_from_location(location: dict | None) -> str:
    """Extract a display filename from a Bedrock reference location."""
    if not location:
        return "unknown"

    loc_type = location.get("type", "")
    if loc_type == "S3":
        uri = (location.get("s3Location") or {}).get("uri", "")
        if uri:
            return unquote(Path(urlparse(uri).path).name) or uri

    for key in ("uri", "url"):
        uri = location.get(key)
        if uri:
            return unquote(Path(urlparse(uri).path).name) or uri

    return "unknown"


def _parse_retrieved_reference(ref: dict) -> dict | None:
    """Normalise one Bedrock retrievedReference for the UI."""
    if not isinstance(ref, dict):
        return None

    location = ref.get("location") or {}
    source = _source_from_location(location)
    if source == "unknown":
        return None

    metadata = ref.get("metadata") or {}
    score = 0.0
    for key in ("score", "relevanceScore", "relevance_score"):
        if key in metadata:
            try:
                score = float(metadata[key])
            except (TypeError, ValueError):
                score = 0.0
            break

    snippet = ((ref.get("content") or {}).get("text") or "").strip()
    return {"source": source, "score": score, "snippet": snippet[:240]}


def _collect_retrieved_references(obj, bucket: list[dict]) -> None:
    """Walk a trace/chunk object and collect all retrievedReferences."""
    if isinstance(obj, dict):
        refs = obj.get("retrievedReferences")
        if isinstance(refs, list):
            for ref in refs:
                parsed = _parse_retrieved_reference(ref)
                if parsed:
                    bucket.append(parsed)
        for value in obj.values():
            _collect_retrieved_references(value, bucket)
    elif isinstance(obj, list):
        for item in obj:
            _collect_retrieved_references(item, bucket)


def _dedupe_sources(sources: list[dict]) -> list[dict]:
    """Keep one entry per source file, preferring the highest score."""
    best: dict[str, dict] = {}
    for item in sources:
        key = item["source"]
        if key not in best or item.get("score", 0) > best[key].get("score", 0):
            best[key] = item
    ordered = sorted(best.values(), key=lambda s: s.get("score", 0), reverse=True)
    return [{"source": s["source"], "score": s.get("score", 0)} for s in ordered]

# ------------------------------------------------------------------
# RAG ENGINE
# ------------------------------------------------------------------

class RAGEngine:
    """
    Thin wrapper around the Bedrock invoke_agent API.

    Lifecycle
    ---------
    1. Instantiate once (e.g. at Flask app startup).  The boto3 client is
       created and credentials are validated immediately.
    2. Call .ask(question, session_id) for each user turn.  The Bedrock
       Agent manages conversational context internally using the sessionId —
       no local history concatenation is required.

    Thread safety
    -------------
    boto3 clients are thread-safe for read operations.  All session state
    is managed server-side by Bedrock, so concurrent requests are safe.
    """

    def __init__(self) -> None:
        self.ready:  bool = False
        self.status: str  = "connecting"

        missing = [v for v, k in [
            ("AWS_ACCESS_KEY_ID",       _AWS_ACCESS_KEY_ID),
            ("AWS_SECRET_ACCESS_KEY",   _AWS_SECRET_ACCESS_KEY),
            ("BEDROCK_AGENT_ID",        _AGENT_ID),
            ("BEDROCK_AGENT_ALIAS_ID",  _AGENT_ALIAS_ID),
        ] if not k]

        if missing:
            self.status = f"error: missing env vars: {', '.join(missing)}"
            _log(self.status)
            return

        try:
            self._client = boto3.client(
                service_name="bedrock-agent-runtime",
                region_name=_AWS_REGION,
                aws_access_key_id=_AWS_ACCESS_KEY_ID,
                aws_secret_access_key=_AWS_SECRET_ACCESS_KEY,
            )
            self._agent_id       = _AGENT_ID
            self._agent_alias_id = _AGENT_ALIAS_ID
            self.ready  = True
            self.status = "ready"
            _log(f"Connected — agentId={_AGENT_ID} agentAliasId={_AGENT_ALIAS_ID}")
        except (BotoCoreError, ClientError) as exc:
            self.status = f"error: {exc}"
            _log(f"Failed to create Bedrock client: {exc}")

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def ask(self, question: str, session_id: str) -> dict:
        """
        Invoke the Bedrock Agent and stream the response.

        Conversational context is managed server-side by the Agent using
        the sessionId — no client-side history concatenation is needed.

        Parameters
        ----------
        question   : the user's current question
        session_id : Bedrock Agent session identifier (persists context
                     across turns for the same session)

        Returns
        -------
        dict with keys:
            answer  -- the model's answer string
            sources -- list of {source, score} from KB retrieval traces
            context -- alias for sources (used by the frontend)

        Raises RuntimeError if the engine is not ready.
        Raises ClientError / BotoCoreError on Bedrock API failures.
        """
        if not self.ready:
            raise RuntimeError(f"RAG engine is not ready: {self.status}")

        response = self._client.invoke_agent(
            agentId=self._agent_id,
            agentAliasId=self._agent_alias_id,
            sessionId=session_id,
            inputText=question,
            enableTrace=True,
        )

        answer_text = ""
        raw_sources: list[dict] = []

        for event in response.get("completion", []):
            chunk = event.get("chunk")
            if chunk:
                if chunk.get("bytes"):
                    answer_text += chunk["bytes"].decode("utf-8")
                attribution = chunk.get("attribution")
                if attribution:
                    _collect_retrieved_references(attribution, raw_sources)

            trace_event = event.get("trace")
            if trace_event:
                trace_data = trace_event.get("trace", {})
                _collect_retrieved_references(trace_data, raw_sources)

                if "orchestrationTrace" in trace_data:
                    orch = trace_data["orchestrationTrace"]
                    if "invocationInput" in orch:
                        inv = orch["invocationInput"]
                        if "actionGroupInvocationInput" in inv:
                            action = inv["actionGroupInvocationInput"]
                            print(
                                f"[Tool Invoked]: {action.get('function', '?')} "
                                f"| Parameters: {action.get('parameters', [])}",
                                flush=True,
                            )

        sources = _dedupe_sources(raw_sources)
        if sources:
            _log(f"Retrieved {len(sources)} source(s): {[s['source'] for s in sources]}")
        else:
            _log("No KB sources found in trace — enableTrace is on; check Agent KB config")

        return {
            "answer":  answer_text.strip(),
            "sources": sources,
            "context": sources,
        }
