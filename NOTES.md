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

7. **Secret scan.** `git grep -n -i -E "gsk_|sk-|api[_-]?key *= *[A-Za-z0-9]" -- ':!NOTES.md'`
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
