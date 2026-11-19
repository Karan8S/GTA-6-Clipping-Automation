"""Standalone batch publisher & scheduler for generated Shorts & Reels.

Optimized for healthy channel growth:
- Enforces strict 2 Shorts/day release pacing.
- Uploads directly via YouTube Data API v3 with status.publishAt.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import StreamClipConfig
from src.publish.youtube_publisher import YouTubePublisher
from src.publish.instagram_publisher import InstagramPublisher
from src.publish.scheduler import ChannelGrowthScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("streamclip.publish_shorts")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Publish and schedule generated vertical Shorts & Reels with healthy growth pacing."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Directory containing generated shorts (defaults to newest in output/shorts/)",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        default=True,
        help="Schedule YouTube Shorts (2/day) instead of immediate public posting (default: True)",
    )
    parser.add_argument(
        "--immediate",
        action="store_true",
        help="Override scheduling and publish immediately as public",
    )
    parser.add_argument(
        "--shorts-per-day",
        type=int,
        default=2,
        help="Max shorts scheduled per day for healthy growth (default: 2)",
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default="Asia/Kolkata",
        help="Timezone for peak engagement windows (default: Asia/Kolkata)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate upload without publishing to live channels",
    )
    return parser.parse_args()


def find_shorts_dir(custom_dir: str | None) -> Path:
    if custom_dir:
        p = Path(custom_dir)
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified directory not found: {custom_dir}")

    base = Path("output/shorts")
    if not base.exists():
        raise FileNotFoundError("output/shorts/ directory does not exist. Run clipping pipeline first.")

    subdirs = [d for d in base.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if not subdirs:
        raise FileNotFoundError("No stream directories found in output/shorts/")

    # Pick the most recently modified directory
    subdirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return subdirs[0]


def main():
    args = parse_args()
    config = StreamClipConfig.load()

    out_dir = find_shorts_dir(args.dir)
    logger.info("Using Shorts directory: %s", out_dir)

    # Check YouTube credentials
    client_secrets = Path(config.publishing.youtube_client_secrets_path or "client_secrets.json")
    has_yt_creds = client_secrets.exists()
    has_ig_creds = bool(config.publishing.instagram_account_id and config.publishing.instagram_access_token)

    is_dry_run = args.dry_run or (not has_yt_creds and not has_ig_creds)

    print("\n==========================================")
    print("STREAMCLIP AUTO-PUBLISH & SCHEDULER")
    print(f"Target Directory: {out_dir}")
    print(f"YouTube Client Secrets ({client_secrets}): {'READY' if has_yt_creds else 'MISSING (Using Dry Run)'}")
    print(f"Instagram Account ID & Token: {'READY' if has_ig_creds else 'NOT CONFIGURED'}")
    print(f"Execution Mode: {'DRY RUN' if is_dry_run else 'LIVE PRODUCTION'}")
    print("==========================================\n")

    # Discover YouTube bundles
    yt_bundles = sorted(out_dir.glob("short_*_youtube_bundle.json"))
    if not yt_bundles:
        # Fallback to any metadata files
        yt_bundles = sorted(out_dir.glob("short_*_metadata.json"))

    if not yt_bundles:
        print(f"No shorts bundles found in {out_dir}")
        return 1

    use_scheduling = args.schedule and not args.immediate
    scheduler = ChannelGrowthScheduler(
        shorts_per_day=args.shorts_per_day,
        timezone_str=args.timezone,
        start_days_ahead=1,
    )
    schedule_slots = scheduler.generate_plan(len(yt_bundles)) if use_scheduling else []

    if use_scheduling:
        print(scheduler.format_plan_table(schedule_slots))
        print()

    yt_publisher = YouTubePublisher(
        client_secrets_path=client_secrets if has_yt_creds else None,
        credentials_cache=config.publishing.youtube_credentials_cache,
        privacy_status="private" if use_scheduling else config.publishing.youtube_privacy_status,
        dry_run=is_dry_run,
    )

    results = []
    for idx, bundle_p in enumerate(yt_bundles):
        data = json.loads(bundle_p.read_text(encoding="utf-8"))
        clip_id = data.get("clip_id", bundle_p.stem)
        video_p = data.get("video_path") or str(out_dir / f"{clip_id}_vertical.mp4")
        title = data.get("title") or (data.get("seo", {}).get("youtube_title"))
        desc = data.get("description") or (data.get("seo", {}).get("youtube_description", ""))
        tags = data.get("tags") or (data.get("seo", {}).get("youtube_tags", []))

        slot = schedule_slots[idx] if schedule_slots and idx < len(schedule_slots) else None
        publish_at = slot.publish_at_iso if slot else None

        print(f"\n>>> Processing {clip_id}: {title}")
        if slot:
            print(f"    Scheduled for: {slot.local_datetime.strftime('%Y-%m-%d %I:%M %p %Z')} ({slot.slot_label})")

        res = yt_publisher.upload_short(
            video_path=video_p,
            title=title,
            description=desc,
            tags=tags,
            publish_at=publish_at,
        )

        status_str = "SUCCESS" if res.success else "FAILED"
        sched_note = f" [Scheduled: {res.publish_at}]" if res.publish_at else ""
        print(f"    YouTube Result: {status_str} -> {res.media_url}{sched_note}")
        if res.error:
            print(f"    Error: {res.error}")

        results.append({"clip": clip_id, "title": title, "result": res})

    print("\n==========================================")
    print("ALL SCHEDULED UPLOADS PROCESSED!")
    print("==========================================")
    for r in results:
        res = r["result"]
        sched = f" | Scheduled: {res.publish_at}" if res.publish_at else ""
        print(f"• {r['clip']}: {res.media_url}{sched}")
    print("==========================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
