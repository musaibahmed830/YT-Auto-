# Running the ComfyUI visual provider locally

`VISUAL_STYLE=comfyui` generates cinematic scene images with a local
ComfyUI (SDXL-Lightning) instance instead of Pexels stock footage or
Pollinations illustrations. **This only works when `main.py` is run
directly on the same Mac that's running ComfyUI** -- GitHub Actions'
cloud runners cannot reach `127.0.0.1:8188` on your machine, so this mode
never works via the daily cron or the "Run workflow" button on GitHub;
see `docs/comfyui-integration-plan.md` for why.

## 1. Start ComfyUI

```bash
cd ~/ComfyUI
source comfy-env/bin/activate
python main.py
```

## 2. Verify it's up

Open **http://127.0.0.1:8188** in a browser -- you should see the ComfyUI
node editor load.

## 3. Configure environment variables

Copy `.env.example` (or export directly in your shell) with at least:

```bash
export GROQ_API_KEY=...
export PEXELS_API_KEY=...       # not used by comfyui mode, but still required at startup
export YT_CLIENT_ID=...
export YT_CLIENT_SECRET=...
export YT_REFRESH_TOKEN=...
export VISUAL_STYLE=comfyui
export COMFYUI_BASE_URL=http://127.0.0.1:8188   # default, only change if you changed ComfyUI's port
export COMFYUI_CHECKPOINT=sdxl_lightning_4step.safetensors
```

## 4. Install Python dependencies (first time only)

```bash
pip install -r requirements.txt
```

## 5. Keep your Mac awake during a run

Video generation can take a few minutes; macOS sleeping mid-run will kill
the ComfyUI connection. Prefix your run with `caffeinate`:

```bash
caffeinate -dims python main.py
```

## 6. Run the doctor check

```bash
python scripts/comfyui_doctor.py
```

This confirms: Python version, ffmpeg/ffprobe present, `GROQ_API_KEY` set,
the trusted workflow template is valid, ComfyUI is reachable, your
configured checkpoint is actually installed, and the output directory is
writable. Fix anything it flags before continuing.

## 7. Run the isolated smoke test

```bash
python scripts/comfyui_smoke_test.py
```

Generates one real test image ("a cinematic rainy city street at night...")
through the actual trusted workflow and prints where it saved the file --
no Groq call, no video assembly, no YouTube upload. This is the fastest
way to confirm ComfyUI + your checkpoint actually work end to end before
running a full video job.

## 8. Run a full video with ComfyUI visuals

```bash
caffeinate -dims python main.py
```

(with `VISUAL_STYLE=comfyui` exported as above). Watch the terminal --
it prints each of the 7 pipeline steps, including scene-by-scene ComfyUI
generation progress.

## Troubleshooting

**"ComfyUI is not reachable"**
ComfyUI isn't running, or is on a different port than `COMFYUI_BASE_URL`
points to. Start it (step 1) and re-run `comfyui_doctor.py`.

**"Checkpoint ... not found"**
Confirm the file actually exists at
`~/ComfyUI/models/checkpoints/sdxl_lightning_4step.safetensors`, and that
`COMFYUI_CHECKPOINT` matches the exact filename ComfyUI sees it as (check
via the ComfyUI web UI's checkpoint dropdown, or `comfyui_doctor.py`'s
output).

**Workflow validation error**
Something in `workflows/sdxl_lightning_api.json` was edited and no longer
matches the expected node/class_type shape `comfyui_workflow.py` checks
for. Restore it from git (`git checkout -- workflows/sdxl_lightning_api.json`)
rather than hand-editing it.

**ffmpeg missing**
Install it (e.g. `brew install ffmpeg`) -- `comfyui_doctor.py` will flag
this explicitly.

**Job seems stuck / very slow**
SDXL-Lightning at 4 steps is fast on Apple Silicon, but a first run also
has to load the checkpoint into memory -- watch the ComfyUI terminal/web
UI queue view for actual progress. If it's genuinely hung, check
Activity Monitor for memory pressure (16GB unified memory is enough for
SDXL-Lightning at the configured 576x1024, but avoid running other heavy
apps at the same time).

**"Unauthorized" / GROQ_API_KEY errors**
Storyboard generation reuses your existing Groq key -- confirm
`GROQ_API_KEY` is exported in the same shell you're running `main.py` from.

**Mac went to sleep mid-run**
Re-run with `caffeinate -dims` prefixed (step 5) -- without it, macOS can
suspend the process and silently stall the ComfyUI connection.

**Image generation timeout**
The smoke test and full pipeline both use a 120-second per-scene timeout.
If your Mac is under heavy load or a very large checkpoint variant is
swapped in, generation can occasionally exceed this -- rerun once
conditions are less loaded.
