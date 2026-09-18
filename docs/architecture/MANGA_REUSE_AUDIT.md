# Manga Reuse Audit

**Source inspected:** `generatemanga` @ `origin/cursor/echo-inkwell-manga-studio-767c` (tip `9a8a580`)  
**Related branches (read-only):** `cursor/core-python-package-f1f0`, `cursor/story-content-bibles-e342`  
**Target:** `comedy-animation-production-os` (Comedy Animation Production OS / CAPOS)  
**Constraint:** Manga repository remains **READ ONLY**. Concepts are ported/adapted; no cross-repo runtime dependency.

**Classification legend**

| Label | Meaning |
|-------|---------|
| `REUSE_CONCEPT` | Keep the idea; rewrite for animation domain |
| `PORT_AND_ADAPT` | Port structure/logic; rename and generalize |
| `REIMPLEMENT` | Rebuild for animation (stills → frames/video) |
| `NOT_APPLICABLE` | Manga/print/story-specific; do not bring over |

---

## 1. Existing manga architecture

Echo of the Inkwell is a **local-first, human-gated, file-backed** Python production toolkit for a coloring-book manga volume.

**Stack:** Python ≥3.11, Pydantic v2, Pillow, Streamlit, reportlab (KDP PDF), optional Diffusers/HF, pytest, JSON configs on disk.

**Hierarchy:**

```
Project → Story pack → PagePlan → PageEntry → PanelPlan → GenerationRecord
```

**Pipeline:**

```
page-plan → PromptBuilder → GenerationBackend → generations/ + record
  → human review → approved/ | rejected/ → gates + preflight → KDP PDF
```

**Hard rules already encoded:** mock art labeled non-production; never silent overwrite of approved assets; export from approved only; secrets from env only; local models not auto-downloaded.

**Note:** `main` is an empty scaffold. Real architecture lives on the Echo studio branch above.

---

## 2. Components worth reusing

| Component | Path (manga) | Class |
|-----------|--------------|-------|
| Package/layout (`src/` + configs + series packs) | `src/echo/`, `config/`, asset folders | `REUSE_CONCEPT` |
| Core paths/config/state/errors/logging | `src/echo/core/*` | `PORT_AND_ADAPT` |
| Status enums + generation records | `src/echo/core/schemas.py` | `PORT_AND_ADAPT` |
| Character manager + bible/continuity/refs | `src/echo/characters/manager.py`, `characters/<slug>/` | `PORT_AND_ADAPT` |
| Layered prompt builder + prompt history | `src/echo/prompts/*` | `PORT_AND_ADAPT` |
| Generation backend ABC + registry + mock | `src/echo/generation/*` | `PORT_AND_ADAPT` |
| Approval workflow (no silent overwrite) | `src/echo/review/approval.py` | `PORT_AND_ADAPT` |
| Continuity checklist + production gates | `src/echo/continuity/*` | `REUSE_CONCEPT` |
| Image QA (exists/size/aspect/checksum) | `src/echo/qa/image_qa.py` | `PORT_AND_ADAPT` |
| Post-gen text overlay (never bake text) | `src/echo/composition/text_overlay.py` | `REUSE_CONCEPT` |
| Provenance: UUID records, `parent_id`, prompt snapshots | `generation/metadata.py`, `prompts/history.py` | `PORT_AND_ADAPT` |
| Operator CLI + status scripts | `scripts/*` | `PORT_AND_ADAPT` |
| Docs + mock-first pytest conventions | `docs/`, `tests/` | `PORT_AND_ADAPT` |
| Git automation (no auto-push / no `.env`) | `src/echo/git/automation.py` | `PORT_AND_ADAPT` |

---

## 3. Components that should NOT be reused

| Component | Why | Class |
|-----------|-----|-------|
| KDP PDF / bleed / blank reverse pages | Print coloring-book deliverable | `NOT_APPLICABLE` |
| Panel grid compositor | Manga page layout ≠ shot/frame timeline | `NOT_APPLICABLE` |
| `PhysicalPageMapper` story≠print mapping | Print-specific | `NOT_APPLICABLE` |
| Echo story content (Kaito, inkwell, school) | Different IP | `NOT_APPLICABLE` |
| Hard-coded `KAITO_REFERENCE_APPROVED` gate name | Project-specific; make data-driven | `REIMPLEMENT` |
| Streamlit “Manga Production Studio” chrome | Wrong product UX | `REIMPLEMENT` |
| Coloring-book style negatives / B&W line art | Wrong visual system | `REIMPLEMENT` |
| Dual page-id schemes (`p1` vs `page_01`) | Known footgun — unify early | `REIMPLEMENT` |

---

## 4. Manga-specific assumptions

- Output is a **print PDF** (8.5×11 + bleed), not video.
- Domain unit is **page/panel**, not episode/shot/frame.
- Visual style is **B&W manga line art / coloring book**.
- Text balloons often leave empty space for post-overlay; coloring rules forbid screentones.
- Production gate is named after a single protagonist (`KAITO_*`).
- Locations/objects lack a first-class manager (characters only).
- No animation, audio, subtitles, aspect-ratio reframing, or season workflow.
- No distributed job queue — sync CLI/UI + optional Colab file exchange.

---

## 5. Generic components

These are product-agnostic production patterns:

1. Local-first human approval before release  
2. Pluggable generation backends + mock for CI  
3. Layered prompts from style + entity locks + scene card  
4. Asset folders with bible / continuity / reference slots  
5. Reference status machine + hard production gates  
6. GenerationRecord provenance + prompt history + parent chain  
7. Continuity checklist as review gate  
8. Secrets only from environment; redacted logs  
9. Metadata in git; binaries out (or LFS later)  
10. Phased maturity model (refs → pilot → volume)

---

## 6. Image-generation architecture

**Interface:** `GenerationBackend` + `GenerationResult` (`backend.py`)  
**Registry:** `get_backend` / `list_backends` (`registry.py`)

| Backend | Behavior | CAPOS class |
|---------|----------|-------------|
| `mock` | Deterministic Pillow PNG; always available | `PORT_AND_ADAPT` |
| `local` | Probes path; real Diffusers largely stubbed | `REIMPLEMENT` |
| `huggingface` | `InferenceClient.text_to_image`; `HF_TOKEN` only | `PORT_AND_ADAPT` |
| `colab` | Outbound job JSON / inbound PNG | `REUSE_CONCEPT` |

Capabilities advertised: seed, negative prompt, reference images, health check, regenerate.

**CAPOS extension required:** `editImage`, `generateVariation`, `inpaint`, `outpaint`, reference-locked edits — manga ABC is generate-centric.

---

## 7. Prompt architecture

`PromptBuilder` layers:

1. Master visual style  
2. Medium-specific rules (coloring book)  
3. Character bible + continuity  
4. Objects + location bibles  
5. Page/panel scene card (action, emotion, camera)  
6. Continuity reminder + reference status  
7. Negative constraints  

Snapshots saved under `prompts/<page_id>/<UTC>_<hex>.json` + `latest.json`.

**CAPOS:** `PORT_AND_ADAPT` as a **Prompt Compiler** with versioned packs: base style + character locks + location + props + episode state + frame action + camera + continuity + negatives. Style content = `REIMPLEMENT`.

---

## 8. Asset / reference architecture

```
characters/<slug>/{character-bible.json,continuity.json,references/}
locations/<slug>/{location-bible.json,continuity.json,references/}
objects/<slug>/{object-bible.json,continuity.json,references/}
```

Reference slots carry status: `MISSING | GENERATED | APPROVED | LOCKED`.  
Kaito uses eight slots (front, 3/4, side, back, full-body, expressions, hands, jacket-detail).

**CAPOS:** Expand to series/character/turnaround/expression/outfit/location/prop/episode/scene/shot references with **canonical versioned asset IDs** (`character-likkle-jay-v1`). Class: `PORT_AND_ADAPT` + stronger versioning (`REIMPLEMENT` for immutable version bumps).

---

## 9. Generation queues / jobs

No Redis/Celery/DB queue. Synchronous CLI/Streamlit; Colab is a file-drop worker.

Records: `generations/<uuid>/record.json` + `generations/_by_page/<page_id>/<uuid>.json`.

**CAPOS:** Keep file-backed job records initially (`PORT_AND_ADAPT`); design interfaces so a real queue can be added later without rewriting domain logic (`REUSE_CONCEPT`).

---

## 10. Review / approval architecture

`ApprovalWorkflow`: `GENERATED → APPROVED | REJECTED`; `LOCKED` protected.  
Approve copies into `approved/` without silent overwrite (`force` or uniquified name).  
Streamlit review: approve (with checklist), regenerate, variations, edit prompt, reject, compare.

**CAPOS:** `PORT_AND_ADAPT` FSM; extend statuses to pipeline stages (`DRAFT`, `QA_FAILED`, `QA_PASSED`, `REQUIRES_REVIEW`, `SUPERSEDED`, `EXPORTED`). UI = `REIMPLEMENT`.

---

## 11. Validation / QA

- File/image checks: exists, corrupt, dimensions, aspect, alpha, SHA-256 dupes  
- Print validator + preflight → `PDF_READY`  
- Human continuity checklist (14 items)

**CAPOS:** Port file checks; replace print with animation validators (`DIMENSION`, `ASPECT_RATIO`, `REFERENCE`, `CHARACTER`, `OUTFIT`, `PROP_*`, `BACKGROUND`, `TEXT`, `WATERMARK`, `SEQUENCE`, `FILE`). Visual similarity interfaces must report `NOT_CHECKED` when CV unavailable — never fake PASS.

---

## 12. Export / render architecture

Manga: panel paste → page compositor → reportlab KDP PDF from approved art only.

**CAPOS:** `NOT_APPLICABLE` for PDF path. `REIMPLEMENT` FFmpeg assembly, multi-aspect reframe (1:1, 9:16, 16:9, 4:5), covers/thumbnails, subtitle mux. Keep **approved-only / QA-pass-or-override** gate idea (`REUSE_CONCEPT`).

---

## 13. Storage architecture

| Class | Manga | CAPOS plan |
|-------|-------|------------|
| Code + JSON manifests | tracked | same |
| Generation binaries | gitignored | same |
| Approved art | ignored by default | same + versioned canonical refs |
| Models / caches | never git | same |
| Runtime state | gitignored | same |

Docs recommend LFS/object storage for large binaries later.

---

## 14. Metadata / provenance architecture

Every attempt: UUID, prompts, seed, backend, model, settings, timestamps, optional `parent_id`.  
Reference slots store `generation_record_id`, timestamps.  
Model licensing report template exists.

**CAPOS:** Extend records with series/season/episode/scene/shot/frame ids, frame type, continuity links, checksum, qaStatus, humanApproval — `PORT_AND_ADAPT`.

---

## 15. UI architecture

Single Streamlit app (`app.py`): Dashboard, Review, Story Editor, Continuity/References, Preflight.

**CAPOS:** `REIMPLEMENT` production dashboard for series/seasons/episodes/script/storyboard/refs/frames/continuity/QA/animation/audio/exports with clear status visibility.

---

## 16. Tests

Pytest with tmp project root + `ECHO_MOCK_GENERATION=1`. Coverage: schemas, prompts, approval transitions, gates, metadata, secrets, missing assets, PDF dimensions.

**CAPOS:** `PORT_AND_ADAPT` fixture pattern. Add tests for continuity inheritance, canonical versioning, watermark exactness `MRLUCIENJOHNSON`, dialogue exactness, prop label `COOKIES`≠`COOKIE`, export prerequisites, QA fail-closed, episode state transitions.

---

## 17. Documentation conventions

Operator-facing Markdown under `docs/` (architecture, generation, continuity, phases, troubleshooting) + honesty templates in `reports/` (“engineering complete ≠ content complete”).

**CAPOS:** Follow the same honesty rule. Required docs listed in IMPLEMENTATION_PLAN.

---

## Domain translation

| Manga | Comedy Animation |
|-------|------------------|
| Project | Series |
| Chapter (label) | Season |
| Page | Episode beat / Scene |
| Panel | Shot |
| Generated still | Frame (`MASTER_REFERENCE`, `KEYFRAME`, `TRANSITION`, `DIALOGUE`, `REACTION`, `ESTABLISHING`, `COVER`, `THUMBNAIL`) |
| Object bible | Prop master (+ state machine) |
| KDP PDF | Final MP4 (+ covers) |

---

## Risks when porting

1. Dual ID conventions in manga — **do not repeat**; one canonical ID scheme.  
2. Hard-coded protagonist gates — use registry/config.  
3. Local diffusion incomplete — never claim generation success without files.  
4. No queue — acceptable for v1 file-backed jobs; design for growth.  
5. Manager asymmetry (characters only) — give locations/props first-class managers.  
6. Echo branch is engineering-ready, book-production incomplete — CAPOS must similarly separate **engineering readiness** from **content-production readiness**.
