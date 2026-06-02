"""
AthleteCare RAG pipeline — AWS Bedrock Knowledge Base backend.

RAGEngine is the single public surface used by the Flask web app.
It wraps a single boto3 call to Bedrock's retrieve_and_generate API,
which handles both retrieval and generation in one round-trip.

Classes
-------
RAGEngine -- instantiate once at startup; call .ask() per user question
"""

import os

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
_KB_ID                 = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID", "")

# Allow full ARN override; otherwise resolve at startup (inference profile
# required for newer models such as Claude Haiku 4.5).
_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-haiku-4-5-20251001-v1:0",
)

_SYSTEM_PROMPT = (
    "You are AthleteCare, a medical assistant for FC Velocity. "
    "Answer only from the provided context — player records, injury history, "
    "treatment protocols, and fitness data. "
    "If not in the context, say so clearly."
)

# Bedrock prompt template — $search_results$ and $output_format_instructions$
# are substituted automatically by Bedrock.
_PROMPT_TEMPLATE = (
    _SYSTEM_PROMPT
    + "\n\n$search_results$\n\n$output_format_instructions$"
)


def _log(msg: str) -> None:
    print(f"[pipeline] {msg}", flush=True)


def _resolve_model_arn(region: str, model_id: str) -> str:
    """
    Return the modelArn Bedrock expects for retrieve_and_generate.

    Newer models (e.g. Claude Haiku 4.5) require an inference-profile ARN
    rather than a foundation-model ARN.  We look up the profile automatically;
    set BEDROCK_MODEL_ARN in .env to skip lookup.
    """
    override = os.environ.get("BEDROCK_MODEL_ARN")
    if override:
        return override

    bedrock = boto3.client(
        "bedrock",
        region_name=region,
        aws_access_key_id=_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=_AWS_SECRET_ACCESS_KEY,
    )

    for profile_id in (f"us.{model_id}", f"global.{model_id}"):
        try:
            profile = bedrock.get_inference_profile(
                inferenceProfileIdentifier=profile_id,
            )
            arn = profile["inferenceProfileArn"]
            _log(f"Resolved inference profile {profile_id} -> {arn}")
            return arn
        except ClientError:
            continue

    return f"arn:aws:bedrock:{region}::foundation-model/{model_id}"


# ------------------------------------------------------------------
# RAG ENGINE
# ------------------------------------------------------------------

class RAGEngine:
    """
    Thin wrapper around the Bedrock retrieve_and_generate API.

    Lifecycle
    ---------
    1. Instantiate once (e.g. at Flask app startup).  The boto3 client is
       created and credentials are validated immediately — no background
       indexing step is needed because retrieval is handled by Bedrock.
    2. Call .ask(question, history) for each user turn.

    Thread safety
    -------------
    boto3 clients are thread-safe for read operations.  All calls are
    stateless (no local index), so concurrent requests are safe.
    """

    def __init__(self) -> None:
        self.ready:  bool = False
        self.status: str  = "connecting"

        missing = [v for v, k in [
            ("AWS_ACCESS_KEY_ID",        _AWS_ACCESS_KEY_ID),
            ("AWS_SECRET_ACCESS_KEY",    _AWS_SECRET_ACCESS_KEY),
            ("BEDROCK_KNOWLEDGE_BASE_ID", _KB_ID),
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
            self._kb_id     = _KB_ID
            self._model_arn = _resolve_model_arn(_AWS_REGION, _MODEL_ID)
            self.ready  = True
            self.status = "ready"
            _log(f"Connected — KB={_KB_ID} model={self._model_arn}")
        except (BotoCoreError, ClientError) as exc:
            self.status = f"error: {exc}"
            _log(f"Failed to create Bedrock client: {exc}")

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def ask(
        self,
        question: str,
        history: list[dict] | None = None,
    ) -> dict:
        """
        Retrieve from the Bedrock Knowledge Base and generate an answer.

        Conversation history is prepended to the question text so that
        Bedrock's prompt sees prior context without requiring server-side
        session management.

        Parameters
        ----------
        question : the user's current question
        history  : list of {"role": "user"|"assistant", "content": str}

        Returns
        -------
        dict with keys:
            answer  -- the model's answer string
            sources -- list of {"source": str, "score": float}

        Raises RuntimeError if the engine is not ready.
        Raises ClientError / BotoCoreError on Bedrock API failures.
        """
        if not self.ready:
            raise RuntimeError(f"RAG engine is not ready: {self.status}")

        # Prepend conversation history into the input text.
        if history:
            lines = []
            for msg in history:
                role = "User" if msg["role"] == "user" else "Assistant"
                lines.append(f"{role}: {msg['content']}")
            input_text = (
                "Conversation so far:\n"
                + "\n".join(lines)
                + f"\n\nCurrent question: {question}"
            )
        else:
            input_text = question

        response = self._client.retrieve_and_generate(
            input={"text": input_text},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": self._kb_id,
                    "modelArn": self._model_arn,
                    "generationConfiguration": {
                        "promptTemplate": {
                            "textPromptTemplate": _PROMPT_TEMPLATE,
                        },
                    },
                    "retrievalConfiguration": {
                        "vectorSearchConfiguration": {
                            "numberOfResults": 5,
                        },
                    },
                },
            },
        )

        answer_text = response.get("output", {}).get("text", "").strip()
        sources     = _extract_sources(response)

        return {
            "answer":  answer_text,
            "sources": sources,
            # "context" alias keeps tests/older callers working
            "context": sources,
        }

    # Backward-compatible alias used by tests and any older call sites.
    def answer(
        self,
        question: str,
        history: list[dict] | None = None,
        **_kwargs,
    ) -> dict:
        """Alias for ask(); retained for backward compatibility."""
        return self.ask(question, history)


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def _extract_sources(response: dict) -> list[dict]:
    """
    Pull unique source URIs and scores from a retrieve_and_generate response.

    Bedrock returns a `citations` list; each citation may reference one or
    more retrieved documents.  Scores are optional metadata.
    """
    sources: list[dict] = []
    seen:    set[str]   = set()

    for citation in response.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            loc = ref.get("location", {})

            # Resolve the document URI — support S3 and web locations.
            uri: str = (
                loc.get("s3Location",  {}).get("uri")
                or loc.get("webLocation", {}).get("url")
                or "unknown"
            )

            if uri in seen:
                continue
            seen.add(uri)

            # Score is stored in metadata when available.
            raw_score = ref.get("metadata", {}).get("score", 0.0)
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = 0.0

            # Use only the filename/key portion for display.
            display = uri.split("/")[-1] if uri != "unknown" else "unknown"

            sources.append({"source": display, "score": score})

    return sources
