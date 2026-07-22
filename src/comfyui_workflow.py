"""
Loads and fills in the trusted SDXL-Lightning ComfyUI workflow template.

Security note: this module NEVER accepts a full user-supplied workflow
graph. Only a small set of validated values (prompt text, width/height,
seed, filename prefix) are injected into fixed node input slots on a copy
of the trusted template loaded from workflows/sdxl_lightning_api.json --
the graph shape, node types, and checkpoint name are never user-controlled.
"""

from __future__ import annotations

import copy
import json
import os
import re

WORKFLOW_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workflows", "sdxl_lightning_api.json"
)

# Semantic role -> node id in the template above. Centralizing this here
# means nothing else in the codebase hard-codes a node id.
NODE_ROLES = {
    "checkpoint": "1",
    "positive_prompt": "2",
    "negative_prompt": "3",
    "latent_size": "4",
    "sampler": "5",
    "vae_decode": "6",
    "save_image": "7",
}

EXPECTED_CLASS_TYPES = {
    "checkpoint": "CheckpointLoaderSimple",
    "positive_prompt": "CLIPTextEncode",
    "negative_prompt": "CLIPTextEncode",
    "latent_size": "EmptyLatentImage",
    "sampler": "KSampler",
    "vae_decode": "VAEDecode",
    "save_image": "SaveImage",
}

MAX_PROMPT_LENGTH = 1500
MIN_DIM, MAX_DIM = 64, 1536
FILENAME_PREFIX_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


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


def _validate_filename_prefix(prefix: str) -> str:
    if not FILENAME_PREFIX_RE.match(prefix):
        raise WorkflowValidationError(
            f"filename_prefix {prefix!r} must match {FILENAME_PREFIX_RE.pattern} "
            "(letters, numbers, underscore, hyphen only -- prevents path traversal)"
        )
    return prefix


def build_workflow(
    *,
    positive_prompt: str,
    negative_prompt: str,
    checkpoint: str,
    width: int = 576,
    height: int = 1024,
    seed: int,
    filename_prefix: str,
    steps: int = 4,
    cfg: float = 1.0,
    sampler_name: str = "euler",
    scheduler: str = "sgm_uniform",
    denoise: float = 1.0,
) -> dict:
    """Returns a fresh copy of the trusted workflow with validated values injected."""
    template = _load_template()
    validate_template(template)

    positive_prompt = _validate_prompt(positive_prompt, "positive_prompt")
    negative_prompt = _validate_prompt(negative_prompt, "negative_prompt")
    width = _validate_dim(width, "width")
    height = _validate_dim(height, "height")
    filename_prefix = _validate_filename_prefix(filename_prefix)
    if not isinstance(seed, int) or seed < 0:
        raise WorkflowValidationError("seed must be a non-negative integer")

    workflow = copy.deepcopy(template)
    workflow[NODE_ROLES["checkpoint"]]["inputs"]["ckpt_name"] = checkpoint
    workflow[NODE_ROLES["positive_prompt"]]["inputs"]["text"] = positive_prompt
    workflow[NODE_ROLES["negative_prompt"]]["inputs"]["text"] = negative_prompt
    workflow[NODE_ROLES["latent_size"]]["inputs"]["width"] = width
    workflow[NODE_ROLES["latent_size"]]["inputs"]["height"] = height
    workflow[NODE_ROLES["sampler"]]["inputs"].update(
        {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "denoise": denoise,
        }
    )
    workflow[NODE_ROLES["save_image"]]["inputs"]["filename_prefix"] = filename_prefix
    return workflow


def save_node_id() -> str:
    return NODE_ROLES["save_image"]
