# Continuity Engine

Independent image generation caused visual drift (hair, props, kitchen geometry, wardrobe, watermarks). CAPOS does **not** solve this with longer prompts alone.

## Reference-locked architecture

Each generated frame declares governing references:

- Series / character / turnaround / expression / outfit  
- Location master / prop master  
- Episode / scene / shot references  

## Inheritance

`ContinuityState.inherit()` copies location, camera, characters, props, lighting into the next frame.  
Dialogue does **not** auto-carry. Script-declared changes apply via `apply_explicit_changes`.

Identity locks (canonical asset IDs, hair locks) cannot be silently rewritten.

## Episode 2 — Di Cookie Jar

Frames 1–2: cookie jar `CLOSED`  
Frames 3+: `OPEN` with lid beside jar  
Frame 3 is the OPEN-state visual master until a reference image replaces/augments metadata.

## Manifest

Each episode writes `continuity.json` listing per-frame continuity, previous/next links, and statuses.
