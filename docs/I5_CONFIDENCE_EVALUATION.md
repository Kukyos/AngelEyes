# I5 — checking activity confidence

`activity` events contain a confidence number supplied by the vision model. The
number is not yet known to equal the chance that the caption is correct. This work
adds an offline evaluator; it does **not** change alerts or claim calibration.

## Label and score a run

After running the engine with `--live` or `--describe`, create a review sheet:

```bash
python -m angelseye.eval_activity prepare runs/phone/events.json \
  --out runs/activity_labels.csv
```

The CSV contains only vision-model activity events. It excludes tracker-generated
"entered" and "left" events and behaviour alerts. For every row, inspect the
blurred keyframe **and the corresponding video moment**. Set `correct` to:

- `1` if the caption describes a visible action accurately;
- `0` if it is wrong, invented, or attributes an action to the wrong person;
- `?` if the footage cannot settle it.

Use at least two independent reviewers where possible and resolve disagreements
without looking at the confidence column. Label the whole chosen run, including
low-confidence and mundane examples; selecting only interesting captions biases the
result. Keep private footage and review sheets under `runs/` (gitignored).

Then score the completed sheet:

```bash
python -m angelseye.eval_activity score runs/phone/events.json \
  --labels runs/activity_labels.csv --out runs/activity_confidence.json
```

Multiple `events.json` paths may be passed, provided their parent run-directory names
are unique. The scorer rejects missing/unclear labels by default. Use
`--allow-incomplete` only for a **provisional** report; it records how many examples
were missing or unclear. Existing label sheets are never overwritten by `prepare`.

## What the report means

The JSON reports sample count, accuracy, mean confidence, Brier score, calibration
error, and accuracy versus mean confidence in five confidence ranges, overall and by
model. A calibrated `0.8` group would be correct about 80% of the time. A lower Brier
score is better; zero is perfect. Show counts with every range: a range with only a
few examples cannot support a strong conclusion.

This scores the **confidence stored in the final event**, the number currently shown
to users. When repeated descriptions are merged, the engine keeps the maximum
confidence for that event. The first keyframe may therefore predate that maximum.
This report must not be presented as raw per-call model calibration. A future
per-call study would need to record each reply with its exact input image.

## Completion gate

I5 remains partial until labelled examples include correct and incorrect captions,
several confidence ranges, and footage beyond the clips used to tune the prompt.
Only then decide whether the displayed number should remain informational, be
recalibrated, or be removed. Do not use it to trigger safety alerts based on a small
or selectively labelled sample.
