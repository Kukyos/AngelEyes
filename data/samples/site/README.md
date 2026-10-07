# MEVA site snapshot

Engine output for the 9 MEVA cameras (2018-03-07 11:00 slot), without the videos: `events.json`,
`tracks.jsonl` and blurred `keyframes/` per camera. Lets the screens run without a GPU; see the
README → "Screens only".

Source footage: MEVA dataset, Kitware/IARPA DIVA, mevadata.org (CC-BY-4.0).

Regenerate after re-running the engine on the site cameras:

```bash
for d in runs/G*; do n=$(basename $d); rm -rf data/samples/site/$n; mkdir -p data/samples/site/$n
  cp -r $d/events.json $d/tracks.jsonl $d/keyframes data/samples/site/$n/; done
```
