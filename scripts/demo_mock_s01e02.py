#!/usr/bin/env python3
"""Mock end-to-end demo for S01E02 — non-production art only."""

from __future__ import annotations

import json
from pathlib import Path

from capos.composition.text import apply_speech_bubble, apply_watermark, compose_cover_title
from capos.core.schemas import WATERMARK_EXACT
from capos.domain.series import load_script
from capos.generation.registry import get_backend
from capos.audio.interfaces import cues_from_script, write_srt, write_vtt


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "assets" / "generations" / "demo_s01e02"
    out_dir.mkdir(parents=True, exist_ok=True)
    backend = get_backend("mock")
    script = load_script("likkle-jay", "s01e02")
    dialogue_by_frame = {
        "s01e02_f02": "JUST ONE COOKIE...",
        "s01e02_f05": "LIKKLE JAY!",
        "s01e02_f07": "MI NEVA DO NUTTN!",
    }
    paths = []
    for i in range(1, 8):
        fid = f"s01e02_f{i:02d}"
        raw = out_dir / f"{fid}_raw.png"
        result = backend.generate_image(
            prompt=f"mock {fid}",
            width=512,
            height=512,
            output_path=raw,
            seed=i,
        )
        assert result.success and raw.is_file()
        step = raw
        if fid in dialogue_by_frame:
            bub = out_dir / f"{fid}_bubble.png"
            written = apply_speech_bubble(step, bub, dialogue=dialogue_by_frame[fid])
            assert written == dialogue_by_frame[fid]
            step = bub
        final = out_dir / f"{fid}.png"
        wm = apply_watermark(step, final)
        assert wm == WATERMARK_EXACT
        paths.append(str(final))

    cover_raw = out_dir / "cover_raw.png"
    backend.generate_image(prompt="cover", width=512, height=512, output_path=cover_raw, seed=99)
    cover = out_dir / "cover.png"
    compose_cover_title(
        cover_raw,
        cover,
        series_title="Likkle Jay",
        season_episode="Season 1, Episode 2",
        episode_title="Di Cookie Jar",
    )
    apply_watermark(cover, cover)

    cues = cues_from_script(script)
    write_srt(cues, out_dir / "episode.srt")
    write_vtt(cues, out_dir / "episode.vtt")

    manifest = {
        "episode_id": "s01e02",
        "non_production": True,
        "frames": paths,
        "cover": str(cover),
        "watermark": WATERMARK_EXACT,
        "note": "Mock demo only — not content-production ready",
    }
    (out_dir / "demo_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
