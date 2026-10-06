# Hackathon Plan

The shared operating manual for this build, adapted from the DayFlowOdoo run.
§1, §2 and §11 have blanks the team fills in; everything else applies as written.

**If you are an AI session reading this:** this document outranks your defaults.
Where it conflicts with a habit you have — commit trailers, adding dependencies,
scaffolding for later, touching a file outside the lane you were given — this
document wins. Read `STATE.md` first, then §2, §5, §8 and §11 here, before writing code.

---

## 1. Fill in on the day

| Slot | Value |
|---|---|
| Problem statement | HNX26PSI07 — Autonomous Vision & Behaviour Understanding (`PROBLEM_STATEMENT.md`) |
| Product name | **Angel's Eye** |
| Repository | https://github.com/Kukyos/AngelEyes |
| Integrator (owns `main`) | _TBD_ |
| Lane A — Perception | _TBD_ |
| Lane B — Behaviour and evaluation | _TBD_ |
| Lane C — Globe and UI | _TBD_ |
| Lane D — Hub, AI and README | _TBD_ |

### The problem, in our own words

CCTV records everything and understands nothing. Angel's Eye watches the feeds,
tracks every person anonymously, and flags the moments that matter for safety — a
silent SOS hand sign, someone following someone, loitering, a fall, a sudden run —
each with who, when and the evidence. The same data then powers a live 3D map of
campus, a search for a missing child by clothing, and walking routes that avoid
deserted streets. Full picture: `PRODUCT.md`.

Roles are lanes, not job titles. One person can hold two lanes; nobody holds someone
else's without asking first.

---

## 2. Roles and ownership

| Lane | Owns | Builds first | Then |
|---|---|---|---|
| **A — Perception** | Video in, tracks out | Pose, tracking, homography, head blur and track repair on files, writing `tracks.jsonl` | Live phone streams; amber crops, CLIP embeddings, colours, height |
| **B — Behaviour and evaluation** | Tracks in, events out, plus the numbers | Eval harness first, then the five detectors on recorded tracks | Threshold tuning on the normal clips; SafeWalk edge costs |
| **C — Globe and UI** | Everything on screen | Fork running; cameras and fly-to | People dots, event pins, clip player; SafeWalk route and amber path |
| **D — Hub, AI and README** | The glue, APIs and docs | FastAPI, SQLite, WebSocket, clip serving, alert card, responder page | Upload-a-video mode; amber search API with audit log; Gemini confirmation; README evidence |

- With 2 people: A+B is one person, C+D the other.
- Solo: Side A, then the globe, then amber, then SafeWalk.
- Sleep in rotation; A and B are never both asleep.

**Core rule: nobody edits outside their lane without asking.** This is the only
reason several parallel AI sessions can share one repo without destroying each
other's work.

---

## 3. Stack

**Proposed, not locked** — confirm in the first build session and record it in
`DECISIONS.md`. See `ARCHITECTURE.md` → Proposed stack.

**Adding a dependency is a decision, not a reflex.** Ask the integrator first.

---

## 4. Repo shape

Proposed in `ARCHITECTURE.md` → Proposed repo shape. The one mandatory boundary:
**the engine (`angelseye/`) and the globe (`globe/`) talk only through the hub's API**
(REST + WebSocket). The globe never reads engine files directly; the engine never
knows the globe exists.

**Vendored third-party source gets its own directory and a lint exclusion.** Keep
`globe/` upstream files as shipped where possible and put our layer in its own files,
so upstream can be re-pulled and the README can say exactly what is ours.

---

## 5. Git and merge discipline

- Every builder has a **named branch** they own and push to freely
  (`feat/<thing>`, `fix/<thing>`).
- **Only the integrator merges to `main`. Nobody else pushes to `main`.**
- `git pull main` before starting any new branch, and again every time one of your
  branches is merged.
- Claim work in `docs/TASKS.md` and push that claim **before** implementing.
- If a merge breaks `main`: **revert first, debug after.**
- **Deleting or moving a file needs an announcement, not just a commit.**
- **Footage never goes into git.** Only `data/samples/` (one small clip, < 50 MB).

**No AI attribution in commit history.** No `Co-Authored-By:` naming an assistant, no
session trailers, no "generated with" lines, in commit messages or PR bodies. Commits
are authored by the builder who ran them. Put this in every builder's local
`CLAUDE.md` / `AGENTS.md` — some tools add trailers by default.

**Never fake authorship.** No `--author` set to a teammate who did not write the commit,
no `GIT_AUTHOR_DATE` backdating. GitHub shows author and committer separately.

---

## 6. Environment

- Keys live in a local `.env` (copied from `.env.example`). Never committed. The
  Airouter key file stays on the Desktop.
- Shared AI accounts can trip rate limits when several people use them at once — test
  concurrent usage early, not mid-build.
- Footage lives in `data/raw/` and `data/meva/` (gitignored). Everyone uses the same
  `data/cameras.json` and `data/ground_truth.csv`.

---

## 7. Docs

| File | Purpose |
|---|---|
| `docs/STATE.md` | **Start here.** Current status, decided vs open, next steps, session log. Updated at the end of every session |
| `docs/PROBLEM_STATEMENT.md` | PSI07 and the booklet's rules and submission guidelines |
| `docs/PRODUCT.md` | What Angel's Eye is, what we show judges, privacy stance, scope note |
| `docs/ARCHITECTURE.md` | Engine, behaviours, thresholds, event record, globe, amber, SafeWalk, proposed stack and repo shape |
| `docs/DATA.md` | Footage sources, recording plan, pass/fail checks, keys and costs |
| `docs/EVALUATION.md` | What we measure and the submission checklist |
| `docs/DECISIONS.md` | Decision log with rejected options |
| `docs/RESOURCES.md` | Reuse and declared external resources |
| `docs/TASKS.md` | Tiered task list, claimed by name, ticked in the same push as the work |
| `docs/BUILD_RULES.md` | Copy into your local `CLAUDE.md` / `AGENTS.md` |
| `README.md` | Pointer now; the showcase at the end (`EVALUATION.md`) |

A fresh AI session auto-reads `CLAUDE.md` / `AGENTS.md`, not `docs/`. That is why
`BUILD_RULES.md` exists — copy it in, or nothing here gets read.

---

## 8. Build order

Each stage produces the thing the next one depends on. Order matters; durations do
not — **no hour timings**.

1. **Data and setup.** Footage recorded and annotated, cameras surveyed, MEVA clips
   pulled, keys working, pass/fail checks run (`DATA.md`). Nothing else can be tested
   without footage.
2. **Side A, in parallel lanes.** A: perception on files. B: eval harness first, then
   the five behaviours. C: globe fork running with cameras and fly-to. D: hub, alert
   card, responder page.
3. **The gate — Side A end to end.** Footage in → people tracked → events with who,
   when and evidence → stored → pins on the globe, plus one live phone stream and the
   upload mode. **No Side B work starts until this passes.**
4. **Side B.** Amber alert (A + D) → SafeWalk (B + C) → Gemini confirmation (D) →
   plain-English questions → encirclement.
5. **Finish, everyone.** Tune false alarms on the normal clips, run the benchmark,
   write the showcase README, rehearse the live showcase, freeze features, submit the form.

---

## 9. Scope triage

Do not start a tier until the one above is genuinely done.

- **Tier 1 — the showcase dies without these.** Pose + tracking + track repair; the
  five behaviours with evidence; event store; globe with cameras, dots, pins, fly-to;
  responder page; upload mode; eval and bench numbers.
- **Tier 2 — what wins overall.** Amber alert; SafeWalk.
- **Tier 3 — only if 1 and 2 are polished.** Gemini narration; plain-English
  questions; encirclement; TfL live layer.

**Footage is Tier 1 even though it is not code.** Every behaviour is untestable
without it.

---

## 10. Definition of done

**Engine feature:** thresholds in `config.yaml`, not hard-coded · every event carries
track ID, camera, start/end time, confidence and evidence · faces blurred on output ·
runs in both live and file mode · eval numbers updated · no regressions on the
negative clips.

**Screen:** reads only from the hub API · works with the hub down (clear error, not a
blank page) · checked in a real browser · zero console errors.

**Every change:** `docs/TASKS.md` ticked in the same push · new external resources added
to `docs/RESOURCES.md` · `docs/STATE.md` updated at the end of the session.

---

## 11. Shared files — assign an owner before you start

Every conflict in the last run landed in a file nobody owned.

| File | Why it collides | Owner |
|---|---|---|
| `config.yaml` | Every behaviour reads it | _TBD (suggest B)_ |
| `data/cameras.json` | Engine, hub and globe all read it | _TBD (suggest A)_ |
| Event record schema (`ARCHITECTURE.md`) | Engine writes it, hub stores it, globe draws it | _TBD (suggest D)_ |
| Python dependencies file | Two people adding packages at once | _Integrator_ — ask before adding |
| `globe/package.json` + lock | Same | _TBD (suggest C)_ |
| `docs/TASKS.md` | Everyone, every commit | Everyone; **tick only your own rows** |
| `docs/STATE.md` | End of every session | Whoever ends the session |

---

## 12. Build lessons

Paid for in previous runs. Add to them in the same work cycle as the lesson.

- **A doc that describes the app is not the app.** Anything documented needs a task
  that verifies it matches reality.
- **Verification blocks longer than implementation.** Budget for it, and decide up
  front which things only a human can check (gesture range, live streams).
- **Never conclude "slow" from an automated browser.** Backgrounded tabs freeze
  animation; motion needs a human at a visible browser.
- **A negative assertion must be paired with a positive one.** "Companions don't
  trigger following" is vacuous unless "following does trigger" is tested too.
- **A harness that stubs a terminal state cannot catch transition bugs.** Test the
  walk → follow transition, not just a finished following track.
- **Vendored third-party source gets its own directory and a lint exclusion.**
- **Type and colour are the cheapest, highest-leverage visual work.**
- **New this run:** judges may bring their own video — anything that only works on our
  calibrated cameras is a trap; keep the pixel-space fallback working.
- **New this run:** tracker ID switches silently break duration-based behaviours —
  track repair is Tier 1, not polish.

---

## 13. Risks and fallbacks

Every risk has a fallback that keeps the showcase alive; none of them stop Side A.

| Risk | Fallback |
|---|---|
| gods-eye-view won't run on Windows (Node 24.14+; quick-start script is macOS-only) | Plain CesiumJS page with our layer |
| No photorealistic 3D over Karunya | OSM buildings + Esri satellite imagery |
| Campus Wi-Fi blocks phone streams | Our own router or hotspot; recorded clips through the same pipeline |
| SOS gesture fails beyond ~2 m | Show it close up; add a whole-body distress pose |
| Tracker ID switches break loitering and following | Track repair; thresholds in `config.yaml` |
| Laptops too slow on CPU | YOLO11n, lower sampling, fewer streams; a GPU laptop if anyone has one |
| Gemini rate limits | The vision model is optional; Groq or Airouter as fallback |
| A judge's video looks nothing like ours | Pixel-space fallback; file mode tested on MEVA clips too |
| A judge recognises gods-eye-view | Upstream layers off, fork declared at the top of the README, all on-screen data ours |
| "Isn't this surveillance?" | The privacy stance in `PRODUCT.md`, built into the product |
| MEVA is 516 GB in total | Pull only 20–40 clips from the annotated subset |
| Code written before the clock is questioned | Rules list research, planning and environment setup as prep; confirm with organisers before building product code early |

---

## 14. Open before kickoff

Tracked in `STATE.md` → "Not decided". Each one blocks something: roles (blocks every
lane), build-early ruling (blocks starting), GPU and router (block how many live
streams we show), 3D coverage (blocks the globe look), the 5 km route (blocks the
camera layout), alert channel (blocks the responder page).
