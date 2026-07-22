# Running the ComfyUI visual providers locally

`VISUAL_STYLE` supports two local-ComfyUI providers instead of Pexels
stock footage or Pollinations illustrations:

- **`image_slideshow`** ("AI Image Slideshow -- faster"): SDXL-Lightning
  generates one photorealistic still image per scene; ffmpeg pans/zooms
  over it (Ken Burns). This is the original `comfyui` provider, renamed.
- **`cinematic_video`** ("AI Cinematic Video -- real movement, slower"):
  the same SDXL starting image per scene, then a local **Wan2.1 VACE
  1.3B** image-to-video pass animates it into a real moving 3-4 second
  clip -- actual subject/environment/camera motion, not a pan over a
  still frame. Needs extra model downloads -- see below.
- **`auto`**: tries `cinematic_video` first, falls back to
  `image_slideshow` if the Wan models/nodes aren't installed or ComfyUI
  is unreachable, and logs which provider actually ran. If
  `cinematic_video` is selected explicitly, it never silently falls back
  -- the job fails with a clear reason instead.

**ComfyUI must be running on the same machine that executes `main.py`**
for any of these -- GitHub-hosted cloud runners (`runs-on: ubuntu-latest`)
can never reach `127.0.0.1:8188` on your Mac, so none of these modes ever
work via `daily_video.yml`'s cron or "Run workflow" button; see
`docs/comfyui-integration-plan.md` for why.

There are two ways to actually run it:

- **Option A -- your own Terminal** (simplest, described in steps 1-9
  below): you type the command yourself, on your Mac.
- **Option B -- trigger from GitHub's website, still runs on your Mac**
  (see "Running via a self-hosted GitHub Actions runner" further down):
  a small GitHub-provided agent runs on your Mac and pulls jobs from
  GitHub, so clicking "Run workflow" on github.com actually executes
  locally where ComfyUI lives -- without ever exposing ComfyUI publicly.

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
export PEXELS_API_KEY=...       # not used by these providers, but still required at startup
export YT_CLIENT_ID=...
export YT_CLIENT_SECRET=...
export YT_REFRESH_TOKEN=...
export VISUAL_STYLE=image_slideshow   # or cinematic_video, or auto
export COMFYUI_BASE_URL=http://127.0.0.1:8188   # default, only change if you changed ComfyUI's port
export COMFYUI_CHECKPOINT=sdxl_lightning_4step.safetensors

# Only needed for VISUAL_STYLE=cinematic_video or auto:
export COMFYUI_WAN_UNET=wan2.1_vace_1.3B_fp16.safetensors
export COMFYUI_WAN_CLIP=umt5_xxl_fp8_e4m3fn_scaled.safetensors
export COMFYUI_WAN_VAE=wan_2.1_vae.safetensors
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

## 8. (Only for `cinematic_video`/`auto`) Download the Wan2.1 VACE models

`cinematic_video` needs three additional model files placed in your
ComfyUI install (**not** the SDXL-Lightning checkpoint used above):

| File | ComfyUI folder |
|---|---|
| `wan2.1_vace_1.3B_fp16.safetensors` | `ComfyUI/models/diffusion_models/` |
| `wan_2.1_vae.safetensors` | `ComfyUI/models/vae/` |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `ComfyUI/models/text_encoders/` |

Download these from the official Wan2.1 VACE 1.3B release, place them in
the folders above, then restart ComfyUI. This is deliberately the
**1.3B VACE** model (not Wan2.1-T2V-1.3B, and not any Wan2.2 14B/5B
variant) -- it's the one sized to actually run image-to-video on a Mac
M1 with 16GB unified memory. Wan2.2 TI2V 5B is a possible future upgrade
once you have more headroom, not something to switch to now.

Once the files are in place, confirm everything end to end:

```bash
python scripts/comfyui_doctor.py --cinematic
python scripts/comfyui_i2v_test.py
```

`comfyui_i2v_test.py` uses (or generates) one test image, animates it
through the real trusted Wan workflow, and verifies via `ffprobe` that
the result is an actual multi-frame video with non-zero duration --
saved to `test_output/comfyui_i2v_test.mp4`. **Run this and confirm it
succeeds before relying on `VISUAL_STYLE=cinematic_video` for a real
video job** -- it's the fastest way to catch a missing model or an
incompatible ComfyUI version without burning a full pipeline run.

## 9. Run a full video with ComfyUI visuals

```bash
caffeinate -dims python main.py
```

(with `VISUAL_STYLE=image_slideshow`, `cinematic_video`, or `auto`
exported as above). Watch the terminal -- it prints each of the 7
pipeline steps, plus `STATE: ...` markers (`generating_storyboard`,
`generating_scene_images`, `animating_scene_N_of_6`,
`rendering_final_video`, `uploading`, `completed`) and, for `cinematic_video`
scenes, which images/videos actually generated.

## Running via a self-hosted GitHub Actions runner

This lets you click **"Run workflow"** on github.com and have it actually
execute on your Mac (where ComfyUI lives), instead of GitHub's cloud
servers. Your Mac connects *out* to GitHub over HTTPS to pull jobs --
nothing is opened or exposed publicly, and ComfyUI itself is never
reachable from the internet.

### One-time setup

1. On github.com, go to your repo -> **Settings -> Actions -> Runners ->
   New self-hosted runner**, choose **macOS** and your chip (**ARM64**
   for M1). GitHub shows you an exact, pre-filled set of `curl`/`tar`/
   `config.sh` commands with a short-lived registration token already
   included -- copy and run those exactly as shown (they're generated
   fresh per-visit, so don't reuse commands from documentation or an old
   screenshot).
2. When `config.sh` asks for labels, you can accept the default.
3. Start it so it keeps running (pick one):
   - Foreground, for testing: `./run.sh` (leave that terminal tab open)
   - As a persistent background service (recommended):
     ```bash
     ./svc.sh install
     ./svc.sh start
     ```
4. Add the same repository secrets this project already uses (Settings ->
   Secrets and variables -> Actions): `GROQ_API_KEY`, `PEXELS_API_KEY`,
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`. These work
   identically on a self-hosted runner.
5. Optional: if your ComfyUI or checkpoint use non-default names, add
   repository **Variables** (not secrets -- these aren't sensitive)
   `COMFYUI_BASE_URL` and `COMFYUI_CHECKPOINT`.

### Using it

1. Make sure ComfyUI is running locally (step 1 above) and the runner
   service is started (step 3 above).
2. On github.com: **Actions -> ComfyUI Cinematic Video (self-hosted) ->
   Run workflow**, fill in the topic/category/video mode/language
   inputs, and run it.
3. The job appears in the Actions tab same as any other run, but its
   logs are actually streaming from your own Mac.

### Security notes

- This repo is **private**, which is what makes a self-hosted runner
  reasonably safe here -- GitHub explicitly warns against self-hosted
  runners on *public* repos, since anyone who can open a pull request
  could get arbitrary code executed on the runner's machine. Keep this
  repo private for as long as you use a self-hosted runner.
- Only people with write access to the repo can trigger
  `workflow_dispatch`, so only you (or trusted collaborators) can start a
  job on your Mac.
- The runner registration token shown by GitHub is short-lived and
  single-use -- there's nothing to keep secret about it after setup.
- If you ever stop wanting a self-hosted runner registered, remove it
  from Settings -> Actions -> Runners, and run `./svc.sh uninstall` (or
  stop `run.sh`) on your Mac.

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

**"No such filter: 'drawtext'" during video assembly**
Homebrew's plain `ffmpeg` formula is built *without* `libfreetype` /
`fontconfig` / `libass`, so it has no `drawtext` filter -- the title card
and captions this pipeline burns in both need it. Switch to the fuller
build (already in homebrew-core, no extra tap needed):

```bash
brew install ffmpeg-full
brew unlink ffmpeg
brew link --overwrite ffmpeg-full
ffmpeg -filters | grep drawtext   # should now print a line
```

`comfyui_doctor.py` checks for this explicitly (`ffmpeg drawtext filter
available`) so it's caught before a full run starts.

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

**`cinematic_video`: "missing required node type(s)"**
Your ComfyUI version predates native Wan2.1 VACE support (the
`WanVaceToVideo`/`TrimVideoLatent`/`ModelSamplingSD3`/`CreateVideo`/
`SaveVideo` node types). Update ComfyUI to a recent release, then
re-run `python scripts/comfyui_doctor.py --cinematic`.

**`cinematic_video`: "missing required model file(s)"**
`comfyui_doctor.py --cinematic` and `wan_dependencies.py` print the exact
filename and destination folder for whatever's missing -- see the table
in step 8 above. Place the file, restart ComfyUI, and re-run the check.

**`cinematic_video` is very slow / seems stuck**
Wan2.1 VACE 1.3B image-to-video is much heavier than the SDXL-Lightning
still-image pass -- expect several minutes per scene on an M1 with 16GB
unified memory, and longer on the first scene while the model loads.
Scenes are generated strictly one at a time on purpose (never run
concurrently) to stay within that memory budget. Watch the ComfyUI
terminal/web UI queue view for real progress; if it looks genuinely
hung, check Activity Monitor for memory pressure and avoid running other
heavy apps during a `cinematic_video` job.

**`cinematic_video` explicitly selected but the job fails instead of falling back**
This is intentional: unlike `auto`, explicitly selecting `cinematic_video`
never silently substitutes the image slideshow. Fix the reported
dependency/availability issue, or switch to `image_slideshow`/`auto` if a
partial-quality fallback is acceptable for that run.
