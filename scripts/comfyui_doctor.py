#!/usr/bin/env python3
"""
Local diagnostic for the ComfyUI visual provider. Run this before your
first `VISUAL_STYLE=comfyui` run to confirm everything it needs is in
place. Exits non-zero if anything required is missing.

Usage:
    python scripts/comfyui_doctor.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

CHECK = "✓"
CROSS = "✗"


def _report(ok: bool, label: str, detail: str = "") -> bool:
    mark = CHECK if ok else CROSS
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{mark}] {label}{suffix}")
    return ok


def check_python() -> bool:
    version = sys.version_info
    ok = version >= (3, 10)
    return _report(ok, f"Python {version.major}.{version.minor}.{version.micro}", "" if ok else "need >= 3.10")


def check_binary(name: str) -> bool:
    path = shutil.which(name)
    if not path:
        return _report(False, name, "not found on PATH")
    try:
        result = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10)
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        return _report(True, name, first_line)
    except Exception as e:
        return _report(False, name, str(e))


def check_comfyui() -> bool:
    try:
        from comfyui_client import ComfyUIClient
    except ImportError as e:
        return _report(False, "ComfyUI client import", str(e))

    client = ComfyUIClient()
    reachable = client.health_check()
    if not _report(reachable, f"ComfyUI reachable at {client.base_url}"):
        print("      Start it with: cd ~/ComfyUI && source comfy-env/bin/activate && python main.py")
        return False

    checkpoint = os.environ.get("COMFYUI_CHECKPOINT", "sdxl_lightning_4step.safetensors")
    try:
        available = client.checkpoint_available(checkpoint)
    except Exception as e:
        return _report(False, f"Checkpoint {checkpoint!r} available", str(e))
    return _report(available, f"Checkpoint {checkpoint!r} available", "" if available else "not found in ComfyUI's checkpoints folder")


def check_workflow_template() -> bool:
    try:
        from comfyui_workflow import _load_template, validate_template
        validate_template(_load_template())
        return _report(True, "Workflow template valid (workflows/sdxl_lightning_api.json)")
    except Exception as e:
        return _report(False, "Workflow template valid", str(e))


def check_output_dir() -> bool:
    out_dir = os.environ.get("WORKER_OUTPUT_DIR", "work")
    try:
        os.makedirs(out_dir, exist_ok=True)
        test_file = os.path.join(out_dir, ".doctor_write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return _report(True, f"Output dir writable ({out_dir})")
    except Exception as e:
        return _report(False, f"Output dir writable ({out_dir})", str(e))


def check_groq_key() -> bool:
    present = bool(os.environ.get("GROQ_API_KEY", "").strip())
    return _report(present, "GROQ_API_KEY set", "" if present else "required for storyboard generation")


def main() -> int:
    print("ComfyUI visual provider -- local doctor\n")
    checks = [
        check_python(),
        check_binary("ffmpeg"),
        check_binary("ffprobe"),
        check_groq_key(),
        check_workflow_template(),
        check_comfyui(),
        check_output_dir(),
    ]
    print()
    if all(checks):
        print("All checks passed -- ready for VISUAL_STYLE=comfyui.")
        return 0
    print("One or more checks failed -- fix the items above before running with VISUAL_STYLE=comfyui.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
