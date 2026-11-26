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

## Phase 6 — Hardening

1. **Readable LLM errors everywhere (`app/llm.py`, `app/routes/runs.py`).** `LLMError`
   now carries a `public_message` a non-developer can read; `str(error)` keeps the raw
   provider detail for the backend log only. `execute_run()` logs the raw text with
   `logger.error` and stores `exc.public_message` on the run. Mapping: missing key →
   "The language model is not configured. Set LLM_API_KEY in backend/.env, then start
   the run again."; 401/403 → "The language model rejected the API key…"; 429 after
   retries → "The language model is busy (rate limited)…"; timeout → "The language
   model did not answer in time…"; connection failure → "Could not reach the language
   model service…"; 5xx → "The language model service is unavailable right now…";
   unusable JSON / unexpected shape → "The language model returned a response AXIOM
   could not use…". Any other pipeline exception now stores "The run failed while
   processing its documents. Check the backend log, then start the run again." instead
   of the raw exception text, and logs the traceback. `test_missing_api_key_fails_the_run`
   was updated to assert the readable sentence, and `test_llm_failure_stores_only_the_readable_message`
   asserts that a 401 body containing a fake key never reaches the run's error.
2. **Startup sweep (`app/pipeline/run_state.py`, `app/main.py`).** `sweep_interrupted_runs()`
   fails every run in `queued`/`researching`/`extracting`/`verifying` with
   "Interrupted before completion. Start the run again." and a `finished_at`. It runs
   once from a `lifespan` hook, logs the count, and never touches `completed` or
   `failed` runs; a failure in the sweep is logged and does not stop the app.
   `test_startup_sweep_fails_only_interrupted_runs` opens a second `TestClient` (a real
   process start) and checks both directions.
3. **Timeouts.** The 60 s `TIMEOUT_SECONDS` and the 4-attempt retry limit from Phase 5b
   are unchanged. `expire_if_stale()` is a read-time check called by `GET /runs/{id}`:
   an active run whose `created_at` is more than 10 minutes old is marked failed with
   "Run timed out." and returned as failed. No background job was added, and no new
   column — the run's own `created_at` is the clock. Tests: a stale run is failed on
   read, a fresh run and an old `completed` run are left alone.
4. **Frontend empty/error states.** Checked in the browser without restyling: the
   Sources page shows "No sources yet. Upload a document to get started." with zero
   sources; with the backend stopped it shows "Cannot reach the AXIOM backend at
   http://localhost:8000. Is uvicorn running?"; `/runs/99999` shows "Run not found."
   with a link back to the Query view; a failed run shows the error inside a panel.
   The empty-state test used a throwaway database (`axiom_empty`) served by a temporary
   backend on the same port, so the development data was never touched; that database
   was dropped afterwards.
5. **Upload guard (`frontend/src/views/SourcesView.tsx`).** The Upload button was
   already disabled through `disabled={uploading}`, but two submits in the same tick
   both read the old `uploading` state, so a fast double click could post twice. A
   `useRef` flag (`uploadInFlight`) now guards `onSubmit` and is cleared in `finally`.
   Verified by firing `form.requestSubmit()` twice in one tick from the browser: one
   source row was created. That test source was deleted afterwards.
6. **No unhandled exceptions (`app/main.py`).** A handler for `Exception` logs the
   traceback with `logger.exception` and answers HTTP 500 with
   `{"detail": "Something went wrong. Check the backend log."}`; the frontend already
   renders `detail`, so the user sees that sentence rather than "undefined".
   `test_unhandled_exception_returns_readable_json` forces a failure in `/search` and
   asserts the body contains neither the exception text nor a traceback.
7. **Packages.** None added. **Cuts.** None: every item was completed inside the time
   box. The known Phase 5b limitation (Doc D's claim verifies instead of staying
   uncertain) is unchanged and still disclosed in the Phase 5b section.

## Phase 7 — Packaging for the BUiLDX submission

1. **The frontend was not in the repository. This was the blocking problem of the phase.**
   `frontend/` had been scaffolded with `create-vite`, which made it its own git repository,
   and the root repo had committed it as a single gitlink (`git ls-files -s frontend` → mode
   `160000`, one entry). GitHub therefore held a pointer to a commit that was never pushed:
   no React source, no `package.json`, no `src/`. The nested `frontend/.git` was moved out of
   the tree (to `/tmp/axiom-frontend-nested-git-backup`, outside the project) so the directory
   is ordinary files again, `git rm --cached frontend` dropped the gitlink, and the 19
   frontend files were added to the root repository. The nested repo's working tree was
   dirty at the time, so the files added are the current state of the code, not the old
   `ded1c06` snapshot. `node_modules/` and `dist/` stay ignored (root `.gitignore` plus
   `frontend/.gitignore`).

2. **The repository was private, and the remote was stale.** A logged-out
   `GET https://api.github.com/repos/sruthikshailesh/Axiom` returned 404 while
   `git ls-remote` worked, i.e. private. It was set to public through the GitHub API with the
   credential already stored in this machine's git credential helper (the token was never
   printed and is not in any file). The remote was also three commits behind local `main`
   (Phase 5, 5b and 6 had never been pushed); Phase 7's commit is the first push since
   `8c0c448`.

3. **README structure.** Written in exactly the requested order: title and tagline, overview,
   problem statement, proposed solution, key features, known limitations, technologies used,
   installation and setup (prerequisites, then database, backend, frontend in order),
   how to run, architecture (Mermaid plus a text workflow), team members and contributions,
   AI assistance, demo data notice. No section is empty. Nothing was invented: the feature
   list contains only behaviour that was executed in Phases 2–6, and the five limitations
   (Doc D's claim verifying instead of staying uncertain, no OCR, no authentication, results
   depending on the LLM provider, several supersession rows describing one change, no
   pagination) are the real ones, not placeholders.

4. **README claims kept deliberately small.** Prerequisites state Node 20.19+/22.12+ because
   Vite 8 requires it (tested on Node 24.20.0, Python 3.9.6, Docker 29.9.2). The README does
   not claim a specific model: the `.env.example` default (`gpt-4o-mini`) is an example, and
   the limitation section says plainly that claim wording and therefore the findings vary by
   model. No benchmark, accuracy figure or "production ready" claim appears anywhere.

5. **Team section.** One entry only, as instructed: "Sruthik Shailesh — solo developer:
   design, backend, frontend, pipeline, testing, and documentation." No other names, no
   invented roles.

6. **`backend/.env.example`** now carries placeholders only: `LLM_API_KEY=your_key_here`
   (it was an empty value, which read as "something is missing" rather than "fill this in"),
   plus `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL` and `DATABASE_URL` matching the compose
   defaults. No real value is in the file. `backend/.env` remains untracked
   (`git ls-files backend/.env` prints nothing).

7. **Secret scan.** `git grep -n -i -E "gsk…|sk-|api[_-]?key *= *[A-Za-z0-9]" -- ':!NOTES.md'`
   returns: the placeholder line in `README.md` and `backend/.env.example`
   (`LLM_API_KEY=your_key_here`), the two deliberately fake literals in
   `backend/tests/test_hardening.py` (`sk-should-not-leak`, used to assert that a provider
   error body never reaches the run's error message), and one false positive in the minified
   `frontend/public/favicon.svg` path data. No real key is present, so nothing was removed
   and no key needed rotating. The real key exists only in `backend/.env`, which is
   gitignored and untracked.

8. **`docker-compose.yml`, `backend/requirements.txt`, `frontend/package.json`.**
   Copied unchanged into the fresh clone and installed from scratch there: `docker compose up
   -d` reached `healthy`, `pip install -r requirements.txt` succeeded on Python 3.9.6, and
   `npm install` succeeded on Node 24.20.0 (it warns that `fsevents` has an install script not
   covered by the npm 11 allow-scripts list — a warning, not a failure, and not needed on
   Linux). No pin was changed.

9. **Fresh-clone test (first pass).** `git clone https://github.com/sruthikshailesh/Axiom.git
   axiom-fresh` into `/tmp`, then only the README followed: compose up, venv, pip, `cp
   .env.example .env` + key, `alembic upgrade head` (four migrations applied to an empty
   volume), `uvicorn`, `npm install`, `npm run dev`. `/health` answered 200, the frontend
   served 200 on an empty source list, and **Load demo** produced run #1 with the synthetic
   banner, 4 claims, 2 supersessions and 1 conflict — the same shape as the development
   environment. The fresh clone got its own database volume (`axiom-fresh_axiom_pgdata`), so
   nothing was inherited from the development data. The throwaway clone was deleted at the
   end of the phase, because its untracked `backend/.env` held a copy of the key; the
   development stack was restarted from its own volume, which still had its data.

10. **README steps corrected after that pass.**
    - Step 2: added the port note — the existing development container was holding 5432, and
      `docker compose up -d` in the fresh clone failed to bind until it was stopped. A reader
      with any local PostgreSQL would hit the same wall, so the README now says to free 5432.
    - Step 5: made explicit that `uvicorn` must run from `backend/`, because
      `pydantic-settings` reads `.env` relative to the working directory; starting it from the
      repository root silently loses `LLM_API_KEY` (the run then fails with the "not
      configured" message rather than reading the file).
    - "How to run": replaced the awkward "use `localhost`, not `127.0.0.1`" wording with the
      actual rule (pick one origin per session so the remembered last-run link resolves).
    - Prerequisites: noted that `venv` must be available (`python3-venv` on Debian/Ubuntu),
      which is the first failure a Ubuntu user would hit at `python3 -m venv .venv`.
    The steps that worked were left alone; the clone was not re-run after these wording-only
    edits, since none of them changes a command that executes.

11. **BUiLDX AI-tool policy — check still pending.** The public BUiLDX Hackathon listing
    (Code-A-Nova, Unstop) shows no AI-tool clause in its rules; the event page is closed and
    its rules text was not available beyond the overview. Several unrelated events use the
    same name (BuildX'26 at IIT Kharagpur, BUiLDX × UpLearn), so no single policy could be
    confirmed for this submission. The README's AI-assistance paragraph therefore states the
    position the stricter published policies require — AI assistants were used, they drafted
    code, tests and documentation, and the developer reviewed and ran everything — and this
    item stays open until the organisers' policy is confirmed.

12. **Packages and cuts.** No package was added in this phase. No application, pipeline,
    verifier or seed-document change was made; the Phase 5b limitation (Doc D's claim verifies
    instead of staying uncertain) is still disclosed in the README's limitations section and
    in the Phase 5b notes above. The only code change is the removal of the nested
    `frontend/.git` (repository metadata, not application code).

## Phase 8 — Sign-in, shell, dashboard, search, guide

1. **Single account, standard library only (`app/auth.py`).** `hash_password()` is
   PBKDF2-HMAC-SHA256 with 200000 iterations and a 16-byte random salt, stored as
   `pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`; `hash_password()` refuses fewer than
   200000 iterations. `verify_password()` parses the stored value defensively and compares
   with `hmac.compare_digest`, so a malformed hash in `.env` denies sign-in instead of
   raising. Tokens are `base64url(JSON).base64url(HMAC-SHA256)`, carrying `sub`, `exp` and
   `iat`; `read_token()` checks the signature before it decodes the payload, rejects
   malformed strings and bad padding, rejects `exp <= now`, and rejects a `sub` that is not
   the configured username (one account, so a token for any other name is useless here).
   No password, hash or token is logged anywhere; the only place a token appears in a
   response is `POST /auth/login`.

2. **Settings are optional so the app boots without them.** `AXIOM_USERNAME`,
   `AXIOM_PASSWORD_HASH` and `AXIOM_SECRET` default to `None` and `AXIOM_TOKEN_HOURS` to
   `12`. With any of the three missing, `POST /auth/login` answers 503 with the sentence the
   phase specifies, rather than failing at import or half-working.

3. **One rejection message, no username/password oracle.** `POST /auth/login` compares the
   username with `hmac.compare_digest` and the password with `verify_password`, and always
   answers `401 {"detail": "Incorrect username or password."}`. The test asserts the two
   failure bodies are byte-identical.

4. **Protection is attached per router, not per handler.** `require_user` reads the
   `Authorization: Bearer` header and is passed as `dependencies=[Depends(require_user)]` on
   the `sources`, `search`, `runs`, `demo` and `dashboard` routers in `main.py`, so a new
   route in one of those files cannot forget it. `GET /health`, `POST /auth/login` and
   `GET /auth/me` stay outside; CORS preflight is handled by the middleware before routing.
   CORS headers are now the explicit list `["Authorization", "Content-Type"]` instead of
   `*`. A missing, malformed, forged or expired token answers 401 with
   `"Your session has ended. Sign in again."`, the same sentence the frontend shows.

5. **`GET /dashboard/summary` returns run metadata, not document text.** It answers
   `sources`, `runs`, `runs_with_conflict` (distinct runs with at least one conflict row),
   `latest_run_status` and `recent_runs` (the last 5, newest first, each with `id`,
   `question`, `status`, `demo`, `created_at`, `finished_at`). The phase asks for counts plus
   a recent-runs list with each run's question; the run's question is user input, not
   document text, so it is the only string in the response. A test asserts the exact key set
   so a document field cannot creep in unnoticed.

6. **`backend/scripts/make_password_hash.py`** reads the password twice with `getpass`
   (never echoed, never in shell history), prints the `AXIOM_PASSWORD_HASH=…` line, and
   prints the iteration count to stderr. Mismatched entries exit non-zero.

7. **Tests get their own credentials (`tests/conftest.py`).** A session-scoped `auth_env`
   fixture invents a random username, a random password and a random secret per run, hashes
   the password with the real function, and issues a real token; nothing is hard-coded and
   nothing is committed. The `client` fixture now carries `Authorization: Bearer <token>` in
   its headers, so every existing test sends a valid token without changing its call sites,
   and a new `anon_client` fixture sends none. `test_hardening.py`'s own `TestClient` call
   now passes `auth_header`. Suite: 48 passed (34 before, 14 new).

8. **Frontend token handling (`src/session.ts`, `src/api.ts`).** One `localStorage` key,
   `axiom.token`, holding only the token string. Every API call attaches the bearer header;
   a 401 clears the token and dispatches `axiom:unauthorized`, which `App` turns into a
   redirect to `/sign-in` with the "Your session has ended" message. Sign-in opts out of
   that path (`skipAuthRedirect`), so a wrong password shows the backend's message on the
   page instead of bouncing the user around.

9. **Sign-in page.** `GlyphField` draws faint dusty-purple characters on a canvas and
   drifts them with `requestAnimationFrame`. It draws a single static frame when
   `prefers-reduced-motion: reduce` matches, and also stops when the page is hidden
   (`visibilitychange` cancels the frame and redraws on return); the media query is watched
   with `addEventListener('change')` so toggling it takes effect without a reload. The whole
   stylesheet also disables animation and transitions under the same media query.

10. **Shell and guard.** `RequireAuth` wraps every route except `/sign-in`; without a token
    it redirects with `Navigate replace`. The sidebar lists Dashboard, Ask, Sources, Search,
    Guide and Sign out, shows the username from `GET /auth/me` at the bottom, and the active
    item is purple (`aria-current` styling comes from `NavLink`'s `active` class). Below
    900px the sidebar becomes a horizontal bar above the content. `Ask` keeps the old query
    view; the Report nav link was removed because the dashboard's recent runs and the
    post-run redirect both reach a report.

11. **Deep link from search to the source.** Clicking a result navigates to
    `/sources?source=<id>&chunk=<id>`; `SourcesView` opens that source once the list arrives
    and scrolls the chunk into view. Two corrections were needed while testing: the scroll
    ran before the opened source's chunks had laid out (fixed with a 120 ms delay), and
    `behavior: 'smooth'` never starts in a backgrounded tab, so the scroll is instant
    (`behavior: 'auto'`, `block: 'start'`). Instant is also what reduced-motion wants.

12. **Search.** 300 ms debounce with a cancellation flag, `limit=20`. Snippets are ~300
    characters starting 90 characters before the first matched term, with the term marked
    inline; the title, doc date and author come from `GET /sources` (the search endpoint
    returns chunk data only, and changing it would have touched pipeline-adjacent code). An
    empty query shows a hint; a finished search with no hits shows "No passages match that
    search."

13. **Dashboard.** Four stat cards (sources, runs, runs with a conflict, latest run status),
    the last five runs with a report link, three quick actions, and an onboarding card when
    there are no sources or no runs. "Load the demo" calls the existing `POST /demo/run` and
    navigates to the report.

14. **Guide.** Seven sections, written against what the app does: what AXIOM does, the three
    steps, accepted types (`.txt`, `.md`, text-based `.pdf`, 10 MB each, scanned PDFs
    rejected because OCR is not built), why date and author matter, good questions, the four
    statuses with one example each, and the limitations (LLM-dependent results, single local
    account, synthetic demo data).

15. **Dev credential lives only in `backend/.env`.** A local development account was
    generated for the acceptance checks: username `sruthik`, a password told to the owner,
    a random secret. The hash and secret are in the gitignored `.env`; `.env.example` carries
    placeholders only. Rotate with `python scripts/make_password_hash.py` and a new
    `AXIOM_SECRET` (which signs every existing token out).

16. **Verification notes.** `preview` runs in a background tab, so `requestAnimationFrame`
    is throttled and the sign-in canvas cannot be watched moving. The motion branch was
    instead verified by counting the frames the component schedules: 2 with motion allowed,
    0 with `prefers-reduced-motion` forced to match, using the real component and a patched
    `matchMedia`. That is a code-path check, not a visual one.

17. **Packages and cuts.** No package added: the redesign is plain CSS plus the two Google
    Fonts loaded by `index.html` (Space Grotesk for headings, Inter for body, with system
    fallbacks). No pipeline, verifier, `decide_status()`, extractor-prompt or seed-document
    change; the Phase 5b limitation is still disclosed in the README. Cut: no avatar, no
    settings page, no password change screen (the hash is edited through the script), and no
    multi-user support by design.

## Phase 9 — Secret scan, fresh-clone retest and push

1. **History secret scan.** The requested scan over every commit
   (`git grep -n -i -E "gsk…|sk-[A-Za-z0-9]|AXIOM_PASSWORD_HASH=pbkdf2|AXIOM_SECRET=…"`
   against `git rev-list --all`, plus one more grep for the development password, whose
   literal is deliberately not repeated in this file) returned matches in three groups, none of them live
   credentials: (a) `NOTES.md` and `README.md` prose that *describes* the variable names and
   the old scan command; (b) placeholder values in `backend/.env.example` and the README
   (`your_salt_hex`, `your_hash_hex`, `your_long_random_secret_here`); (c) the fixture string
   `sk-should-not-leak` in `backend/tests/test_hardening.py`, which exists to prove that a
   provider error body is not leaked into an API response — it is not a key. The regex also
   matched `frontend/public/favicon.svg`, because the CSS property `mask-type:alpha` contains
   the letters `sk-t`, which has nothing to do with credentials.
   `git ls-files backend/.env` prints nothing, and no commit ever contained
   a real Google API key, the development password or the development `AXIOM_SECRET`, so no
   history rewrite was needed.

2. **Stale remote.** `git fetch origin` showed local `main` one commit ahead (Phase 8,
   `d0cf0b8`) and `origin/main` had no commits that local did not, so the push was a
   fast-forward; no force-push.

3. **Fresh-clone retest.** Cloned into `/tmp/axiom-fresh` and followed only the README, with
   two deliberate local deviations, both outside the repository: a brand-new database
   (`axiom_fresh` in the existing `axiom-db` container, created with `CREATE DATABASE`) so
   `alembic upgrade head` was a real migration run instead of a no-op and the demo started
   from an empty corpus; and the existing LLM key from the development `.env` copied into the
   clone's `.env`, because there is no second provider key on this machine. The three
   `AXIOM_*` values were new: username `freshowner`, a hash printed by
   `python scripts/make_password_hash.py`, and a fresh `AXIOM_SECRET` from
   `secrets.token_hex(32)`. Everything else followed the README as written:
   `python3 -m venv .venv`, `pip install -r requirements.txt`, `cp .env.example .env`,
   `alembic upgrade head`, `uvicorn app.main:app --host 127.0.0.1 --port 8000`,
   `npm install`, `npm run dev`.

4. **Fresh-clone results.** `GET /health` → `{"status":"ok","db":"ok"}` (200). Sign-in with the
   new credentials → 200 with a token; a wrong password → 401 "Incorrect username or
   password." Load demo → run #1 completed with 4 claims, the synthetic-data banner, three
   supersession rows and one conflict row, all rendered in the report view. The Google Fonts
   `<link>` fetched both `woff2` files from `fonts.gstatic.com` (200) and
   `document.fonts.check()` reports both Inter and Space Grotesk loaded, with `body` computing
   to `Inter, system-ui, …` and the heading to `"Space Grotesk", …` — so the page text is not
   falling back to the system font.

5. **README fix found by the retest (the only one).** The **Dashboard** bullet in *How to run*
   had a two-line continuation that started at column 0, which ends the list item mid-sentence
   and renders the rest as a stray indented paragraph. The sentence was rewrapped inside the
   bullet. No other bullet, code block or table in the README had the same defect (checked by
   scanning for unindented lines that follow an indented bullet continuation).

6. **What was not verifiable here.** The shared preview panel in this session accepted
   `preview_click` calls but the page never received the click: a real click at the centre of
   the "Load the demo" button produced no request, while `elementFromPoint` at that point
   returned the button itself and a `document…click()` from the page did. So the UI flow was
   driven with real DOM clicks from inside the page (React handlers, fetch, router and the
   backend all exercised) rather than with mouse input, and the sign-in/mouse-click path was
   not re-proved by hand this phase. Phase 8's acceptance runs did click it by hand.

7. **Cleanup.** The clone's `backend/.env` (which held the new secret and a copy of the LLM
   key) was deleted together with the whole `/tmp/axiom-fresh` folder after the test, and the
   throwaway `axiom_fresh` database was dropped, so the fresh secret exists nowhere.

8. **The scan found one real problem: in this file.** The first version of item 1 quoted the
   scan command verbatim, which wrote the development account's password into `NOTES.md`.
   The string is not a provider key and the account is local-only, but it is still a password
   and it briefly reached `origin/main` in the Phase 9 commit. It was removed from the file,
   the commit was amended (`git commit --amend`) and the branch was updated with
   `git push --force-with-lease`, so the published history contains no copy of it. This is the
   only history rewrite in the project; nothing else was force-pushed. The lesson is recorded
   here rather than quietly fixed: a scan command that contains a secret is itself a leak.

## Phase 8b — Sign-in split-screen redesign

1. **What was removed, and why.** The sign-in card had a `Create account` tab, a
   `Forgot password?` link, and `Terms` / `Privacy` links. AXIOM has exactly one local
   account, no registration, no password reset and no legal pages, so every one of them was
   a dead control that promised behaviour the app does not have. All three are gone: the card
   is a single form with no tabs, and the page now contains **no links at all** (checked: the
   rendered document has zero `<a>` elements). The `One local account. Not production
   authentication.` footer stays, because it is the honest statement of what the account is.

2. **Sign-in logic untouched.** `login()`, `setToken()`/`getToken()`, `errorMessage()`, the
   `busy` flag, the `busy ? 'Signing in…' : 'Sign in'` label and the existing disabled rule
   are the Phase 8 code, only re-hosted in the new markup. `api.ts`, `session.ts`, `App.tsx`,
   the route guard, sign-out and the 401 handling were not opened. No backend file changed and
   no package was added; the redesign is JSX plus plain CSS.

3. **Layout.** One grid, `.auth-page`: a single column below 900px and
   `minmax(0, 1.08fr) minmax(400px, 0.92fr)` at 900px and wider, so 900px is the desktop
   breakpoint exactly as specified. At 1440px the columns compute to 777.6px and 662.4px, the
   left column is the full 900px of viewport height, and the card sits centred in the right
   column. Below 900px the left column collapses to its content height, `.auth-left-foot`
   (workflow strip plus status bar) is `display: none`, and the card follows the headline, so
   the mobile page shows wordmark, headline, subline, then the card.

4. **Left column.** Inline SVG mark only (three lines forming the `A`, gold dot at the apex —
   no image file, `aria-hidden`); `AXIOM` wordmark in gold with `0.42em` letter-spacing and
   `RESEARCH INTELLIGENCE` in small grey capitals beneath it; the two-line headline with
   `traceable` and `visible` in `var(--gold)`; the muted subline; the five-step strip with the
   gold UPLOAD dot; then the rounded status bar (red warning triangle plus `CONFLICT`, a
   divider, and the sentence) and the one-line status legend underneath.

5. **The background canvas** is one `<canvas>` inside `.auth-left` (not the whole page), drawn
   with `requestAnimationFrame`: drifting nodes joined by thin edges that fade with distance,
   plus a few low-opacity braces/slashes/digits. It is the Phase 8 loop's structure — one
   `restart()` that draws a single still frame and returns instead of scheduling when
   `prefers-reduced-motion: reduce` matches, when `document.hidden` is true, or when the
   component's `still` state (the same media query, watched with `addEventListener('change')`)
   is set. Nothing animates while the tab is hidden, and toggling the OS setting takes effect
   without a reload.

6. **Colours and fonts.** `--gold` was already `#c9a86a`, so no variable was added; the
   redesign uses the existing `--bg`, `--surface`, `--surface-2`, `--accent`,
   `--accent-line`, `--accent-soft` and `--muted`. The status bar's icon and label use
   `var(--conflict)`, the same red (`#e06666`) the report badges use for a conflict — measured
   on the page as `rgb(224, 102, 102)` for both. Fonts are unchanged: headings compute to
   `Space Grotesk`, body text to `Inter`, from the same `index.html` link.

7. **Accessibility.** Each input has a real `<label for>` (the old markup wrapped the input
   in the label, which is why the password field is now a `label` plus an input/button row); the
   error box keeps `role="alert"`; the eye toggle is a `<button type="button">` whose
   `aria-label` switches between `Show password` and `Hide password`, and it lives outside the
   label so clicking it cannot be read as clicking the field. Every control has a visible
   `:focus-visible` ring: inputs `2px var(--accent)`, the eye and the submit button
   `2px var(--gold)`. Tabbing the form in order (username → password → eye → submit) showed
   `:focus-visible` true and a 2px outline on each of the four.

8. **Motion.** The UPLOAD dot pulses with one 2.8s `auth-pulse` keyframe; the stylesheet's
   `prefers-reduced-motion: reduce` block sets `animation: none` on it, and the existing global
   rule already collapses every other animation/transition duration.

9. **What was checked, and how.** Wrong password → `Incorrect username or password.` in a
   red-bordered box inside the card with `role="alert"`, URL still `/sign-in`; correct
   password → `/dashboard`; the eye toggle flips `type` between `password` and `text` and swaps
   its label both ways; 820px viewport → one column, strip and status bar at zero size, card
   below the headline, no horizontal overflow; a clean reload logs no console errors (the only
   `console` errors in the session were the browser's own `401` resource lines from the
   deliberately wrong passwords); `npm run build` (tsc + vite) passes. `preview_click` reached
   the page this time, so the submit button and the eye were exercised with real mouse input.

10. **Reduced motion was verified as a code path, not by toggling the OS setting.** This
    preview tab is hidden (`document.hidden === true`), and Chromium runs no animation frames
    in a hidden tab, so frame counting cannot distinguish the two states here — the first
    attempt measured zero frames either way. Instead `requestAnimationFrame` was stubbed to
    record schedulings: with motion allowed the component schedules the loop (2 registrations
    on mount, and ticking one callback scheduled another, so the loop reschedules itself);
    with `matchMedia` reporting `reduce` the same mount scheduled **0** and the canvas still
    held a drawn still frame (3,330 non-transparent pixels). The dot's stop is the live
    stylesheet rule quoted in item 8. What was *not* done is flipping macOS Reduce Motion and
    watching the page, because the browser exposes no media emulation here.

11. **Cuts.** No avatar, no illustration, no second canvas, no theme switch, no animation on
    the strip beyond the pulse, and no change to the desktop shell, the other views, or any
    backend file.

## Full UI pass

1. **Scope.** Frontend-only polish pass over every screen (Sign-in, Dashboard, Ask, Report demo/failed, Sources docs/empty, Search results/none/empty, Guide) at 1440/1024/820/390px. No backend file, route, schema, verifier, extractor prompt, seed document, preset question, sign-in logic, token handling, route guard, sign-out or 401 handling changed.

2. **Files changed.** `frontend/src/index.css`, `frontend/src/views/DashboardView.tsx`, `frontend/src/views/SearchView.tsx`, `frontend/src/views/SourcesView.tsx`. `NOTES.md` updated. No new routes, libraries or files.

3. **Audit items fixed.** Placeholder contrast on `.auth-input::placeholder` raised from `#6f7682` (3.88–4.06:1) to `#8a9099` (≈5.18:1). Added visible `<label>` for the search input. Added a page heading to the Dashboard view. Added a next-step sentence to the search no-results and empty-source-chunk states. Added `:focus-visible` rings for `.nav-link`, `.claim-head`/`.source-head`, `.result`, `.run-question`, `.link`. Added `overflow-wrap: anywhere` to `.claim-text`, `.run-question`, `.chunk-text`, `.quote`, `.result-snippet`. Added `--radius` and `--shadow` tokens and normalized box radii/shadow to them. Normalized the largest off-scale font sizes (30→28, 26→28, 22→20, 19→20, 18→20).

4. **Audit items not fixed (and why).** Full font-size normalization to the 12/14/16/20/28/40 scale was limited to the largest sizes; the remaining 10–15px labels were left because changing them shifts the sign-in and status layouts without a11y benefit (all pass 4.5:1). The sidebar's 900px horizontal-bar breakpoint and the auth 900px two-column breakpoint were left as-is (already verified at 820px). No dark-mode toggle, i18n, SEO or analytics were added (out of scope).

5. **Verification.** `npm run build` passes (tsc -b + vite build, no TS errors). All screens measured 390px `scrollWidth` at a 390px viewport (Dashboard, Ask, Sources, Search, Guide, Report #29, Report #26). Demo run #29 keeps the synthetic-data banner, 4 claims, 3 supersessions and 1 conflict. Failed run #26 shows a readable error with a link back. Console shows only Vite/React DevTools info, no errors. `.venv/bin/pytest` passes: 48 passed. `git diff --stat -- backend` prints nothing.

6. **Commit.** Local commit "Full UI pass"; not pushed.

## Phase 10 — Google sign-in check, final UI pass, remaining-work audit

1. **Google sign-in was skipped, not built.** `GOOGLE_CLIENT_ID` is absent from
   `backend/.env`, and the instructions say to skip Part 1 in that case. So no
   `POST /auth/google` route, no `google_client_id`/`allowed_emails` settings, no Google
   tests and no "Continue with Google" button exist. The sign-in page was checked at
   1440px and 390px: it shows only the username/password form, with no Google button, no
   "or" line and no broken element. Nothing in the README or UI claims Google sign-in is
   available. If it is added later, `REMAINING.md` records the work as skipped and this
   section should be replaced.

2. **Final UI pass.** The audit ran at 1440px and 390px on Sign-in, Dashboard, Ask,
   Report (demo #29 and failed #26), Sources, Search (results, no results, empty query)
   and Guide. Fixes, in order: completed the type scale to exactly 12/14/16/20/28/40px
   (the sign-in micro-labels at 10–13px moved to 12px, 15px to 16px, and the headline
   clamp is now 28–40px); finished the single `--radius`/`--shadow` tokens (the sign-in
   card moved from 16px to `var(--radius)`); added hover/focus states for the claim and
   source fold-out rows and for the text links; and added a next step to the report's
   empty claims, supersessions and conflicts states. `prefers-reduced-motion` still
   disables the canvas loop and all animation/transition durations; statuses keep a text
   label; every input has a visible label; each page has exactly one `h1` (the shell's
   AXIOM wordmark). No route, UI library or backend file changed.

3. **Verified, not just edited.** `npm run build` passes with no TypeScript errors.
   `.venv/bin/pytest` passes (48 passed). At a 390px viewport every screen's
   `scrollWidth` equals 390 with no element past the viewport edge; at 1440px there is no
   overflow either. Demo run #29 keeps the synthetic-data banner, 3 supersessions and 1
   conflict; failed run #26 shows "The run could not finish." with a link back to the
   query view. The browser console showed only Vite/React DevTools info, no errors.

4. **Remaining-work audit.** `REMAINING.md` was created at the repository root. It records
   the track as blocked (needs the user's choice), the AI-tool policy as open, the local
   password as open and unchanged (`verify_password(<the local password>, hash)` against
   `AXIOM_PASSWORD_HASH` is still true, so it still matches the value shown earlier in
   chat), Google sign-in as skipped,
   the UI pass as done, the demo video and its Drive upload as open, the dashboard
   submission as open with the README fields listed, and the public-repo/README check as
   open until after the final push.

5. **Demo video script (the user records this).** Suggested shot list, roughly 2–3
   minutes: (a) sign in with the local account; (b) the Dashboard, pointing out the
   counts and the recent runs; (c) Sources, showing the four synthetic documents and one
   expanded source's chunks; (d) Ask, then **Load demo**; (e) the report: read the
   synthetic-data banner, open a claim to show its quote and source, then show the
   Supersessions and Conflicts sections; (f) Search, searching a term and opening a
   result; (g) the Guide's status legend. Keep the demo banner in frame so the synthetic
   data is never implied to be real.

6. **Hackathon timing.** The first commit `a9835be` is dated `2026-11-25 15:58:20 +0530`,
   after the 11:00 AM kickoff on 25 November. No commit predates the kickoff, so there is
   no earlier work to disclose. Freeze time is 9:00 PM on 26 November.

7. **No secret committed.** The secret scan over tracked files found only the placeholder
   the placeholder value in `backend/.env.example`; `backend/.env` stays untracked. No
   Google client secret, provider key or real `AXIOM_SECRET` is in the repository.

## Phase 11 — Account creation

1. **What was added.** `POST /auth/register` creates a row in a new `app_user` table
   (`id bigserial pk, username text unique not null, password_hash text not null,
   created_at timestamptz default now()`), added by
   `backend/alembic/versions/0005_users.py` on top of `0004_demo_flag`; no earlier
   migration was edited. The route validates the username (3–32 characters from
   `[A-Za-z0-9._-]`, lowercased before storing) and the password (at least 8
   characters), hashes with the existing `hash_password` from `backend/app/auth.py`,
   and stores only the hash. Nothing logs the password. Success answers `201 {username}`
   and does not sign the caller in. Validation failures are `422` with one sentence
   naming the rule that failed, and a taken username is `409` with "That username is
   already taken." Register is not behind `require_user`, and an in-memory per-IP limit
   (10 attempts a minute) answers `429` with "Too many attempts. Try again in a minute."

2. **Sign-in still accepts the `.env` account.** `POST /auth/login` checks `app_user`
   first and falls back to the configured `AXIOM_USERNAME`/`AXIOM_PASSWORD_HASH`
   account, so the local account works exactly as before. Every failure keeps the single
   "Incorrect username or password." message. Sessions for registered users work because
   `read_token()`'s final single-account check now asks `account_exists(username)`
   (the `.env` username, or a row in `app_user`) instead of comparing against
   `settings.axiom_username`. The token format, its signature and expiry, the route guard
   and the 401 handling are unchanged, as are `verifier.py`, `decide_status()`, the
   extractor prompt, the demo seed and the preset question.

3. **Frontend.** The sign-in card is a two-tab card again (Sign in / Create account,
   `role="tablist"`/`role="tab"`/`role="tabpanel"`). The create form has username,
   password and confirm fields, checks the two passwords match before it submits, shows
   the backend message in place, and on success switches to Sign in with the notice
   "Account created. Sign in to continue." and the username prefilled. The footer now
   reads "Accounts are stored locally. Not production authentication."

4. **Tests.** `backend/tests/test_register.py` adds 10 tests: successful registration,
   duplicate `409`, short password `422`, a registered user can sign in, the `.env`
   account still signs in, and a wrong password still gets the generic message, plus
   username-rule and rate-limit coverage. Every test account is generated by a fixture
   (`reader.<hex>` usernames, `secrets.token_urlsafe` passwords); no username or password
   is written into a test, a doc or the code. The suite clears the rate limiter and
   truncates `app_user` between tests.

5. **Verified.** `.venv/bin/pytest -q` passes (58 passed, 48 before). `npm run build`
   passes with no TypeScript errors (Vite built 33 modules). In the browser, creating an
   account answered `201`, switching to Sign in showed the notice, and signing in reached
   `/dashboard` with the sidebar username and dashboard data loaded; a duplicate username
   showed "That username is already taken."; a wrong password stayed on `/sign-in` with
   "Incorrect username or password."; and the `.env` account still signed in. The console
   had no JavaScript errors. The migration was applied locally with
   `alembic upgrade head` (`0004_demo_flag -> 0005_users`).

6. **Commit.** Local commit "Add account creation"; not pushed.

## Phase 12 — App shell redesign

1. **What changed.** The shell is now a 260px dark sidebar plus a top bar: the AXIOM mark
   and gold wordmark with "RESEARCH INTELLIGENCE" beneath, search and collapse icon
   buttons, a dusty-purple "New question" button, a quick-actions card (upload, ask, load
   demo), the six navigation rows with a purple left bar on the current page, a collapsible
   Recents list of the last five runs, and a user footer whose initial/name/"Local account"
   button opens a Sign out menu. The top bar carries the page title, a search field with a
   ⌘K hint (⌘K / Ctrl+K focuses it; submitting opens `/search?q=…`) and the username
   dropdown. Below 900px the sidebar becomes a slide-in panel opened from a menu button.
   Ask moved from `/` to `/ask`, and `/` redirects there.

2. **What the overview shows.** A command-center card (eyebrow, "Welcome back, {username}",
   one line built from real counts, three actions), four stat cards, a "Needs your
   attention" card, a "Claim statuses" card with a bar per status, and a ten-row recent-runs
   table. Attention lists only real items: runs whose report contains a conflict (found by
   reading the recent runs' details when the summary reports conflicts), failed runs with
   their stored error line, and sources with zero chunks. Every empty state is one
   sentence: "Nothing needs attention right now.", "No claims yet.", "No runs yet. Ask a
   question, or load the demo to see a full report.", and "No runs yet." in Recents.

3. **Backend.** One read-only change to `GET /dashboard/summary`: `claim_status_counts`
   (one GROUP BY over `claim.status`, zero-padded to the four statuses),
   `failed_run_count`, and `latest_run` (`id`, `status`, `question`, `created_at`).
   Existing fields keep their names and meaning. One deviation, stated plainly: the recent
   window grew from 5 to 10 rows (`RECENT_RUN_LIMIT`) so the dashboard's ten-row table has
   ten rows; the existing test's `min(5, …)` assertion was updated to match. A new test
   checks the four claim counts against the database's own GROUP BY, the failed count
   against a `status = 'failed'` count, and that `latest_run` is the newest row.

4. **Unchanged on purpose.** Sign-in (layout, copy, animation, logic), token handling, the
   route guard, 401 handling, sign-out, `verifier.py`, `decide_status()`, the extractor
   prompt, the demo seed and question, and the synthetic-data banner. Report content and
   behaviour are the same; only its header (eyebrow "REPORT", question as the h1, status
   badge, timestamp) and its section cards changed.

5. **Verified in the browser** at 1440px and 390px: the four stat numbers matched
   `/dashboard/summary` (sources 8, runs 32, runs with a conflict 15, claim statuses
   10/26/17/14); every sidebar link resolved to its label's route and Report was a
   disabled span with the tooltip "Run a question first" once the summary was empty; both
   Load demo buttons reached a completed report with the synthetic-data banner, three
   supersessions and one conflict; ⌘K focused the search and "ionosphere" returned six
   passages; collapsing left the content's width and top unchanged; at 390px
   `document.documentElement.scrollWidth` was 390 on every page with the runs table
   scrolling inside its own container; the five forbidden strings were absent from every
   page; and the console showed only Vite/React DevTools info. Body text measured 6.4–7.5:1
   against its cards, and links moved to a lighter dusty purple to clear 4.5:1.

6. **Commit.** Local commit "AXIOM app shell redesign"; not pushed.

## Phase 13 — Typography and UI polish

1. **Diagnosis before edits.** Measured in the running app at 1440 px. The heading family
   loaded only at 500–700, so `document.fonts.check('16px "Space Grotesk"')` returned
   false; Inter had no 700, so `<strong>` was synthesised. Body line-height was 1.55
   (24.8 px at 16 px) instead of 1.6. The page eyebrow used 0.18em tracking at weight 400,
   the h1 carried +0.01em instead of a tight heading value, and `.badge` text colours
   measured 4.20–4.21:1 on their own tints. The page background was #111318 and the card
   #1a1d24 (1.07:1), so a card was only visible because of its border. One browser-default
   element (`.nav-backdrop`, font 13.3 px Arial) fell outside the type system.

2. **Font weights (documented in the README).** `frontend/index.html` now requests
   Inter 400;500;600;700 and Space Grotesk 400;500;600;700. No family was added or
   removed. The 400 heading face and the 700 body face are the only change; both now
   report loaded in `document.fonts.check()`.

3. **Tokens.** `src/index.css` defines `--font-heading`, `--font-body`, `--font-mono`,
   the six sizes (`--text-xs` … `--text-2xl`), the four weights, three line heights and
   two tracking values. Every `font-size` and `font-weight` declaration in the stylesheet
   uses a token; a grep for raw `font-size: <number>` and `font-weight: <number>` returns
   nothing. `button, input, select, textarea { font: inherit }` removes the last
   browser-default font.

4. **Palette change justified by measurement.** The card surface moved from #1a1d24 to
   #232833 so a card reads as a surface without its border (1.26:1 against #111318), with
   one shadow token that includes `inset 0 1px 0 rgba(255,255,255,0.04)`. `--surface-2`
   became #191d25 and `--border` #333a47. Because a lighter card lowers badge contrast,
   the conflict text moved from #e06666 to #ec8b8b and superseded from #8b919c to #a9b0bb.
   The four status hues are unchanged; only their lightness was tuned to clear 4.5:1 on
   the tinted badge backgrounds.

5. **Role mapping.** h1 = 40 px Space Grotesk 600/1.15/-0.01em; card title = 20 px 600/1.15;
   eyebrow = 12 px Inter 500 uppercase +0.08em in `--accent-text`; body = 16 px/1.6;
   meta = 14 px muted; stat numbers = 28 px 600 tabular; table cells = 14 px tabular;
   buttons = 14 px 500; quotes = 14 px mono in a bordered block with a 3 px accent bar.
   Run status and claim badges gained a `::before` dot so colour is never the only cue.

6. **Spacing and states.** Section gaps 24 px, card padding 20 px (24 px on the command
   card), 16 px between form fields. One hover lift colour (#2b3140) and one row hover
   surface; table rows, claims, sources and attention rows have hover backgrounds. All
   focus rings are 2 px accent at 2 px offset, including a global `:focus-visible`
   fallback and a ring on the top-bar search box (the input itself is borderless). The
   disabled primary button is 40% opacity with `cursor: not-allowed`.

7. **Empty states and loading.** `components/EmptyState.tsx` is now the only empty state:
   heading, one sentence and a next-step button or link, used on Overview (attention,
   claim statuses, recent runs), Report (claims, supersessions, conflicts), Sources (empty
   library, a source with no chunks) and Search (no query, no matches).
   `components/Skeleton.tsx` replaces the bare "Loading…" text on the Overview stat cards
   and recent-runs table, the Report and the Sources library; its shimmer is removed under
   `prefers-reduced-motion`.

8. **Deliberate small UI changes.** The active nav item already had a left accent bar plus
   a lighter background, so it was left as is. The duplicate Guide link in the sidebar
   footer was removed (Guide remains in the nav); the footer overlapped the Recents list
   at 900 px once the type grew. Recents now shows the three most recent runs and clips
   instead of spilling. The native file picker is themed with `::file-selector-button`.
   Paragraphs are capped at 76ch inside cards, and page h1s drop to 28 px below 900 px so
   a long report question does not fill a phone screen.

9. **Screenshots.** Ten captures in `docs/screenshots/` at 1×: eight at 1440×900 and two
   at 390×796. They were captured through the browser preview at a 1440×900 viewport and
   resampled to 1440 px wide with `sips`; the three text-dense frames that still exceeded
   300 KB were re-encoded as 256-colour PNGs with a throwaway Python script (no package
   added). The small purple "Freebuff" pill at the top-left of the desktop captures is
   injected by the preview tool, not by AXIOM; it is not part of the app and could not be
   removed from the screenshot.

10. **Verified in the browser.** All pages: only 12/14/16/20/28/40 px and only
    400/500/600/700; no element resolves to a fallback font; the lowest body-text contrast
    is 4.79:1 (the primary button's #141220 on #8b7aa8); scrollWidth equals 390 at every
    screen; one h1 per page; the demo banner text is unchanged; no console errors. Not
    verified: hover and focus states were confirmed from the stylesheet and computed
    outlines, not by driving every control with a mouse and keyboard.
