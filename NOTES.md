# NOTES – deviations and decisions

Every claim traceable. Every conflict visible. Every uncertainty stated.

Scope kept to the phase at hand: Phase 1 had no schema tables, LLM adapter,
LangGraph or agent code. Phase 2 added ingestion only – no pipeline, no
claims/runs/evidence/conflicts/supersession tables, no frontend changes.

## Phase 1 deviations and decisions

1. **Backend virtualenv instead of a bare `pip install`.**
   The machine's system Python is 3.9 from Apple's toolchain, so packages are
   installed into `backend/.venv` (gitignored):
   `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
   The code stays 3.9-compatible. Run commands with `.venv/bin/uvicorn` /
   `.venv/bin/alembic` (or activate the venv first).

2. **`docker-compose.yml` env vars have defaults.**
   `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` are read from the
   environment and default to `axiom` / `axiom` / `axiom`, so
   `docker compose up -d` works with no extra setup and the vars can still be
   overridden. The container is named `axiom-db`. No top-level `version:` key –
   obsolete in Compose v2+.

3. **No real `backend/.env` is committed** – only `.env.example`, which matches
   the compose defaults. `app/config.py` has the same value as its default, so
   the app boots without copying the file. `.env` is gitignored.

4. **Alembic baseline.** `alembic/env.py` sets `sqlalchemy.url` from
   `DATABASE_URL` through `app.config.settings`. Migration `0001_initial` is
   intentionally empty and was not edited in Phase 2.

5. **Frontend was scaffolded with `create-vite` (react-ts) and then stripped.**
   Demo content (`App.css`, logos, README, counter/social sections) was
   removed. It ships React 19 / Vite 8 / TypeScript 7 with `package-lock.json`;
   no additional libraries were added. The template's `oxlint` dev dependency
   and `.oxlintrc.json` were kept as-is.

## Phase 2 – Ingestion: changes and decisions

1. **Packages added (all pinned, no existing pin changed):**
   - `pypdf==6.21.4` → `requirements.txt` (PDF text extraction).
   - `python-multipart==0.0.20` → `requirements.txt`. FastAPI raises
     `RuntimeError: Form data requires "python-multipart"` for multipart
     uploads; this surfaced during the first test run and was added, pinned and
     logged here.
   - `requirements-dev.txt` (new): `pytest==8.4.2`, `httpx==0.28.1`
     (httpx is what Starlette's `TestClient` uses).

2. **Test database.** `DATABASE_URL_TEST` if set, otherwise `DATABASE_URL`
   with `_test` appended to the database name (`axiom_test`). `tests/conftest.py`
   creates that database if it is missing (connecting to `/postgres`), runs
   `alembic upgrade head` against it once per session, and truncates
   `chunk, source ... RESTART IDENTITY` so test IDs are stable. `docker-compose.yml`
   did not need a second database service.

3. **`alembic/env.py` now sets `target_metadata = Base.metadata`** (imports
   `app.models`) so a future `autogenerate` works. `0001_initial` is untouched.

4. **`chunk.tsv` is read-only.** It is a Postgres
   `GENERATED ALWAYS AS (to_tsvector('english', text)) STORED` column, mapped
   with `server_default=FetchedValue()` and `deferred=True`, so SQLAlchemy never
   writes it. Verified with `\d chunk`: generated column plus `ix_chunk_tsv`
   (GIN) and `ix_chunk_source_id_position` (btree) both present.

5. **Chunk sizing is derived, not hardcoded:** `385` words (≈500 tokens) and
   `46`-word overlap (≈60 tokens), so the step is 339 words. A 1,000-word input
   yields 3 chunks (385/385/322 words).

6. **Empty text is rejected with 422 for every file type**, not only PDFs
   ("File contains no extractable text."). This keeps sources with zero chunks
   out of the database. Scanned/unreadable PDFs get 422 with an OCR hint;
   malformed PDFs also get 422 rather than 500.

7. **`POST /sources` response shape** is
   `{"id": int, "title": str, "chunk_count": int}`. `GET /sources` returns
   `id, title, filename, doc_date, author, uploaded_at, chunk_count`, newest
   first. `GET /search` returns
   `chunk_id, source_id, position, text, rank`.

8. **Search route placement.** `app/search.py` holds the reusable
   `search_chunks(db, query, limit)` helper; the thin `GET /search` handler
   lives in `app/routes/search.py` so `sources.py` stays focused on sources.

9. **Acceptance fixtures live in `samples/`** (`sample.txt`, `sample.pdf`,
   `scanned.pdf`, `sample.docx`), generated with a minimal hand-built PDF writer
   so no PDF-generation dependency was added. The 11 MB file for the 413 check
   was created in `/tmp` and is not part of the repo.

## Phase 3 – Pipeline: changes and decisions

1. **Packages added (pinned; no existing pin changed):**
   - `langgraph==0.6.11` → `requirements.txt`. This is the newest LangGraph that
     installs on Python 3.9 (3.9 wheels for all transitive deps, including
     `langchain-core==0.3.86`). Python was **not** switched.
   - `httpx==0.28.1` → promoted from `requirements-dev.txt` to
     `requirements.txt`, because `app/llm.py` uses it at runtime. The pin is the
     same one the dev requirements already had.
2. **Only the `openai` provider is implemented.** `app/llm.py` reads
   `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` and optional `LLM_BASE_URL` from
   the environment *at call time*, so a missing key is a per-run
   `LLMError("LLM_API_KEY is not set")` rather than an import-time crash.
   `LLM_PROVIDER` defaults to `openai`; any other value raises `LLMError`.
   `LLM_BASE_URL` lets the same code talk to any OpenAI-compatible endpoint.
   `backend/.env.example` documents the four variables; no key is committed.
3. **Status rules live in one function**, `decide_status()` in
   `app/pipeline/verifier.py`, called once per surviving claim. Mutual support
   between two claims from different sources is checked *before* the
   source-count rule: each of the two claims may rest on a single source, and
   together they still earn `verified` / `0.9`. The spec does not state a
   confidence for `conflict` or `superseded`; both keep `0.5` (verifier-set
   intermediate value) and carry the reason in `conflict`/`supersession`.
4. **Pairwise comparison is topic-scoped without embeddings.** Claims are paired
   when their texts share a non-stopword word of four or more letters, and at
   most `MAX_PAIRWISE_COMPARISONS = 10` pairs are compared per run (the count is
   noted in the run's in-memory log) to bound LLM spend. No vector search was
   added.
5. **There is no `run.log` column.** "Record how many claims were dropped" and
   the other pipeline notes go to the `axiom.pipeline` logger and to an
   in-memory `log` list in the graph state; the schema stays exactly as
   specified. `run.error` holds only the failure message.
6. **Quote check is whitespace-insensitive but otherwise exact**: the quote is
   compared after collapsing runs of whitespace, so a quote copied across a line
   break passes while a paraphrase fails.
7. **Run status can never stick at `running`.** `app/pipeline/run_state.py` sets
   `completed`/`failed` with `finished_at`; the route catches `LLMError` and any
   other exception, rolls back, and marks the run failed with a readable
   message.
8. **`/runs` is synchronous** as specified: `POST /runs` creates the run row with
   status `running`, invokes the compiled graph, and returns `{id, status,
   error}`. `GET /runs/{id}` returns the claims with their evidence (chunk id,
   source title, quote, role), plus conflicts and supersessions.
9. **Migration `0003_pipeline`** adds `run`, `claim`, `evidence`, `conflict` and
   `supersession` with the two check constraints (`status` values, `role`
   values) and `ON DELETE CASCADE` from every child row. `0001_initial` and
   `0002_ingestion` are untouched. `tests/conftest.py` truncates the new tables
   between runs.
10. **Tests never call a real provider.** `app/llm.complete_json` is monkeypatched
    with a fake that returns fixed JSON, including verbatim quotes read out of
    the prompt. The graph, route, quote check and status rules run for real.

## Phase 4 — Frontend

1. **Runs are asynchronous.** `POST /runs` inserts the row as `queued`, schedules
   `execute_run(run_id, question)` with FastAPI `BackgroundTasks`, and answers
   `202 {id, status: "queued"}` immediately. The background task opens its own
   `SessionLocal` because the request session is closed once the response is
   sent. `GET /runs/{id}` reports the live status while the graph runs.
2. **Stages come from the graph, not the route.** `build_graph()` wraps each
   node with `run_state.mark_status()` so the run is `researching`, then
   `extracting`, then `verifying`. `mark_status()` refuses to touch a run that
   is already `completed` or `failed`, so a stage update can never reopen a
   finished run.
3. **Terminal transitions are unchanged** (`mark_completed` / `mark_failed` with
   `finished_at`). `execute_run` catches `LLMError`, any other exception, and
   even a failure inside the failure handler, so a background task can never
   leave a run in flight.
4. **CORS allows the two loopback origins explicitly**:
   `http://localhost:5173` and `http://127.0.0.1:5173`. Never `*`. The extra
   `127.0.0.1` entry is a deliberate deviation from the "only localhost:5173"
   wording: the in-app browser preview loads the dev server from
   `127.0.0.1:5173`, and a hard-coded single origin made every API call fail
   there.
5. **Phase 3 tests were adapted to the new model, not weakened.** `POST /runs`
   now asserts `202` and `status == "queued"`; `_wait_for_run()` polls
   `GET /runs/{id}` until `completed`/`failed` (TestClient runs the background
   task inline). A new test opens a run directly and checks that the status is
   already `extracting` inside the first LLM call. The missing-key test now
   patches `app.config.settings.llm_api_key`: `Settings` is read once at import
   (including a real key that later appeared in `backend/.env`), so deleting
   `os.environ` no longer simulates a missing key.
6. **`react-router-dom` 7.18.7 pinned exactly** — the only package added. The
   app is wrapped in `BrowserRouter` in `main.tsx`. The nav has three links:
   Query (`/`), Report (`/runs/:id`) and Sources (`/sources`). A report needs a
   run id, so the Report link targets the last run id remembered in
   `localStorage` (`axiom.lastRunId`) and is a disabled label until a run
   exists.
7. **Polling is a 1 s self-rescheduling `setTimeout`**, cleared on unmount. It
   stops as soon as the status is `completed` or `failed`, and it never
   overlaps a fetch the way a bare interval can.
8. **The API client is one module, `frontend/src/api.ts`.** Base URL comes from
   `VITE_API_URL`, defaulting to `http://localhost:8000`. Network failures
   become `Cannot reach the AXIOM backend at <url>. Is uvicorn running?`;
   non-2xx responses surface the backend's `detail` (string, or the joined
   `loc: msg` items of a pydantic validation array).
9. **Cuts.** No seed data and no working "Load demo" button (Phase 5); the
   button is disabled with the "Available in Phase 5" tooltip. No list
   virtualization or pagination in the source library — the corpora are small.
   No frontend test suite was added: the phase specifies none, and the
   acceptance checks were run by hand in the browser.

## Phase 5 — Seed data and demo path

1. **Migration `0004_demo_flag`** adds `run.demo BOOLEAN NOT NULL DEFAULT false`
   (`op.add_column` with `server_default=sa.false()`); downgrade drops the
   column. `0001`–`0003` are untouched. `Run.demo` is mapped as
   `Mapped[bool]` with the same server default, so every `Run(...)` created by
   `POST /runs` gets `demo=false` without the route setting it.
2. **`backend/demo/`** holds the four plain-text documents (one chunk each,
   ~170–200 words). Their titles, dates and authors are declared in
   `app/demo.py`, not parsed out of the files. `load_demo(db)` reuses
   `app.ingest.extract.extract_text` and `app.ingest.chunk.chunk_text` — the
   same functions `POST /sources` uses — so no second parsing path exists.
3. **`load_demo` is idempotent on title.** If a source with the same title is
   already there it is reused and its chunks are left as they are; only missing
   documents are ingested. Repeated `POST /demo/run` calls therefore keep the
   corpus at four demo sources.
4. **`POST /demo/run` returns 202 `{id, status: "queued", demo: true}`** and
   schedules the same `execute_run` background task as `POST /runs`, so the demo
   uses the Phase 4 run execution model unchanged. The router is registered in
   `main.py` (version 0.5.0). `GET /runs/{id}` now also returns `demo`.
5. **Frontend changes are limited to the two the phase asks for.**
   `QueryView` enables the button (its own `demoLoading`/`demoError` state, so it
   stays disabled while the request is in flight and shows the backend's
   message on failure) and `ReportView` renders the honesty banner above the run
   panel when `run.demo` is true (`alert-demo`, accent border, `role="note"`).
   `api.ts` gained `startDemoRun()` and the `demo` field on `RunDetail`; no other
   Phase 4 behaviour changed.
6. **Tests.** `backend/tests/test_demo.py` has two tests: `load_demo` called
   twice yields four demo sources (not eight), and `POST /demo/run` answers 202
   with `demo: true` and the run's question equals `DEMO_QUESTION`. Both reuse
   `fake_llm` and `_wait_for_run` imported from `test_pipeline.py`; no real LLM
   is called. Suite: 27 passed.
7. **Demo outcome — a real-LLM run does not reproduce the intended three
   outcomes, and this is reported rather than patched around.** Five demo runs
   against the configured model produced the same shape every time:
   two claims, one conflict, zero supersessions, and no claim from Doc D.
   Root cause is extraction, not the status rules: the extractor folds Doc A's
   statement and Doc C's statement into one claim (often with claim_date
   `2026-02-05` or `null`), which both removes the old/new pair a supersession
   needs and puts the surviving pair on the same date — so `decide_status()`
   applies the documented rule and returns `conflict`. `verifier.py` and the
   status rules were not modified; no seed sentence was rewritten to force a
   result. The uncertain case also cannot appear while Doc D is never extracted.
   Owner also comes back `null`, which adds "Missing owner." to the notes.
8. **Cuts.** No extra seed documents, no pipeline/prompt changes, no
   frontend redesign. Per-evidence document dates are still not shown in the
   report (Phase 4 only renders the claim's own date), because the phase limits
   changes to the button and the banner.
9. **Browser-tool note.** Synthetic `preview_click` on the query page did not
   reach React after a full reload, so the demo button was exercised through a
   programmatic `element.click()` in the page; the app handler itself is fine
   (the fetch and navigation happen).

## Phase 5b — Extraction fixes for the demo

1. **Extractor prompt (`app/pipeline/prompts.py`).** The rules now say: exactly one
   claim per chunk (the chunk's central statement, not a summary or several claims
   from one chunk), never merge statements that come from different chunks or
   different sources even on the same topic, extract a "changed / dropped / replaced
   / pending" statement as its own claim, use the chunk header's author as `owner`
   when the text names none, use the header's date as `claim_date` when the text
   states none, and keep the chunk-id citation and verbatim-quote rules.
2. **Coverage line in the user prompt.** `extractor_user()` now ends with
   "Cover every chunk: return at least one claim that cites each of these chunk
   ids (…) unless that chunk states no checkable fact." Without it the model
   returned claims for only two of the four demo chunks (Phase 5's symptom). A
   system-level "extract a claim from every chunk" wording was tried first and made
   this model return **HTTP 400 `json_validate_failed`** every time, so it was
   removed; the user-prompt line plus the one-claim-per-chunk rule returns all four
   claims with the right owners and dates.
3. **Coverage repair pass (`app/pipeline/extractor.py`) — a deviation from
   "prompts.py only".** The model still sometimes omits a chunk entirely (run 20 of
   Phase 5b returned three of four claims). After the first extraction, any chunk id
   that no returned claim cites is re-extracted on its own and its claims are added,
   with an `extractor: coverage repair re-extracted N chunk(s)` log line. This is a
   structural guarantee that no retrieved source is silently skipped; it does not
   touch claim validation, quote checking or the status rules.
4. **LLM retries (`app/llm.py`) — a deviation, needed to finish the checks.** The
   configured model (`openai/gpt-oss-20b`) intermittently returns HTTP 400
   `json_validate_failed`, 429 rate limits and dropped connections. `_chat()` now
   retries up to 4 attempts with a 2 s × attempt backoff for 429/5xx, connection
   errors, and 400 responses whose body contains `json_validate_failed`; every other
   response still fails immediately with the same `LLMError` text.
5. **Retrieval fallback (`app/pipeline/researcher.py`).** If full-text search
   returns at least one demo source but fewer than four, the Researcher appends the
   first chunk (by position) of every demo source that was not returned, matched by
   the `[SYNTHETIC DEMO DATA]` title prefix, and logs
   `researcher: demo fallback added the top chunk from N unretrieved demo source(s)`.
   It is scoped to the demo corpus so an ordinary run never has demo chunks injected.
   `app/search.py` is unchanged. In the recorded runs the query returned all four
   demo chunks on its own, so the fallback did not fire (it is covered by the new
   test and by the retrieval call it makes).
6. **Doc D sentence and title.** Old sentence: "Search performance on large documents
   is unresolved, and a decision on adding a second index is pending." New sentence:
   "PostgreSQL full-text search is the current search technology, but its performance
   on large documents is unresolved, and a decision on adding a second index is
   pending." The rest of the document is unchanged. Its title went from
   `[SYNTHETIC DEMO DATA] Lantern Open Issue` to
   `[SYNTHETIC DEMO DATA] Lantern Open Issue (Search Performance)`; the prefix is kept.
7. **Demo source refresh.** Because the Doc D title changed and its text changed, the
   Phase 5 demo rows in the development database were replaced: the old Doc D source
   (title without "(Search Performance)") was deleted, and `load_demo()` now replaces
   a demo source's chunks when the file on disk no longer matches the stored chunks
   (old chunks are deleted, so their evidence rows cascade away). `load_demo()` is
   still idempotent on title for unchanged files: the third and fourth `Load demo`
   keep exactly four demo sources.
8. **Tests.** `backend/tests/test_demo.py` gained
   `test_demo_chunks_exist_and_retrieval_covers_all_four_sources`: it loads the demo,
   asserts every demo source has at least one stored chunk, calls `researcher_node()`
   with `DEMO_QUESTION` and asserts a chunk from each of the four sources comes back,
   then runs `POST /demo/run` with `fake_llm` from `test_pipeline.py`. No real LLM is
   called. Suite: 28 passed.
9. **Demo outcome over three recorded runs (21, 22, 23) — check 5 fails, reported
   rather than patched.** A supersession with the Architecture claim as old and a
   Planning Meeting claim as new appears in 3/3 runs; the Doc C vs Doc B conflict
   appears in 3/3 runs; owner is filled from the source author on every claim in
   every run. Doc D's claim is **not** `uncertain`: it accords with the Planning
   Meeting's PostgreSQL claim, so `decide_status()` returns `verified` (0.9) through
   the mutual-support rule, and its note is empty instead of "Supported by one source
   only." That is the rule working as specified — an uncertain Doc D claim cannot
   exist while the Planning Meeting claim says the same thing — so `verifier.py`, the
   status rules and the seed sentences were left alone.
10. **Cuts.** No new seed documents, no changes to `verifier.py` / `decide_status()` /
    the pairwise logic, no changes to Phase 4 views, and the preset question is
    unchanged. The report still shows more than one supersession per run (three pairs
    describing the same change), because every contradicting/superseding pair is
    stored; collapsing them is a view/verifier change and was not made.
