"""
Uploads a finished video to YouTube using the YouTube Data API v3.

Auth uses a long-lived OAuth refresh token (generated once locally via
get_refresh_token.py) so the pipeline can run unattended in CI.
"""

import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from _sanitize import sanitize_credential

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_credentials():
    return Credentials(
        token=None,
        refresh_token=sanitize_credential(os.environ["YT_REFRESH_TOKEN"]),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=sanitize_credential(os.environ["YT_CLIENT_ID"]),
        client_secret=sanitize_credential(os.environ["YT_CLIENT_SECRET"]),
        scopes=SCOPES,
    )


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    thumbnail_path: str | None = None,
    privacy_status: str = "public",
    category_id: str = "22",  # "People & Blogs"; change to fit your niche
):
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

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
    print(f"[upload_youtube] Uploaded: https://www.youtube.com/watch?v={video_id}")

    if thumbnail_path:
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path)).execute()

    return video_id


if __name__ == "__main__":
    print("Run via main.py with a real video path.")
