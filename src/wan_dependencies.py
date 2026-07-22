"""
Verifies a local ComfyUI install actually has everything the
cinematic_video (Wan2.1 VACE image-to-video) provider needs BEFORE a job
starts -- per spec, never silently begin a cinematic_video job with
missing node types or model files. Reports the exact missing model
filenames and which ComfyUI models/ subfolder they belong in.
"""

from __future__ import annotations

from comfyui_client import ComfyUIClient
from comfyui_i2v_workflow import EXPECTED_CLASS_TYPES as I2V_CLASS_TYPES

# field name -> (loader class_type, input name on that loader, destination folder under ComfyUI/models/)
REQUIRED_MODEL_INPUTS = {
    "unet_name": ("UNETLoader", "unet_name", "ComfyUI/models/diffusion_models/"),
    "clip_name": ("CLIPLoader", "clip_name", "ComfyUI/models/text_encoders/"),
    "vae_name": ("VAELoader", "vae_name", "ComfyUI/models/vae/"),
}


class WanDependencyError(Exception):
    pass


def verify_wan_dependencies(client: ComfyUIClient, *, unet_name: str, clip_name: str, vae_name: str) -> None:
    info = client.object_info()

    missing_nodes = sorted({ct for ct in I2V_CLASS_TYPES.values() if ct not in info})
    if missing_nodes:
        raise WanDependencyError(
            "This ComfyUI install is missing required node type(s) for cinematic_video: "
            f"{', '.join(missing_nodes)}. Update ComfyUI to a version with native Wan2.1 "
            "VACE support (comfyanonymous/ComfyUI, a recent release)."
        )

    requested = {"unet_name": unet_name, "clip_name": clip_name, "vae_name": vae_name}
    missing_models = []
    for field, filename in requested.items():
        loader_class, input_name, dest_folder = REQUIRED_MODEL_INPUTS[field]
        try:
            available = info[loader_class]["input"]["required"][input_name][0]
        except (KeyError, IndexError, TypeError):
            available = []
        if filename not in available:
            missing_models.append(f"  - {filename}  ->  place in {dest_folder}")

    if missing_models:
        raise WanDependencyError(
            "cinematic_video is missing required model file(s):\n"
            + "\n".join(missing_models)
            + "\n\nDownload these from the official Wan2.1 VACE 1.3B release and restart ComfyUI, "
            "then re-run scripts/comfyui_i2v_test.py to confirm."
        )
