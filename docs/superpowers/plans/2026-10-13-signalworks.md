# SignalWorks Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for native execution or superpowers:subagent-driven-development if the user selects delegation. Track tasks with checkboxes.

**Goal:** Add a reproducible reliability lab and Anatomy explainer to the existing GitHub engineering portfolio.

**Architecture:** LedgerStream remains the transactional engine. A new Python scenario runner records committed SQLite states as deterministic versioned traces. A static SVG website replays these traces with accessible controls and an explicit recorded-run disclosure.

**Tech Stack:** Python 3.11+, SQLite, standard-library unittest, HTML/CSS/JavaScript, Anatomy SVG kit, Node for geometry generation and browser checks.

**Spec:** [SignalWorks design](../specs/2026-10-13-signalworks-design.md), approved by the user.

## Global constraints
- Preserve LedgerStream and unrelated work; cite it as the foundation.
- Synthetic order data only; integer cents; no external services or paid infrastructure.
- Public caption: “Interactive replay of a recorded local run using synthetic data.”
- No production-scale, Kafka, distributed exactly-once, or live-cloud claims.
- SVG Figure with 40–80 purposeful parts, dark/light themes, red accent, keyboard/touch support, reduced motion, and offscreen pause.
- Push verified work and create a reviewable pull request; verify hosting separately.

## Review focus
- Repeated scenario execution must not inherit earlier databases or random event IDs.
- A crash must leave state, receipts, quarantine, and checkpoint at the last committed state.
- A stale entity version arriving at the next source sequence must not resurrect a tombstone.
- Reset/scenario changes during playback must cancel pending animation and avoid mixed counters.
- Missing trace data or disabled JavaScript must leave a useful explanation and an explicit unavailable state.

## Task 1 — Reproducible scenario traces
**Files:** Create signalworks/__init__.py, signalworks/scenarios.py, signalworks/__main__.py, tests/test_signalworks.py, evidence/signalworks-traces.json.
**Consumes:** OutboxSource(path, stream), change(order_id, payload, delete=False, fail_after_source=False), read(after=0); Projection(path), apply(events, fail_after=None), checkpoint(stream).
**Produces:** build_traces() -> dict; snapshot(projection: Projection) -> dict; CLI `python3 -m signalworks --output evidence/signalworks-traces.json`.
- [ ] Inspect the current remote and repository instructions; create an isolated checkout and branch. Compare the current LedgerStream API against the local reference before edits.
- [ ] Write failing unittest cases for deterministic repeated generation, trace schema, duplicate/full-replay state equality, quarantine-and-continue, crash rollback/reopen/recovery, and delete/stale behavior. Confirm failure because signalworks is absent.
- [ ] Implement source-created deterministic IDs through a scoped injected UUID provider during generation; never modify the engine's production identity behavior. Inject malformed/conflicting/stale envelopes explicitly as transport test fixtures and label them accordingly.
- [ ] Implement separate temporary source/sink databases per scenario, DB-query snapshots after commit/rollback, and schema-versioned JSON with event ID, source sequence, entity version, disposition, checkpoint, counts, paid cents, and narrative. Reopen Projection after the crash.
- [ ] Cover successful processing, duplicate, malformed payload, crash/recovery, replay, deletion/stale update; preserve existing engine tests for atomic source/outbox, routing failures, conflict and sequence gaps and add trace-level evidence for those failures.
- [ ] Run new and existing LedgerStream tests; regenerate twice and compare exact bytes. Commit engine-adapter tests and evidence.

## Task 2 — Anatomy machine and recorded-run player
**Files:** Create demos/signalworks/build.mjs, geometry.mjs, index.html, player.mjs, style.css, traces.json, and a scoped anatomy-kit directory with upstream license.
**Consumes:** Task 1 trace schema, with copies generated from the canonical evidence file.
**Produces:** Static demo at demos/signalworks/index.html; build script regenerates dark/light artwork and trace asset.
- [ ] Read Anatomy craft, motion, API and verification references and the nearest complete example. Document one-to-one mechanism mapping and 40–80 supported parts before geometry.
- [ ] Write player tests using Node's test runner for trace selection, bounds, reset during playback, timer cancellation, and unavailable-data behavior; run to confirm failure.
- [ ] Implement player state separately from DOM/animation. API: createPlayer(traces, onChange) with select(id), step(), play(), pause(), reset(), destroy(); inject scheduling for deterministic tests. Counters read exclusively from the current recorded snapshot.
- [ ] Build the parcel sorting/inspection machine with the installed Anatomy kit, clear physical supports, four tones, one active accent, quarantine tray and receipt mechanism. Keep geometry and runtime behavior in separate files.
- [ ] Implement scenario selection, run/step/pause/reset, readable event history, committed versus pending state, exact disclosure, architecture explanation, run command, evidence/source links, fallback content, responsive layout, and theme control for verification.
- [ ] Use elapsed-time interpolation; cancel transitions on reset/selection; pause when offscreen or page hidden; respect reduced motion and maintain keyboard/touch access. Avoid automatic screen-reader announcements every frame.
- [ ] Run player tests; inspect desktop/mobile, dark/light and motion close-ups. Run applicable Anatomy geometry audit and zero line-end checks; fix failures and report any unavailable checks accurately. Commit demo.

## Task 3 — Portfolio integration and release
**Files:** Modify README.md; create docs/signalworks.md, docs/superpowers/specs/2026-10-13-signalworks-design.md, docs/superpowers/plans/2026-10-13-signalworks.md; add scripts/verify_signalworks.py if needed to consolidate checks.
**Consumes:** Runnable scenarios, evidence, standalone demo.
**Produces:** Discoverable portfolio entry, reproducible verification command, GitHub branch and pull request.
- [ ] Add a SignalWorks row as a LedgerStream extension, case-study narrative, mechanism-to-code mapping, architecture diagram, commands, guarantees/limits, provenance and a static demo link. Confirm relative links resolve.
- [ ] Provide `python3 scripts/verify_signalworks.py` to run the focused tests, regenerate traces in a temporary destination, and compare both checked-in trace copies; nonzero on mismatch.
- [ ] Run full repository tests when dependencies are available, focused verification, Node tests, static asset checks, and browser checks for keyboard, reset, scenario switching, mobile overflow, reduced motion, offscreen pause, console errors and failure fallback. Record actual results and pre-existing failures separately.
- [ ] Review the final diff against the approved spec, including real-engine versus browser-replay disclosure, claim accuracy and imported kit licensing. Fix actionable defects and rerun affected checks.
- [ ] Follow the ship skill for commit/push/PR publication under existing user authorization. Attach the PR to this chat. Do not merge or claim live hosting without verified configuration and authorization.

## Self-review
All spec sections map to tasks: backend/evidence (1), website/Anatomy/accessibility (2), documentation/GitHub (3). Review-focus cases have explicit tests above. Actual remote file structure and instructions must be checked before implementation; discovered API differences require updating this plan before dependent work.
