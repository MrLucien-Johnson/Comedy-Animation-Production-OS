# Architecture

CAPOS is a **local-first, human-gated, file-backed** production OS for illustrated comedy animation series.

## Hierarchy

```
Series → Season → Episode → Scene → Shot → Frame
```

Frame types: `MASTER_REFERENCE`, `KEYFRAME`, `TRANSITION`, `DIALOGUE`, `REACTION`, `ESTABLISHING`, `COVER`, `THUMBNAIL`.

## Package map (`src/capos/`)

| Module | Role |
|--------|------|
| `core` | Status enums, schemas, paths, config, errors |
| `domain` | Series loaders, continuity engine |
| `references` | Canonical versioned asset store |
| `prompts` | Prompt compiler + style locks |
| `generation` | Provider ABC, mock/HF/null backends, records |
| `qa` | Fail-closed validators |
| `composition` | Watermark, speech bubbles, covers |
| `animation` | Simple motion plans |
| `audio` | Voice/music/SFX interfaces + SRT/VTT |
| `export` | FFmpeg assembly + reframe metadata |
| `review` | Approval / lock-as-canon |
| `comedy` | Setup→punchline structure |
| `pipeline` | Stage workflow + export gates |

## Data flow

```
Series Bible + Episode Brief
  → Script (locked dialogue)
  → Storyboard
  → Continuity plan (inherit unless changed)
  → Reference resolution (canonical asset IDs)
  → Prompt compiler
  → Generation backend (prefer reference edit)
  → Frame QA (fail closed)
  → Text compositing (dialogue + watermark)
  → Animation plan → FFmpeg export
  → Human approval → publishable export
```

## Independence

No runtime dependency on the manga repository. Concepts were audited in `docs/architecture/MANGA_REUSE_AUDIT.md` and adapted here.
