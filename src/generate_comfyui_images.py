"""
Generates cinematic scene clips using a LOCAL ComfyUI (SDXL-Lightning)
instance instead of Pexels stock footage or Pollinations illustrations.

Only runs when main.py is executed on the same machine as ComfyUI --
GitHub Actions' cloud runners can never reach 127.0.0.1:8188 on your Mac,
so this provider is local-only by nature (see docs/comfyui-local-worker.md).
"""

from __future__ import annotations

import os
import random
import subprocess

from comfyui_client import ComfyUIClient, ComfyUIError, ComfyUIUnavailableError
from comfyui_workflow import build_workflow, save_node_id

DEFAULT_CHECKPOINT = "sdxl_lightning_4step.safetensors"
GENERATION_TIMEOUT_SECONDS = 120
TARGET_FPS = 25

# Maps the storyboard's cameraMotion vocabulary to bounds-safe zoompan
# expressions. Pan drift is clamped to min(desired_drift, available_margin)
# so it can never push the crop window out of bounds regardless of the
# current zoom level -- same approach already validated for the
# illustration provider's motion presets.
def _motion_expr(motion: str, frames: int) -> tuple[str, str, str]:
    x_center = "iw/2-(iw/zoom/2)"
    y_center = "ih/2-(ih/zoom/2)"

    def pan_x(sign: str, scale: float = 0.35) -> str:
        return f"{x_center}{sign}min((iw-iw/zoom)/2,(on/{frames})*(iw*{scale}))"

    presets = {
        "slow_push_in": ("min(zoom+0.0015,1.2)", x_center, y_center),
        "slow_zoom_out": ("if(eq(on,0),1.2,max(zoom-0.0015,1.0))", x_center, y_center),
        "pan_left": ("1.15", pan_x("-"), y_center),
        "pan_right": ("1.15", pan_x("+"), y_center),
    }
    return presets.get(motion, presets["slow_push_in"])


def _image_to_clip(img_path: str, out_path: str, width: int, height: int, duration: float, motion: str) -> None:
    fps = TARGET_FPS
    frames = int(duration * fps)
    zoom_expr, x_expr, y_expr = _motion_expr(motion, frames)
    vf = (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={width}x{height}:fps={fps}"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path,
            "-vf", vf, "-t", str(duration), "-pix_fmt", "yuv420p",
            out_path,
        ],
        check=True, capture_output=True,
    )


def generate_comfyui_images(
    scenes: list[dict],
    out_dir: str,
    orientation: str = "portrait",
    checkpoint: str | None = None,
    job_id: str | None = None,
) -> list[str]:
    """
    scenes: storyboard scenes (see storyboard.py) -- each needs imagePrompt,
    negativePrompt, cameraMotion, durationSeconds.
    Returns local clip file paths in scene order (skipping any scene whose
    generation failed, matching the existing providers' error-tolerance).
    """
    width, height = (1080, 1920) if orientation == "portrait" else (1920, 1080)
    # ComfyUI is given a downscaled generation size (per the original spec:
    # 576x1024) -- ffmpeg upscales during the Ken Burns pass same as any
    # other still-image provider.
    gen_width, gen_height = (576, 1024) if orientation == "portrait" else (1024, 576)
    os.makedirs(out_dir, exist_ok=True)

    checkpoint = checkpoint or os.environ.get("COMFYUI_CHECKPOINT", DEFAULT_CHECKPOINT)
    client = ComfyUIClient()

    if not client.health_check():
        raise ComfyUIUnavailableError(
            "ComfyUI is not reachable. Start it locally first: "
            "cd ~/ComfyUI && source comfy-env/bin/activate && python main.py"
        )

    run_prefix = f"scene_{job_id}" if job_id else "scene"
    paths = []
    for i, scene in enumerate(scenes):
        seed = random.randint(0, 2**31 - 1)
        filename_prefix = f"{run_prefix}_{i:02d}"

        try:
            workflow = build_workflow(
                positive_prompt=scene["imagePrompt"],
                negative_prompt=scene.get("negativePrompt", ""),
                checkpoint=checkpoint,
                width=gen_width,
                height=gen_height,
                seed=seed,
                filename_prefix=filename_prefix,
            )
            prompt_id = client.submit_workflow(workflow)
            history = client.wait_for_completion(prompt_id, GENERATION_TIMEOUT_SECONDS)
            image_refs = client.extract_image_refs(history, save_node_id())

            img_path = os.path.join(out_dir, f"illustration_{i:02d}.png")
            client.download_image(image_refs[0], img_path)
        except ComfyUIError as e:
            print(f"[generate_comfyui_images] Skipping scene {i} -- generation failed: {e}")
            continue

        clip_path = os.path.join(out_dir, f"clip_{i:02d}.mp4")
        try:
            _image_to_clip(
                img_path, clip_path, width, height,
                duration=scene.get("durationSeconds", 3.0),
                motion=scene.get("cameraMotion", "slow_push_in"),
            )
        except subprocess.CalledProcessError as e:
            print(f"[generate_comfyui_images] ffmpeg failed to animate scene {i}: {e}")
            continue

        paths.append(clip_path)

    return paths


if __name__ == "__main__":
    test_scenes = [
        {
            "imagePrompt": "A cinematic rainy city street at night, photorealistic, vertical composition",
            "negativePrompt": "illustration, cartoon, text, watermark",
            "cameraMotion": "slow_push_in",
            "durationSeconds": 3.0,
        }
    ]
    result = generate_comfyui_images(test_scenes, "test_comfyui_output")
    print(result)
