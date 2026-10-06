# Decisions

A log of what we decided and why, including the options we rejected, so no reasoning
lives only in a chat. Newest decisions are appended at the bottom. When you change a
decision, add a new entry that supersedes the old one — don't rewrite history.

---

## D1 — Problem statement: PSI07 (2026-10-06)

**Decided:** PSI07, Autonomous Vision & Behaviour Understanding, with a women's and
children's safety product on top.

**How we got there.** The constraints that filtered the ten statements:
1. Judges may bring their own inputs and hidden tests, so favour statements where API
   models generalise without training.
2. Wins should be visible live; a rubric scored on things a demo can't show is risky.
3. Crowded statements cost more to stand out in.
4. One overall winner from ~400 teams — this weights peak impressiveness, not just
   maxing one rubric.

| PS | What it is, plainly | What we'd have built / the hook | Why not (or why) |
|---|---|---|---|
| 01 Document intelligence | Ask questions over PDFs (tables, charts, scans); every answer cites document, page, section; charts read visually | Citations that highlight the exact box on the page; chart numbers extracted and re-plotted over the original as proof; a "damage slider" that blurs/stains the page live; all maths done in code | Solid, but the most-picked statement |
| 02 Video temporal reasoning | Ask a video "what happened right before the alarm?"; every answer needs a timestamp; right event at wrong time = half credit | Event log with timestamps; answer jumps the video to that second with the person boxed | Timestamp accuracy on their videos; heavy setup |
| 03 Cyber threat intel | Stitch innocent-looking logs into an attack story; false-alarm cap | Simulated company + attacks, entity graph, MITRE stages, cinematic attack replay, zero alarms on clean logs | False-alarm cap on unseen judge logs |
| 04 Fraud rings | Find groups of accounts acting together; risk score + reason per transaction/account; false-alarm cap | Simulated transactions with rings, graph clustering, ring lights up | Same cap as 03, less dramatic, Kaggle-crowded |
| 05 Medical images | X-ray second opinion: points to the spot, confidence, phrased as "Doctor, consider…" | Pre-trained model + heatmap + Gemini with notes | Everyone shows the same heatmap; sensitive domain |
| 06 Inpainting | Erase things from photo/video seamlessly; nothing else may move; no flicker | Paste original pixels back outside the hole as a provable "nothing else changed" map | GPU; video consistency very hard in 24h |
| **07 Behaviour understanding** | Track people, understand behaviour, flag who and when | **Chosen** — see below | Crowded with YOLO demos, so the product layer must carry it |
| 08 Proof-carrying data analyst | Every number comes with runnable code; refuse unanswerable questions | Trap scanner before the AI; compute every valid interpretation (dates, currency, dupes) and answer only if they agree; two blind solvers must agree; every number re-runs in the judge's browser (Pyodide); edit a cell and dependent proofs turn red | Was the first recommendation: mechanical rubric, least crowded, reuses AutoLAB's runner and NetSage's rules-before-AI pattern. Rejected by the team as not cool or usable enough to win overall |
| 09 Coding agent | A homemade Claude Code that fixes bugs without breaking tests; hidden tests | — | Judges compare it to tools they already use |
| 10 Deepfake forensics | Real-or-fake score with reasons; must catch unseen fake types | — | Generalising to unseen fakes is near impossible in 24h |

Earlier ranking was 08 > 01 > 03. The team chose 07 instead, with the "God's Eye"
idea and a women's safety twist: the detection engine answers PSI07, and the data it
produces powers a product nobody else will have.

## D2 — Two sides and a gate (2026-10-06)

Side A (scored engine) must run end to end before any Side B (globe extras, amber,
SafeWalk) work starts. Rationale: PSI07 scores Side A; Side B is worthless without it,
and the submission's required Scope Note maps directly onto MVP vs stretch.

## D3 — Five behaviours only (2026-10-06)

SOS gesture, following, loitering, fall, sudden run (encirclement as stretch). Each one
appears in what we show judges; anything else is scope creep. Thresholds configurable
so short staged clips still trigger.

## D4 — Globe: fork gods-eye-view (2026-10-06)

The team wants the God's Eye look. Fork it (MIT), turn off upstream's flights, ships,
satellites, CCTV layer and voice agent so everything on screen is ours, keep its
night-vision/thermal looks, and declare the fork at the top of the README — the repo
went viral (#1 GitHub trending, Aug 2026), so some judges will recognise it.
Fallback: a plain CesiumJS page. Voice agent cut: it needs an OpenAI Realtime key we
don't have.

## D5 — Privacy stance (2026-10-06)

No face recognition, no gender inference, faces blurred, rolling buffer, amber alert
authority-only with an audit log, SafeWalk on aggregates only, mock footage of
consenting teammates only. Rationale: "parents monitor kids on street CCTV" would let
anyone claiming to be a parent track a person across a city; judges will ask; and
gender classification is unreliable and unnecessary because the threats are behaviours.

## D6 — Data sources (2026-10-06)

Real continuous 5 km street CCTV is not obtainable (police-owned; bystanders can't be
published). Use our own staged recordings + MEVA + TfL JamCams; place clips along a
5 km route as labelled mock feeds. Details and sources: `DATA.md`.

## D7 — Name: Angel's Eye (2026-10-06)

Working name TRINETRA was replaced by **Angel's Eye** (repo `AngelEyes`, Python
package `angelseye`).

## D8 — Efficiency is a measured claim (2026-10-06)

Cheap-first cascade; the vision-language model only sees candidate events and is
optional. We show streams × fps and % of frames sent to the VLM from `angelseye.bench`,
never an estimate.

## D9 — How we work and present (2026-10-06)

- No hour-by-hour timings in plans — dependency order and gates instead.
- No scripted demo, no video: we show the working system live, as a plain ordered list
  of features (`PRODUCT.md`).
- Prep is for getting a clear picture of what we build; building early is acceptable to
  the team, subject to checking the organisers' rules (open in `STATE.md`).

## D10 — Ambition raised; capability map first (2026-10-06)

The team does not want to stop at the PSI07 minimum or at five behaviours. Before any
build, `CAPABILITY_MAP.md` lists everything that is possible by layer (tracks, pose,
pairs, crowd, cross-camera, context) and every Side B feature, each with feasibility,
data need and how it would be measured. D3's five behaviours remain the *committed*
build scope until the team promotes more from the map; each promotion gets its own
entry here. D2 (Side A before Side B) is unchanged.

## D11 — Behaviours apply to anyone, not to women (2026-10-06)

Cross-camera and context rules (e.g. a person who never exits a street) flag **any**
person. Women's and children's safety sets priorities and alert wording, not a
classifier. Consistent with D5 (no gender inference).

## D12 — Offender-registry layer and non-consensual tracking (2026-10-06)

- Tracking a named person by appearance without their consent (the "mother tracks
  daughter purely through footage" idea): **rejected.** The consented trip share
  replaces it (`CAPABILITY_MAP.md` §3.3).
- Public sex-offender registry layer: **open, not in MVP or showcase.** Needs a verified
  official public source and a team decision between the options in
  `CAPABILITY_MAP.md` §3.4. If built, it never links a registered person to a camera
  track.

## Still open

Tracked in `STATE.md` → "Not decided".
