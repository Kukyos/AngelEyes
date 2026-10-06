# Angel's Eye — the product

Angel's Eye turns ordinary CCTV into a safety network. It tracks every person,
understands what they are doing, and flags **who** did **what** and **when** —
with evidence. It answers PSI07, then uses the same data to protect women and
find missing children.

## Where the idea came from (team's own words, kept)

- Build on the "God's Eye" idea (`bilawalsidhu/gods-eye-view`, a viral open-source
  3D-globe "spy satellite" console) and link it to PSI07, with a women's safety twist.
- "The main thing I want to abuse is the fact that we get data" — CCTV footage. The
  detection engine produces tracks, activities and crowd counts; the product is
  what we build on top of that data.
- An "amber alert": find a child across a series of street CCTV cameras (mock footage,
  for legality).
- Path planning for women's safety: show crowded vs deserted spots and route around them.
- "The detection of activity from footage is all they asked, and we have to achieve
  it efficiently." Side A must be excellent and fast; Side B is what wins overall.
- Hard is fine. The bar: judges asking "how did you even build that".

## Two sides

**Side A — the scored core.** An efficient perception and behaviour engine.
Footage in; timestamped behaviour events with evidence out. Must be excellent and
measured. Details: `ARCHITECTURE.md`.

**Side B — the wow.** Built only on Side A's output (tracks, events, crowd counts):
- a 3D campus globe with live people dots, camera cones and alerts
- **Amber alert** — appearance search across cameras for a missing child
- **SafeWalk** — routing that avoids deserted and dark streets
- a responder page on a guard's phone

## Why it can win overall (one winner from ~400 teams)

- It hits every PSI07 rubric line — actions, events, normal vs abnormal, tracking,
  timing — with measured numbers, not claims.
- Other teams will stop at boxes on a video. We turn detections into a live safety
  product on a globe.
- It is usable now: phones or existing CCTV as cameras, one laptop as the brain, a
  guard's phone as the responder.

## Scope note (goes into the README)

- **MVP:** Side A end to end (footage in → people tracked → five behaviours → events
  with who/when/evidence → stored), plus the globe showing cameras, people dots, alerts
  and fly-to, plus the responder page and the upload-a-video mode.
- **Stretch, in order:** amber alert → SafeWalk → Gemini confirmation and narration →
  plain-English questions over events → encirclement behaviour.

## What we show the judges

We show the working system live at the table, in this order. Every feature we build
is one of these steps; anything not on this list is cut or stretch. No video, no
scripted lines.

1. **Globe with live cameras.** Campus map, camera cones, and live people dots from the feeds.
2. **SOS gesture, live.** A teammate makes the Signal for Help sign at a phone camera.
   The alert shows track ID, time, confidence and evidence; the globe flies there; the
   responder phone receives it.
3. **Following vs walking together.** Run the recorded following clip, then the
   side-by-side clip. Only the first triggers, with both paths drawn.
4. **The judge's own video.** Upload any clip; get an events JSON and an annotated video back.
5. **Amber alert (stretch 1).** Case ID, then a clothing description, then sightings
   across cameras with times, the path, and the predicted next camera. Audit log visible.
6. **SafeWalk (stretch 2).** Fastest vs safest route, with deserted and dark stretches highlighted.
7. **The numbers.** Streams × fps on one laptop, % of frames sent to the vision model,
   precision / recall / start-time error on annotated clips, false alarms on normal clips.
8. **Privacy, when asked.** See below.

## Privacy and guardrails

Judges will ask "isn't this mass surveillance?" The answer is built into the system,
not added at the end.

- **No face recognition, ever.** Identity is an anonymous track ID; amber search matches
  clothing, colours and estimated height.
- **No gender inference.** The threats we flag (following, SOS, falls, running,
  loitering) are behaviours, not genders. Women's safety shapes which behaviours we
  prioritise, not who we classify.
- **Faces blurred** on every frame that leaves the engine, including clips and the globe.
- **Rolling buffer.** Raw footage is discarded; only event clips (~5 s either side) are kept.
- **Amber alert is authority-only.** It needs a case ID, and every search is written to
  an audit log shown in the UI. This blocks "anyone claiming to be a parent" from
  tracking a person across a city. (Upstream gods-eye-view's own responsible-use note
  excludes tracking individuals — expect a judge to raise it.)
- **SafeWalk uses aggregates only:** people counts and brightness per street, never
  individual tracks.
- **Mock footage only,** of consenting teammates. No bystanders, because the repo and
  sample data are public.
