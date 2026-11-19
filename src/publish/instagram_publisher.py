"""Instagram Reels publisher using Instagram Graph API."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional
import requests

from src.publish.youtube_publisher import UploadResult

logger = logging.getLogger("streamclip.publish.instagram")


class InstagramPublisher:
    """Publishes vertical video clips to Instagram Reels via the Meta Graph API."""

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_token: Optional[str] = None,
        dry_run: bool = True,
    ):
        self.account_id = account_id
        self.access_token = access_token
        self.dry_run = dry_run
        self.base_url = "https://graph.facebook.com/v21.0"

    def upload_reel(
        self,
        video_path: Path | str,
        caption: str,
        public_video_url: Optional[str] = None,
    ) -> UploadResult:
        """Publish a vertical video to Instagram Reels."""
        video_path = Path(video_path)
        if not video_path.exists():
            return UploadResult(
                platform="instagram",
                success=False,
                error=f"Video file not found: {video_path}",
                is_dry_run=self.dry_run,
            )

        # Always save an Instagram export bundle locally
        bundle_path = video_path.parent / f"{video_path.stem}_instagram_bundle.json"
        bundle_data = {
            "video_path": str(video_path.resolve()),
            "caption": caption,
            "account_id": self.account_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        bundle_path.write_text(json.dumps(bundle_data, indent=2), encoding="utf-8")

        # Dry run guard
        if self.dry_run or not self.account_id or not self.access_token:
            logger.info("[DRY RUN] Simulating Instagram Reel publish for: %s", video_path.name)
            mock_id = f"ig_reel_{video_path.stem}"
            return UploadResult(
                platform="instagram",
                success=True,
                media_id=mock_id,
                media_url=f"https://instagram.com/reel/{mock_id}",
                is_dry_run=True,
            )

        try:
            # Resumable direct byte upload (no public video URL needed)
            file_size = video_path.stat().st_size
            container_endpoint = f"{self.base_url}/{self.account_id}/media"

            if public_video_url:
                container_payload = {
                    "media_type": "REELS",
                    "video_url": public_video_url,
                    "caption": caption,
                    "access_token": self.access_token,
                }
                res = requests.post(container_endpoint, data=container_payload, timeout=30)
                res_data = res.json()
                if "id" not in res_data:
                    return UploadResult(platform="instagram", success=False, error=f"Container creation failed: {res.text}")
                creation_id = res_data["id"]
            else:
                # Step 1: Initialize resumable container
                init_payload = {
                    "media_type": "REELS",
                    "upload_type": "resumable",
                    "caption": caption,
                    "access_token": self.access_token,
                }
                init_res = requests.post(container_endpoint, data=init_payload, timeout=30)
                init_data = init_res.json()
                if "id" not in init_data or "uri" not in init_data:
                    return UploadResult(
                        platform="instagram",
                        success=False,
                        error=f"Resumable container init failed: {init_res.text}",
                    )
                creation_id = init_data["id"]
                upload_uri = init_data["uri"]

                # Step 2: Upload raw video bytes directly
                with open(video_path, "rb") as vf:
                    upload_headers = {
                        "Authorization": f"OAuth {self.access_token}",
                        "offset": "0",
                        "file_size": str(file_size),
                    }
                    up_res = requests.post(upload_uri, headers=upload_headers, data=vf, timeout=120)
                    if up_res.status_code not in (200, 201):
                        return UploadResult(
                            platform="instagram",
                            success=False,
                            error=f"Binary video upload failed ({up_res.status_code}): {up_res.text}",
                        )

            logger.info("Instagram Reels container ID: %s. Polling for readiness...", creation_id)

            # Step 2: Poll container status
            status_endpoint = f"{self.base_url}/{creation_id}?fields=status_code&access_token={self.access_token}"
            for _ in range(30):  # poll up to 2.5 minutes
                time.sleep(5)
                stat_res = requests.get(status_endpoint, timeout=15)
                stat_data = stat_res.json()
                status = stat_data.get("status_code")
                if status == "FINISHED":
                    break
                elif status == "ERROR":
                    return UploadResult(
                        platform="instagram",
                        success=False,
                        error=f"Instagram video processing error: {stat_res.text}",
                    )

            # Step 3: Publish container
            publish_endpoint = f"{self.base_url}/{self.account_id}/media_publish"
            publish_res = requests.post(
                publish_endpoint,
                data={"creation_id": creation_id, "access_token": self.access_token},
                timeout=30,
            )
            pub_data = publish_res.json()
            if "id" in pub_data:
                published_id = pub_data["id"]
                return UploadResult(
                    platform="instagram",
                    success=True,
                    media_id=published_id,
                    media_url=f"https://instagram.com/reel/{published_id}",
                    is_dry_run=False,
                )
            else:
                return UploadResult(
                    platform="instagram",
                    success=False,
                    error=f"Instagram media_publish failed: {publish_res.text}",
                )

        except Exception as e:
            logger.error("Instagram publish failed: %s", e)
            return UploadResult(
                platform="instagram",
                success=False,
                error=str(e),
                is_dry_run=False,
            )
