"""
AthleteCare entry point.

Run from the RAG-App/ directory:
    python run.py
"""

from backend.app import app

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
