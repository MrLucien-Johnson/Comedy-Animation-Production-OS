# Implementation Plan — Comedy Animation Production OS

## Goal

Build an independent, production-ready **Comedy Animation Production OS (CAPOS)** for recurring illustrated comedy sketch series. First series configuration: **Likkle Jay**. Core engine must remain series-agnostic.

Engineering readiness ≠ content-production readiness. Both are reported separately.

---

## What will be reused (from manga — concepts only)

See `docs/architecture/MANGA_REUSE_AUDIT.md`.

- Local-first human approval before release  
- Pluggable generation backends + mock for CI  
- Layered / compiled prompts with versioned history  
- Bible + continuity + reference-slot packs  
- GenerationRecord provenance + parent chain  
- Fail-closed gates; approved-only export  
- Metadata-in-git / binaries-out storage  
- Operator CLI + pytest mock-first conventions  

**No runtime dependency on the manga working tree.**

---

## What will be adapted

| Manga piece | CAPOS adaptation |
|-------------|------------------|
| `echo.core` | `capos.core` — paths, config, errors, logging |
| `ArtStatus` | Expanded pipeline `StageStatus` |
| `GenerationRecord` | Frame-aware `GenerationRecord` + `FrameManifest` |
| `CharacterManager` | Unified `ReferenceStore` for characters/locations/props |
| `PromptBuilder` | `PromptCompiler` with lock layers |
| `ApprovalWorkflow` | Same FSM + lock-as-canon / supersede |
| Image QA | Animation continuity validators |
| Streamlit chrome | Production OS dashboard |
| Post-gen text | Speech bubbles, titles, **exact watermark** |

---

## What will be newly built

1. Domain: Series → Season → Episode → Scene → Shot → Frame  
2. Frame types + continuity inheritance engine  
3. Canonical versioned asset IDs (never silent overwrite)  
4. Likkle Jay Series Bible + episode seeds (incl. Di Cookie Jar)  
5. Comedy structure engine + engagement checks  
6. Provider ABC with edit/variation/inpaint/outpaint hooks  
7. Deterministic watermark + dialogue compositing  
8. Animation plan + FFmpeg export + reframe metadata  
9. Audio/subtitle provider-neutral interfaces  
10. Season production workflow with stage statuses  
11. Full documentation set  

---

## Repository structure

```
comedy-animation-production-os/
  README.md
  pyproject.toml
  requirements.txt
  .env.example
  .gitignore
  config/                 # project, generation, export, gates
  src/capos/              # installable package
    core/ domain/ references/ prompts/
    generation/ qa/ composition/ animation/
    audio/ export/ review/ comedy/ pipeline/
  series/likkle-jay/      # first series configuration
  scripts/                # operator CLIs
  app.py                  # production UI
  tests/
  docs/
  assets/                 # generations, approved, rejected, exports (gitignored binaries)
```

---

## Dependencies

**Runtime:** pydantic≥2.6, Pillow, streamlit, python-dotenv, PyYAML, GitPython  
**Export:** system `ffmpeg` (already present in environment)  
**Optional:** huggingface_hub, diffusers/torch (not required for mock CI)  
**Dev:** pytest, ruff (lint)

No paid provider assumed. Mock backend always available for tests.

---

## Phases

| Phase | Deliverable | Exit criteria |
|-------|-------------|-----------------|
| 0 | Reuse audit + this plan | Docs committed |
| 1 | Core schemas / domain model | Schema tests pass |
| 2 | Likkle Jay Series Bible | Machine + human bible present |
| 3 | Canonical reference system | Versioning tests pass |
| 4 | Episode / script / storyboard | Episode 2 seed + schema |
| 5 | Continuity engine | Inheritance tests pass |
| 6 | Prompt compiler | Prompt version tests pass |
| 7 | Generation provider abstraction | Mock generate; availability honest |
| 8 | QA validators | Fail-closed + watermark/dialogue tests |
| 9 | Production UI | Streamlit dashboard runs |
| 10 | Animation / video assembly | FFmpeg plan + reframe metadata |
| 11 | Audio / subtitles | Interfaces + SRT/VTT from script |
| 12 | Season production workflow | Stage status machine |
| 13 | End-to-end validation | lint, typecheck, tests, build |

---

## Phases (execution order)

0. Audit + architecture docs + package skeleton  
1. Core schemas / domain model  
2. Series Bible + references + continuity + prompts  
3. Providers + QA + export + Streamlit  
4. Phase 1 — canonical production activation  
5. Phase 2 — canon creation & approval pipeline  
6. **Phase 2A — local ComfyUI / LOW_VRAM_6GB activation** (this track)  
7. Human style selection → character/location/prop masters (gated)  
8. Season production only after SEASON_PRODUCTION_READY  

See `docs/PHASE2A_COMFYUI_LOW_VRAM.md`, `docs/COMFYUI_LOCAL_SETUP.md`, `docs/MODEL_SELECTION.md`.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Visual continuity drift from full regen | Reference-locked edit path; continuity manifests; QA fail-closed |
| Image models rewrite dialogue/watermark | Deterministic post-compositing; never bake text when avoidable |
| Fake capability claims | Mock labeled; `NOT_CHECKED` when CV absent; no placeholder-as-production |
| Provider refusals | Log refusal; revise wording without changing story intent; never weaken safety |
| Scope explosion (full animation) | Simple animation plan first; richer motion later |
| Manga dual-ID footgun | Single ID scheme from day one |

---

## Testing strategy

- Unit: schemas, status transitions, continuity inheritance, prompt compile, watermark string, dialogue lock, prop label `COOKIES`  
- Integration: mock generation → QA → approval → export prerequisite gate  
- Negative: QA fail blocks export without human override  
- CI: mock-only; no network generation required  

---

## Definition of done (engineering)

- [ ] Package installable (`pip install -e .`)  
- [ ] Docs listed in master prompt present  
- [ ] Likkle Jay series config loadable  
- [ ] Continuity engine inherits state unless script changes it  
- [ ] Canonical assets versioned; no silent overwrite  
- [ ] Prompt compiler produces versioned snapshots  
- [ ] Provider registry reports real availability  
- [ ] QA fail-closed on export  
- [ ] Watermark compositor emits exactly `MRLUCIENJOHNSON`  
- [ ] Dialogue compositor preserves locked text  
- [ ] Production UI shows series/episode/frame statuses  
- [ ] `pytest` green; lint clean; build succeeds  
- [ ] Engineering vs content readiness reported separately  

**Content-production readiness** additionally requires real approved canonical reference images and human-approved episode frames — not claimed until they exist.
