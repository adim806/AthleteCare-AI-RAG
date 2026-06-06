"""
AthleteCare RAG system — documented test queries.

Each test sends a real question through the full RAGEngine pipeline and
validates that the answer is non-empty and the retrieved context contains
at least one result.  Expected answer keywords are checked to give
confidence that the retrieval is pointing at the right document.

Run with:
    cd RAG-App
    pytest tests/test_queries.py -v

NOTE: These tests hit the HuggingFace cloud API and the Gemini API, so they
require a live internet connection and valid API keys.  They may take a few
minutes on the first run because the engine has to embed all documents.
"""

import sys
import os

# Ensure the project root is on sys.path for absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from backend.rag.pipeline import RAGEngine  # noqa: E402


# ------------------------------------------------------------------
# SHARED FIXTURE — initialise the engine once for the test session
# ------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine() -> RAGEngine:
    """
    Initialise a single RAGEngine for all tests.

    Embedding all documents is expensive (~1-2 min on first run) so we
    share one instance across the session.
    """
    e = RAGEngine()
    e.initialise()
    assert e.ready, "RAGEngine failed to initialise"
    return e


# ==================================================================
# TEST 1 — Player rehab status
# ==================================================================

def test_player_rehab_status(engine: RAGEngine):
    """
    Question : What is Oren Shoval's current rehab status?
    Expected : Answer mentions rehab or treatment details from players.txt
               or clinical_notes.txt.
    """
    question = "What is Oren Shoval's current rehab status?"
    result   = engine.answer(question)

    answer  = result["answer"].lower()
    context = result["context"]

    assert answer, "Answer must not be empty"
    assert len(context) > 0, "At least one context chunk must be retrieved"

    assert any(kw in answer for kw in ["rehab", "rehabilitation", "treatment", "shoval", "injury"]), (
        f"Expected rehab/player keywords in answer.\nGot: {result['answer']}"
    )

    print("\n[TEST 1] Player rehab status")
    print(f"  Q: {question}")
    print(f"  A: {result['answer'][:300]}")
    print(f"  Sources: {[c['source'] for c in context]}")


# ==================================================================
# TEST 2 — ACL rehabilitation duration
# ==================================================================

def test_acl_rehab_duration(engine: RAGEngine):
    """
    Question : How long does ACL reconstruction rehabilitation take?
    Expected : Answer mentions timeline/weeks/months from
               return_to_play.txt or treatment_protocols.txt.
    """
    question = "How long does ACL reconstruction rehabilitation take?"
    result   = engine.answer(question)

    answer  = result["answer"].lower()
    context = result["context"]

    assert answer, "Answer must not be empty"
    assert len(context) > 0, "At least one context chunk must be retrieved"

    assert any(kw in answer for kw in ["week", "month", "month", "acl", "rehabilitat"]), (
        f"Expected duration/ACL keywords in answer.\nGot: {result['answer']}"
    )

    print("\n[TEST 2] ACL rehabilitation duration")
    print(f"  Q: {question}")
    print(f"  A: {result['answer'][:300]}")
    print(f"  Sources: {[c['source'] for c in context]}")


# ==================================================================
# TEST 3 — FIFA 11+ warm-up protocol
# ==================================================================

def test_fifa_11_plus_warmup(engine: RAGEngine):
    """
    Question : What does the FIFA 11+ warm-up include?
    Expected : Answer mentions exercises/protocol from
               prevention_guidelines.txt.
    """
    question = "What does the FIFA 11+ warm-up include?"
    result   = engine.answer(question)

    answer  = result["answer"].lower()
    context = result["context"]

    assert answer, "Answer must not be empty"
    assert len(context) > 0, "At least one context chunk must be retrieved"

    assert any(kw in answer for kw in ["fifa", "11+", "warm", "exercise", "prevention"]), (
        f"Expected FIFA 11+ keywords in answer.\nGot: {result['answer']}"
    )

    print("\n[TEST 3] FIFA 11+ warm-up protocol")
    print(f"  Q: {question}")
    print(f"  A: {result['answer'][:300]}")
    print(f"  Sources: {[c['source'] for c in context]}")


# ==================================================================
# TEST 4 — Players on prevention programmes
# ==================================================================

def test_players_on_prevention_programmes(engine: RAGEngine):
    """
    Question : Which players are currently on prevention programmes?
    Expected : Answer names players or mentions prevention from
               players.txt or prevention_guidelines.txt.
    """
    question = "Which players are currently on prevention programmes?"
    result   = engine.answer(question)

    answer  = result["answer"].lower()
    context = result["context"]

    assert answer, "Answer must not be empty"
    assert len(context) > 0, "At least one context chunk must be retrieved"

    assert any(kw in answer for kw in ["prevention", "programme", "program", "player"]), (
        f"Expected prevention/player keywords in answer.\nGot: {result['answer']}"
    )

    print("\n[TEST 4] Players on prevention programmes")
    print(f"  Q: {question}")
    print(f"  A: {result['answer'][:300]}")
    print(f"  Sources: {[c['source'] for c in context]}")


# ==================================================================
# TEST 5 — ACWR injury risk threshold
# ==================================================================

def test_acwr_injury_risk(engine: RAGEngine):
    """
    Question : What ACWR value indicates high injury risk?
    Expected : Answer mentions a numeric threshold from
               fitness_assessments.txt or prevention_guidelines.txt.
    """
    question = "What ACWR value indicates high injury risk?"
    result   = engine.answer(question)

    answer  = result["answer"].lower()
    context = result["context"]

    assert answer, "Answer must not be empty"
    assert len(context) > 0, "At least one context chunk must be retrieved"

    assert any(kw in answer for kw in ["acwr", "ratio", "1.", "risk", "load"]), (
        f"Expected ACWR/threshold keywords in answer.\nGot: {result['answer']}"
    )

    print("\n[TEST 5] ACWR injury risk threshold")
    print(f"  Q: {question}")
    print(f"  A: {result['answer'][:300]}")
    print(f"  Sources: {[c['source'] for c in context]}")


# ==================================================================
# TEST 6 — Conversation history (multi-turn)
# ==================================================================

def test_multi_turn_history(engine: RAGEngine):
    """
    Tests that passing history doesn't break the pipeline and the answer
    is still coherent.
    """
    history = [
        {"role": "user",      "content": "How long does ACL rehabilitation take?"},
        {"role": "assistant", "content": "ACL reconstruction rehabilitation typically takes 9-12 months."},
    ]
    question = "What are the return-to-play criteria after that?"
    result   = engine.answer(question, history=history)

    answer  = result["answer"].lower()
    assert answer, "Answer must not be empty with history"
    assert len(result["context"]) > 0, "Context must be returned with history"

    print("\n[TEST 6] Multi-turn conversation")
    print(f"  Q: {question}")
    print(f"  A: {result['answer'][:300]}")
    print(f"  Sources: {[c['source'] for c in result['context']]}")


# ==================================================================
# TEST 7 — Irrelevant question (out-of-domain)
# ==================================================================

def test_irrelevant_question(engine: RAGEngine):
    """
    Question : What is the capital of France?
    Expected : The system should indicate it does not have enough
               information in the documents to answer, rather than
               hallucinating from general knowledge.
    """
    question = "What is the capital of France?"
    result   = engine.answer(question)

    answer  = result["answer"].lower()
    context = result["context"]

    assert answer, "Answer must not be empty"

    not_in_docs_phrases = [
        "don't have enough information",
        "do not have enough information",
        "not in the",
        "no relevant information",
        "not covered",
        "outside the scope",
        "cannot find",
        "no information",
        "is not in the context",
        "not available",
    ]
    has_disclaimer = any(phrase in answer for phrase in not_in_docs_phrases)

    assert has_disclaimer or len(context) == 0, (
        "Expected the model to refuse or indicate lack of information for "
        f"an out-of-domain question.\nGot: {result['answer']}"
    )

    print("\n[TEST 7] Irrelevant question (out-of-domain)")
    print(f"  Q: {question}")
    print(f"  A: {result['answer'][:300]}")
    print(f"  Sources: {[c['source'] for c in context]}")
    print(f"  Context count: {len(context)} (0 means threshold filtered all)")
