# Engineering vs Content Readiness

## Three gates (keep separate)

| Gate | Meaning | Current |
|------|---------|---------|
| **ENGINEERING COMPLETE** | Code, schemas, workflows, tests | **YES** (Phase 1 activation) |
| **CONTENT PRODUCTION READY** | Approved canonical **images** exist | **NO** |
| **SEASON PRODUCTION READY** | Minimum canon APPROVED + real provider + golden refs | **NO** (fail-closed) |

## Engineering readiness

| Area | Status |
|------|--------|
| Domain schemas / hierarchy | Ready |
| Canonical asset types + CanonStatus lifecycle | Ready |
| Turnaround / expression / prop-state registry | Ready (metadata; REFERENCE_REQUIRED) |
| Scale system (Jay height = 1.0) | Ready |
| Spatial regions (e.g. LEFT_COUNTER) | Ready |
| Golden frame + REFERENCE_REQUIRED workflow | Ready |
| Provider availability dashboard states | Ready |
| Deterministic text masters | Ready |
| Visual QA (aHash → REVIEW_REQUIRED only) | Ready |
| SEASON_PRODUCTION_READY gate | Ready (correctly FAILs) |
| Production UI Canon / Golden / Readiness | Ready |
| Tests | 34 passed |

## Content-production readiness

| Area | Status |
|------|--------|
| Approved canonical reference **images** | **Not ready** — no production image files |
| Likkle Jay / Auntie Bev turnarounds on disk | **Not ready** |
| Location masters on disk | **Not ready** |
| Cookie jar state masters on disk | **Not ready** |
| S01E02 F3 open-jar golden image | **REFERENCE_REQUIRED** — awaiting user upload |
| Human-approved episode frames | **Not ready** |
| Real provider generations | **Not claimed** — mock AVAILABLE; HF NOT_CONFIGURED without token |

## Remaining blockers for SEASON_PRODUCTION_READY

1. Generate or import approved images for all required masters/turnarounds  
2. Approve + lock those assets (APPROVE requires a real file)  
3. Upload S01E02 Frame 3 open-cookie-jar golden reference  
4. Configure a real image provider (e.g. `HF_TOKEN`) — mock alone is insufficient  
5. Only then recommend automated season production  

Mock demo frames remain **non-production**.
