"""Advanced Subtitle generator producing ASS files and pixel-perfect viral overlay frames."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from src.analysis.highlight_detector import SubtitleWord
from src.config import SubtitleConfig

logger = logging.getLogger("streamclip.subtitles")


@dataclass
class TimedSubtitleOverlay:
    concat_file: Path
    frames_dir: Path
    has_subtitles: bool


class SubtitleGenerator:
    """Generates styled ASS files and high-contrast PIL image sequences for center captions."""

    def __init__(self, config: SubtitleConfig):
        self.config = config

    def generate_ass(
        self,
        words: List[SubtitleWord],
        output_ass_path: Path | str,
        video_width: int = 1080,
        video_height: int = 1920,
    ) -> Path:
        """Create ASS file with center-positioned karaoke subtitles."""
        output_ass_path = Path(output_ass_path)
        output_ass_path.parent.mkdir(parents=True, exist_ok=True)

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ViralCenter,{self.config.font_name},{self.config.font_size},{self.config.primary_color},&H000000FF,{self.config.outline_color},&H80000000,-1,0,0,0,100,100,1,0,1,{self.config.outline_width},{self.config.shadow_depth},5,40,40,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        dialogue_lines: List[str] = []

        if not words:
            output_ass_path.write_text(header, encoding="utf-8")
            return output_ass_path

        batch_size = max(1, self.config.max_words_per_batch)
        batches = [words[i : i + batch_size] for i in range(0, len(words), batch_size)]

        for batch in batches:
            pos_tag = f"\\pos({video_width // 2},{video_height // 2})"

            for active_idx, current_word in enumerate(batch):
                word_start = current_word.start
                word_end = current_word.end

                start_str = self._format_timestamp(word_start)
                end_str = self._format_timestamp(word_end)

                text_tokens = []
                for idx, w in enumerate(batch):
                    cleaned_word = w.word.upper().strip()
                    if idx == active_idx:
                        text_tokens.append(f"{{\\c{self.config.highlight_color}\\fscx112\\fscy112}}{cleaned_word}{{\\rViralCenter}}")
                    else:
                        text_tokens.append(f"{{\\c{self.config.primary_color}}}{cleaned_word}")

                batch_text = f"{{{pos_tag}}}" + " ".join(text_tokens)
                dialogue_lines.append(
                    f"Dialogue: 0,{start_str},{end_str},ViralCenter,,0,0,0,,{batch_text}"
                )

        content = header + "\n".join(dialogue_lines) + "\n"
        output_ass_path.write_text(content, encoding="utf-8")
        return output_ass_path

    def render_overlay_manifest(
        self,
        words: List[SubtitleWord],
        output_dir: Path,
        total_duration_sec: float,
        video_width: int = 1080,
    ) -> TimedSubtitleOverlay:
        """Render transparent PNG subtitle frames and generate FFmpeg concat demuxer manifest."""
        frames_dir = output_dir / "sub_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        concat_file = output_dir / "subtitles_concat.txt"

        if not words:
            # Generate 1 transparent empty frame spanning full duration
            empty_png = frames_dir / "empty.png"
            Image.new("RGBA", (video_width, 240), (0, 0, 0, 0)).save(empty_png)
            concat_file.write_text(f"file '{empty_png.resolve()}'\nduration {total_duration_sec:.3f}\nfile '{empty_png.resolve()}'\n", encoding="utf-8")
            return TimedSubtitleOverlay(concat_file=concat_file, frames_dir=frames_dir, has_subtitles=False)

        # Batch words
        batch_size = max(1, self.config.max_words_per_batch)
        batches = [words[i : i + batch_size] for i in range(0, len(words), batch_size)]

        font = self._load_font(size=44)
        band_h = 240
        empty_png = frames_dir / "empty.png"
        Image.new("RGBA", (video_width, band_h), (0, 0, 0, 0)).save(empty_png)

        entries = []
        current_t = 0.0

        for b_idx, batch in enumerate(batches):
            for active_idx, word in enumerate(batch):
                w_start = max(current_t, word.start)
                w_end = max(w_start + 0.1, word.end)

                # If there is a silence gap before this word
                if w_start > current_t + 0.05:
                    gap = w_start - current_t
                    entries.append((empty_png, gap))
                    current_t += gap

                # Render frame for this word active state
                frame_img = Image.new("RGBA", (video_width, band_h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(frame_img)

                # Measure widths of each word in the batch
                word_texts = [w.word.upper().strip() for w in batch]
                spacings = [draw.textlength(wt + " ", font=font) for wt in word_texts]
                total_w = sum(spacings)

                # Center the entire batch phrase
                start_x = (video_width - total_w) / 2.0
                curr_x = start_x
                y_pos = band_h // 2

                for idx, (wt, sp) in enumerate(zip(word_texts, spacings)):
                    is_active = (idx == active_idx)
                    text_color = (255, 235, 0, 255) if is_active else (255, 255, 255, 255)
                    stroke_col = (0, 0, 0, 255)
                    stroke_w = 4 if is_active else 3

                    draw.text(
                        (curr_x, y_pos),
                        wt,
                        font=font,
                        fill=text_color,
                        stroke_width=stroke_w,
                        stroke_fill=stroke_col,
                        anchor="lm",
                    )
                    curr_x += sp

                frame_path = frames_dir / f"f_{b_idx:03d}_{active_idx:02d}.png"
                frame_img.save(frame_path)

                dur = w_end - w_start
                entries.append((frame_path, dur))
                current_t = w_end

        # Fill remaining duration with empty frame
        if current_t < total_duration_sec:
            rem = total_duration_sec - current_t
            entries.append((empty_png, rem))

        # Write concat demuxer manifest
        lines = []
        for path, dur in entries:
            safe_p = str(path.resolve()).replace("'", "'\\''")
            lines.append(f"file '{safe_p}'")
            lines.append(f"duration {dur:.3f}")
        if entries:
            last_p = str(entries[-1][0].resolve()).replace("'", "'\\''")
            lines.append(f"file '{last_p}'")

        concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return TimedSubtitleOverlay(concat_file=concat_file, frames_dir=frames_dir, has_subtitles=True)

    def _load_font(self, size: int = 44) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Attempt to load popular bold system fonts, falling back to default."""
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        for f in font_candidates:
            if Path(f).exists():
                try:
                    return ImageFont.truetype(f, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int(round((seconds - int(seconds)) * 100))
        if centisecs >= 100:
            centisecs = 99
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
