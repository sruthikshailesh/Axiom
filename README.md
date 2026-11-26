# AXIOM

**Every claim traceable. Every conflict visible. Every uncertainty stated.**

AXIOM is a document intelligence tool for teams whose decisions are scattered across
notes, specs, meeting minutes and PDFs. You upload the documents, ask a question, and
AXIOM answers with individual **claims** instead of prose — each claim carries the exact
quote it was drawn from, a label saying how far it can be trusted, and a pointer to the
document it came from. When two documents disagree, or when a newer document replaces an
older decision, AXIOM says so instead of quietly picking one.

## Overview

AXIOM ingests your team's text documents, splits them into searchable chunks, and runs a
three-stage pipeline over the chunks relevant to your question: a **Researcher** finds the
passages, an **Extractor** turns them into atomic claims with verbatim quotes, and a
**Verifier** checks each quote against its source and compares claims against each other.
The result is a report where every statement is labelled `verified`, `conflict`,
`uncertain` or `superseded`, and where you can always click back to the sentence that
produced it.

## Problem statement

In any project, the answer to "what did we decide?" lives in more than one document and
more than one point in time. A design doc says one thing, a later meeting note says
another, and a status update quietly contradicts both. A team member who reads the wrong
one builds the wrong thing.

Two failures follow from this, and neither is solved by ordinary search:

- **Currency.** Search returns every document that mentions a topic, with no indication
  which statement is the current decision and which has been replaced.
- **Disagreement.** A confident-sounding paragraph and a contradicting paragraph look
  identical in a search result list. Nothing in the interface says "these two sources
  disagree" — a reader has to notice it themselves, or not notice it at all.

LLM chat tools make this worse rather than better: they summarise the corpus into a
fluent answer with no visible per-statement evidence, so a reader cannot tell which part
of the answer came from which document, or that two documents conflicted at all.

## Proposed solution

AXIOM replaces the summarised answer with an evidence-backed claim graph:

1. **Ingest.** A document is uploaded, its text extracted, and split into overlapping
   chunks that are indexed with PostgreSQL full-text search.
2. **Research.** For a question, the Researcher retrieves the most relevant chunks.
3. **Extract.** The Extractor reads those chunks and returns atomic claims, each with a
   **verbatim quote** and the chunk id it came from.
4. **Verify.** The Verifier checks every quote actually appears in the cited chunk, then
   compares claims with each other: support from more than one source earns `verified`;
   a contradiction between sources earns `conflict`; an unsupported single-source
   statement stays `uncertain`; a newer document overriding an older one records a
   **supersession**.
5. **Report.** The report view lists every claim with its status, its quote, its source
   document, and the conflict/supersession relations it participates in — so a reader can
   audit each statement, not just trust the summary.

A quote that cannot be found in its cited chunk is dropped, so the report cannot contain a
claim whose evidence does not exist in the corpus.

## Live demo

| | URL |
| --- | --- |
| Frontend | LIVE_FRONTEND_URL |
| API | LIVE_API_URL |

- The API answers `GET LIVE_API_URL/health` with `{"status":"ok","db":"ok"}`; that route
  needs no sign-in.
- **The free Render backend sleeps when idle.** After a pause, the first request can take
  about 60 seconds while the service starts. Load `/health` (or the frontend) and wait for
  it to answer before signing in; a slow first load is the service waking up, not an error.
- The live site uses only the **synthetic demo data** and **one local account**. It is a
  demo of the real pipeline, not a private workspace: anyone with the account sees the same
  documents and runs, and the database can be reset between demos.

## Key features

Only features that are implemented and working are listed here.

- **Document ingestion** for `.txt`, `.md` and `.pdf` files, with the extracted text split
  into overlapping chunks.
- **Full-text search** over those chunks using PostgreSQL's `tsvector` index.
- **Claim extraction with verbatim quotes**: every claim cites the chunk it came from and
  the exact sentence that supports it.
- **Quote verification**: quotes are checked against the source chunk (whitespace-normalised)
  and unverifiable claims are dropped.
- **Status labels**: `verified`, `conflict`, `uncertain`, `superseded`.
- **Conflict detection** between claims from different source documents.
- **Supersession detection** when a newer document replaces an earlier decision, with the
  old and new claims both recorded.
- **A report view with evidence**: per-claim status, notes, quote, source title, and the
  conflicts and supersessions the claim takes part in.
- **Sign-in** with local accounts created on the sign-in screen (or the account in
  `backend/.env`): PBKDF2 password hashes in Postgres and an HMAC-signed token that every
  API route except `/health`, `/auth/login` and `/auth/register` requires.
- **A dashboard**: counts of sources, runs and runs-with-a-conflict, the latest run's
  status, the last five runs with links to their reports, and quick actions.
- **Search**: full-text search with a debounced query box, highlighted snippets, and a click
  straight through to the matched passage inside its source.
- **A synthetic demo**: one click loads four fictional documents and runs a preset
  question end to end, with an on-screen banner marking the data as synthetic.
- **A source library** showing every ingested document, its date, author and chunk count.
- **Readable failure states**: a failed run explains what went wrong (missing key, rate
  limit, timeout, backend down) instead of showing a raw HTTP body.

## Known limitations

These are real, current limitations — not roadmap items presented as finished work.

- **The demo does not show an `uncertain` claim from its open-issue document.** The
  synthetic "open issue" document (Doc D) is meant to surface an unresolved question, but
  because a second demo document states the same thing about search technology, the
  Verifier's mutual-support rule correctly labels Doc D's claim `verified` rather than
  `uncertain`. The `uncertain` status itself works and appears for genuinely
  single-source claims; it is simply not demonstrated by this particular demo corpus. The
  status rules were not bent to make the demo look better.
- **Scanned PDFs are rejected.** Extraction uses `pypdf`, which reads a PDF's text layer.
  A scanned or image-only PDF has no text layer and is rejected with a 422 and an OCR hint.
  OCR is out of scope.
- **Sign-in is local accounts, not production authentication.** Accounts are rows in the
  local `app_user` table, created from the sign-in screen; the single account in
  `backend/.env` remains as a fallback. There is no password reset, no email verification,
  no roles and no per-user data separation, and only registration is rate-limited — login
  is not. Every signed-in request sees the same data. CORS is limited to the origins in
  `CORS_ORIGINS` (the two loopback origins by default). Do not expose this deployment to
  the internet as-is.
- **Results depend on the LLM provider's output.** Claim wording, how many claims are
  extracted, and therefore which conflicts and supersessions are found, vary between
  models and between runs of the same model. The verifier's rules are deterministic, but
  its inputs are not. The demo was recorded over several runs; the supersession and the
  conflict appeared in every recorded run, but a different model may produce a different
  set of claims from the same documents.
- **One change can produce more than one supersession row.** Every contradicting
  old/new claim pair is stored, so the report may show several pairs describing the same
  change rather than one collapsed entry.
- **No pagination or virtualisation** in the source library; the corpora AXIOM was built
  for are small.

## Technologies used

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, React Router |
| Backend | FastAPI, Python 3.9 |
| Database | PostgreSQL 16 with full-text search (`tsvector` + GIN index) |
| Orchestration | LangGraph (Researcher → Extractor → Verifier) |
| Migrations | Alembic |
| LLM | Any OpenAI-compatible chat completions API |
| Auth | Standard-library PBKDF2 password hashing and HMAC-SHA256 signed tokens |
| Typography | Space Grotesk (headings, 400–700) and Inter (body, 400–700), loaded from Google Fonts |
| Infra | Docker Compose (database only) |

## Installation and setup

### Prerequisites

- **Docker** with Compose v2 (for PostgreSQL).
- **Python 3.9 or newer** (`python3 --version`), with `venv` available (on Debian/Ubuntu install `python3-venv`).
- **Node.js 20.19+ or 22.12+** and npm (required by Vite 8; tested on Node 24.20).
- A key for an **OpenAI-compatible LLM API**. The model must be able to return JSON in a
  chat completion. Nothing else in the project needs an account or a paid service.

### 1. Clone the repository

```bash
git clone https://github.com/sruthikshailesh/Axiom.git
cd Axiom
```

### 2. Start the database

From the repository root:

```bash
docker compose up -d
```

This starts PostgreSQL 16 on `localhost:5432` with the database `axiom`, user `axiom`,
password `axiom`, in a named volume. Confirm it is ready with
`docker compose ps` (status `healthy`).

If a PostgreSQL server is already listening on port 5432 (another container, or a local
install), stop it first: this container needs that port and will not start without it.

### 3. Install and configure the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

Now open `backend/.env` and set your key:

```ini
LLM_API_KEY=your_key_here
```

The other variables already have working defaults:

| Variable | Meaning |
| --- | --- |
| `DATABASE_URL` | Postgres connection string; matches the compose defaults. |
| `LLM_PROVIDER` | Only `openai` is implemented. |
| `LLM_API_KEY` | Your key. Never commit this file. |
| `LLM_MODEL` | Model name as your provider expects it. |
| `LLM_BASE_URL` | Optional; point at any OpenAI-compatible endpoint. Leave empty for the default. |

The app also needs the three sign-in variables before anyone can use it; create the
password hash and set `AXIOM_USERNAME`, `AXIOM_PASSWORD_HASH` and `AXIOM_SECRET` as
described in [Sign-in](#sign-in). Until then the login screen answers "Sign-in is not
configured."

### 4. Create the tables

Still in `backend/` with the virtualenv active:

```bash
alembic upgrade head
```

### 5. Start the backend

Run this from the `backend/` directory — the app reads `backend/.env` from there:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check it: <http://localhost:8000/health> should return `{"status":"ok","db":"ok"}`.

### 6. Install and start the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev
```

The page loads two Google Fonts with a `<link>` in `frontend/index.html`: **Space Grotesk**
for headings and **Inter** for body text, each with a system-font fallback. Without network
access the app still renders, in the fallback fonts.

## How to run

With the database container, the backend on port 8000 and the frontend on port 5173 all
running, open **<http://localhost:5173>** in a browser and sign in with the account from
the [Sign-in](#sign-in) section. Every page except the sign-in screen needs that session.

- **Sign in.** Enter `AXIOM_USERNAME` and the password whose hash you put in `backend/.env`.
  A wrong password says "Incorrect username or password." and keeps you on the page; a
  session that expires or a token that has been tampered with sends you back here with
  "Your session has ended. Sign in again."
- **Dashboard.** Summary cards, the last five runs and quick actions. This is where sign-in
  lands you. Stay on that one origin for the session (the backend also allows
  `127.0.0.1:5173`) so the remembered last-run link keeps working.

- **Run the demo.** On the Query view, click **Load demo**. This inserts four synthetic
  documents into an empty database, starts a run with the preset question, and opens the
  report. The report shows a banner saying the data is synthetic, and the run takes
  roughly 20–60 seconds depending on the model. If `LLM_API_KEY` is missing or rejected,
  the run fails with a readable message rather than hanging.
- **Ask your own question.** Type a question on the Query view and press **Ask**. AXIOM
  retrieves matching chunks from whatever is already ingested.
- **Add your own documents.** Open **Sources**, choose a `.txt`, `.md` or `.pdf` file and
  click **Upload**. The file appears in the shelf with its chunk count. Ask a question
  afterwards to build a report over it.
- **Search the corpus directly.** `GET http://localhost:8000/search?q=deployment`
  returns the matching chunks with their ranks.
- **Revisit a report.** The report URL is `/runs/<id>`; the nav remembers the last run id
  you opened.

To stop, press `Ctrl+C` in both terminals and run `docker compose down` (add `-v` to drop
the database volume as well).

## Deployment

The app deploys as two managed services and needs no code change to do it: **Render** runs
the API and a managed PostgreSQL database, **Vercel** serves the built frontend. The only
things to configure are environment variables, listed here by name only.

### 1. Render — PostgreSQL

Create a Render **Postgres** instance (any paid or free plan) in the same region as the web
service. When it is ready, open it and copy its **Internal Database URL**. That value is
`DATABASE_URL` for the web service. The API accepts it in Render's form (`postgres://…` or
`postgresql://…`) and rewrites it to the psycopg 3 driver itself, so no editing is needed.

### 2. Render — web service

- **New → Web Service**, pick this repository, and set **Root Directory** to `backend`.
- **Runtime: Docker.** Render builds `backend/Dockerfile`, which installs
  `backend/requirements.txt` only (Python 3.11), copies `app/`, `alembic/` and `demo/`, runs
  `alembic upgrade head`, then starts `uvicorn app.main:app` on Render's `$PORT`.
- **Health check path:** `/health`.
- **Environment variables** (names only — set the values in the Render dashboard):

| Variable | Where the value comes from |
| --- | --- |
| `DATABASE_URL` | The Render Postgres instance's Internal Database URL. |
| `CORS_ORIGINS` | Comma-separated frontend origins, e.g. the Vercel URL. No wildcard, no trailing slash. |
| `AXIOM_USERNAME` | The single demo account's username. |
| `AXIOM_PASSWORD_HASH` | Generated locally with `python scripts/make_password_hash.py` (see [Sign-in](#sign-in)). |
| `AXIOM_SECRET` | A long random string; changing it signs everyone out. |
| `AXIOM_TOKEN_HOURS` | Optional; session lifetime in hours. |
| `LLM_PROVIDER` | `openai` (the only implementation). |
| `LLM_API_KEY` | The LLM provider key. Never commit it. |
| `LLM_MODEL` | Model name as the provider expects it. |
| `LLM_BASE_URL` | Optional OpenAI-compatible endpoint. |

Sign-in answers 503 until the three `AXIOM_*` sign-in variables are all set, and every run
fails with a readable message until `LLM_API_KEY` is set. `/health` needs only
`DATABASE_URL`.

### 3. Vercel — frontend

- **Add New → Project**, import this repository, and set **Root Directory** to `frontend`.
  Vercel detects Vite: build `npm run build`, output `dist`.
- **Environment variable:** `VITE_API_URL` = the Render web service URL (no trailing
  slash). Vite inlines it at build time, so redeploy after changing it; when it is unset the
  frontend falls back to `http://localhost:8000`.
- `frontend/vercel.json` rewrites every path to `/index.html`, so `/dashboard`, `/runs/12`
  and `/sign-in` load directly on a refresh instead of 404ing.

After both are live, put the two URLs in the [Live demo](#live-demo) table. A cheap smoke
test: `LIVE_API_URL/health`, then sign in on `LIVE_FRONTEND_URL`, run the demo, and reload
`/runs/<id>` to check the rewrite.

## Screenshots

All screenshots are 1440 px wide (the two mobile ones are 390 px) and were taken
of the running app.

![Sign-in screen](docs/screenshots/sign-in.png)

*Sign-in: the local-account card beside the AXIOM masthead.*

![Overview](docs/screenshots/overview.png)

*Overview: summary counts, items that need attention, claim statuses and recent runs.*

![Ask](docs/screenshots/ask.png)

*Ask: one question box, with the synthetic demo loader beside it.*

![Demo report](docs/screenshots/report-demo.png)

*Report for the synthetic demo run: honesty banner, pipeline steps, and a claim with its
quote and source open.*

![Failed report](docs/screenshots/report-failed.png)

*A failed run states what went wrong and links back to Ask.*

![Sources](docs/screenshots/sources.png)

*Sources: the upload form and the source library.*

![Search](docs/screenshots/search.png)

*Search: full-text results with the matched term highlighted.*

![Guide](docs/screenshots/guide.png)

*Guide: the pipeline, the accepted file types and what each status means.*

![Overview at 390 px](docs/screenshots/overview-390.png)

*Overview at 390 px: the sidebar becomes a top bar and the stat cards stack.*

![Report at 390 px](docs/screenshots/report-390.png)

*The same report at 390 px, with no horizontal page scroll.*

## Sign-in

AXIOM signs in with **local accounts** meant for one machine: one account may come from
`backend/.env` as a fallback, and further accounts are created on the sign-in screen. This
is not production authentication: there is no user management, no password reset and no
per-user data separation.

### Create an account

On the sign-in screen choose **Create account**, enter a username and the same password
twice, and submit. A username is 3–32 characters — letters, digits, `.`, `_` or `-` — and is
stored in lowercase; the password must be at least 8 characters. The account is a row in
the local `app_user` table in Postgres, and only a PBKDF2-SHA256 hash of the password is
written; the password itself is never stored or logged. After it is created you return to
**Sign in** and use it there.

A username that already exists answers "That username is already taken." A rule that fails
says which rule it was, and more than 10 attempts from one address within a minute answer
"Too many attempts. Try again in a minute." The account in `backend/.env` keeps working, so
you cannot be locked out.

These accounts live in this machine's database. This is not production authentication: no
password reset, no email verification, no roles, and every signed-in user sees the same
data.

### Create the password hash

From `backend/`, with the virtualenv active:

```bash
python scripts/make_password_hash.py
```

The password is typed twice with `getpass`, so it is never echoed and never lands in your
shell history. The script prints a line like:

```
AXIOM_PASSWORD_HASH=pbkdf2_sha256$200000$<salt_hex>$<hash_hex>
```

That is PBKDF2-HMAC-SHA256 with 200 000 iterations and a random 16-byte salt. Paste the
line into `backend/.env`.

### Set the three variables

Add these to `backend/.env` (see `backend/.env.example`):

| Variable | Meaning |
| --- | --- |
| `AXIOM_USERNAME` | The only username that can sign in. |
| `AXIOM_PASSWORD_HASH` | The line printed by `scripts/make_password_hash.py`. |
| `AXIOM_SECRET` | Any long random string (for example `python3 -c "import secrets; print(secrets.token_hex(32))"`). It signs the session tokens; changing it signs everyone out. |
| `AXIOM_TOKEN_HOURS` | Optional, default `12`: how long a session lasts. |

Restart the backend after editing `.env` — settings are read at startup. If any of the
three variables is missing, `POST /auth/login` answers `503` with "Sign-in is not
configured. Set AXIOM_USERNAME, AXIOM_PASSWORD_HASH and AXIOM_SECRET in backend/.env."
and the rest of the app stays signed-out and unreachable, which is intended.

### How a session works

`POST /auth/login` returns a token shaped `payload.signature`: base64url JSON holding the
username and an expiry, signed with HMAC-SHA256 using `AXIOM_SECRET`. The browser stores
that single string in `localStorage` under `axiom.token` and sends it as
`Authorization: Bearer <token>`. Every API route except `GET /health` and
`POST /auth/login` rejects a missing, malformed, forged or expired token with `401`. A
`401` clears the stored token and returns you to the sign-in screen. Nothing logs a
password, a hash or a token.

## Architecture

```mermaid
flowchart LR
    U["User in browser"] --> FE["React + TypeScript frontend<br/>Vite dev server, port 5173"]
    FE -- "REST JSON" --> API["FastAPI backend<br/>port 8000"]
    API -- "extract text, chunk, insert" --> DB[("PostgreSQL 16<br/>sources, chunks,<br/>tsvector + GIN index")]
    API -- "schedules a background run" --> R["Researcher"]
    subgraph PIPE["LangGraph pipeline"]
        R --> E["Extractor"]
        E --> V["Verifier"]
    end
    R -- "full-text query" --> DB
    E -- "chunks + prompt" --> LLM["OpenAI-compatible<br/>LLM API"]
    V -- "pairwise comparison" --> LLM
    E -- "claims + evidence" --> DB
    V -- "statuses, conflicts,<br/>supersessions" --> DB
    DB -- "claims with evidence" --> API
    API -- "run status + report" --> FE
```

### Workflow

0. The user signs in. The browser holds one signed token and sends it as a bearer header;
   FastAPI validates it before any router runs, and a `401` sends the browser back to the
   sign-in screen.
1. The user uploads a document. FastAPI extracts its text (`pypdf` for PDFs), splits it
   into overlapping chunks, and stores the chunks — PostgreSQL computes the `tsvector` for
   each one.
2. The user asks a question. `POST /runs` inserts a run row as `queued` and schedules the
   pipeline as a background task, so the request returns immediately; the frontend polls
   `GET /runs/{id}` once a second.
3. **Researcher** runs a full-text search for the question and keeps the top chunks
   (for the demo corpus it also makes sure every demo document is represented).
4. **Extractor** sends those chunks to the LLM, which returns one claim per chunk with a
   verbatim quote and a chunk citation. A coverage pass re-extracts any chunk the model
   skipped, so a retrieved source is never silently dropped.
5. **Verifier** checks each quote against its chunk, drops claims whose quote is not
   present, compares claims pairwise on shared topics, and assigns `verified`,
   `conflict`, `uncertain` or `superseded`, recording conflict and supersession rows.
6. The run is marked `completed` (or `failed` with a readable reason, including on timeout
   and on an interrupted backend restart).
7. The frontend renders the report: statuses, notes, quotes, source titles, conflicts and
   supersessions.

## Team members and contributions

- **Sruthik Shailesh** — solo developer: design, backend, frontend, pipeline, testing, and
  documentation.

## AI assistance

This project was built with AI coding assistants. An AI agent pair-programmed the
codebase with the developer, phase by phase: it drafted code, ran the test suite, drove
the browser checks, and wrote large parts of the documentation you are reading. The
developer directed each phase, reviewed the code and the changes, ran and verified the
application end to end, and is responsible for everything in the repository. Every feature
listed under **Key features** was executed and observed working; the gaps are listed under
**Known limitations** rather than described as done.

## Demo data notice

All four documents behind the **Load demo** button are **synthetic and fictional**, written
for this project to exercise the pipeline. "Lantern" is not a real product, the people
named in the documents are not real people, and the dates are invented. The report marks
these documents with an on-screen banner, and their titles are prefixed with
`[SYNTHETIC DEMO DATA]`. The `samples/` folder likewise contains test files used during
development, including one intentionally unreadable scanned PDF.
