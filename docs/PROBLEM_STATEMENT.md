# Problem statement and rules

Transcribed from the HackNex 2026 Internal Qualifier booklet (Division of
Computer Science and Engineering, Karunya Institute of Technology and Sciences).
The PDF is in `materials/` (gitignored). Tracks named on the cover: Generative AI ·
Computer Vision · Agentic AI · Applied ML.

---

## HNX26PSI07: Autonomous Vision & Behaviour Understanding

*Computer Vision · Action Recognition · Object Tracking · Behaviour Analysis*

### What you're building
Finding objects in video is easy — understanding what they're doing is hard. Build a
vision system that finds people or objects, tracks them (knows it's the same one
even if it moves), and understands their behavior. Spot if behavior is normal or
unusual, and surface meaningful events (not just "there's a person").

Pick a scenario: workplace safety, retail, factory, campus, traffic, or crowds.

*Example:* A person walking around a warehouse is normal. A person standing still in
one spot for 10 minutes is unusual.

### Key rules
- Can't just list detections. Must explain what they're doing, not just that they exist.
- Every flag for unusual behavior must point to which entity and when.
  "Something weird happened" doesn't count — say who and when.

### How you'll be judged
- Can it recognize what people/objects are doing?
- Does it spot meaningful events?
- Can it tell normal from abnormal behavior?
- Does it track the same object across the video?
- Does it find objects accurately?
- Are events detected at the right time?

### What to build first
- Collect videos for your chosen scenario
- Detect and track objects, classify normal vs one abnormal behavior
- Advanced: Handle multiple behavior types, general anomaly detection

**Our scenario:** campus and street safety, with a women's and children's safety focus.

---

## Submission guidelines (apply to every statement)

Your submission must demonstrate a working solution and clearly explain how it was built.

- **Working System** – A functional solution that addresses the chosen problem.
- **Source Code** – A Git repository containing the complete source code and a clear
  README with instructions to set up and run the system end-to-end.
- **Data Pipeline** – A clear demonstration of how input data is collected, processed,
  and passed through your system.
- **Core Model / Reasoning** – The central logic, model, or reasoning mechanism that
  powers your solution.
- **Evidence & Explanation** – Supporting evidence that demonstrates how your system
  works, such as citations, timestamps, confidence scores, intermediate outputs, or
  relevant code.
- **Sample Input & Output** – At least one representative example showing the system
  working from input to output.
- **Scope Note** – Clearly distinguish the minimum viable solution you implemented from
  any additional stretch goals or features you attempted.
- **Live Demonstration** – Demonstrate the working system during evaluation. A recorded
  demonstration may be used where permitted.

## How to submit

Submit through a **public** Git repository. The README must explain:
- What the project does
- Technologies, libraries, and models used
- How to install dependencies
- How to configure and run the system
- How to reproduce the demonstrated results

The submission counts towards participation — submit the link by the end of your
evaluation. A presentation (PPT) is not necessary.

**Submission link:** https://forms.gle/KGjkU5u66Va1MDhu5

## Rules and instructions

- **Preparation is allowed:** problem statements are shared in advance. Teams may use
  this time to understand the problem, research technologies, plan their approach, and
  prepare their development environment.
- **AI usage:** AI tools are permitted, provided teams review, understand, and take
  responsibility for their submitted work.
- **Declare your resources:** mention any external APIs, datasets, pre-trained models,
  open-source components, or other significant resources used. (Ours: `RESOURCES.md`.)
- **Demonstrate your work:** be able to explain the approach, demonstrate the working
  system, and answer questions about the implementation.
- **Evaluation integrity:** work independently; no attempts to access or manipulate
  evaluation data or hidden test cases.
- **Team conduct:** respectful and collaborative environment.
- **Organizer's decision** on qualification and judging is final.

---

## The other nine statements (for reference)

Summaries and why we passed on each are in `DECISIONS.md` D1.

| ID | Title |
|---|---|
| PSI01 | Multimodal Document Intelligence |
| PSI02 | Video Understanding & Temporal Reasoning |
| PSI03 | AI-Powered Cyber Threat Intelligence |
| PSI04 | Real-Time Financial Fraud Intelligence |
| PSI05 | Multimodal Medical Image Intelligence |
| PSI06 | Generative Computer Vision & Scene Reconstruction |
| PSI08 | Proof-Carrying Data Analyst (Agentic GenAI) |
| PSI09 | AI Software Engineering Agent |
| PSI10 | Multimodal Deepfake & Digital Forensics |
