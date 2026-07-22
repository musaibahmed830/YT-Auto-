"""
Generates real moving-video scene clips ("cinematic_video" provider) using
two local ComfyUI passes, one scene at a time:

  1. SDXL-Lightning generates one accurate vertical starting image per
     scene (the same trusted workflow the image_slideshow provider uses).
  2. Wan2.1 VACE 1.3B animates that image into a real 3-4 second moving
     clip via the trusted Wan image-to-video workflow.

Local-only, same as generate_comfyui_images.py -- GitHub's cloud runners
can't reach 127.0.0.1:8188. Never runs scenes concurrently: Wan on a Mac
M1 with 16GB unified memory needs one scene's model pass to finish before
the next starts.
"""

from __future__ import annotations

import os
import random

from comfyui_client import ComfyUIClient, ComfyUIError, ComfyUIUnavailableError
from comfyui_workflow import build_workflow as build_image_workflow, save_node_id as image_save_node_id
from comfyui_i2v_workflow import build_i2v_workflow, save_video_node_id
from wan_dependencies import verify_wan_dependencies

DEFAULT_CHECKPOINT = "sdxl_lightning_4step.safetensors"
DEFAULT_UNET = "wan2.1_vace_1.3B_fp16.safetensors"
DEFAULT_CLIP = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
DEFAULT_VAE = "wan_2.1_vae.safetensors"

IMAGE_GEN_TIMEOUT_SECONDS = 120
VIDEO_GEN_TIMEOUT_SECONDS = 600  # Wan 1.3B on M1 16GB can take several minutes per scene

I2V_WIDTH, I2V_HEIGHT = 480, 832
I2V_LENGTH = 49  # ~3s at 16fps, Wan's causal VAE wants 4n+1 frame counts
I2V_FPS = 16


def generate_cinematic_video(
    scenes: list[dict],
    out_dir: str,
    orientation: str = "portrait",
    job_id: str | None = None,
) -> list[str]:
    """
    scenes: storyboard scenes (see storyboard.py) -- each needs imagePrompt,
    negativePrompt, motionPrompt, durationSeconds.
    Returns local MP4 clip paths in scene order (skipping any scene whose
    image or animation step failed, matching the existing providers'
    error-tolerance). Raises ComfyUIUnavailableError / WanDependencyError
    before starting any scene if ComfyUI or the required Wan models/nodes
    aren't available -- per spec, a cinematic_video job never starts with
    missing dependencies.
    """
    gen_width, gen_height = (576, 1024) if orientation == "portrait" else (1024, 576)
    os.makedirs(out_dir, exist_ok=True)

    checkpoint = os.environ.get("COMFYUI_CHECKPOINT", DEFAULT_CHECKPOINT)
    unet_name = os.environ.get("COMFYUI_WAN_UNET", DEFAULT_UNET)
    clip_name = os.environ.get("COMFYUI_WAN_CLIP", DEFAULT_CLIP)
    vae_name = os.environ.get("COMFYUI_WAN_VAE", DEFAULT_VAE)

    client = ComfyUIClient()
    if not client.health_check():
        raise ComfyUIUnavailableError(
            "ComfyUI is not reachable. Start it locally first: "
            "cd ~/ComfyUI && source comfy-env/bin/activate && python main.py"
        )

    verify_wan_dependencies(client, unet_name=unet_name, clip_name=clip_name, vae_name=vae_name)

    run_prefix = f"scene_{job_id}" if job_id else "scene"
    n = len(scenes)

    print("STATE: generating_scene_images")
    scene_images: list[str | None] = []
    for i, scene in enumerate(scenes):
        seed = random.randint(0, 2**31 - 1)
        try:
            img_workflow = build_image_workflow(
                positive_prompt=scene["imagePrompt"],
                negative_prompt=scene.get("negativePrompt", ""),
                checkpoint=checkpoint,
                width=gen_width,
                height=gen_height,
                seed=seed,
                filename_prefix=f"{run_prefix}_{i:02d}_start",
            )
            prompt_id = client.submit_workflow(img_workflow)
            history = client.wait_for_completion(prompt_id, IMAGE_GEN_TIMEOUT_SECONDS)
            image_refs = client.extract_image_refs(history, image_save_node_id())

            img_path = os.path.join(out_dir, f"start_{i:02d}.png")
            client.download_image(image_refs[0], img_path)
            scene_images.append(img_path)
        except ComfyUIError as e:
            print(f"[generate_cinematic_video] Skipping scene {i} -- starting image failed: {e}")
            scene_images.append(None)

    paths = []
    for i, (scene, img_path) in enumerate(zip(scenes, scene_images)):
        if img_path is None:
            continue

        print(f"STATE: animating_scene_{i + 1}_of_{n}")
        seed = random.randint(0, 2**31 - 1)
        clip_path = os.path.join(out_dir, f"clip_{i:02d}.mp4")
        try:
            uploaded = client.upload_image(img_path)
            i2v_workflow = build_i2v_workflow(
                positive_prompt=scene.get("motionPrompt") or scene["imagePrompt"],
                negative_prompt=scene.get("negativePrompt", ""),
                image_filename=uploaded["name"],
                unet_name=unet_name,
                clip_name=clip_name,
                vae_name=vae_name,
                width=I2V_WIDTH,
                height=I2V_HEIGHT,
                length=I2V_LENGTH,
                fps=I2V_FPS,
                seed=seed,
                filename_prefix=f"{run_prefix}_{i:02d}_video",
            )
            prompt_id = client.submit_workflow(i2v_workflow)
            history = client.wait_for_completion(prompt_id, VIDEO_GEN_TIMEOUT_SECONDS)
            video_ref = client.extract_video_ref(history, save_video_node_id())
            client.download_file(video_ref, clip_path)
        except ComfyUIError as e:
            print(f"[generate_cinematic_video] Skipping scene {i} -- animation failed: {e}")
            continue

        paths.append(clip_path)

    return paths


if __name__ == "__main__":
    test_scenes = [
        {
            "imagePrompt": "A cinematic rainy city street at night, photorealistic, vertical composition",
            "negativePrompt": "illustration, cartoon, text, watermark",
            "motionPrompt": (
                "The man slowly raises his head and looks toward the approaching car. "
                "Rain continues falling and his jacket moves subtly in the wind. "
                "The camera performs a gentle push-in. Natural realistic body motion."
            ),
            "cameraMotion": "slow_push_in",
            "durationSeconds": 3.0,
        }
    ]
    result = generate_cinematic_video(test_scenes, "test_cinematic_output")
    print(result)
