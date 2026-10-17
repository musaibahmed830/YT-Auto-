"""
Channel Manager for Multi-Channel YouTube Automation.
Stores and manages credentials, niches, schedules, and upload history
for multiple connected YouTube channels using SQLite.
"""

import os
import sqlite3
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "channels.db")


def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes channels and upload history tables."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id TEXT PRIMARY KEY,
            channel_title TEXT NOT NULL,
            channel_id TEXT,
            channel_avatar TEXT,
            client_id TEXT NOT NULL,
            client_secret TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            niche TEXT DEFAULT 'General',
            schedule_times TEXT DEFAULT '06:00,18:00',
            privacy_status TEXT DEFAULT 'public',
            is_active INTEGER DEFAULT 1,
            total_uploads INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            channel_title TEXT NOT NULL,
            video_id TEXT NOT NULL,
            title TEXT NOT NULL,
            is_short INTEGER DEFAULT 0,
            episode_number INTEGER,
            youtube_url TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        )
    """)
    conn.commit()

    # If environment variables have a default channel and database is empty, auto-import it!
    cursor.execute("SELECT COUNT(*) as count FROM channels")
    if cursor.fetchone()["count"] == 0:
        def_rt = os.environ.get("YT_REFRESH_TOKEN", "").strip()
        def_cid = os.environ.get("YT_CLIENT_ID", "").strip()
        def_cs = os.environ.get("YT_CLIENT_SECRET", "").strip()
        if def_rt and def_cid and def_cs:
            add_channel(
                channel_title="Primary Channel",
                client_id=def_cid,
                client_secret=def_cs,
                refresh_token=def_rt,
                niche="Automation Series",
            )
    conn.close()


def add_channel(
    channel_title: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    niche: str = "General",
    schedule_times: str = "06:00,18:00",
    privacy_status: str = "public",
) -> dict:
    """
    Validates credentials with YouTube API, pulls channel info/avatar,
    and saves to database.
    """
    # Clean tokens
    client_id = "".join(c for c in client_id.strip() if 32 < ord(c) < 127)
    client_secret = "".join(c for c in client_secret.strip() if 32 < ord(c) < 127)
    refresh_token = "".join(c for c in refresh_token.strip() if 32 < ord(c) < 127)

    channel_id = None
    avatar = "https://www.youtube.com/s/desktop/f1722e1a/img/favicon_144x144.png"
    fetched_title = channel_title

    # Try to verify and fetch live channel info from YouTube API
    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"],
        )
        youtube = build("youtube", "v3", credentials=creds)
        resp = youtube.channels().list(part="snippet,statistics", mine=True).execute()
        items = resp.get("items", [])
        if items:
            channel_id = items[0]["id"]
            snippet = items[0]["snippet"]
            fetched_title = snippet.get("title") or channel_title
            avatar = snippet.get("thumbnails", {}).get("default", {}).get("url", avatar)
    except Exception as e:
        print(f"[channel_manager] Note: could not fetch live channel snippet ({e}), using default details.")

    conn = _get_connection()
    cursor = conn.cursor()
    record_id = channel_id or f"ch_{int(datetime.utcnow().timestamp())}"

    cursor.execute("""
        INSERT OR REPLACE INTO channels (
            id, channel_title, channel_id, channel_avatar,
            client_id, client_secret, refresh_token,
            niche, schedule_times, privacy_status, is_active,
            total_uploads, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
    """, (
        record_id, fetched_title, channel_id or record_id, avatar,
        client_id, client_secret, refresh_token,
        niche, schedule_times, privacy_status, datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

    return {
        "id": record_id,
        "channel_title": fetched_title,
        "channel_id": channel_id,
        "avatar": avatar,
        "niche": niche,
    }


def list_channels() -> list[dict]:
    """Returns list of all registered channels."""
    init_db()
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM channels ORDER BY created_at DESC")
    rows = cursor.fetchall()
    channels = []
    for r in rows:
        d = dict(r)
        # mask sensitive secret
        d["has_credentials"] = bool(d.get("refresh_token") and d.get("client_id"))
        d.pop("refresh_token", None)
        d.pop("client_secret", None)
        channels.append(d)
    conn.close()
    return channels


def get_channel(channel_id: str) -> dict | None:
    """Returns full channel record with credentials for uploading."""
    init_db()
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM channels WHERE id = ? OR channel_id = ?", (channel_id, channel_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def toggle_channel_status(channel_id: str, is_active: bool):
    """Activates or pauses automation for a specific channel."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE channels SET is_active = ? WHERE id = ?", (1 if is_active else 0, channel_id))
    conn.commit()
    conn.close()


def delete_channel(channel_id: str):
    """Removes a channel from the database."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()


def record_upload(
    channel_id: str,
    channel_title: str,
    video_id: str,
    title: str,
    is_short: bool = False,
    episode_number: int | None = None,
):
    """Logs an upload in history and increments channel counter."""
    conn = _get_connection()
    cursor = conn.cursor()
    yt_url = f"https://www.youtube.com/watch?v={video_id}"
    cursor.execute("""
        INSERT INTO upload_history (
            channel_id, channel_title, video_id, title,
            is_short, episode_number, youtube_url, uploaded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        channel_id, channel_title, video_id, title,
        1 if is_short else 0, episode_number, yt_url, datetime.utcnow().isoformat()
    ))
    cursor.execute("""
        UPDATE channels SET total_uploads = total_uploads + 1 WHERE id = ? OR channel_id = ?
    """, (channel_id, channel_id))
    conn.commit()
    conn.close()


def get_upload_history(limit: int = 50) -> list[dict]:
    """Retrieves recent upload history."""
    init_db()
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM upload_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    history = [dict(r) for r in rows]
    conn.close()
    return history
