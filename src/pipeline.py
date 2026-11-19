"""StreamClip Master Pipeline: Automates stream clipping, vertical formatting, SEO & publishing."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.analysis.face_tracker import FaceTracker
from src.analysis.highlight_detector import HighlightCandidate, HighlightDetector
from src.composer.subtitles import SubtitleGenerator
from src.composer.video_composer import VideoComposer
from src.config import StreamClipConfig
from src.ingest.downloader import StreamDownloader, StreamMetadata
from src.publish.instagram_publisher import InstagramPublisher
from src.publish.youtube_publisher import UploadResult, YouTubePublisher
from src.publish.scheduler import ChannelGrowthScheduler, ScheduleSlot
from src.seo.metadata_generator import SEOGenerator, ShortSEOMetadata

logger = logging.getLogger("streamclip.pipeline")


@dataclass
class ProcessedShort:
    clip_id: str
    video_path: Path
    thumbnail_path: Path
    subtitles_path: Path
    start_sec: float
    end_sec: float
    duration_sec: float
    transcript: str
    seo: ShortSEOMetadata
    youtube_result: Optional[UploadResult] = None
    instagram_result: Optional[UploadResult] = None


@dataclass
class PipelineResult:
    stream_metadata: StreamMetadata
    shorts: List[ProcessedShort] = field(default_factory=list)


class StreamClipPipeline:
    """End-to-end automated pipeline from stream URL to published Shorts/Reels."""

    def __init__(self, config: Optional[StreamClipConfig] = None):
        self.config = config or StreamClipConfig.load()
        self.downloader = StreamDownloader(cache_dir=self.config.work_dir)
        self.highlight_detector = HighlightDetector()
        self.face_tracker = FaceTracker()
        self.subtitle_generator = SubtitleGenerator(self.config.subtitles)
        self.video_composer = VideoComposer(self.config.layout)
        self.seo_generator = SEOGenerator(self.config.seo)

        self.yt_publisher = YouTubePublisher(
            client_secrets_path=self.config.publishing.youtube_client_secrets_path,
            credentials_cache=self.config.publishing.youtube_credentials_cache,
            privacy_status=self.config.publishing.youtube_privacy_status,
            dry_run=self.config.publishing.dry_run,
        )
        self.ig_publisher = InstagramPublisher(
            account_id=self.config.publishing.instagram_account_id,
            access_token=self.config.publishing.instagram_access_token,
            dry_run=self.config.publishing.dry_run,
        )

    def process_stream(
        self,
        stream_url_or_path: str,
        max_clips: Optional[int] = None,
        game_title: Optional[str] = None,
        streamer_name: Optional[str] = None,
        auto_publish: Optional[bool] = None,
    ) -> PipelineResult:
        """Run complete automated stream ingestion, clipping, rendering, SEO and publishing."""
        max_clips = max_clips or self.config.highlights.target_clips_per_stream
        should_publish = auto_publish if auto_publish is not None else not self.config.publishing.dry_run

        logger.info(">>> STEP 1: Ingesting stream metadata from %s", stream_url_or_path)
        meta = self.downloader.extract_info(stream_url_or_path)
        game = game_title or meta.categories[0] if meta.categories else self.config.seo.game_title
        streamer = streamer_name or meta.uploader or self.config.seo.streamer_name

        logger.info(">>> STEP 2: Extracting audio for excitement & speech analysis")
        audio_wav = self.downloader.download_audio(stream_url_or_path)

        logger.info(">>> STEP 3: Detecting top viral moments and transcribing speech")
        candidates = self.highlight_detector.detect_highlights(
            audio_wav,
            target_duration_sec=self.config.highlights.max_clip_duration_sec - 10.0,
            max_clips=max_clips,
        )
        logger.info("Found %d high-scoring candidate moments", len(candidates))

        processed_shorts: List[ProcessedShort] = []
        out_dir = self.config.output_dir / meta.video_id
        out_dir.mkdir(parents=True, exist_ok=True)

        # Calculate optimal YouTube growth schedule (2 Shorts/day max)
        scheduler = ChannelGrowthScheduler(
            shorts_per_day=self.config.publishing.youtube_shorts_per_day,
            timezone_str=self.config.publishing.youtube_schedule_timezone,
            peak_times=self.config.publishing.youtube_schedule_times,
            start_days_ahead=self.config.publishing.youtube_schedule_start_days_ahead,
        )
        schedule_slots: List[ScheduleSlot] = []
        if self.config.publishing.youtube_schedule_mode:
            schedule_slots = scheduler.generate_plan(len(candidates))
            logger.info("\n%s\n", scheduler.format_plan_table(schedule_slots))

        for idx, candidate in enumerate(candidates, start=1):
            slot = schedule_slots[idx - 1] if schedule_slots and (idx - 1) < len(schedule_slots) else None
            logger.info(">>> STEP 4.%d: Processing clip [%.1fs - %.1fs] (score: %.2f)%s",
                        idx, candidate.start_sec, candidate.end_sec, candidate.score,
                        f" [Scheduled: {slot.publish_at_iso}]" if slot else "")

            # 4a: Download/trim the raw video slice
            raw_clip_path = self.config.work_dir / f"{meta.video_id}_{candidate.clip_id}_raw.mp4"
            self.downloader.download_clip_segment(
                stream_url_or_path,
                start_sec=candidate.start_sec,
                end_sec=candidate.end_sec,
                output_path=raw_clip_path,
            )

            # 4b: Determine facecam crop box and gameplay box using actual clip dimensions
            in_w, in_h = self._get_video_dimensions(raw_clip_path)
            if self.config.layout.facecam_mode == "auto":
                facecam_box = self.face_tracker.detect_facecam_box(
                    raw_clip_path, preset_fallback=self.config.layout.facecam_preset
                )
            elif self.config.layout.facecam_mode == "preset":
                facecam_box = self.face_tracker.get_preset_box(in_w, in_h, self.config.layout.facecam_preset)
            else:
                facecam_box = self.face_tracker.get_preset_box(in_w, in_h, "bottom-right")

            gameplay_box = self.face_tracker.get_gameplay_box(in_w, in_h, crop_ratio=0.8)

            # 4c: Generate word-level ASS subtitles & animated center overlay
            ass_path = out_dir / f"{candidate.clip_id}_captions.ass"
            self.subtitle_generator.generate_ass(
                words=candidate.words,
                output_ass_path=ass_path,
                video_width=self.config.layout.output_width,
                video_height=self.config.layout.output_height,
            )
            sub_overlay = self.subtitle_generator.render_overlay_manifest(
                words=candidate.words,
                output_dir=out_dir / f"{candidate.clip_id}_subs",
                total_duration_sec=candidate.duration_sec,
                video_width=self.config.layout.output_width,
            )

            # 4d: Render vertical 9:16 composite (Upper facecam, lower gameplay, center captions)
            rendered_video_path = out_dir / f"{candidate.clip_id}_vertical.mp4"
            self.video_composer.render_short(
                input_video_path=raw_clip_path,
                output_video_path=rendered_video_path,
                facecam_box=facecam_box,
                gameplay_box=gameplay_box,
                subtitles_concat_path=sub_overlay.concat_file,
            )

            # 4e: Generate cover thumbnail
            thumb_path = out_dir / f"{candidate.clip_id}_cover.jpg"
            self.video_composer.extract_cover_thumbnail(
                rendered_video_path, thumb_path, timestamp_sec=min(2.0, candidate.duration_sec / 2.0)
            )

            # 4f: Generate viral SEO metadata
            seo = self.seo_generator.generate_metadata(
                stream_title=meta.title,
                transcript=candidate.transcript or "Unbelievable play in GTA 6!",
                game_title=game,
                streamer_name=streamer,
            )

            # 4g: Publish to YouTube Shorts & Instagram Reels
            yt_res = None
            ig_res = None
            if self.config.publishing.youtube_enabled:
                yt_res = self.yt_publisher.upload_short(
                    video_path=rendered_video_path,
                    title=seo.youtube_title,
                    description=seo.youtube_description,
                    tags=seo.youtube_tags,
                    publish_at=slot.publish_at_iso if slot else None,
                )

            if self.config.publishing.instagram_enabled:
                ig_res = self.ig_publisher.upload_reel(
                    video_path=rendered_video_path,
                    caption=seo.instagram_caption,
                )

            # Save full clip metadata package
            clip_meta_path = out_dir / f"{candidate.clip_id}_metadata.json"
            clip_info = {
                "clip_id": candidate.clip_id,
                "stream_title": meta.title,
                "game": game,
                "streamer": streamer,
                "start_sec": candidate.start_sec,
                "end_sec": candidate.end_sec,
                "duration_sec": candidate.duration_sec,
                "transcript": candidate.transcript,
                "schedule_slot": {
                    "publish_at_iso": slot.publish_at_iso,
                    "local_time": slot.local_datetime.isoformat(),
                    "label": slot.slot_label,
                } if slot else None,
                "seo": {
                    "youtube_title": seo.youtube_title,
                    "youtube_description": seo.youtube_description,
                    "youtube_tags": seo.youtube_tags,
                    "instagram_caption": seo.instagram_caption,
                    "instagram_hashtags": seo.instagram_hashtags,
                },
                "publishing": {
                    "youtube": yt_res.__dict__ if yt_res else None,
                    "instagram": ig_res.__dict__ if ig_res else None,
                },
            }
            clip_meta_path.write_text(json.dumps(clip_info, indent=2), encoding="utf-8")

            processed_shorts.append(
                ProcessedShort(
                    clip_id=candidate.clip_id,
                    video_path=rendered_video_path,
                    thumbnail_path=thumb_path,
                    subtitles_path=ass_path,
                    start_sec=candidate.start_sec,
                    end_sec=candidate.end_sec,
                    duration_sec=candidate.duration_sec,
                    transcript=candidate.transcript,
                    seo=seo,
                    youtube_result=yt_res,
                    instagram_result=ig_res,
                )
            )

        return PipelineResult(stream_metadata=meta, shorts=processed_shorts)

    @staticmethod
    def _get_video_dimensions(video_path: Path) -> tuple[int, int]:
        import subprocess
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0", str(video_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        parts = res.stdout.strip().split("x")
        return int(parts[0]), int(parts[1])
