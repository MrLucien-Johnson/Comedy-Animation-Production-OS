"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys

from capos import __version__
from capos.core.schemas import COOKIE_LABEL_EXACT, WATERMARK_EXACT, FrameManifest
from capos.core.status import FrameType, StageStatus
from capos.domain.continuity import (
    build_frame_sequence,
    cookie_jar_episode2_plan,
    initial_kitchen_continuity,
)
from capos.domain.series import list_series, load_episode_brief, load_script, load_series
from capos.export.ffmpeg_export import ffmpeg_available
from capos.generation.registry import get_backend, health_all, try_register_optional_backends
from capos.prompts.compiler import PromptCompiler
from capos.qa.validators import assert_cookie_label_exact, assert_watermark_exact


def cmd_status(_: argparse.Namespace) -> int:
    try_register_optional_backends()
    series = list_series()
    ff_ok, ff_reason = ffmpeg_available()
    print(
        json.dumps(
            {
                "version": __version__,
                "series": series,
                "ffmpeg": {"available": ff_ok, "detail": ff_reason},
                "backends": health_all(),
                "watermark": WATERMARK_EXACT,
                "cookie_label": COOKIE_LABEL_EXACT,
                "engineering_readiness": "partial",
                "content_production_readiness": "not_claimed",
            },
            indent=2,
        )
    )
    return 0


def cmd_series_show(args: argparse.Namespace) -> int:
    cfg = load_series(args.series_id)
    print(cfg.model_dump_json(indent=2))
    return 0


def cmd_compile_e2(_: argparse.Namespace) -> int:
    """Compile prompts for Di Cookie Jar continuity sequence (metadata only)."""
    frames = []
    for i in range(1, 8):
        fid = f"s01e02_f{i:02d}"
        frames.append(
            FrameManifest(
                frame_id=fid,
                series_id="likkle-jay",
                season_id="s01",
                episode_id="s01e02",
                scene_id="kitchen-1",
                shot_id=f"shot-{i}",
                frame_type=FrameType.KEYFRAME,
                action=f"Episode 2 frame {i}",
                status=StageStatus.DRAFT,
            )
        )
    seq = build_frame_sequence(
        frames,
        initial=initial_kitchen_continuity(),
        changes_by_frame=cookie_jar_episode2_plan(),
    )
    compiler = PromptCompiler("likkle-jay")
    versions = []
    for fr in seq:
        payload = compiler.compile_frame(fr, persist=True)
        versions.append({"frame_id": fr.frame_id, "prompt_version": payload["prompt_version"]})
    print(json.dumps({"compiled": versions, "note": "Prompts only — no images claimed"}, indent=2))
    return 0


def cmd_validate_constants(_: argparse.Namespace) -> int:
    assert_watermark_exact(WATERMARK_EXACT)
    assert_cookie_label_exact(COOKIE_LABEL_EXACT)
    brief = load_episode_brief("likkle-jay", "s01e02")
    script = load_script("likkle-jay", "s01e02")
    print(
        json.dumps(
            {
                "watermark": WATERMARK_EXACT,
                "cookie_label": COOKIE_LABEL_EXACT,
                "episode": brief.title,
                "locked_lines": [line.text for line in script.lines if line.locked],
                "ok": True,
            },
            indent=2,
        )
    )
    return 0


def cmd_mock_generate(args: argparse.Namespace) -> int:
    backend = get_backend("mock")
    result = backend.generate_image(
        prompt=args.prompt or "mock frame",
        width=512,
        height=512,
        output_path=args.output,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "success": result.success,
                "output_path": str(result.output_path) if result.output_path else None,
                "backend": result.backend,
                "non_production": True,
                "error": result.error,
            },
            indent=2,
        )
    )
    return 0 if result.success else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capos", description="Comedy Animation Production OS")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="Show system status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("series", help="Show series config")
    p.add_argument("series_id")
    p.set_defaults(func=cmd_series_show)

    p = sub.add_parser("compile-e2", help="Compile Di Cookie Jar frame prompts")
    p.set_defaults(func=cmd_compile_e2)

    p = sub.add_parser("validate-constants", help="Validate watermark and cookie label")
    p.set_defaults(func=cmd_validate_constants)

    p = sub.add_parser("mock-generate", help="Generate a non-production mock image")
    p.add_argument("-o", "--output", default="assets/generations/mock.png")
    p.add_argument("--prompt", default="")
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=cmd_mock_generate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
