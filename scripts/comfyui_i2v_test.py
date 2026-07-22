#!/usr/bin/env python3
"""
Isolated Wan2.1 VACE image-to-video smoke test -- animates one real image
through the trusted Wan I2V workflow and confirms ComfyUI produced an
actual moving MP4 (multiple frames, non-zero duration), not just a still
frame wrapped in a video container.

This repo has no npm/package.json, so there is no "npm run" alias -- run
it directly:

    python3 scripts/comfyui_i2v_test.py

Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from comfyui_client import ComfyUIClient, ComfyUIError, ComfyUIUnavailableError  # noqa: E402
from comfyui_workflow import build_workflow, save_node_id  # noqa: E402
from comfyui_i2v_workflow import build_i2v_workflow, save_video_node_id  # noqa: E402
from wan_dependencies import verify_wan_dependencies, WanDependencyError  # noqa: E402

TEST_IMAGE_PATH = os.path.join("test_output", "comfyui_smoke_test.png")
TEST_MOTION_PROMPT = (
    "The man slowly raises his head and looks toward the approaching car. "
    "Rain continues falling and his jacket moves subtly in the wind. "
    "The camera performs a gentle push-in. Natural realistic body motion."
)
TEST_NEGATIVE = "static image, no motion, blurry, distorted, extra limbs"
OUTPUT_DIR = "test_output"
IMAGE_TIMEOUT_SECONDS = 120
VIDEO_TIMEOUT_SECONDS = 600


def _ensure_test_image(client: ComfyUIClient) -> str:
    if os.path.exists(TEST_IMAGE_PATH):
        print(f"Using existing test image: {TEST_IMAGE_PATH}")
        return TEST_IMAGE_PATH

    print("No existing test image found -- generating one with SDXL-Lightning...")
    checkpoint = os.environ.get("COMFYUI_CHECKPOINT", "sdxl_lightning_4step.safetensors")
    workflow = build_workflow(
        positive_prompt="A cinematic rainy city street at night, photorealistic, vertical composition",
        negative_prompt="illustration, cartoon, anime, text, watermark, low resolution",
        checkpoint=checkpoint,
        width=576, height=1024, seed=42, filename_prefix="i2v_test_start",
    )
    prompt_id = client.submit_workflow(workflow)
    history = client.wait_for_completion(prompt_id, IMAGE_TIMEOUT_SECONDS)
    image_refs = client.extract_image_refs(history, save_node_id())
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client.download_image(image_refs[0], TEST_IMAGE_PATH)
    return TEST_IMAGE_PATH


def _probe_video(path: str) -> tuple[int, float]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-count_frames",
            "-show_entries", "stream=nb_read_frames,duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    streams = json.loads(result.stdout).get("streams") or []
    if not streams:
        raise RuntimeError("ffprobe found no video stream in the output file")
    stream = streams[0]
    frames = int(stream.get("nb_read_frames", 0) or 0)
    duration = float(stream.get("duration", 0) or 0)
    return frames, duration


def main() -> int:
    unet_name = os.environ.get("COMFYUI_WAN_UNET", "wan2.1_vace_1.3B_fp16.safetensors")
    clip_name = os.environ.get("COMFYUI_WAN_CLIP", "umt5_xxl_fp8_e4m3fn_scaled.safetensors")
    vae_name = os.environ.get("COMFYUI_WAN_VAE", "wan_2.1_vae.safetensors")

    client = ComfyUIClient()
    print(f"Checking ComfyUI at {client.base_url} ...")
    if not client.health_check():
        print(f"ERROR: ComfyUI is not reachable at {client.base_url}.")
        print("Start it with: cd ~/ComfyUI && source comfy-env/bin/activate && python main.py")
        return 1
    print("ComfyUI is up.")

    try:
        verify_wan_dependencies(client, unet_name=unet_name, clip_name=clip_name, vae_name=vae_name)
    except WanDependencyError as e:
        print(f"ERROR: {e}")
        return 1
    print("Wan2.1 VACE nodes + models are present.")

    try:
        image_path = _ensure_test_image(client)

        print("Uploading starting image to ComfyUI...")
        uploaded = client.upload_image(image_path)

        print("Submitting Wan2.1 VACE image-to-video workflow...")
        workflow = build_i2v_workflow(
            positive_prompt=TEST_MOTION_PROMPT,
            negative_prompt=TEST_NEGATIVE,
            image_filename=uploaded["name"],
            unet_name=unet_name,
            clip_name=clip_name,
            vae_name=vae_name,
            seed=42,
            filename_prefix="i2v_test",
        )
        prompt_id = client.submit_workflow(workflow)
        print(f"Prompt ID: {prompt_id} -- this can take several minutes on an M1 "
              "(first run also has to load the checkpoint into memory)...")
        history = client.wait_for_completion(prompt_id, VIDEO_TIMEOUT_SECONDS)
        video_ref = client.extract_video_ref(history, save_video_node_id())

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out_path = os.path.join(OUTPUT_DIR, "comfyui_i2v_test.mp4")
        client.download_file(video_ref, out_path)
    except (ComfyUIError, ComfyUIUnavailableError) as e:
        print(f"ERROR: {e}")
        return 1

    print("Verifying the output is an actual moving video (not a single frame)...")
    try:
        frames, duration = _probe_video(out_path)
    except Exception as e:
        print(f"ERROR: could not probe output video: {e}")
        return 1

    if frames <= 1 or duration <= 0:
        print(f"ERROR: output does not look like real video (frames={frames}, duration={duration}s)")
        return 1

    print(f"\nSuccess! {frames} frames, {duration:.2f}s -- saved to {os.path.abspath(out_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
