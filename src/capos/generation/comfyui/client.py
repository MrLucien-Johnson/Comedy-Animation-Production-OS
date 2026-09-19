"""ComfyUI API client — queue, history, view, OOM classification."""

from __future__ import annotations

import json
import time
import uuid
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ComfyFailureKind(StrEnum):
    CUDA_OUT_OF_MEMORY = "CUDA_OUT_OF_MEMORY"
    MODEL_LOAD_FAILURE = "MODEL_LOAD_FAILURE"
    VAE_LOAD_FAILURE = "VAE_LOAD_FAILURE"
    WORKFLOW_FAILURE = "WORKFLOW_FAILURE"
    NODE_FAILURE = "NODE_FAILURE"
    TIMEOUT = "TIMEOUT"
    OUTPUT_MISSING = "OUTPUT_MISSING"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    UNAVAILABLE = "UNAVAILABLE"
    CONFIG_MISSING = "CONFIG_MISSING"
    UNKNOWN = "UNKNOWN"


def classify_comfy_error(message: str) -> ComfyFailureKind:
    m = (message or "").lower()
    if any(x in m for x in ("out of memory", "cuda oom", "cuda_out_of_memory", "oom")):
        return ComfyFailureKind.CUDA_OUT_OF_MEMORY
    if "vae" in m and ("load" in m or "failed" in m):
        return ComfyFailureKind.VAE_LOAD_FAILURE
    if "model" in m and ("load" in m or "not found" in m or "missing" in m):
        return ComfyFailureKind.MODEL_LOAD_FAILURE
    if "timeout" in m:
        return ComfyFailureKind.TIMEOUT
    if "node" in m and ("error" in m or "failed" in m):
        return ComfyFailureKind.NODE_FAILURE
    if "workflow" in m:
        return ComfyFailureKind.WORKFLOW_FAILURE
    return ComfyFailureKind.UNKNOWN


class ComfyUIClient:
    def __init__(self, base_url: str, *, timeout_s: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.client_id = str(uuid.uuid4())

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, bytes]:
        url = f"{self.base_url}{path}"
        req = Request(url, data=data, method=method, headers=headers or {})
        try:
            with urlopen(req, timeout=timeout or self.timeout_s) as resp:
                return resp.status, resp.read()
        except HTTPError as exc:
            body = exc.read() if hasattr(exc, "read") else b""
            return exc.code, body
        except URLError as exc:
            raise ConnectionError(f"ComfyUI unreachable: {exc}") from exc

    def health(self) -> dict[str, Any]:
        try:
            status, body = self._request("GET", "/system_stats", timeout=3)
            if status != 200:
                return {"ok": False, "reason": f"HTTP {status}", "raw": body[:500]}
            stats = json.loads(body.decode("utf-8"))
            return {"ok": True, "reason": f"reachable at {self.base_url}", "stats": stats}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": str(exc)}

    def queue_prompt(self, workflow: dict[str, Any]) -> str:
        payload = json.dumps({"prompt": workflow, "client_id": self.client_id}).encode("utf-8")
        status, body = self._request(
            "POST",
            "/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        if status != 200:
            raise RuntimeError(f"ComfyUI /prompt failed HTTP {status}: {body[:800]!r}")
        data = json.loads(body.decode("utf-8"))
        if "error" in data:
            raise RuntimeError(str(data["error"]))
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI /prompt missing prompt_id: {data}")
        return prompt_id

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        status, body = self._request("GET", f"/history/{prompt_id}")
        if status != 200:
            raise RuntimeError(f"ComfyUI /history failed HTTP {status}")
        data = json.loads(body.decode("utf-8"))
        return data.get(prompt_id) or data.get(str(prompt_id)) or {}

    def get_queue(self) -> dict[str, Any]:
        status, body = self._request("GET", "/queue")
        if status != 200:
            raise RuntimeError(f"ComfyUI /queue failed HTTP {status}")
        return json.loads(body.decode("utf-8"))

    def list_checkpoints(self) -> list[str]:
        """Best-effort checkpoint list from ComfyUI. Empty if endpoint unsupported."""
        for path in ("/models/checkpoints", "/experiment/models/checkpoints"):
            try:
                status, body = self._request("GET", path, timeout=5)
                if status == 200 and body:
                    data = json.loads(body.decode("utf-8"))
                    if isinstance(data, list):
                        return [str(x) for x in data]
            except Exception:  # noqa: BLE001
                continue
        return []

    def checkpoint_present(self, name: str) -> tuple[bool, str]:
        names = self.list_checkpoints()
        if not names:
            return (
                False,
                "Could not list checkpoints via API — verify manually in ComfyUI models/checkpoints/",
            )
        if name in names or any(name in n for n in names):
            return True, f"found in ComfyUI checkpoint list ({len(names)} total)"
        return False, f"checkpoint '{name}' not found among {len(names)} listed checkpoints"

    def interrupt(self) -> None:
        self._request("POST", "/interrupt", data=b"{}")

    def fetch_image(self, *, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        qs = urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
        status, body = self._request("GET", f"/view?{qs}", timeout=60)
        if status != 200 or not body:
            raise RuntimeError(f"ComfyUI /view failed for {filename} HTTP {status}")
        return body

    def wait_for_completion(
        self,
        prompt_id: str,
        *,
        poll_interval_s: float = 1.0,
        timeout_s: float = 300.0,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            hist = self.get_history(prompt_id)
            if hist:
                # status / outputs present when done
                status_obj = hist.get("status") or {}
                if status_obj.get("completed") or hist.get("outputs"):
                    if status_obj.get("status_str") == "error" or status_obj.get("messages"):
                        # may still have error messages
                        msgs = status_obj.get("messages") or []
                        err_text = json.dumps(msgs)
                        kind = classify_comfy_error(err_text)
                        if kind != ComfyFailureKind.UNKNOWN or "error" in err_text.lower():
                            raise RuntimeError(f"{kind.value}: {err_text[:2000]}")
                    return hist
            time.sleep(poll_interval_s)
        raise TimeoutError(f"{ComfyFailureKind.TIMEOUT.value}: prompt_id={prompt_id}")

    def first_image_from_history(self, history: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
        outputs = history.get("outputs") or {}
        for _node_id, node_out in outputs.items():
            images = node_out.get("images") or []
            if not images:
                continue
            meta = images[0]
            raw = self.fetch_image(
                filename=meta["filename"],
                subfolder=meta.get("subfolder", ""),
                folder_type=meta.get("type", "output"),
            )
            if not raw:
                raise RuntimeError(ComfyFailureKind.OUTPUT_MISSING.value)
            return raw, meta
        raise RuntimeError(ComfyFailureKind.OUTPUT_MISSING.value)

    def save_image_bytes(self, raw: bytes, output_path: Path) -> Path:
        if not raw or len(raw) < 32:
            raise RuntimeError(ComfyFailureKind.INVALID_OUTPUT.value)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(raw)
        # decode check deferred to caller with Pillow
        return output_path
