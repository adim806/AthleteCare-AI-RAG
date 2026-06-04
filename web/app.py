"""
AthleteCare Flask web application.

Endpoints
---------
GET  /                              -- serve the chat UI
GET  /api/status                    -- RAG engine readiness
GET  /api/dashboard                 -- squad status + documents by audience
GET  /api/sessions                  -- list all sessions
POST /api/sessions                  -- create a new session
GET  /api/sessions/<id>/messages    -- fetch all messages for a session
DELETE /api/sessions/<id>           -- delete a session and its messages
PATCH  /api/sessions/<id>/title     -- rename a session
POST /api/ask                       -- submit a question and get an answer
"""

import os
import sys

from flask import Flask, jsonify, render_template, request

# ------------------------------------------------------------------
# PATH BOOTSTRAP
# Ensure the project root (parent of web/) is on sys.path so that
# `import database` and `from rag.pipeline import RAGEngine` work
# regardless of the working directory when the app is launched.
# ------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dashboard  # noqa: E402
import database as db  # noqa: E402 — import after path bootstrap
from rag.pipeline import RAGEngine  # noqa: E402

# ------------------------------------------------------------------
# FLASK APP
# ------------------------------------------------------------------

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["JSON_SORT_KEYS"] = False

# ------------------------------------------------------------------
# RAG ENGINE — ready immediately; Bedrock needs no local index build
# ------------------------------------------------------------------

_engine = RAGEngine()

# ------------------------------------------------------------------
# DATABASE INITIALISATION
# ------------------------------------------------------------------

with app.app_context():
    db.init_db()


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def _ok(data=None, **kwargs):
    payload = {"data": data or {}}
    payload.update(kwargs)
    return jsonify(payload)


def _err(message: str, code: int = 400):
    return jsonify({"error": {"message": message}}), code


# ------------------------------------------------------------------
# ROUTES — STATIC
# ------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ------------------------------------------------------------------
# ROUTES — STATUS
# ------------------------------------------------------------------

@app.route("/api/status")
def status():
    return _ok(
        data={
            "ready":    _engine.ready,
            "status":   _engine.status,
            "progress": {"current": 0, "total": 0},
            "vectors":  0,
        }
    )


@app.route("/api/dashboard")
def knowledge_dashboard():
    return _ok(data=dashboard.get_dashboard())


# ------------------------------------------------------------------
# ROUTES — SESSIONS
# ------------------------------------------------------------------

@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    return _ok(data=db.list_sessions())


@app.route("/api/sessions", methods=["POST"])
def create_session():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "New conversation").strip()[:120]
    session = db.create_session(title=title)
    return _ok(data=session), 201


@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def get_messages(session_id: str):
    if not db.get_session(session_id):
        return _err("Session not found.", 404)
    return _ok(data=db.get_messages(session_id))


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id: str):
    if not db.get_session(session_id):
        return _err("Session not found.", 404)
    db.delete_session(session_id)
    return "", 204


@app.route("/api/sessions/<session_id>/title", methods=["PATCH"])
def rename_session(session_id: str):
    if not db.get_session(session_id):
        return _err("Session not found.", 404)
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()[:120]
    if not title:
        return _err("Title must not be empty.")
    db.update_session_title(session_id, title)
    return _ok(data={"title": title})


# ------------------------------------------------------------------
# ROUTES — ASK
# ------------------------------------------------------------------

@app.route("/api/ask", methods=["POST"])
def ask():
    if not _engine.ready:
        return _err(
            f"The knowledge base is unavailable ({_engine.status}). "
            "Please check your AWS credentials and Knowledge Base ID.",
            503,
        )

    body = request.get_json(silent=True) or {}
    question   = (body.get("question")   or "").strip()
    session_id = (body.get("session_id") or "").strip()

    if not question:
        return _err("question must not be empty.")

    if not session_id:
        return _err("session_id must not be empty.")

    if not db.get_session(session_id):
        return _err("Session not found.", 404)

    # Persist the user message
    db.add_message(session_id=session_id, role="user", content=question)

    # Build conversation history (exclude current question — already added)
    history = db.get_history_for_llm(session_id, limit=20)
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    # Run the RAG pipeline
    try:
        result = _engine.ask(question=question, history=history)
    except Exception as exc:
        return _err(f"RAG pipeline error: {exc}", 500)

    answer_text = result["answer"]
    sources     = result["sources"]

    # Auto-title the session after the first user message
    session = db.get_session(session_id)
    if session and session["title"] == "New conversation":
        auto_title = question[:60] + ("…" if len(question) > 60 else "")
        db.update_session_title(session_id, auto_title)

    # Persist the assistant message (sources stored under "context" key for
    # compatibility with the existing frontend source-display logic)
    db.add_message(
        session_id=session_id,
        role="assistant",
        content=answer_text,
        context=sources,
    )

    return _ok(
        data={
            "answer":     answer_text,
            "context":    sources,
            "session_id": session_id,
        }
    )


# ------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
