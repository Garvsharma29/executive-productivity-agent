# Executive Productivity Agent

An AI-powered agent that converts messy executive inputs (emails, meeting transcripts, chat messages, voice notes) into a structured **daily action brief**.

## Project Status

> **🚧 Scaffold only** — the project structure is in place but no features are implemented yet.

### What exists today

| Component | Status |
|-----------|--------|
| Backend (FastAPI) | ✅ Scaffold with health endpoint |
| Frontend (React + Vite) | ✅ Placeholder app |
| PostgreSQL (Docker) | ✅ docker-compose ready |
| Data ingestion pipeline | ⬜ Not started |
| Commitment extraction | ⬜ Not started |
| Deduplication | ⬜ Not started |
| Deadline detection | ⬜ Not started |
| Daily brief generation | ⬜ Not started |
| Natural-language queries | ⬜ Not started |

## Planned Capabilities

- **Identify commitments** made by the executive across multiple input sources.
- **Separate "my actions" from "waiting on others"** with clear ownership tracking.
- **Detect deadlines and flag overdue items** using deterministic date logic.
- **Deduplicate** the same action across different sources.
- **Flag unclear ownership** rather than inventing it.
- **Produce a daily brief** summarising what needs attention.
- **Answer natural-language questions** such as *"What did I promise Raghav?"* or *"What needs action today?"*

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, Vite |
| Backend | Python 3.12, FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy |
| Validation | Pydantic |
| Agent Orchestration | Custom Python (no framework) |
| Infrastructure | Docker Compose |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+ & npm
- Docker & Docker Compose

### 1. Start PostgreSQL

```bash
docker compose up -d
```

### 2. Run the Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # edit as needed
uvicorn app.main:app --reload --port 8000
```

Health check: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 3. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

Dev server: [http://localhost:5173](http://localhost:5173)

### 4. Run Tests

```bash
cd backend
pip install anyio pytest-anyio
pytest
```

## Architecture Principles

1. **LLM for language, Python for logic** — the LLM assists with text understanding/extraction; deterministic code handles deadlines, ownership validation, and status rules.
2. **Source traceability** — every extracted commitment links back to its source evidence.
3. **No invented facts** — if ownership, a deadline, or a person is not in the source data, the system flags uncertainty rather than guessing.
4. **Simplicity** — no LangChain, no vector databases, no over-engineering. Every component must be explainable.

## Project Structure

```
executive-productivity-agent/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI route handlers
│   │   ├── core/           # Settings, configuration
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/
│   │   │   ├── ingestion/      # Raw data parsing
│   │   │   ├── extraction/     # Commitment extraction (LLM-assisted)
│   │   │   ├── normalization/  # Date/name standardisation
│   │   │   ├── deduplication/  # Cross-source dedup
│   │   │   ├── deadline/       # Deadline & overdue detection
│   │   │   ├── retrieval/      # NL query handling
│   │   │   └── agent/          # Pipeline orchestration
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # React + TypeScript + Vite
├── data/
│   ├── raw/                # Source assessment data (not committed)
│   └── processed/          # Pipeline output artefacts
├── docs/
│   ├── architecture/
│   └── process-flow/
├── docker-compose.yml
└── README.md
```
