"""YouTube Shorts publisher using official YouTube Data API v3."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("streamclip.publish.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


@dataclass
class UploadResult:
    platform: str
    success: bool
    media_id: Optional[str] = None
    media_url: Optional[str] = None
    publish_at: Optional[str] = None
    error: Optional[str] = None
    is_dry_run: bool = False


class YouTubePublisher:
    """Uploads vertical videos directly to YouTube Shorts with SEO metadata and optional scheduling."""

    def __init__(
        self,
        client_secrets_path: Optional[str | Path] = None,
        credentials_cache: str | Path = ".credentials/youtube_token.json",
        privacy_status: str = "public",
        dry_run: bool = True,
    ):
        self.client_secrets_path = Path(client_secrets_path) if client_secrets_path else None
        self.credentials_cache = Path(credentials_cache)
        self.privacy_status = privacy_status
        self.dry_run = dry_run

    def upload_short(
        self,
        video_path: Path | str,
        title: str,
        description: str,
        tags: List[str],
        publish_at: Optional[str] = None,
    ) -> UploadResult:
        """Upload video file as a YouTube Short (optionally scheduled)."""
        video_path = Path(video_path)
        if not video_path.exists():
            return UploadResult(
                platform="youtube",
                success=False,
                error=f"Video file not found: {video_path}",
                is_dry_run=self.dry_run,
            )

        # Dry run guard
        if self.dry_run or not self.client_secrets_path or not self.client_secrets_path.exists():
            sched_str = f" [SCHEDULED: {publish_at}]" if publish_at else ""
            logger.info("[DRY RUN] Simulating YouTube Short upload%s for: %s", sched_str, title)
            mock_id = f"yt_short_{video_path.stem}"
            return UploadResult(
                platform="youtube",
                success=True,
                media_id=mock_id,
                media_url=f"https://youtube.com/shorts/{mock_id}",
                publish_at=publish_at,
                is_dry_run=True,
            )

        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = None
            if self.credentials_cache.exists():
                creds = Credentials.from_authorized_user_file(str(self.credentials_cache), SCOPES)

            if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secrets_path), SCOPES)
                creds = flow.run_local_server(port=0)
                self.credentials_cache.parent.mkdir(parents=True, exist_ok=True)
                with open(self.credentials_cache, "w") as token_file:
                    token_file.write(creds.to_json())

            youtube = build("youtube", "v3", credentials=creds)

            status_body = {
                "selfDeclaredMadeForKids": False,
            }
            if publish_at:
                # YouTube API requirement: scheduled videos must have privacyStatus='private'
                status_body["privacyStatus"] = "private"
                status_body["publishAt"] = publish_at
            else:
                status_body["privacyStatus"] = self.privacy_status

            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": "20",  # 20 = Gaming
                },
                "status": status_body,
            }

            media = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                resumable=True,
                chunksize=1024 * 1024 * 5,  # 5MB chunks
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info("Uploaded %d%% to YouTube", int(status.progress() * 100))

            video_id = response.get("id")
            return UploadResult(
                platform="youtube",
                success=True,
                media_id=video_id,
                media_url=f"https://youtube.com/shorts/{video_id}",
                is_dry_run=False,
            )

        except Exception as e:
            logger.error("YouTube upload failed: %s", e)
            return UploadResult(
                platform="youtube",
                success=False,
                error=str(e),
                is_dry_run=False,
            )
