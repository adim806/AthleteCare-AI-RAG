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
            sources -- empty list (citations provided by the Agent's KB)
            context -- empty list (alias for sources)

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
        )

        answer_text = ""

        for event in response.get("completion", []):
            chunk = event.get("chunk")
            if chunk:
                answer_text += chunk["bytes"].decode("utf-8")

            trace_event = event.get("trace")
            if trace_event:
                trace_data = trace_event.get("trace", {})
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

        return {
            "answer":  answer_text.strip(),
            "sources": [],
            "context": [],
        }
