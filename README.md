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


<img width="2550" height="1269" alt="צילום מסך 2026-06-14 110324" src="https://github.com/user-attachments/assets/50fc1854-a620-4431-898f-fe6e78ea87e7" />

<img width="2544" height="1265" alt="צילום מסך 2026-06-14 110351" src="https://github.com/user-attachments/assets/9bc61493-db8a-4c16-a9e3-69dce4409855" />


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
         AWS Bedrock Agent           Session Messages
         invoke_agent                 (SQLite — UI history)
         (retrieval + generation +
          session context + traces)
                    │
                    ▼
             Streamed Answer
             + Action Group traces
```

| Component | Technology |
|-----------|-----------|
| Web framework | Flask 3 |
| RAG backend | AWS Bedrock Agent (`invoke_agent`) |
| AWS SDK | boto3 |
| Conversation store | SQLite (UI display) + Bedrock Agent (context) |
| Containerisation | Docker |

### Folder Structure

| Folder | Role |
|--------|------|
| `backend/` | All server-side Python — Flask app, database, dashboard, RAG pipeline |
| `frontend/` | All client-side assets — HTML, CSS, images (ready for React migration) |
| `data/` | Source medical documents indexed by AWS Bedrock Knowledge Base |
| `tests/` | Integration tests against the live Bedrock pipeline |

There is **no local vector index** and no client-side history management.
Retrieval, generation, and multi-turn context are all handled server-side by
the Bedrock Agent. The app starts immediately.

## Data Source

The corpus consists of **14 medical, performance, and scheduling documents**
(plus a hero visual asset) covering FC Velocity's squad and clinical operations:

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
| `season_schedule.txt` | Full 2025–26 season calendar — league fixtures, cup draw, international breaks, pre-season phases, and fixture-congestion windows for load planning |

The local `data/` folder holds the source documents. `backend/dashboard.py` reads
`squad_status_daily.txt` and maps files to the five staff audiences for the
welcome-screen insight panel and the **Squad Status** sidebar module.
`season_schedule.txt` and `injury_history.txt` also feed the **Match Schedule**
and **Analytics & Reports** UI modules (static client-side views). At runtime,
Q&A queries an **AWS Bedrock Knowledge Base** that indexes these files
(typically synced from S3). Chunking, embedding, and vector search are managed
by Bedrock — not by application code.

## RAG Pipeline

The entire RAG backend lives in `backend/rag/pipeline.py` as a single `RAGEngine`
class:

1. **User submits a question** via the web UI (`POST /api/ask`).
2. **`invoke_agent`** — the question and `sessionId` are passed directly to the
   Bedrock Agent. The Agent manages multi-turn conversational context
   server-side; no client-side history concatenation is needed.
3. **Event-stream processing** — the response is an event stream. The engine
   loops through `response["completion"]`:
   - **Chunk events** — decoded bytes are appended to build the final answer.
   - **Trace events** — Action Group invocations (function name + parameters)
     are printed to the console for observability.
4. **Persistence** — the question and answer are saved to SQLite so the UI
   can display the full conversation history on page refresh.

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

The UI is a **single-page Flask app** (`frontend/templates/index.html` +
`frontend/static/style.css`) with a client-side view switcher — no React router.
Chat, RAG, and session APIs are unchanged; department modules are **UI-only**
views backed by static JS data aligned with the `data/` corpus (except Squad
Status, which reuses `GET /api/dashboard`).

### Layout

- **Dark-themed UI** — navy (`#0B1E3D`) and green (`#00A86B`) palette with cyan accents on the hero section.
- **Branding** — AthleteCare / "Sports Medicine Intelligence for Professional Football".
- **Clickable logo** (top-left) — returns to the home welcome screen from any view or active chat (session is deselected, not deleted).
- **Sidebar** — department modules, new consultation, and session list (create, switch, delete consultations).
- **Main area** — switches between the home/chat view and full-page module views; the input bar is visible only on home/chat.
- **Startup** — brief connection overlay until Bedrock reports ready; then dashboard and sessions load.
- **Error handling** — network and API errors shown inline in the chat.
- **Responsive design** — sidebar collapses on mobile; hero and insight panel stack vertically; module detail panels stack below lists on narrow screens.

### Home screen (consultation)

- **Welcome screen** — AI Sports Medicine hero visual, **insight panel** (Squad + Library tabs), and suggestion chips for common clinical questions.
- **Squad tab** — live-style snapshot from `squad_status_daily.txt`: players not fit for full training vs. cleared.
- **Library tab** — documents grouped by the five target audiences (accordion per role).
- **Chat interface** with user/assistant message bubbles.
- **Source display** — each answer shows expandable clinical source citations.

### Sidebar modules

| Module | Purpose | Data source |
|--------|---------|-------------|
| **Staff Hub** | Contact details, areas of responsibility, and availability for CMO, physios, fitness coach, nutritionist, and sports scientist | Static JS (names aligned with `medical_staff_guide.txt` and `dashboard.py` audiences) |
| **Squad Status** | Full roster with filters: All · Injured · In Rehab · Fit | `GET /api/dashboard` → `squad_status_daily.txt` |
| **Knowledge Base** | Secure document archive in a **tree view** — expand folders, browse all 14 corpus files | Static JS tree; **Indexed in RAG** badge when file exists in `data/` |
| **Match Schedule** | Season fixtures, training sessions, congestion windows; click an event for medical/GPS load reports | Static JS aligned with `season_schedule.txt` |
| **Analytics & Reports** | Periodic reports, injury trend analyses, and treatment summaries | Static JS aligned with `injury_history.txt`, `season_schedule.txt`, and related files |

#### Knowledge Base categories

| Category | Documents |
|----------|-----------|
| **Club Protocols** | treatment_protocols, return_to_play, concussion_protocol, prevention_guidelines |
| **Player Records & Status** | players, injury_history, squad_status_daily, fitness_assessments |
| **Clinical Notes** | clinical_notes_active, clinical_notes_archive |
| **Operations & Reference** | medical_staff_guide, quick_reference, nutrition_plans, season_schedule |

#### Match Schedule highlights

- Filter by **All · Matches · Training · Congestion**.
- Season overview banner (2025–26, Cup Final day).
- Selected sessions show **medical/clinical reports** and **GPS load metrics** (ACWR, distance, sprints) where available — e.g. Cup Final week, February congestion protocol.

#### Analytics & Reports highlights

- Filter by **All · Periodic Reports · Injury Trends · Treatment Summaries**.
- Summary stats bar (counts per category).
- Click a report card for full sections and source document references — e.g. season medical summary, ACWR February analysis, Cohen/Shoval/Volkov treatment summaries.

### API vs UI data

| Feature | Backend API |
|---------|-------------|
| RAG Q&A, sessions, status | Yes (`/api/ask`, `/api/sessions`, `/api/status`) |
| Welcome insight panel (Squad + Library) | Yes (`GET /api/dashboard`) |
| Squad Status module | Yes (same dashboard payload, client-side filters) |
| Staff Hub, Knowledge Base, Match Schedule, Analytics & Reports | No — static UI data only (no new routes) |

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
BEDROCK_AGENT_ID=your_agent_id
BEDROCK_AGENT_ALIAS_ID=your_agent_alias_id
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
├── requirements.txt        # Python dependencies (Flask, boto3, pytest)
├── Dockerfile              # Docker image build recipe
├── .dockerignore
├── .env                    # AWS credentials (not committed)
├── .gitignore
├── README.md
├── data/                   # Source medical documents (14 .txt files)
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
│   └── season_schedule.txt
├── backend/                # All server-side Python code
│   ├── __init__.py
│   ├── app.py              # Flask routes & API endpoints
│   ├── database.py         # SQLite session & message persistence
│   ├── dashboard.py        # Squad status + documents by staff audience
│   └── rag/
│       ├── __init__.py
│       └── pipeline.py     # RAGEngine — Bedrock invoke_agent (event stream + traces)
├── frontend/               # All client-side assets (ready for React migration)
│   ├── templates/
│   │   └── index.html      # Single-page UI — chat, view switcher, sidebar modules (HTML + inline JS)
│   └── static/
│       ├── style.css       # Dark-theme stylesheet (navy + green; modules, tree, schedule, reports)
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
