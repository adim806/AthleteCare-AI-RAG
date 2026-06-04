# AthleteCare — Sports Medicine Intelligence for Professional Football

A Retrieval-Augmented Generation (RAG) web application that serves as a
smart medical assistant for the **medical and fitness staff** of a professional
football club. The system is built for a critical department whose mission is
to **maintain player availability and prevent injuries** — keeping the squad
fit, load-managed, and ready to perform.

Each staff member asks questions in natural language and receives answers
**grounded in club documents with citations**, without manually opening files.

> A RAG-powered smart medical assistant for a professional football club's medical
> staff. Every team member — physiotherapist, physician, fitness coach, nutritionist —
> asks questions in natural language and receives document-grounded answers with
> citations, without manually opening files.

<img width="2558" height="1343" alt="image1" src="https://github.com/user-attachments/assets/cd245f0b-b89b-4a07-b063-ba0095652b23" />


### Five target audiences (one platform)

The welcome-screen **Knowledge Library** organises documents by role so each
audience sees what matters to their workflow:

| Audience | Typical use |
|----------|-------------|
| **Chief Medical Officer** | Injury clearance, RTP authority, concussion, squad oversight |
| **Physiotherapists** | Treatment protocols, clinical notes, rehab progressions |
| **Sports Scientists** | Load metrics, ACWR, fitness testing, injury-risk monitoring |
| **Fitness Coaches** | Training availability, prevention programmes, session planning |
| **Sports Nutritionists** | Player diet plans, supplementation, recovery nutrition |

## Topic & Motivation

The chosen domain is **sports medicine documentation** — the kind of
knowledge base that every professional football club's medical department
maintains: player medical records, injury history, treatment protocols,
return-to-play criteria, fitness assessments, and clinical session notes.

This topic was selected because:

- It mirrors a real professional need — medical staff constantly look up
  treatment protocols and player-specific rehab plans under time pressure.
- The documents contain factual, verifiable clinical content, which makes it
  straightforward to validate retrieval accuracy.
- It demonstrates a high-value RAG use case (medical knowledge search) that
  translates directly to real-world sports medicine operations.

## Architecture Overview

```
User ──▶ Flask Web UI ──▶ POST /api/ask
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
         AWS Bedrock Knowledge Base   Conversation
         retrieve_and_generate        History (SQLite)
         (retrieval + generation)            │
                    │                        │
                    └────────┬───────────────┘
                             ▼
                      Grounded Answer
                      + source citations
```

| Component | Technology |
|-----------|-----------|
| Web framework | Flask 3 |
| RAG backend | AWS Bedrock Knowledge Base (`retrieve_and_generate`) |
| Generation model | Anthropic Claude Haiku 4.5 (via inference profile) |
| Embeddings (managed by Bedrock) | Amazon Titan Embed Text v2 |
| AWS SDK | boto3 |
| Conversation store | SQLite |
| Containerisation | Docker |

There is **no local vector index**. Retrieval, embedding, and generation are
handled entirely by AWS Bedrock. The app starts immediately — no 1–2 minute
embedding step on launch.

## Data Source

The corpus consists of **14 medical and performance documents** (plus a hero
visual asset) covering FC Velocity's squad and clinical operations:

| File | Content |
|------|---------|
| `players.txt` | Player profiles — positions, baselines, and current medical status |
| `injury_history.txt` | Full injury history per player — type, date, mechanism, days missed |
| `treatment_protocols.txt` | Standard treatment protocols for common football injuries |
| `return_to_play.txt` | Return-to-play guidelines and clearance criteria |
| `fitness_assessments.txt` | Fitness test results, ACWR values, and readiness scores |
| `prevention_guidelines.txt` | FIFA 11+, neuromuscular training, load management |
| `medical_staff_guide.txt` | Matchday protocols, emergency procedures, documentation |
| `quick_reference.txt` | Red flags, drug dosages, taping techniques |
| `clinical_notes_active.txt` | Current physiotherapy assessments and session diary |
| `clinical_notes_archive.txt` | Historical clinical notes |
| `concussion_protocol.txt` | Graduated return-to-sport after head injury |
| `nutrition_plans.txt` | Individual diet protocols and supplementation |
| `squad_status_daily.txt` | Daily availability snapshot — who is cleared, modified, or unavailable |
| `clinical_notes.txt` | Legacy combined notes (retained for compatibility) |

The local `data/` folder holds the source documents. `dashboard.py` reads
`squad_status_daily.txt` and maps files to the five staff audiences for the
welcome-screen insight panel. At runtime, Q&A queries an **AWS Bedrock
Knowledge Base** that indexes these files (typically synced from S3). Chunking,
embedding, and vector search are managed by Bedrock — not by application code.

## RAG Pipeline

The entire RAG backend lives in `rag/pipeline.py` as a single `RAGEngine`
class:

1. **User submits a question** via the web UI (`POST /api/ask`).
2. **Conversation history** is loaded from SQLite and prepended to the input
   text so multi-turn questions work (e.g. "What about return-to-play after that?").
3. **Bedrock `retrieve_and_generate`** — one API call that:
   - Retrieves the top relevant chunks from the Knowledge Base
   - Generates an answer using Claude Haiku 4.5 with a custom system prompt
   - Returns citations with source document references
4. **Persistence** — the question, answer, and source metadata are saved to
   SQLite for session continuity.

### System Prompt

```
You are AthleteCare, a medical assistant for FC Velocity. Answer only from
the provided context — player records, injury history, treatment protocols,
and fitness data. If not in the context, say so clearly.
```

### Model Configuration

Newer Bedrock models (including Claude Haiku 4.5) require an **inference
profile ARN**, not a foundation-model ARN. On startup, `RAGEngine` resolves
the correct profile automatically. You can also set it explicitly in `.env`:

```
BEDROCK_MODEL_ARN=arn:aws:bedrock:us-east-1:ACCOUNT_ID:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0
```

### Hallucination Reduction

- The system prompt instructs the model to answer **only** from retrieved context.
- Bedrock Knowledge Base RAG natively grounds answers in cited source documents.
- Out-of-domain questions receive a clear "not in the context" response.

### Edge Case Handling

| Scenario | Behaviour |
|----------|-----------|
| Empty question | Returns 400 error |
| Engine not ready (missing AWS creds) | Returns 503 with status message |
| Session not found | Returns 404 error |
| Bedrock API exception | Returns 500 with error message |
| Irrelevant question (out-of-domain) | LLM states information is not in the context |

## Web Application

- **Dark-themed UI** — navy (`#0B1E3D`) and green (`#00A86B`) palette with cyan accents on the hero section.
- **Branding** — AthleteCare / "Sports Medicine Intelligence for Professional Football".
- **Sidebar** with session management (create, switch, delete consultations).
- **Welcome screen** — AI Sports Medicine hero visual, **insight panel** (Squad + Library tabs), and suggestion chips for common clinical questions.
- **Squad tab** — live-style snapshot from `squad_status_daily.txt`: players not fit for full training vs. cleared.
- **Library tab** — documents grouped by the five target audiences (accordion per role).
- **Chat interface** with user/assistant message bubbles.
- **Source display** — each answer shows expandable clinical source citations.
- **Startup** — brief connection overlay until Bedrock reports ready; then dashboard and sessions load.
- **Error handling** — network and API errors shown inline in the chat.
- **Responsive design** — sidebar collapses on mobile; hero and insight panel stack vertically on narrower screens.

## Installation & Running

### Prerequisites

- Python 3.11+
- An AWS account with:
  - Bedrock model access enabled for **Claude Haiku 4.5**
  - A configured **Knowledge Base** with the medical documents indexed
- Internet connection (for AWS API calls)

### Environment Variables

Create a `.env` file in the project root (never commit it):

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
BEDROCK_KNOWLEDGE_BASE_ID=your_knowledge_base_id
BEDROCK_MODEL_ID=anthropic.claude-haiku-4-5-20251001-v1:0
# Optional — skip automatic inference-profile lookup:
# BEDROCK_MODEL_ARN=arn:aws:bedrock:us-east-1:ACCOUNT_ID:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0
```

### Option A — Local Python

```bash
cd RAG-App

# Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies (use python -m pip to ensure correct venv)
python -m pip install -r requirements.txt

# Start the app
python run.py
```

On Windows, prefer the venv Python explicitly:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Open **http://localhost:5000** — the app is ready immediately.

### Option B — Docker

```bash
cd RAG-App

docker build -t athletecare-rag .
docker run -d --name athletecare -p 5000:5000 --env-file .env athletecare-rag
```

Useful Docker commands:

```bash
docker logs -f athletecare       # watch logs in real time
docker stop athletecare          # stop the container
docker start athletecare         # restart the container
docker rm -f athletecare         # remove and re-create if needed
```

### Running Tests

```bash
pytest tests/test_queries.py -v -s
```

Tests require live AWS credentials and a configured Bedrock Knowledge Base.

## Test Queries & Validation

The test suite (`tests/test_queries.py`) validates the full RAG pipeline with
**7 documented test cases**:

| # | Question | Expected Behaviour |
|---|----------|--------------------|
| 1 | What is Oren Shoval's current rehab status? | Mentions rehab details for the named player |
| 2 | How long does ACL reconstruction rehabilitation take? | Mentions a timeline in weeks/months |
| 3 | What does the FIFA 11+ warm-up include? | Describes exercises in the programme |
| 4 | Which players are currently on prevention programmes? | Names players enrolled in prevention |
| 5 | What ACWR value indicates high injury risk? | Mentions a numeric threshold (e.g. >1.5) |
| 6 | What are the return-to-play criteria after ACL rehab? (with history) | Coherent multi-turn answer |
| 7 | What is the capital of France? (irrelevant) | Refuses or states lack of information |

These same questions appear as suggestion chips on the welcome screen.

## Troubleshooting

### "Legacy model" ValidationException

Older Claude models (e.g. Claude 3 Haiku) are marked legacy by AWS. Ensure
`.env` uses **Claude Haiku 4.5** and that `BEDROCK_MODEL_ARN` points to an
**inference profile**, not a foundation-model ARN.

### Multiple servers on port 5000

If you see intermittent errors, check that only one Flask process is running:

```powershell
# Windows — stop anything on port 5000
Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
```

Then start a single instance with `.venv\Scripts\python.exe run.py`.

### ModuleNotFoundError: boto3

Install into the correct virtual environment:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Project Structure

```
RAG-App/
├── run.py                  # Entry point — starts Flask on port 5000
├── database.py             # SQLite session & message persistence
├── dashboard.py            # Squad status + documents by staff audience (welcome panel)
├── requirements.txt        # Python dependencies (Flask, boto3, pytest)
├── Dockerfile              # Docker image build recipe
├── .dockerignore
├── .env                    # AWS credentials (not committed)
├── .gitignore
├── README.md
├── data/                   # Source medical documents (14 .txt files + rag_image.jpg)
│   ├── players.txt
│   ├── injury_history.txt
│   ├── treatment_protocols.txt
│   ├── return_to_play.txt
│   ├── fitness_assessments.txt
│   ├── prevention_guidelines.txt
│   ├── medical_staff_guide.txt
│   ├── quick_reference.txt
│   ├── clinical_notes_active.txt
│   ├── clinical_notes_archive.txt
│   ├── concussion_protocol.txt
│   ├── nutrition_plans.txt
│   ├── squad_status_daily.txt
│   └── clinical_notes.txt
├── rag/
│   ├── __init__.py
│   └── pipeline.py         # RAGEngine — Bedrock retrieve_and_generate
├── web/
│   ├── app.py              # Flask routes & API endpoints
│   ├── templates/
│   │   └── index.html      # Chat UI (HTML + inline JS)
│   └── static/
│       ├── style.css       # Dark-theme stylesheet (navy + green)
│       └── images/
│           └── rag_hero.jpg  # Welcome-screen hero visual
└── tests/
    └── test_queries.py     # Integration tests (7 documented queries)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve the chat UI |
| GET | `/api/status` | Engine readiness (`ready`, `status`) |
| GET | `/api/dashboard` | Squad availability + documents by staff audience |
| GET | `/api/sessions` | List all chat sessions |
| POST | `/api/sessions` | Create a new session |
| GET | `/api/sessions/<id>/messages` | Fetch messages for a session |
| DELETE | `/api/sessions/<id>` | Delete a session |
| PATCH | `/api/sessions/<id>/title` | Rename a session |
| POST | `/api/ask` | Submit a question and get a grounded answer |
