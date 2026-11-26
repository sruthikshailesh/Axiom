# REMAINING — before the BUiLDX submission

Status legend: **done** = verified in this run; **open** = still to do; **blocked** = needs the
user's answer or an external action.

Freeze time: **9:00 PM on 26 November**.

## Track

- [ ] **Track — open (blocked, needs the user's answer).** The submission needs one track.
      Options: AI & ML, Cybersecurity, Fintech, Healthtech, Civictech, Open Innovation.
      AXIOM is a document-intelligence application; AI & ML is the natural fit, but the
      user must choose and enter it on the dashboard form.

## Compliance

- [ ] **AI-tool policy — open.** The BUiLDX dashboard must be checked for any AI-tool rule,
      and the README's "AI assistance" paragraph must match it. The current paragraph
      discloses that AI assistants drafted code, tests and documentation and that the
      developer reviewed and verified everything; if the dashboard forbids AI tools, that
      paragraph (and the eligibility) must be revisited before submission.

## Sign-in

- [ ] **Local password — open (unchanged since it was shown in chat).** Verified in this
      run: verifying the local password from chat against `settings.axiom_password_hash`
      returned `True`, so the value in `backend/.env` still matches the one that appeared
      in the earlier notes. It has not been rotated. Rotate it with
      `python scripts/make_password_hash.py` and a new `AXIOM_SECRET` if the exposure is a
      concern; doing so signs out every existing session.
- [x] **Google sign-in — skipped.** `GOOGLE_CLIENT_ID` is not set in `backend/.env`, so
      Part 1 was skipped per the instructions. No backend endpoint, no frontend button and
      no README section were added; the sign-in page shows no Google button and no broken
      element (verified at 1440px and 390px). Nothing claims Google sign-in is built.

## UI

- [x] **UI pass — done in this run.** Audited every screen at 1440px and 390px. Fixed the
      remaining issues: completed the type scale to 12/14/16/20/28/40px, finished the
      radius/shadow tokens, added hover/focus states for the fold-out rows and links, and
      added a next step to the report's empty claims/supersessions/conflicts states.
      390px `scrollWidth` matched the viewport on Sign-in, Dashboard, Ask, Report #29,
      Report #26, Sources, Search and Guide; no horizontal overflow at 1440px; one `h1`
      per page; console showed no uncaught errors. Remaining minor item: the full type
      scale is applied to CSS, but no visual regression test suite exists (manual checks
      only).

## Demo video

- [ ] **Demo video — open.** The user records it. Script: `NOTES.md`, Phase 10, item 5.
- [ ] **Demo video upload to Google Drive with viewing access — open.** Upload the recorded
      video and set link sharing so the reviewers can watch it.

## Submission form

- [ ] **Dashboard submission — open.** The README provides content for these fields; check
      each against the actual form: project name (**AXIOM**), tagline, short description,
      problem statement, proposed solution, key features, technologies used, installation
      and run steps, architecture, team members and contributions, AI-assistance
      disclosure, demo-data notice, and known limitations.

## Repository

- [ ] **Repo still public and README renders logged out — open.** Re-check after the final
      push: load the GitHub repository URL in a logged-out browser or private window and
      confirm the README body, tables, code blocks, Mermaid diagram and images render.

## Timing

- [x] **Hackathon timing note — verified.** The first commit `a9835be` is dated
      `2026-11-25 15:58:20 +0530`, after the 11:00 AM kickoff on 25 November. No commit in
      the history predates the kickoff, so there is no earlier work to disclose.

## Known limitations in the README

- [x] **Uncertain-claim case not shown in the demo — done.** Listed under "Known
      limitations" in `README.md`.
- [x] **Scanned PDFs rejected — done.** Listed under "Known limitations".
- [x] **Single local account — done.** Listed under "Known limitations".
- [x] **Google testing mode — N/A.** Google sign-in was skipped, so there is no Google
      testing-mode limitation to disclose. This item should be revisited only if Google
      sign-in is added later.
