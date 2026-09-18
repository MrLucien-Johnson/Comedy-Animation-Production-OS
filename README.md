# Comedy Animation Production OS (CAPOS)

Production system for recurring illustrated comedy sketch series.

**First series configuration:** Likkle Jay  
**Core engine:** series-agnostic (Series → Season → Episode → Scene → Shot → Frame)

## Status

| Track | Status |
|-------|--------|
| Engineering readiness | In progress — see phases in `docs/IMPLEMENTATION_PLAN.md` |
| Content-production readiness | Not claimed — canonical reference *images* and approved episode frames must exist and pass QA |

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
streamlit run app.py
```

## Repository layout

- `src/capos/` — core engine
- `series/` — series configurations (Likkle Jay first)
- `config/` — project / generation / export / gates
- `docs/` — architecture and operator docs
- `scripts/` — CLI operators
- `tests/` — automated tests
- `assets/` — generations, approved, rejected, exports (binaries gitignored)

## Honesty rules

- Do not claim an image was generated unless a file exists.
- Do not claim continuity was checked unless a validator or human ran.
- Do not claim animation was rendered unless an output exists.
- Placeholder files are never production assets.

## Manga reference

Architecture ideas were audited from the separate GenerateManga / Echo studio work.
That repository is **read-only** for this project. See `docs/architecture/MANGA_REUSE_AUDIT.md`.

## License

MIT
