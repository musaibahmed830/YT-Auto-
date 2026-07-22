"""
Typed client for a LOCAL ComfyUI instance (default http://127.0.0.1:8188).

This only ever talks to localhost -- ComfyUI must never be exposed
publicly. Only the trusted workflow template (comfyui_workflow.py) is
ever submitted; this client never accepts an arbitrary user-supplied
workflow graph.
"""

from __future__ import annotations

import os
import time
import uuid

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8188"
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30
MAX_NETWORK_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


class ComfyUIError(Exception):
    """Raised for ComfyUI execution/validation errors -- never retried."""


class ComfyUIUnavailableError(Exception):
    """Raised when ComfyUI can't be reached at all after retries."""


def _safe_component(name: str) -> str:
    """
    Rejects path-traversal or path-separator characters in any filename/
    subfolder ComfyUI reports back to us before we join it into a local
    path -- defensive even though this data nominally comes from a local,
    trusted ComfyUI instance.
    """
    if not name or "/" in name or "\\" in name or ".." in name:
        raise ComfyUIError(f"Unsafe filename/subfolder component from ComfyUI: {name!r}")
    return name


class ComfyUIClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.environ.get("COMFYUI_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.client_id = str(uuid.uuid4())

    def _request(self, method: str, path: str, **kwargs):
        last_error = None
        for attempt in range(1, MAX_NETWORK_RETRIES + 1):
            try:
                resp = requests.request(
                    method, f"{self.base_url}{path}",
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    **kwargs,
                )
                resp.raise_for_status()
                return resp
            except requests.ConnectionError as e:
                last_error = e
                if attempt < MAX_NETWORK_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
        raise ComfyUIUnavailableError(
            f"Could not reach ComfyUI at {self.base_url} after {MAX_NETWORK_RETRIES} attempts. "
            f"Is it running? (cd ~/ComfyUI && source comfy-env/bin/activate && python main.py) -- {last_error}"
        )

    def health_check(self) -> bool:
        try:
            self._request("GET", "/queue")
            return True
        except ComfyUIUnavailableError:
            return False

    def object_info(self) -> dict:
        return self._request("GET", "/object_info").json()

    def checkpoint_available(self, checkpoint_name: str) -> bool:
        info = self.object_info()
        try:
            names = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        except (KeyError, IndexError, TypeError):
            return False
        return checkpoint_name in names

    def submit_workflow(self, workflow: dict) -> str:
        """Submits a (trusted, already-validated) workflow graph. Returns prompt_id."""
        resp = self._request(
            "POST", "/prompt",
            json={"prompt": workflow, "client_id": self.client_id},
        )
        body = resp.json()
        if body.get("node_errors"):
            raise ComfyUIError(f"ComfyUI rejected the workflow: {body['node_errors']}")
        prompt_id = body.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"ComfyUI did not return a prompt_id: {body}")
        return prompt_id

    def wait_for_completion(self, prompt_id: str, timeout_seconds: int, poll_interval: float = 1.5) -> dict:
        """Polls /history/{prompt_id} until ComfyUI reports it finished. Returns the history entry."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            resp = self._request("GET", f"/history/{prompt_id}")
            history = resp.json()
            entry = history.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ComfyUIError(f"ComfyUI execution failed for {prompt_id}: {status}")
                if entry.get("outputs"):
                    return entry
            time.sleep(poll_interval)
        raise ComfyUIError(f"Timed out after {timeout_seconds}s waiting for ComfyUI prompt {prompt_id}")

    def extract_image_refs(self, history_entry: dict, save_node_id: str) -> list[dict]:
        """Pulls the {filename, subfolder, type} refs for the SaveImage node's output."""
        outputs = history_entry.get("outputs", {})
        node_output = outputs.get(save_node_id)
        if not node_output or not node_output.get("images"):
            raise ComfyUIError(f"No image output found for save node {save_node_id!r} in history: {outputs}")
        return node_output["images"]

    def download_image(self, image_ref: dict, out_path: str) -> str:
        filename = _safe_component(image_ref["filename"])
        subfolder = _safe_component(image_ref.get("subfolder", "")) if image_ref.get("subfolder") else ""
        img_type = image_ref.get("type", "output")
        if img_type not in ("output", "temp"):
            raise ComfyUIError(f"Unexpected ComfyUI image type: {img_type!r}")

        resp = self._request(
            "GET", "/view",
            params={"filename": filename, "subfolder": subfolder, "type": img_type},
        )
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path

    # ---- Wan2.1 VACE image-to-video support ----

    def upload_image(self, local_path: str, subfolder: str = "") -> dict:
        """
        Uploads a local image into ComfyUI's own input directory so a
        LoadImage node can reference it by filename. Returns ComfyUI's
        {name, subfolder, type} response. Reads the file into memory first
        (rather than streaming an open file handle) so a network retry in
        _request never resubmits an already-exhausted file object.
        """
        with open(local_path, "rb") as f:
            image_bytes = f.read()
        files = {"image": (os.path.basename(local_path), image_bytes, "image/png")}
        data = {"overwrite": "true"}
        if subfolder:
            data["subfolder"] = subfolder
        resp = self._request("POST", "/upload/image", files=files, data=data)
        return resp.json()

    def extract_video_ref(self, history_entry: dict, save_node_id: str) -> dict:
        """
        Pulls the {filename, subfolder, type} ref for a SaveVideo node's
        output. ComfyUI's exact output key for video nodes has changed
        across versions ("videos", or the older "gifs" key reused by
        animated-output nodes), so this checks the plausible keys instead
        of assuming one -- and surfaces the raw output on a mismatch so the
        real key is visible instead of a silent KeyError.
        """
        outputs = history_entry.get("outputs", {})
        node_output = outputs.get(save_node_id, {})
        for key in ("videos", "gifs", "images"):
            refs = node_output.get(key)
            if refs:
                return refs[0]
        raise ComfyUIError(
            f"No video output found for save node {save_node_id!r}. Raw node output: {node_output!r}"
        )

    def download_file(self, file_ref: dict, out_path: str) -> str:
        """/view serves any output file type, not just images -- reused for video bytes."""
        return self.download_image(file_ref, out_path)
