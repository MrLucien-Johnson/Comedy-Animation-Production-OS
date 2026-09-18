"""Prompt compiler — versioned layered prompt assembly."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from capos.core.paths import prompts_dir, series_dir
from capos.core.schemas import FrameManifest
from capos.prompts.style import (
    BASE_STYLE,
    FAMILY_FRIENDLY,
    NEGATIVE_CONSTRAINTS,
    NO_BAKED_TEXT,
)
from capos.scale.system import compile_scale_prompt_block, load_scale
from capos.spatial.layout import compile_spatial_prompt_block, load_location_space


class PromptCompiler:
    """Assemble BASE STYLE + locks + episode state + frame action + negatives."""

    def __init__(self, series_id: str, *, root: Path | None = None) -> None:
        self.series_id = series_id
        self.root = root
        self.series_path = series_dir(series_id, root=root)

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _character_lock(self, character_id: str) -> str:
        path = self.series_path / "characters" / character_id / "character.json"
        data = self._read_json(path)
        if not data:
            return f"CHARACTER: {character_id}"
        locks = data.get("continuity_locks", {})
        parts = [
            f"CHARACTER LOCK: {data.get('display_name', character_id)}",
            data.get("description", ""),
            f"Hair lock (HARD): {locks.get('hair', data.get('hair', ''))}",
            f"Wardrobe: {locks.get('wardrobe', data.get('wardrobe', ''))}",
            f"Must remain constant: {', '.join(data.get('must_remain_constant', []))}",
            f"Prohibited: {', '.join(data.get('prohibited_variations', []))}",
        ]
        return "\n".join(p for p in parts if p)

    def _location_lock(self, location_id: str | None) -> str:
        if not location_id:
            return ""
        path = self.series_path / "locations" / location_id / "location.json"
        data = self._read_json(path)
        if not data:
            return f"LOCATION: {location_id}"
        return "\n".join(
            [
                f"LOCATION LOCK: {data.get('display_name', location_id)}",
                data.get("description", ""),
                f"Camera baseline: {data.get('camera_baseline', '')}",
                f"Palette: {data.get('palette', '')}",
                f"Must remain constant: {', '.join(data.get('must_remain_constant', []))}",
                "Do not randomly mirror the room.",
            ]
        )

    def _prop_lock(self, prop_id: str) -> str:
        path = self.series_path / "props" / prop_id / "prop.json"
        data = self._read_json(path)
        if not data:
            return f"PROP: {prop_id}"
        label = data.get("label")
        label_line = f"Label text EXACT: {label}" if label else ""
        return "\n".join(
            p
            for p in [
                f"PROP LOCK: {data.get('display_name', prop_id)}",
                data.get("description", ""),
                label_line,
                f"Scale: {data.get('scale_rules', '')}",
                f"States allowed: {', '.join(data.get('states', []))}",
                "Episode state may change; identity must not.",
            ]
            if p
        )

    def compile_frame(
        self,
        frame: FrameManifest,
        *,
        extra_positive: str = "",
        extra_negative: str = "",
        persist: bool = True,
    ) -> dict[str, Any]:
        char_blocks = [self._character_lock(c) for c in frame.characters]
        prop_ids = []
        for p in frame.continuity.props:
            prop_ids.append(p.prop_id)
        prop_blocks = [self._prop_lock(pid) for pid in prop_ids]
        location_id = frame.continuity.location_id

        continuity_req = [
            "CONTINUITY REQUIREMENTS:",
            f"Inherit prior frame state unless script changes it. From: {frame.continuity_from}",
            f"Location asset: {frame.location_reference_id}",
            f"Character assets: {', '.join(frame.character_reference_ids)}",
            f"Prop assets: {', '.join(frame.prop_reference_ids)}",
        ]
        for p in frame.continuity.props:
            continuity_req.append(f"Prop {p.prop_id} state={p.state.value} pos={p.position}")
        for c in frame.continuity.characters:
            if c.hair_lock:
                continuity_req.append(f"Hair lock {c.character_id}: {c.hair_lock}")

        # Prefer art without baked text — dialogue composited later.
        dialogue_note = ""
        if frame.dialogue:
            dialogue_note = (
                "DIALOGUE is locked for post-compositing; leave speech-bubble space; "
                f"do NOT render lettering. Approved text (for planning only): {frame.dialogue!r}"
            )

        scale_block = ""
        spatial_block = ""
        try:
            scale_block = compile_scale_prompt_block(load_scale(self.series_id, root=self.root))
        except Exception:
            scale_block = ""
        if location_id:
            try:
                space = load_location_space(self.series_id, location_id, root=self.root)
                prop_regions = {}
                for p in frame.continuity.props:
                    # Prefer explicit LEFT_COUNTER style positions
                    if p.position and p.position.split(";")[0].strip().isupper():
                        prop_regions[p.prop_id] = p.position.split(";")[0].strip()
                    elif p.prop_id == "cookie-jar":
                        prop_regions[p.prop_id] = "LEFT_COUNTER"
                spatial_block = compile_spatial_prompt_block(space, prop_regions=prop_regions)
            except Exception:
                spatial_block = ""

        edit_hint = (
            "GENERATION PRINCIPLE: Prefer reference-based EDIT/VARIATION/INPAINT over full "
            "regeneration when only expression, arms, or speech change. Preserve background, "
            "camera, hair, clothes, jar identity/scale/position."
        )

        positive_parts = [
            BASE_STYLE.strip(),
            FAMILY_FRIENDLY.strip(),
            "\n\n".join(char_blocks),
            self._location_lock(location_id),
            "\n\n".join(prop_blocks),
            scale_block,
            spatial_block,
            f"FRAME: {frame.frame_id} type={frame.frame_type.value}",
            f"ACTION: {frame.action}",
            f"EXPRESSION: {frame.expression}",
            f"CAMERA: {frame.camera.angle}; {frame.camera.framing}; {frame.camera.lens_notes}",
            "\n".join(continuity_req),
            dialogue_note,
            edit_hint,
            NO_BAKED_TEXT.strip(),
            extra_positive.strip(),
        ]
        positive = "\n\n".join(p for p in positive_parts if p)
        negative = NEGATIVE_CONSTRAINTS.strip()
        if extra_negative:
            negative = f"{negative}, {extra_negative.strip()}"

        version = hashlib.sha256(f"{positive}\n---\n{negative}".encode()).hexdigest()[:12]
        payload = {
            "frame_id": frame.frame_id,
            "series_id": frame.series_id,
            "episode_id": frame.episode_id,
            "positive": positive,
            "negative": negative,
            "prompt_version": version,
            "reference_assets": [
                *frame.character_reference_ids,
                *([frame.location_reference_id] if frame.location_reference_id else []),
                *frame.prop_reference_ids,
            ],
            "dimensions": {"width": frame.width, "height": frame.height},
            "compiled_at": datetime.now(UTC).isoformat(),
        }
        if persist:
            self._persist(frame.frame_id, payload)
        return payload

    def _persist(self, frame_id: str, payload: dict[str, Any]) -> None:
        out = prompts_dir(root=self.root) / frame_id
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        versioned = out / f"{stamp}_{payload['prompt_version']}.json"
        latest = out / "latest.json"
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        versioned.write_text(text, encoding="utf-8")
        latest.write_text(text, encoding="utf-8")
