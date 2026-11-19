"""StreamClip Command-Line Interface."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import StreamClipConfig
from src.pipeline import StreamClipPipeline

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def main():
    parser = argparse.ArgumentParser(
        description="StreamClip Auto: Turn YouTube streams into viral YouTube Shorts & Instagram Reels with split layout, center captions, and SEO."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: process
    proc_p = subparsers.add_parser("process", help="Process a stream URL or local video file")
    proc_p.add_argument("url", help="YouTube stream link (VOD/ended stream) or local MP4 path")
    proc_p.add_argument("--clips", type=int, default=3, help="Number of viral shorts to generate (default: 3)")
    proc_p.add_argument("--game", type=str, default="GTA 6", help="Game title (default: GTA 6)")
    proc_p.add_argument("--streamer", type=str, default=None, help="Streamer name")
    proc_p.add_argument("--facecam", choices=["auto", "top-left", "top-right", "bottom-left", "bottom-right"],
                        default="auto", help="Streamer facecam position (default: auto)")
    proc_p.add_argument("--publish", action="store_true", help="Publish directly to social handles (disables dry-run)")
    proc_p.add_argument("--config", type=str, default=None, help="Path to custom config YAML")

    # Command: demo
    demo_p = subparsers.add_parser("demo", help="Generate a synthetic gaming stream and run end-to-end demo")
    demo_p.add_argument("--duration", type=int, default=25, help="Synthetic stream duration in seconds (default: 25)")

    # Command: inspect
    info_p = subparsers.add_parser("info", help="Fetch stream metadata without processing")
    info_p.add_argument("url", help="YouTube stream URL")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "info":
        cfg = StreamClipConfig.load()
        pipeline = StreamClipPipeline(cfg)
        meta = pipeline.downloader.extract_info(args.url)
        table = Table(title="Stream Metadata", show_header=True)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Title", meta.title)
        table.add_row("Uploader", meta.uploader)
        table.add_row("Duration", f"{meta.duration / 60.0:.1f} minutes")
        table.add_row("Categories", ", ".join(meta.categories))
        console.print(table)
        return

    if args.command == "demo":
        from tests.synthetic_stream import create_synthetic_stream
        demo_dir = Path(".cache/streamclip/demo")
        demo_dir.mkdir(parents=True, exist_ok=True)
        demo_video = demo_dir / "synthetic_stream.mp4"
        console.print(Panel("[bold green]Generating synthetic GTA 6 style stream video with facecam & audio peaks...[/bold green]"))
        create_synthetic_stream(demo_video, duration_sec=args.duration)
        stream_target = str(demo_video)
        game = "GTA 6"
        streamer = "SpeedDemon"
        clips_count = 1
        facecam_mode = "auto"
        publish = False
    else:
        stream_target = args.url
        game = args.game
        streamer = args.streamer
        clips_count = args.clips
        facecam_mode = args.facecam
        publish = args.publish

    # Load configuration
    cfg = StreamClipConfig.load(args.config if hasattr(args, "config") else None)
    if facecam_mode != "auto":
        cfg.layout.facecam_mode = "preset"
        cfg.layout.facecam_preset = facecam_mode
    if publish:
        cfg.publishing.dry_run = False

    pipeline = StreamClipPipeline(cfg)
    console.print(Panel(f"[bold cyan]Starting StreamClip Automation[/bold cyan]\nTarget: {stream_target}\nGame: {game}"))

    result = pipeline.process_stream(
        stream_url_or_path=stream_target,
        max_clips=clips_count,
        game_title=game,
        streamer_name=streamer,
        auto_publish=publish,
    )

    console.print(Panel(f"[bold green]Successfully generated {len(result.shorts)} Viral Shorts![/bold green]"))

    for idx, s in enumerate(result.shorts, 1):
        table = Table(title=f"Short #{idx}: {s.clip_id}", show_header=True)
        table.add_column("Field", style="bold yellow")
        table.add_column("Details", style="white")
        table.add_row("Vertical Video (9:16)", str(s.video_path))
        table.add_row("Cover Thumbnail", str(s.thumbnail_path))
        table.add_row("Duration", f"{s.duration_sec:.1f}s")
        table.add_row("YouTube SEO Title", s.seo.youtube_title)
        table.add_row("YouTube Description", s.seo.youtube_description[:120] + "...")
        table.add_row("Instagram Caption", s.seo.instagram_caption[:120] + "...")
        table.add_row("YouTube Status", f"{s.youtube_result.media_url} (Dry-run: {s.youtube_result.is_dry_run})" if s.youtube_result else "Disabled")
        table.add_row("Instagram Status", f"{s.instagram_result.media_url} (Dry-run: {s.instagram_result.is_dry_run})" if s.instagram_result else "Disabled")
        console.print(table)


if __name__ == "__main__":
    main()
