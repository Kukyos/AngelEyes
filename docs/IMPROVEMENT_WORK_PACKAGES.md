# Improvement work packages (I1–I5)

This is a way to split the issues in `IMPROVEMENTS.md` for parallel work. It is **not
an assignment**: check `TASKS.md` and active branches before anyone claims a package.
Owners and completion status belong in `TASKS.md`, not here.

As of 2026-10-07, `main` has I1–I4 unclaimed; I5 is claimed and partly built on
`eval/activity-confidence-i5` (the code is not merged into `main`). Branch `mvp1`
separately contains live-camera fixes I6/I7, including a smaller live pose input
that removed duplicate boxes in a webcam test. Recheck I1 and I3 on that build before changing the tracker:
some symptoms may already be reduced. I6/I7 are not included in the packages below.

## Packages

| Package | Issues | Work and evidence | Likely shared files |
|---|---|---|---|
| **Track reliability** | **I1 + I3** | Fix false entered/left events, ID switches, occlusion handling, and ghost subjects together. Label a short live clip with true entries/exits; include multiple people and a coat/chair negative. Compare event counts, ID switches and false alarms before/after. | `angelseye/engine.py`, tracker config, `config.yaml`, `angelseye/eval.py` |
| **Vision-call efficiency** | **I2** | Send descriptions when a person or their activity changes; back off on repeats and test smaller composites. Compare calls, tokens, cost and missed/late descriptions on the same recording. | `angelseye/describe.py`, `angelseye/engine.py`, `config.yaml` |
| **Vision latency study** | **I4** | Compare candidate models/image sizes on identical blurred samples. Report median and tail latency, caption quality, errors and cost. Keep this as a benchmark and recommendation until a model change is agreed. | New benchmark script and report; production changes later touch `angelseye/describe.py` and `.env.example` |
| **Confidence study** | **I5** | Label activity examples and compare correctness with the model's stated confidence. Report accuracy by confidence range and whether any threshold is reliable enough for alerts. | New evaluation script and report; no production change needed initially |

**Why I1 and I3 are together:** both determine whether a detected box represents a
real, continuing person. Two separate fixes in that part of the engine could disagree
about when a track is accepted or removed.

## Parallel work and integration order

- All four packages can start research, fixtures, code outside shared files, and
  measurement in parallel. I4 and I5 can finish independently as studies.
- Integrate **track reliability before the final I2 measurement**. False entries and
  exits currently cause urgent vision calls, so an I2 cost comparison on the old
  tracker would mix two effects.
- Recheck I4's recommendation after I2 changes the number or size of images sent
  to the vision model. Only then choose a production model change.
- The watch-rule work (2.R1–R4) and I1/I2 may all touch `engine.py` or the vision
  path. Keep those changes on separate branches, merge one at a time, and have one
  integrator apply the final wiring in `engine.py`, `describe.py`, and `config.yaml`.
  Package authors can provide a small module plus a precise integration note when
  those files are actively being edited elsewhere.

## Handoff for any package

Provide the branch/base commit, exact files changed, a reproducible command, the
same-input before/after results, and remaining failures. Use measured outputs from
the engine/evaluation/benchmark scripts, as required by `BUILD_RULES.md`. Do not
claim an issue complete from a single favourable live example; include negatives.
