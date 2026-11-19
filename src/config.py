"""Configuration models and settings loader for StreamClip."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Literal, Optional, Tuple
import yaml
from pydantic import BaseModel, Field


class VideoLayoutConfig(BaseModel):
    """Layout specification for vertical 9:16 composite."""
    output_width: int = 1080
    output_height: int = 1920
    fps: int = 30
    
    # Split proportions: upper half streamer facecam, lower half gameplay
    upper_height: int = 960
    lower_height: int = 960
    
    # Facecam framing
    facecam_mode: Literal["auto", "preset", "custom"] = "auto"
    facecam_preset: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = "bottom-right"
    # Custom box: [x, y, w, h] as normalized 0.0-1.0 floats or pixel values
    custom_facecam_box: Optional[List[float]] = None
    
    # Gameplay framing
    gameplay_crop_mode: Literal["center", "fit_blur_bg"] = "center"
    
    # Divider styling
    show_divider: bool = True
    divider_thickness: int = 6
    divider_color: str = "0xFF007F"  # Hot pink / neon accent in hex or BGR


class SubtitleConfig(BaseModel):
    """Karaoke / animated styled subtitles placed in the center of the video."""
    enabled: bool = True
    font_name: str = "Montserrat,Arial,Impact,sans-serif"
    font_size: int = 26
    primary_color: str = "&H00FFFFFF"     # White
    highlight_color: str = "&H0000FFFF"   # Vibrant Yellow
    outline_color: str = "&H00000000"     # Black outline
    outline_width: float = 3.5
    shadow_depth: float = 2.0
    alignment: int = 2                    # Bottom-center of the designated subtitle band
    vertical_margin: int = 920            # Near center divider (1080x1920)
    max_words_per_batch: int = 3          # 2-4 words shown at a time for viral short pace


class HighlightConfig(BaseModel):
    """Highlight and viral moment detection parameters."""
    min_clip_duration_sec: float = 25.0
    max_clip_duration_sec: float = 58.0
    target_clips_per_stream: int = 3
    audio_energy_threshold_percentile: float = 85.0
    silence_threshold_db: float = -38.0
    min_speech_duration_sec: float = 10.0


class SEOConfig(BaseModel):
    """Metadata and SEO generation preferences."""
    streamer_name: str = "Gamer"
    game_title: str = "GTA 6"
    gemini_api_key: Optional[str] = None
    default_tags: List[str] = Field(default_factory=lambda: [
        "shorts", "youtube shorts", "gaming", "viral", "funny gaming moments",
        "twitch clips", "stream highlights", "gta 6", "gta vi", "vice city"
    ])
    default_hashtags: List[str] = Field(default_factory=lambda: [
        "#shorts", "#gaming", "#gta6", "#gtavi", "#gamingclips", "#viral", "#reels", "#explore"
    ])


class PublishingConfig(BaseModel):
    """Social publishing settings."""
    dry_run: bool = True  # Default to dry-run for safety until user configures credentials
    
    # YouTube configuration
    youtube_enabled: bool = True
    youtube_client_secrets_path: Optional[str] = None
    youtube_credentials_cache: str = ".credentials/youtube_token.json"
    youtube_privacy_status: Literal["public", "unlisted", "private"] = "public"
    
    # YouTube Channel Growth Scheduling (Max 2 Shorts / day)
    youtube_schedule_mode: bool = True
    youtube_shorts_per_day: int = 2
    youtube_schedule_timezone: str = "Asia/Kolkata"
    youtube_schedule_times: List[str] = Field(default_factory=lambda: ["13:00", "19:00"])
    youtube_schedule_start_days_ahead: int = 1
    
    # Instagram configuration
    instagram_enabled: bool = True
    instagram_account_id: Optional[str] = None
    instagram_access_token: Optional[str] = None


class StreamClipConfig(BaseModel):
    """Global configuration model."""
    work_dir: Path = Path(".cache/streamclip")
    output_dir: Path = Path("output/shorts")
    layout: VideoLayoutConfig = Field(default_factory=VideoLayoutConfig)
    subtitles: SubtitleConfig = Field(default_factory=SubtitleConfig)
    highlights: HighlightConfig = Field(default_factory=HighlightConfig)
    seo: SEOConfig = Field(default_factory=SEOConfig)
    publishing: PublishingConfig = Field(default_factory=PublishingConfig)

    @classmethod
    def load(cls, config_path: Optional[Path | str] = None) -> StreamClipConfig:
        data = {}
        p = Path(config_path) if config_path else Path("config.yaml")
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        
        # Overlay environment variables
        if os.getenv("GEMINI_API_KEY"):
            data.setdefault("seo", {})["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
        if os.getenv("INSTAGRAM_ACCESS_TOKEN"):
            data.setdefault("publishing", {})["instagram_access_token"] = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        if os.getenv("INSTAGRAM_ACCOUNT_ID"):
            data.setdefault("publishing", {})["instagram_account_id"] = os.getenv("INSTAGRAM_ACCOUNT_ID")
        if os.getenv("YOUTUBE_CLIENT_SECRETS"):
            data.setdefault("publishing", {})["youtube_client_secrets_path"] = os.getenv("YOUTUBE_CLIENT_SECRETS")
        if os.getenv("STREAMCLIP_DRY_RUN"):
            data.setdefault("publishing", {})["dry_run"] = os.getenv("STREAMCLIP_DRY_RUN").lower() in ("1", "true", "yes")

        return cls(**data)
