"""
Uploads finished videos and sets custom thumbnails on YouTube using the YouTube Data API v3.

Auth uses a long-lived OAuth refresh token (generated once locally via
get_refresh_token.py) so the pipeline can run unattended in CI or background jobs.
"""

from __future__ import annotations

import os
from typing import Optional, List, Dict, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def _clean_token(val: Optional[str]) -> str:
    if not val:
        return ""
    return "".join(c for c in val.strip() if 32 < ord(c) < 127)


def _get_credentials():
    return Credentials(
        token=None,
        refresh_token=_clean_token(os.environ.get("YT_REFRESH_TOKEN", "")),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_clean_token(os.environ.get("YT_CLIENT_ID", "")),
        client_secret=_clean_token(os.environ.get("YT_CLIENT_SECRET", "")),
        scopes=SCOPES,
    )


def _get_youtube_client(channel_credentials: Optional[Dict[str, Any]] = None):
    if channel_credentials:
        creds = Credentials(
            token=None,
            refresh_token=_clean_token(channel_credentials.get("refresh_token", "")),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=_clean_token(channel_credentials.get("client_id", "")),
            client_secret=_clean_token(channel_credentials.get("client_secret", "")),
            scopes=SCOPES,
        )
    else:
        creds = _get_credentials()

    return build("youtube", "v3", credentials=creds)


def set_thumbnail(
    video_id: str,
    thumbnail_path: str,
    channel_credentials: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Uploads and applies a custom thumbnail to a specific YouTube video ID.
    Handles verification checks gracefully.
    """
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        print(f"[upload_youtube] ⚠️ Thumbnail file not found: {thumbnail_path}")
        return False

    try:
        youtube = _get_youtube_client(channel_credentials)
        print(f"[upload_youtube] Uploading custom thumbnail for video {video_id} ({os.path.basename(thumbnail_path)})...")

        media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg", resumable=True)
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
        print(f"[upload_youtube] ✓ Successfully set thumbnail for: https://www.youtube.com/watch?v={video_id}")
        return True
    except Exception as e:
        err_msg = str(e)
        if "does not have permission" in err_msg or "403" in err_msg:
            print(f"[upload_youtube] ⚠️ Permission Note: Channel must have phone verification enabled to upload custom thumbnails.")
            print(f"               Verify at: https://www.youtube.com/verify")
        else:
            print(f"[upload_youtube] ⚠️ Failed to set thumbnail for {video_id}: {e}")
        return False


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: List[str],
    thumbnail_path: Optional[str] = None,
    privacy_status: str = "public",
    category_id: str = "22",  # 'People & Blogs'
    channel_credentials: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Uploads a video to YouTube and automatically sets its custom thumbnail if provided.
    Returns the YouTube video ID.
    """
    youtube = _get_youtube_client(channel_credentials)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[upload_youtube] Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"[upload_youtube] Uploaded video: https://www.youtube.com/watch?v={video_id}")

    if thumbnail_path:
        set_thumbnail(video_id=video_id, thumbnail_path=thumbnail_path, channel_credentials=channel_credentials)

    return video_id


if __name__ == "__main__":
    print("Run via main.py with a real video path.")
