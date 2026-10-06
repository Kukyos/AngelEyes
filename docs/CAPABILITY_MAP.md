# Capability map — what is possible

Pre-planning output (`TASKS.md` 0.8). Written before any build, to see the whole
space first. Nothing here is committed scope — `ARCHITECTURE.md` and `PRODUCT.md` stay
the build plan until the team promotes items from this map (record each promotion in
`DECISIONS.md`).

Ambition: go well beyond the minimum and beyond a single fall detector — cover every
behaviour that can be defined from tracks, pose and place, then show it as a product.

Ratings: **Feasibility** H / M / L with current tooling. **Measure** = how we would
produce the number we are allowed to quote (`angelseye.eval`).

---

## 1. What the problem statement requires (the floor)

Source: `PROBLEM_STATEMENT.md`, PSI07.

| Must | Notes |
|---|---|
| Detect people or objects | Scored: detection accuracy |
| Track the same entity across the video | Scored. Includes leaving and re-entering frame |
| Say what entities are *doing*, not just that they exist | A bare detection list fails |
| Tell normal from abnormal | Scored |
| Surface meaningful events, at the right time | Scored: event timing |
| Every abnormal flag names **which entity** and **when** | Hard rule. Our event record already enforces it |
| Statement's own minimum | One scenario, detect + track, normal vs **one** abnormal behaviour |
| "Advanced" tier | Multiple behaviour types, general anomaly detection |
| Submission | Working system, public repo + README, data pipeline, evidence (timestamps, confidence), sample in/out, scope note (MVP vs stretch), declared resources, live demo |

Everything below the line is our ambition, not a requirement, and the scope note must
say so.

---

## 2. Side A — behaviours by layer

Most behaviours are **rules over tracks**, not trained models. Thresholds live in
`config.yaml`; each needs staged clips plus ground truth to tune and measure.

### 2.1 Single track + zones (tracker only)

| Behaviour | Definition | Feas. | Needs | Measure |
|---|---|---|---|---|
| Loitering / standing still | Within radius r for T s | H | zones optional | start/end error, P/R |
| Prolonged stationary in a sensitive spot | Same, inside a drawn zone (gate, ATM, school entrance) | H | zone polygons | P/R |
| Wrong-way movement | Heading against the zone's flow | H | zone flow vectors | P/R |
| Restricted-zone entry / after-hours presence | Track inside zone outside allowed hours | H | zones + schedule | P/R |
| Sudden run | Speed jump above walking pace | H | homography for m/s (pixel fallback exists) | P/R, timing |
| Erratic path | High heading change rate, doubling back | M | tuning | P/R |
| Pacing / circling a location | Repeated passes of the same point | M | — | P/R |
| Abandoned object | Static object with no owner track nearby for T s | M | object detector beyond "person" | P/R |

### 2.2 Pose (single person)

| Behaviour | Definition | Feas. | Needs | Measure |
|---|---|---|---|---|
| Fall | Box tall→wide, hip drops fast, stays down | H | pose | P/R, timing |
| **Lying on the ground > 1 min** | Prone for T_long; distinguishes fall-and-recover from stay-down | H | pose + duration state | P/R, timing |
| Slumped / sitting on ground long | Low torso, no movement | M | pose | P/R |
| Hands raised / defensive posture | Wrists above head, arms crossed in front | M | pose | P/R |
| SOS / Signal for Help gesture | Hand-state sequence | M (range-limited) | hand crop upscaling; pass/fail test at 2/3/4 m (`TASKS` 1.9) | detection rate by distance |
| Distress pose (long-range backup) | Both arms raised and crossed | M | pose | P/R |
| Crouching / hiding | Low, still, near edge of frame | L–M | pose | P/R |

### 2.3 Two or more tracks

| Behaviour | Definition | Feas. | Needs | Measure |
|---|---|---|---|---|
| Following | Follower path matches leader path delayed 1–10 s | M | homography; track repair | P/R, timing |
| Walking together (anti-false-alarm) | Delay ~0 s, under 1.5 m | H | same | false-alarm rate |
| Approach and close in | Closing distance, converging headings | M | — | P/R |
| Blocking / cornering | Track stays between a person and their exit | L–M | scene geometry | P/R |
| Encirclement | 3+ tracks within 2.5 m, >180° coverage | M | — | P/R |
| Grab / drag / struggle | Rapid two-person contact, one pulled | L | pose + motion; VLM confirmation likely | P/R, small sample |
| Child separates from adult | Child-sized track leaves adult, no re-pair | M | height from homography (no face/gender) | P/R |
| Following a lone person at night | Following rule × empty street × dark | M | context layer | P/R |

### 2.4 Crowd

| Behaviour | Definition | Feas. | Needs | Measure |
|---|---|---|---|---|
| Counts / density per camera | People per zone, rolling | H | — | count error vs hand count |
| Sudden dispersal | Many tracks scatter fast | M | — | P/R |
| Crush / unsafe density | Density above threshold, low flow | M | — | P/R |
| Stationary pocket in a flowing crowd | Cluster static while rest moves | L–M | — | P/R |

### 2.5 Cross-camera

| Behaviour | Definition | Feas. | Needs | Measure |
|---|---|---|---|---|
| Re-entry on the same camera | Track lost then found again | H | track repair | ID-switch count |
| **Transit-time anomaly** ("never came out of the street") | Entered camera A, not seen at B within expected transit time, with no building/exit between | M | camera graph with expected travel times; re-ID | P/R on staged clips; false-alarm rate |
| Appearance search across cameras | Clothing/colour/height query ranked across cameras | M | embeddings per track; authority-only gate | top-k hit rate on MEVA |
| Predicted next camera | Adjacency graph + heading | H once graph exists | cameras.json | next-camera accuracy |

Rule for all of §2.5: apply to **any person**, never "women". No gender inference
(`PRODUCT.md`, D5). Women's safety decides which behaviours we prioritise and how we
word alerts, not who we classify.

Honest limits: re-ID without faces degrades with similar clothing, night and crowds.
It is probabilistic; report measured accuracy only.

### 2.6 Context and general anomaly

| Capability | Definition | Feas. | Needs | Measure |
|---|---|---|---|---|
| Time-of-day baselines | Learn normal activity per camera and hour | M | enough footage per camera | anomaly P/R vs staged events |
| Lone person on an empty street | People count = 1 (or low), dark | H | counts + brightness | P/R |
| General anomaly score | Deviation from baseline path/speed/dwell for this place and hour | M | baselines | AUC-style on staged vs normal |
| VLM second opinion | Keyframes of a candidate event → confirm/narrate | H | Gemini key; optional | agreement with ground truth; % frames sent |

General anomaly detection is the statement's "advanced" tier. Few teams will reach it.

### 2.7 Engine cross-cutting

| Item | Note |
|---|---|
| Night footage | Own night clips are required to claim anything about night (`DATA.md`) |
| Occlusion, ID switches | Measure ID switches per clip; track repair is the mitigation |
| Efficiency | Motion gate + cheap-first cascade; quote streams×fps and % to VLM from `angelseye.bench` only |
| Judge's own video | Pixel-space fallback must work with no calibration |

---

## 3. Side B — product features

Side B starts only after the Side A gate (`HACKATHON_PLAN.md` §8).

### 3.1 Mobile app, safety-first maps (alternative to a traditional maps app)

Build as a phone-first web app (PWA) unless a native app is justified later.

| Feature | Definition | Feas. | Data | Measure |
|---|---|---|---|---|
| Safest-route walking | Edge cost = length × (1 + deserted + dark + recent incident); fastest vs safest shown | H | OSM street graph (OSMnx), rolling counts, brightness, events | route stats: % of route on observed-busy/lit segments |
| **Prefer crowded streets** | Weight edges by observed rolling footfall so the route favours populated segments | H | rolling people counts per camera | same |
| Deserted-area check | Per-segment busy/deserted score | H where a camera sees the street | counts | — |
| Unknown-coverage handling | Segments with no camera get a labelled moderate penalty, never "safe" | H | — | — |
| Time-aware routing | Same street scored differently by hour | M | baselines per hour | — |
| Heatmap | Busy / deserted / dark layer | H | counts, brightness | — |
| Live-event overlay | Active alerts as pins, with severity | H | event store | — |
| Share-my-trip | The walker opts in; camera network corroborates ("passed cam 3 at 18:42, nothing flagged"); follower sees progress | M | consent flow, anonymous track link | — |
| Arrive-safe check-in / auto-escalate | No arrival by expected time → ping contact, then responder | H | trip + timer | — |
| SOS button | Phone sends location + nearest cameras' recent clips to responder | H | responder page | — |
| Suspicious-activity reporter | Crowd report with location, category, optional photo; rate-limited, moderated, shown as unverified | M | moderation; abuse controls | — |
| Tap a camera | Opens **blurred** recent frames or event clips; not a raw public live feed | M | blur pipeline | — |
| Guard / responder page | Alert + clip + map link on a phone | H | ntfy.sh or Telegram | — |
| Plain-English questions | "What happened near Gate 2 after 9 pm?" over the event store | M | Groq + SQL tools | — |

### 3.2 Amber (missing child)

Appearance search across cameras. Authority-only, case ID required, audit-logged
(D5). Details: `ARCHITECTURE.md`.

### 3.3 "A mother tracks her daughter" — two versions

| Version | What it is | Status |
|---|---|---|
| **Consented trip share** | The daughter opts in; the network corroborates her trip as above | In scope (3.1) |
| **Tracking someone by appearance, no consent** | Anonymous-ID tracking of a named person through cameras | **Out.** It is the surveillance D5 rules out; any claimant could use it on anyone |

### 3.4 Public sex-offender registry layer — OPEN DECISION

Idea: let a user see registered offenders in an area, to warn them.

Considerations recorded here so the team decides with the facts:

- **Source.** To my knowledge India's national database (NCRB) is restricted to law
  enforcement and is not public; some other countries run public registries
  (e.g. US state registries). **Verify before design.** Without an official public
  source, there is nothing legitimate to display.
- **Risks if shown to the public:** vigilantism; misidentification (same name, stale
  address); defamation claims; harm to people who have served their sentence; the app
  becoming the target of complaints. These land on the builders.
- **Hard constraints if it is ever built:** official public source only; show the
  official record unchanged with its date and source; never link a registry person to a
  live camera track or to anyone's appearance (that would be face-based identification,
  banned by D5); no photos pulled from anywhere else.
- **Lower-risk alternatives:** (a) area-level counts or an "official registry says N
  registered in this ward" note, with a link to the authority; (b) a police-side alert
  when a registered person enters a flagged zone, with human review and no public
  display; (c) skip it and put the effort into hotspot and incident data from our own
  events.
- **Recommendation:** do not include in the MVP or the live showcase. Decide
  alternatives (a)/(b)/(c) with the team; if (a) or (b) is chosen, it is a post-Side-A
  stretch.

---

## 4. Deployment and legal paths

This is planning guidance, not legal advice. Have a qualified person confirm before any
real-footage use.

| Path | Footage | What it takes |
|---|---|---|
| **Hackathon / own build** | Own staged clips of consenting teammates, MEVA, TfL JamCams | Nothing beyond what `DATA.md` already says. This is the plan |
| **Campus pilot** | Karunya's own cameras | Written permission from the institution, privacy notice, retention limit, access controls. Most realistic real-world step |
| **Government / police** | Their cameras | Procurement or an MoU; footage stays with them and we act as a vendor or partner. Public-facing Side B runs under their authorisation. Relevant programmes to look up: Smart City and Safe City (Nirbhaya Fund) |

Points that shape the design either way:
- Government exemptions under India's DPDP Act (2023) belong to the agency, not to a
  private team. We cannot use public CCTV without authorisation.
- Raw public live feeds aggregate people's movements; the app shows blurred frames and
  event clips.
- Each deployment needs retention, access control and audit by default — already in D5.

---

## 5. Pre-planning checklist (what to settle before building)

1. Promote items from §2 and §3 into scope, in dependency order, with a gate each.
   Record in `DECISIONS.md`.
2. For each promoted behaviour: the staged clip it needs (add to `DATA.md` shot list) and
   its ground-truth rows (`data/ground_truth.csv`).
3. Decide §3.4 (registry) and the deployment path (§4).
4. Resolve the open items in `STATE.md`.
5. Ask the organisers whether pre-clock code is allowed (`TASKS` 0.2).
