"""FFmpeg-based composite video renderer for 9:16 Shorts/Reels."""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from src.analysis.face_tracker import CropBox
from src.config import VideoLayoutConfig

logger = logging.getLogger("streamclip.composer")


class VideoComposer:
    """Composites facecam (upper half) and gameplay (lower half) with centered captions."""

    def __init__(self, layout: VideoLayoutConfig):
        self.layout = layout

    def render_short(
        self,
        input_video_path: Path | str,
        output_video_path: Path | str,
        facecam_box: CropBox,
        gameplay_box: CropBox,
        subtitles_concat_path: Optional[Path | str] = None,
        banner_overlay_path: Optional[Path | str] = None,
    ) -> Path:
        """Render high-quality 9:16 vertical short (1080x1920) with split layout & persistent banner or captions."""
        input_p = Path(input_video_path)
        output_p = Path(output_video_path)
        output_p.parent.mkdir(parents=True, exist_ok=True)

        w = self.layout.output_width       # 1080
        upper_h = self.layout.upper_height  # 960
        lower_h = self.layout.lower_height  # 960

        # Construct FFmpeg complex filter
        # 1. Upper: crop facecam, scale to fill 1080x960
        upper_filter = (
            f"[0:v]crop={facecam_box.width}:{facecam_box.height}:{facecam_box.x}:{facecam_box.y},"
            f"scale={w}:{upper_h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{upper_h}[upper]"
        )

        # 2. Lower: crop gameplay, scale to fill 1080x960
        lower_filter = (
            f"[0:v]crop={gameplay_box.width}:{gameplay_box.height}:{gameplay_box.x}:{gameplay_box.y},"
            f"scale={w}:{lower_h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{lower_h}[lower]"
        )

        # 3. Stack vertically: upper + lower = 1080x1920
        stack_filter = "[upper][lower]vstack=inputs=2[stacked]"

        last_stream = "[stacked]"
        filter_chains = [upper_filter, lower_filter, stack_filter]

        # 4. Optional accent divider line
        if self.layout.show_divider:
            div_t = self.layout.divider_thickness
            div_y = upper_h - (div_t // 2)
            divider_filter = (
                f"{last_stream}drawbox=x=0:y={div_y}:w={w}:h={div_t}:"
                f"color={self.layout.divider_color}@1:t=fill[with_divider]"
            )
            filter_chains.append(divider_filter)
            last_stream = "[with_divider]"

        cmd_inputs = ["-i", str(input_p)]

        # 5. Overlay persistent hook banner or animated subtitles
        has_banner = banner_overlay_path and Path(banner_overlay_path).exists()
        has_sub_overlay = subtitles_concat_path and Path(subtitles_concat_path).exists()

        if has_banner:
            cmd_inputs.extend(["-i", str(Path(banner_overlay_path).resolve())])
            banner_y = upper_h - 55  # Centered right over divider band (e.g. 960 - 55 = 905)
            banner_filter = f"{last_stream}[1:v]overlay=x=0:y={banner_y}:eof_action=repeat[final]"
            filter_chains.append(banner_filter)
            last_stream = "[final]"
        elif has_sub_overlay:
            cmd_inputs.extend(["-f", "concat", "-safe", "0", "-i", str(Path(subtitles_concat_path).resolve())])
            sub_y = upper_h - 120  # Centered right over the divider band (y = 840 to 1080)
            overlay_filter = f"{last_stream}[1:v]overlay=x=0:y={sub_y}:shortest=1[final]"
            filter_chains.append(overlay_filter)
            last_stream = "[final]"

        complex_filter = ";".join(filter_chains)

        cmd = [
            "ffmpeg", "-y",
            *cmd_inputs,
            "-filter_complex", complex_filter,
            "-map", last_stream,
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "19",
            "-pix_fmt", "yuv420p",
            "-r", str(self.layout.fps),
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_p),
        ]

        logger.info("Executing composite render for %s -> %s", input_p.name, output_p.name)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("FFmpeg render failed: %s", result.stderr)
            raise RuntimeError(f"FFmpeg composite render failed: {result.stderr[-500:]}")

        return output_p

    def extract_cover_thumbnail(
        self,
        video_path: Path | str,
        output_thumb_path: Path | str,
        timestamp_sec: float = 2.0,
    ) -> Path:
        """Extract a high-resolution vertical thumbnail frame for social cover."""
        thumb_p = Path(output_thumb_path)
        thumb_p.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp_sec),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_p),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return thumb_p
