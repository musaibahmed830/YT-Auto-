"""
Loads and fills in the trusted Wan2.1 VACE 1.3B image-to-video ComfyUI
workflow template.

Security note: same rule as comfyui_workflow.py -- this module NEVER
accepts a full user-supplied workflow graph. Only a small set of
validated values (prompt text, model filenames, dimensions, frame count,
fps, seed, filename prefix, the already-uploaded input image's filename)
are injected into fixed node input slots on a copy of the trusted
template loaded from workflows/wan21_vace_i2v_api.json.
"""

from __future__ import annotations

import copy
import json
import os
import re

WORKFLOW_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workflows", "wan21_vace_i2v_api.json"
)

# Semantic role -> node id in the template above. Centralizing this here
# means nothing else in the codebase hard-codes a node id.
NODE_ROLES = {
    "unet": "1",
    "clip_loader": "2",
    "vae_loader": "3",
    "positive_prompt": "4",
    "negative_prompt": "5",
    "load_image": "6",
    "model_sampling": "7",
    "vace": "8",
    "sampler": "9",
    "trim_latent": "10",
    "vae_decode": "11",
    "create_video": "12",
    "save_video": "13",
}

EXPECTED_CLASS_TYPES = {
    "unet": "UNETLoader",
    "clip_loader": "CLIPLoader",
    "vae_loader": "VAELoader",
    "positive_prompt": "CLIPTextEncode",
    "negative_prompt": "CLIPTextEncode",
    "load_image": "LoadImage",
    "model_sampling": "ModelSamplingSD3",
    "vace": "WanVaceToVideo",
    "sampler": "KSampler",
    "trim_latent": "TrimVideoLatent",
    "vae_decode": "VAEDecode",
    "create_video": "CreateVideo",
    "save_video": "SaveVideo",
}

MAX_PROMPT_LENGTH = 1500
MIN_DIM, MAX_DIM = 64, 1536
MIN_LENGTH, MAX_LENGTH = 9, 121  # Wan's causal VAE wants 4n+1 frame counts
MIN_FPS, MAX_FPS = 4, 30
MIN_STEPS, MAX_STEPS = 1, 50
MIN_CFG, MAX_CFG = 0.0, 20.0
MIN_SHIFT, MAX_SHIFT = 0.0, 20.0
MIN_STRENGTH, MAX_STRENGTH = 0.0, 2.0
FILENAME_PREFIX_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
IMAGE_FILENAME_RE = re.compile(r"^[^/\\]{1,255}$")


class WorkflowValidationError(Exception):
    pass


def _load_template() -> dict:
    with open(WORKFLOW_PATH) as f:
        return json.load(f)


def validate_template(template: dict) -> None:
    """Confirms the template still has every expected node/class_type before
    we ever submit it -- catches accidental edits to the trusted JSON file."""
    for role, node_id in NODE_ROLES.items():
        node = template.get(node_id)
        if not node:
            raise WorkflowValidationError(f"Workflow template missing node {node_id!r} ({role})")
        expected = EXPECTED_CLASS_TYPES[role]
        if node.get("class_type") != expected:
            raise WorkflowValidationError(
                f"Workflow template node {node_id!r} ({role}) has class_type "
                f"{node.get('class_type')!r}, expected {expected!r}"
            )


def _validate_prompt(text: str, label: str) -> str:
    if not isinstance(text, str):
        raise WorkflowValidationError(f"{label} must be a string")
    if len(text) > MAX_PROMPT_LENGTH:
        raise WorkflowValidationError(f"{label} exceeds {MAX_PROMPT_LENGTH} characters")
    return text


def _validate_dim(value: int, label: str) -> int:
    if not isinstance(value, int) or not (MIN_DIM <= value <= MAX_DIM):
        raise WorkflowValidationError(f"{label} must be an integer between {MIN_DIM} and {MAX_DIM}")
    return value


def _validate_range(value, lo, hi, label: str):
    if not isinstance(value, (int, float)) or not (lo <= value <= hi):
        raise WorkflowValidationError(f"{label} must be a number between {lo} and {hi}")
    return value


def _validate_filename_prefix(prefix: str) -> str:
    if not FILENAME_PREFIX_RE.match(prefix):
        raise WorkflowValidationError(
            f"filename_prefix {prefix!r} must match {FILENAME_PREFIX_RE.pattern} "
            "(letters, numbers, underscore, hyphen only -- prevents path traversal)"
        )
    return prefix


def _validate_image_filename(name: str) -> str:
    if not name or ".." in name or not IMAGE_FILENAME_RE.match(name):
        raise WorkflowValidationError(f"image_filename {name!r} is not a safe filename")
    return name


def build_i2v_workflow(
    *,
    positive_prompt: str,
    negative_prompt: str,
    image_filename: str,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    seed: int,
    filename_prefix: str,
    width: int = 480,
    height: int = 832,
    length: int = 49,
    fps: int = 16,
    steps: int = 20,
    cfg: float = 6.0,
    sampler_name: str = "uni_pc",
    scheduler: str = "simple",
    shift: float = 8.0,
    strength: float = 1.0,
) -> dict:
    """Returns a fresh copy of the trusted Wan VACE i2v workflow with
    validated values injected. image_filename must already exist in
    ComfyUI's input directory (see ComfyUIClient.upload_image)."""
    template = _load_template()
    validate_template(template)

    positive_prompt = _validate_prompt(positive_prompt, "positive_prompt")
    negative_prompt = _validate_prompt(negative_prompt, "negative_prompt")
    image_filename = _validate_image_filename(image_filename)
    width = _validate_dim(width, "width")
    height = _validate_dim(height, "height")
    length = _validate_range(length, MIN_LENGTH, MAX_LENGTH, "length")
    fps = _validate_range(fps, MIN_FPS, MAX_FPS, "fps")
    steps = _validate_range(steps, MIN_STEPS, MAX_STEPS, "steps")
    cfg = _validate_range(cfg, MIN_CFG, MAX_CFG, "cfg")
    shift = _validate_range(shift, MIN_SHIFT, MAX_SHIFT, "shift")
    strength = _validate_range(strength, MIN_STRENGTH, MAX_STRENGTH, "strength")
    filename_prefix = _validate_filename_prefix(filename_prefix)
    if not isinstance(seed, int) or seed < 0:
        raise WorkflowValidationError("seed must be a non-negative integer")

    workflow = copy.deepcopy(template)
    workflow[NODE_ROLES["unet"]]["inputs"]["unet_name"] = unet_name
    workflow[NODE_ROLES["clip_loader"]]["inputs"]["clip_name"] = clip_name
    workflow[NODE_ROLES["vae_loader"]]["inputs"]["vae_name"] = vae_name
    workflow[NODE_ROLES["positive_prompt"]]["inputs"]["text"] = positive_prompt
    workflow[NODE_ROLES["negative_prompt"]]["inputs"]["text"] = negative_prompt
    workflow[NODE_ROLES["load_image"]]["inputs"]["image"] = image_filename
    workflow[NODE_ROLES["model_sampling"]]["inputs"]["shift"] = shift
    workflow[NODE_ROLES["vace"]]["inputs"].update(
        {
            "width": width,
            "height": height,
            "length": int(length),
            "strength": strength,
        }
    )
    workflow[NODE_ROLES["sampler"]]["inputs"].update(
        {
            "seed": seed,
            "steps": int(steps),
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
        }
    )
    workflow[NODE_ROLES["create_video"]]["inputs"]["fps"] = int(fps)
    workflow[NODE_ROLES["save_video"]]["inputs"]["filename_prefix"] = filename_prefix
    return workflow


def save_video_node_id() -> str:
    return NODE_ROLES["save_video"]
