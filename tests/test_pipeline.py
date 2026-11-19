"""Comprehensive test suite for StreamClip pipeline."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
import pytest

from src.analysis.audio_peaks import AudioPeakDetector
from src.analysis.face_tracker import CropBox, FaceTracker
from src.analysis.highlight_detector import SubtitleWord
from src.composer.subtitles import SubtitleGenerator
from src.composer.video_composer import VideoComposer
from src.config import StreamClipConfig
from src.pipeline import StreamClipPipeline
from src.publish.instagram_publisher import InstagramPublisher
from src.publish.youtube_publisher import YouTubePublisher
from src.seo.metadata_generator import SEOGenerator
from tests.synthetic_stream import create_synthetic_stream


def test_config_loading():
    cfg = StreamClipConfig.load()
    assert cfg.layout.output_width == 1080
    assert cfg.layout.output_height == 1920
    assert cfg.layout.upper_height == 960
    assert cfg.layout.lower_height == 960
    assert cfg.subtitles.enabled is True
    assert cfg.publishing.dry_run is True


def test_face_tracker_presets():
    tracker = FaceTracker()
    box_br = tracker.get_preset_box(1920, 1080, "bottom-right")
    assert box_br.width > 0
    assert box_br.height > 0
    assert box_br.x >= int(0.70 * 1920)
    assert box_br.y >= int(0.65 * 1080)

    game_box = tracker.get_gameplay_box(1920, 1080, crop_ratio=0.8)
    assert game_box.width == int(1920 * 0.8)
    assert game_box.height == int(1080 * 0.8)


def test_subtitles_generation(tmp_path: Path):
    cfg = StreamClipConfig.load()
    gen = SubtitleGenerator(cfg.subtitles)
    words = [
        SubtitleWord("OH", 0.0, 0.4),
        SubtitleWord("MY", 0.4, 0.7),
        SubtitleWord("GOD", 0.7, 1.2),
        SubtitleWord("WHAT", 1.3, 1.7),
        SubtitleWord("A", 1.7, 1.9),
        SubtitleWord("PLAY", 1.9, 2.5),
    ]
    ass_file = tmp_path / "test_subs.ass"
    gen.generate_ass(words, ass_file, 1080, 1920)

    assert ass_file.exists()
    content = ass_file.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "ViralCenter" in content
    assert "Dialogue:" in content
    assert "\\pos(540,960)" in content


def test_seo_generator():
    cfg = StreamClipConfig.load()
    seo = SEOGenerator(cfg.seo)
    meta = seo.generate_metadata(
        stream_title="GTA 6 Cops Chase Impossible Heist",
        transcript="Bro they called the SWAT team on me, there's no way I survive this cops chase!",
        game_title="GTA 6",
        streamer_name="Speedy",
    )

    assert meta.youtube_title
    assert len(meta.youtube_title) <= 70
    assert "#Shorts" in meta.youtube_title or "GTA" in meta.youtube_title
    assert "Speedy" in meta.youtube_description
    assert len(meta.youtube_tags) >= 5
    assert any("gta 6" in t for t in meta.youtube_tags)
    assert "#gaming" in meta.instagram_caption.lower()
    assert len(meta.instagram_hashtags) >= 5


def test_publishers_dry_run(tmp_path: Path):
    dummy_video = tmp_path / "dummy.mp4"
    dummy_video.write_bytes(b"dummy mp4 bytes")

    # YouTube publisher in dry-run
    yt = YouTubePublisher(dry_run=True)
    yt_res = yt.upload_short(dummy_video, "Test Title", "Test Desc", ["tag1"])
    assert yt_res.success is True
    assert yt_res.is_dry_run is True
    assert "youtube.com/shorts/" in yt_res.media_url

    # Instagram publisher in dry-run
    ig = InstagramPublisher(dry_run=True)
    ig_res = ig.upload_reel(dummy_video, "Test Caption #shorts")
    assert ig_res.success is True
    assert ig_res.is_dry_run is True
    assert "instagram.com/reel/" in ig_res.media_url

    # Verify Instagram local bundle creation
    bundle = tmp_path / f"{dummy_video.stem}_instagram_bundle.json"
    assert bundle.exists()
    bundle_data = json.loads(bundle.read_text())
    assert bundle_data["caption"] == "Test Caption #shorts"


def test_end_to_end_synthetic_pipeline(tmp_path: Path):
    # 1. Create a 12-second synthetic stream with streamer facecam + audio peak
    synthetic_stream = tmp_path / "test_stream.mp4"
    create_synthetic_stream(synthetic_stream, duration_sec=12)
    assert synthetic_stream.exists()

    # 2. Configure pipeline with custom output
    cfg = StreamClipConfig.load()
    cfg.work_dir = tmp_path / "cache"
    cfg.output_dir = tmp_path / "output"
    cfg.highlights.min_clip_duration_sec = 6.0
    cfg.highlights.max_clip_duration_sec = 10.0
    cfg.highlights.target_clips_per_stream = 1
    cfg.layout.facecam_mode = "preset"
    cfg.layout.facecam_preset = "bottom-right"

    pipeline = StreamClipPipeline(cfg)
    result = pipeline.process_stream(
        stream_url_or_path=str(synthetic_stream),
        max_clips=1,
        game_title="GTA 6",
        streamer_name="ApexDriver",
        auto_publish=False,
    )

    assert len(result.shorts) == 1
    short = result.shorts[0]

    # Verify generated vertical video file
    assert short.video_path.exists()
    assert short.thumbnail_path.exists()
    assert short.subtitles_path.exists()

    # 3. Check video dimensions with ffprobe (must be 1080x1920)
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        str(short.video_path),
    ]
    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    dim = probe_res.stdout.strip()
    assert dim == "1080x1920", f"Expected 1080x1920, got {dim}"
