# ComfyUI local-visual-provider integration plan

## What this repo actually is (inspected before writing this plan)

`YT-Auto-` is a single-user, single-channel Python pipeline triggered by
GitHub Actions (`.github/workflows/daily_video.yml`) on a daily cron plus
manual `workflow_dispatch`. There is no website, no authentication, no
database, and no Vercel deployment in this repo -- those exist in a
separate project (`yt-auto-saas`, Next.js + Supabase). This plan is
written for the repo as it actually exists.

Existing pipeline (`main.py`, `src/`):

1. `trend_fetch.resolve_topic()` -- pick a topic (trending/category/custom)
2. `seo_research.research_keywords()` -- real search-phrase data
3. `generate_script.generate_script()` -- Groq call -> title/description/
   tags/narration/`visual_keywords`, language-aware (`src/languages.py`)
4. `generate_voiceover.generate_voiceover()` -- Piper TTS, per-language voice
5. Visual step, already an existing provider abstraction via the
   `VISUAL_STYLE` env var:
   - `"stock"` (default) -> `fetch_visuals.fetch_clips()` (Pexels)
   - `"ai_illustration"` -> `generate_illustrations.generate_illustrations()`
     (Pollinations.ai, free, keyless), with an optional
     `CUSTOM_VISUAL_PROMPT` override and per-clip motion presets
6. `assemble_video.assemble_video()` -- ffmpeg: normalize clips to a
   shared fps, crossfade between scenes, burn in title + dramatic
   captions derived from the narration, mux the voiceover
7. `generate_thumbnail.generate_thumbnail()`
8. `upload_youtube.upload_video()`

This plan adds a **third visual provider, `"comfyui"`**, following the
exact same shape as the existing two (a function that returns a list of
local `.mp4` clip paths, called from `main.py`'s existing branch).

## The one architectural constraint that reshapes the original spec

The requested design (website creates a job -> local Mac worker polls and
claims it -> worker calls ComfyUI at `127.0.0.1:8188`) exists to solve a
real problem: GitHub's cloud runners and a residential Mac cannot reach
each other directly, so a durable, internet-reachable coordination point
(a database + API) is required in between. That coordination layer only
exists in the *other* project (`yt-auto-saas`), not here.

Since this repo has no website/database, and ComfyUI must never be
exposed publicly (per the original spec, correctly), **`visual_style=comfyui`
can only run when `main.py` is executed directly on the same Mac that is
running ComfyUI** -- not via the GitHub Actions cron/dispatch, which runs
on GitHub's cloud runners and can never reach `127.0.0.1:8188` on your
machine. The daily scheduled workflow keeps using `stock`/`ai_illustration`
exactly as today, unaffected. `comfyui` is a **local-only run mode**,
started from your own Terminal.

Concretely, the phases from the original 16-phase spec that assumed a
website/database (job queue table, `/api/video-jobs` routes, worker-claim
endpoints, dashboard progress UI) do not apply to this repo and are not
built here -- there is nothing on this side for them to attach to. If/when
this should also work from `yt-auto-saas`, that integration is a
separate, later piece of work in that project.

## What's actually built here

- `src/comfyui_client.py` -- typed client for `/prompt`, `/history/{id}`,
  `/view`, `/queue`, `/object_info`, with timeouts, bounded retries for
  network errors (not for permanent/validation errors), and output-file
  path-traversal prevention.
- `workflows/sdxl_lightning_api.json` -- trusted ComfyUI API-format graph
  (`CheckpointLoaderSimple` -> `CLIPTextEncode` x2 -> `EmptyLatentImage`
  -> `KSampler` -> `VAEDecode` -> `SaveImage`), no custom nodes required.
  `src/comfyui_workflow.py` holds the node-role mapping (positive prompt /
  negative prompt / latent size / sampler / save node) so nothing depends
  on hard-coded node IDs scattered through the codebase, and validates the
  loaded template before every submission.
- `src/storyboard.py` -- reuses the existing Groq client/key handling to
  turn a topic + narration into a strict 6-scene JSON storyboard (schema
  validated, one malformed-JSON repair attempt, safe failure after that).
- `src/generate_comfyui_images.py` -- same public shape as
  `generate_illustrations.generate_illustrations()`: takes prompts, returns
  local clip paths (still image -> Ken Burns motion clip, alternating
  movement per scene, reusing the same ffmpeg motion-preset code already
  used by the illustration provider).
- `main.py` -- new `VISUAL_STYLE=comfyui` branch; still just three
  well-known values (`stock` / `ai_illustration` / `comfyui`), no
  user-controlled provider values reach ffmpeg or ComfyUI.
- `.github/workflows/daily_video.yml` -- `comfyui` added to the
  `visual_style` choice list for documentation/consistency, with an
  explicit description noting it only works on a local manual run, never
  on the actual scheduled/Actions-triggered run (Actions cannot reach it).
- `scripts/comfyui_doctor.py` -- local-only diagnostic: Python version,
  ffmpeg/ffprobe presence, ComfyUI reachability, checkpoint presence via
  `/object_info`, output-dir write access.
- `scripts/comfyui_smoke_test.py` -- generates one real test image
  through the trusted workflow and prints the saved path; no production
  credentials required.
- Security: only prompt strings + a small set of validated numeric
  settings are injected into the trusted workflow template -- the workflow
  graph itself, checkpoint name, and node structure are never
  user-controlled; output filenames are sanitized against path traversal;
  prompt length is capped; scene count is fixed at 6.
- Docs: `docs/comfyui-local-worker.md` (exact macOS run instructions +
  troubleshooting), README gets a short pointer to it.

## Limitations, stated plainly

- `comfyui` mode does not run on the daily cron or `workflow_dispatch` --
  both execute on GitHub's cloud runners, which cannot reach your Mac.
  It only runs when you invoke `main.py` yourself, locally, with ComfyUI
  already running.
- No job-queue database, no dashboard, no multi-user support -- this repo
  is single-user by design, matching everything else in it.
- I cannot execute your actual ComfyUI instance from here (it's on your
  machine, not reachable from this environment) -- everything is built
  and syntax/schema-validated on my end; the real end-to-end image
  generation needs to be smoke-tested by you with the provided script.
