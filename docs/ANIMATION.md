# Animation

Goal: **simple animation** suitable for short-form comedy, not expensive full frame-by-frame first.

## Supported motion cues

Camera pan, slow zoom, parallax, character translation, blink, mouth movement, head movement, arm movement, prop movement, reaction poses, transition frames, holds.

See `src/capos/animation/plan.py` (`AnimationPlan`, `MotionCue`).

Architecture allows richer animation later. Do not claim a render exists unless an output file is present.
