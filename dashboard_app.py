"""
AutoTube AI - Multi-Channel Web Dashboard (FastAPI)
Provides a rich web interface and REST APIs to:
1. Connect and manage multiple YouTube channels (OAuth 2.0 & Manual Token entry).
2. Plan and edit multi-part story series (Main Videos + Shorts).
3. Watch video previews in the browser before or after uploading.
4. Monitor upload history and trigger instant or scheduled automated publishing.
"""

import os
import sys
import json
import sqlite3
import threading
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from channel_manager import (
    list_channels,
    add_channel,
    get_channel,
    toggle_channel_status,
    delete_channel,
    get_upload_history,
    record_upload,
    init_db,
)
from story_series import (
    load_series_state,
    plan_series,
    get_next_pending_episode,
    mark_episode_completed,
    ensure_scenes,
)
from assemble_video import assemble_synced_video
from generate_thumbnail import generate_thumbnail
from upload_youtube import upload_video

app = FastAPI(title="AutoTube AI Multi-Channel Studio", version="2.0.0")

# Setup directories
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
WORK_DIR = os.path.join(BASE_DIR, "work")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(WORK_DIR, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory background task status
TASK_STATE = {
    "is_running": False,
    "current_action": "Idle",
    "progress_percent": 0,
    "log_messages": [],
}


def log_msg(msg: str):
    print(f"[dashboard] {msg}")
    TASK_STATE["current_action"] = msg
    TASK_STATE["log_messages"].append(msg)
    if len(TASK_STATE["log_messages"]) > 50:
        TASK_STATE["log_messages"].pop(0)


# ── Schemas ──────────────────────────────────────────────────────────────────
class ChannelCreateRequest(BaseModel):
    channel_title: str
    client_id: str
    client_secret: str
    refresh_token: str
    niche: Optional[str] = "General"
    privacy_status: Optional[str] = "public"
    schedule_times: Optional[str] = "06:00,18:00"


class StoryPlanRequest(BaseModel):
    prompt: str
    episodes: int = 5


class RunEpisodeRequest(BaseModel):
    channel_id: Optional[str] = None  # None = default active channel, or specific ID
    episode_number: Optional[int] = None  # None = next pending


# ── Page Routes ──────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>AutoTube AI Dashboard</h1><p>Initializing static assets...</p>")


# ── Channel APIs ─────────────────────────────────────────────────────────────
@app.get("/api/channels")
def get_channels_endpoint():
    return {"channels": list_channels()}


@app.post("/api/channels")
def create_channel_endpoint(req: ChannelCreateRequest):
    try:
        res = add_channel(
            channel_title=req.channel_title,
            client_id=req.client_id,
            client_secret=req.client_secret,
            refresh_token=req.refresh_token,
            niche=req.niche or "General",
            schedule_times=req.schedule_times or "06:00,18:00",
            privacy_status=req.privacy_status or "public",
        )
        return {"success": True, "channel": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/channels/{channel_id}/toggle")
def toggle_channel_endpoint(channel_id: str, active: bool):
    toggle_channel_status(channel_id, active)
    return {"success": True}


@app.delete("/api/channels/{channel_id}")
def delete_channel_endpoint(channel_id: str):
    delete_channel(channel_id)
    return {"success": True}


# ── Google OAuth 2.0 Web Connect ──────────────────────────────────────────────
@app.get("/api/auth/google-url")
def get_google_oauth_url(request: Request):
    """
    Generates a Google OAuth 2.0 authorization URL allowing users to connect
    any YouTube channel with 1 click.
    """
    client_id = os.environ.get("YT_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(status_code=400, detail="YT_CLIENT_ID is not configured in .env")

    # Use current host as redirect URI
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth/callback"

    scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
    scope_str = "%20".join(scopes)

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={scope_str}&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    return {"auth_url": auth_url, "redirect_uri": redirect_uri}


@app.get("/auth/callback")
def handle_google_oauth_callback(request: Request, code: str):
    """Exchanges auth code for refresh token and auto-registers the channel."""
    import requests
    client_id = os.environ.get("YT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YT_CLIENT_SECRET", "").strip()
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth/callback"

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    resp = requests.post(token_url, data=data, timeout=30)
    if resp.status_code != 200:
        return HTMLResponse(f"<h3>OAuth Error:</h3><pre>{resp.text}</pre>")

    token_data = resp.json()
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        return HTMLResponse("<h3>Error: No refresh token returned. Did you approve offline access?</h3>")

    # Add channel
    add_channel(
        channel_title="Connected YouTube Channel",
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        niche="Story & Shorts",
    )
    return RedirectResponse(url="/?connected=1")


# ── Story Series APIs ─────────────────────────────────────────────────────────
@app.get("/api/series/status")
def get_series_endpoint():
    state = load_series_state()
    return {"state": state}


@app.post("/api/series/plan")
def plan_series_endpoint(req: StoryPlanRequest, background_tasks: BackgroundTasks):
    if TASK_STATE["is_running"]:
        raise HTTPException(status_code=400, detail="Another video rendering task is currently in progress.")

    def _plan_bg():
        TASK_STATE["is_running"] = True
        log_msg(f"Planning {req.episodes}-part series for: '{req.prompt[:50]}...'")
        try:
            plan_series(req.prompt, total_episodes=req.episodes)
            log_msg("Story planning complete!")
        except Exception as e:
            log_msg(f"Planning failed: {e}")
        finally:
            TASK_STATE["is_running"] = False

    background_tasks.add_task(_plan_bg)
    return {"success": True, "message": "Planning started in background."}


@app.post("/api/series/save")
def save_series_endpoint(updated_state: dict):
    state_file = os.path.join(BASE_DIR, "series_state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(updated_state, f, indent=2, ensure_ascii=False)
    return {"success": True}


# ── Execution & Video Generation ──────────────────────────────────────────────
def _execute_episode_task(channel_id: Optional[str] = None, episode_number: Optional[int] = None):
    TASK_STATE["is_running"] = True
    log_msg("Starting automated video generation...")
    try:
        # 1. Determine Channel
        target_ch = None
        if channel_id:
            target_ch = get_channel(channel_id)
        if not target_ch:
            # pick first active channel
            channels = [c for c in list_channels() if c.get("is_active")]
            if channels:
                target_ch = get_channel(channels[0]["id"])

        ch_title = target_ch.get("channel_title", "YouTube Channel") if target_ch else "Default Channel"
        log_msg(f"Target YouTube Channel: '{ch_title}'")

        # 2. Get Episode
        state = load_series_state()
        if not state or not state.get("episodes"):
            raise ValueError("No story series found. Please plan a story series first.")

        episode = None
        if episode_number:
            for ep in state["episodes"]:
                if ep.get("episode_number") == episode_number:
                    episode = ep
                    break
        else:
            episode = get_next_pending_episode()

        if not episode:
            raise ValueError("All episodes in this series have already been completed!")

        ep_num = episode["episode_number"]
        log_msg(f"Rendering Episode {ep_num}: '{episode.get('episode_title')}'")

        # 3. Render & Upload Long-Form Video (60s, 16:9)
        full_pkg = episode["full_script"]
        scenes_main = ensure_scenes(full_pkg)
        vid_main_path = os.path.join(OUTPUT_DIR, f"ep{ep_num}_main.mp4")
        thumb_path = os.path.join(OUTPUT_DIR, f"ep{ep_num}_thumb.jpg")

        log_msg(f"Assembling 16:9 Main Video ({len(scenes_main)} synced scenes)...")
        assemble_synced_video(
            scenes=scenes_main,
            title_text=full_pkg["title"],
            out_path=vid_main_path,
            work_dir=os.path.join(WORK_DIR, f"dash_ep{ep_num}_main"),
            orientation="horizontal",
            max_duration=90.0,
        )
        generate_thumbnail(vid_main_path, full_pkg["title"], thumb_path)

        main_vid_id = None
        if target_ch and target_ch.get("refresh_token"):
            log_msg(f"Uploading Main Video to '{ch_title}'...")
            main_vid_id = upload_video(
                video_path=vid_main_path,
                title=full_pkg["title"],
                description=full_pkg["description"],
                tags=full_pkg.get("tags", []),
                thumbnail_path=thumb_path,
                privacy_status=target_ch.get("privacy_status", "public"),
                channel_credentials=target_ch,
            )
            record_upload(
                channel_id=target_ch["id"],
                channel_title=ch_title,
                video_id=main_vid_id,
                title=full_pkg["title"],
                is_short=False,
                episode_number=ep_num,
            )

        # 4. Render & Upload YouTube Short (20s, 9:16)
        short_pkg = episode["short_script"]
        scenes_short = ensure_scenes(short_pkg)
        vid_short_path = os.path.join(OUTPUT_DIR, f"ep{ep_num}_short.mp4")

        log_msg(f"Assembling 9:16 YouTube Short ({len(scenes_short)} synced scenes)...")
        assemble_synced_video(
            scenes=scenes_short,
            title_text=short_pkg["title"],
            out_path=vid_short_path,
            work_dir=os.path.join(WORK_DIR, f"dash_ep{ep_num}_short"),
            orientation="vertical",
            max_duration=22.0,
        )

        short_vid_id = None
        if target_ch and target_ch.get("refresh_token"):
            log_msg(f"Uploading YouTube Short to '{ch_title}'...")
            short_title = short_pkg["title"]
            if "#shorts" not in short_title.lower():
                short_title = f"{short_title[:50]} #shorts"

            short_vid_id = upload_video(
                video_path=vid_short_path,
                title=short_title,
                description=short_pkg["description"],
                tags=short_pkg.get("tags", []) + ["shorts"],
                privacy_status=target_ch.get("privacy_status", "public"),
                channel_credentials=target_ch,
            )
            record_upload(
                channel_id=target_ch["id"],
                channel_title=ch_title,
                video_id=short_vid_id,
                title=short_title,
                is_short=True,
                episode_number=ep_num,
            )

        # Mark completed
        mark_episode_completed(ep_num, main_video_id=main_vid_id or "local_rendered", short_video_id=short_vid_id or "local_rendered")
        log_msg(f"🎉 Episode {ep_num} generation & upload finished successfully!")

    except Exception as e:
        log_msg(f"Error during video execution: {e}")
    finally:
        TASK_STATE["is_running"] = False


@app.post("/api/series/run-episode")
def run_episode_endpoint(req: RunEpisodeRequest, background_tasks: BackgroundTasks):
    if TASK_STATE["is_running"]:
        raise HTTPException(status_code=400, detail="A video rendering task is already running.")

    background_tasks.add_task(_execute_episode_task, req.channel_id, req.episode_number)
    return {"success": True, "message": "Episode generation started."}


# ── Status & History APIs ─────────────────────────────────────────────────────
@app.get("/api/task-status")
def get_task_status():
    return TASK_STATE


@app.get("/api/history")
def get_history_endpoint():
    return {"history": get_upload_history(50)}


@app.get("/api/video-stream/{filename}")
def stream_video_endpoint(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video file not found.")


@app.get("/api/system-health")
def get_system_health():
    return {
        "gemini_api_key": bool(os.environ.get("GEMINI_API_KEY")),
        "groq_api_key": bool(os.environ.get("GROQ_API_KEY")),
        "pexels_api_key": bool(os.environ.get("PEXELS_API_KEY")),
        "edge_tts": "Ready (100% Free Unlimited)",
        "connected_channels": len(list_channels()),
    }


if __name__ == "__main__":
    import uvicorn
    init_db()
    port = int(os.environ.get("PORT", 8000))
    print(f"\n=======================================================")
    print(f"🚀 AutoTube AI Studio Dashboard: http://localhost:{port}")
    print(f"=======================================================\n")
    uvicorn.run("dashboard_app:app", host="0.0.0.0", port=port, reload=True)
