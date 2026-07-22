# Running the ComfyUI visual provider locally

`VISUAL_STYLE=comfyui` generates cinematic scene images with a local
ComfyUI (SDXL-Lightning) instance instead of Pexels stock footage or
Pollinations illustrations. **ComfyUI must be running on the same
machine that executes `main.py`** -- GitHub-hosted cloud runners
(`runs-on: ubuntu-latest`) can never reach `127.0.0.1:8188` on your Mac,
so this mode never works via `daily_video.yml`'s cron or "Run workflow"
button; see `docs/comfyui-integration-plan.md` for why.

There are two ways to actually run it:

- **Option A -- your own Terminal** (simplest, described in steps 1-8
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
