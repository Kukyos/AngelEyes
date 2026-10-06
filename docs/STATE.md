# State — start here

**Every new session reads this file first, and updates it before the session ends.**
It says where the project is right now, what is decided, what is not, and what to
do next. Everything else in `docs/` is reference; this is the handoff.

Last updated: 2026-10-06 (planning session, before any code).

---

## Where we are

- **Planning is done. No code exists.** The repo holds only these docs.
- Product: **Angel's Eye** — CCTV that understands what people are doing, built
  for women's and children's safety. See `PRODUCT.md`.
- Problem statement: **HNX26PSI07 — Autonomous Vision & Behaviour Understanding**.
  See `PROBLEM_STATEMENT.md`.
- Event: HackNex 2026 Internal Qualifier (Karunya CSE), 24 hours, ~400 teams,
  **one overall winner** (not one per problem statement). The 24-hour event
  starts 2026-10-07.
- Repo: https://github.com/Kukyos/AngelEyes
- Team plan as a shareable doc (same content as these files, with two diagrams):
  https://claude.ai/code/artifact/030d5815-7305-4814-bc2f-18ca33ba8ed7
- Source booklet: `materials/HackNex 2026 - Internal Qualifier PS.pdf`
  (gitignored; original at `SHITIBUILT/HacknexResource/`).

## Decided

| Decision | Detail | Where |
|---|---|---|
| Problem statement | PSI07, chosen over PSI08 (the earlier recommendation) | `DECISIONS.md` D1 |
| Two sides | Side A = scored perception + behaviour engine; Side B = the "God's Eye" safety layer built on Side A's data | `PRODUCT.md` |
| The gate | Side A runs end to end before any Side B work starts | `HACKATHON_PLAN.md` §8 |
| Five behaviours | SOS gesture, following, loitering, fall, sudden run (+ encirclement as stretch) | `ARCHITECTURE.md` |
| Globe | Fork `bilawalsidhu/gods-eye-view` (MIT); upstream layers and voice agent off; plain CesiumJS fallback | `DECISIONS.md` D4 |
| Privacy | No face recognition, no gender inference, faces blurred, amber alert authority-only + audit log, mock footage of consenting teammates only | `PRODUCT.md` |
| Data | Own staged recordings + MEVA (real multi-camera footage, CC-BY-4.0) + TfL JamCams for live crowd levels. Real 5 km street CCTV is not obtainable | `DATA.md` |
| Money | Nothing required; optional Airouter top-up and a Wi-Fi router | `DATA.md` |
| How we present | Live showcase at the table. No video, no scripted pitch lines | `PRODUCT.md`, `DECISIONS.md` D9 |
| How we plan | Dependency order and gates. No hour-by-hour timings | `DECISIONS.md` D9 |

## Not decided — the next session starts here

- [ ] **Who builds what.** Lanes A–D are defined in `HACKATHON_PLAN.md` §2; nobody is assigned.
- [ ] **Whether we start building before the 24-hour clock.** The rules list
      research, planning and environment setup as allowed prep — not product code.
      Check with the organisers first.
- [ ] Final team size (plan works for 4, collapses to 2 or 1).
- [ ] Does anyone have an NVIDIA GPU laptop? (Plan assumes CPU only.)
- [ ] Can someone bring a Wi-Fi router or reliable hotspot? (Campus Wi-Fi may block phone streams.)
- [ ] Does Google's photorealistic 3D cover Karunya? (Check in Google Earth.)
- [ ] Which 5 km route we draw on the map (campus + which road).
- [ ] Responder alerts: ntfy.sh or a Telegram bot.
- [ ] Stack and repo shape in `ARCHITECTURE.md` are **proposed**, not locked.
- [ ] **Which items from `CAPABILITY_MAP.md` get promoted into scope** (pre-planning,
      `TASKS` 0.8). The map is the input; D3's five behaviours are still the committed set.
- [ ] Public offender-registry layer: verify an official public source, then pick
      option (a), (b) or (c) in `CAPABILITY_MAP.md` §3.4 (D12).
- [ ] Deployment path beyond the hackathon: own build, campus pilot, or government
      partner (`CAPABILITY_MAP.md` §4).

## First steps for the next session

1. Read this file, then `HACKATHON_PLAN.md`, `PRODUCT.md`, `ARCHITECTURE.md`.
2. Resolve the "Not decided" list with the team; write the answers here and in
   `HACKATHON_PLAN.md` §1 and §11.
3. Each builder: `cp docs/BUILD_RULES.md CLAUDE.md` (gitignored).
4. Start `TASKS.md` Stage 1 (data and setup). Recording footage blocks everything.

## Housekeeping (outside this repo)

- Plaintext Groq keys found in `SHITIBUILT/Claweo/config.py` and
  `SHITIBUILT/ParticleAI/SD-INTEGRATION.md` — rotate them before anything goes public.
- The Airouter key file lives on the Desktop. Never copy it into this repo.

## Session log

| Date | Session | Outcome |
|---|---|---|
| 2026-10-06 | Pre-planning | Pushed docs to GitHub. Re-read PSI07's must-do list. Wrote `CAPABILITY_MAP.md` (all behaviours by layer, Side B features, legal paths); added D10–D12 and task 0.8. No code. |
| 2026-10-06 | Planning | Read the booklet; compared all 10 statements; chose PSI07 + safety layer; named it Angel's Eye; researched data, keys and costs; wrote these docs. No code. |
