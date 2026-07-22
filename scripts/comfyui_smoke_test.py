#!/usr/bin/env python3
"""
Isolated ComfyUI smoke test -- generates one real image through the
trusted SDXL-Lightning workflow. No production credentials, no Groq call,
no video pipeline involved -- just confirms your local ComfyUI + checkpoint
setup can actually produce an image end to end.

Usage:
    python scripts/comfyui_smoke_test.py

Exits non-zero on any failure.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from comfyui_client import ComfyUIClient, ComfyUIError, ComfyUIUnavailableError  # noqa: E402
from comfyui_workflow import build_workflow, save_node_id  # noqa: E402

TEST_PROMPT = "A cinematic rainy city street at night, photorealistic, vertical composition"
TEST_NEGATIVE = "illustration, cartoon, anime, text, watermark, low resolution"
OUTPUT_DIR = "test_output"
TIMEOUT_SECONDS = 120


def main() -> int:
    checkpoint = os.environ.get("COMFYUI_CHECKPOINT", "sdxl_lightning_4step.safetensors")
    print(f"Using checkpoint: {checkpoint}")

    client = ComfyUIClient()
    print(f"Checking ComfyUI at {client.base_url} ...")
    if not client.health_check():
        print(f"ERROR: ComfyUI is not reachable at {client.base_url}.")
        print("Start it with: cd ~/ComfyUI && source comfy-env/bin/activate && python main.py")
        return 1
    print("ComfyUI is up.")

    try:
        workflow = build_workflow(
            positive_prompt=TEST_PROMPT,
            negative_prompt=TEST_NEGATIVE,
            checkpoint=checkpoint,
            width=576,
            height=1024,
            seed=42,
            filename_prefix="smoke_test",
        )
        print("Submitting test workflow...")
        prompt_id = client.submit_workflow(workflow)
        print(f"Prompt ID: {prompt_id} -- waiting for ComfyUI to finish...")
        history = client.wait_for_completion(prompt_id, TIMEOUT_SECONDS)
        image_refs = client.extract_image_refs(history, save_node_id())

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out_path = os.path.join(OUTPUT_DIR, "comfyui_smoke_test.png")
        client.download_image(image_refs[0], out_path)
    except (ComfyUIError, ComfyUIUnavailableError) as e:
        print(f"ERROR: {e}")
        return 1

    print(f"\nSuccess! Image saved to: {os.path.abspath(out_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
