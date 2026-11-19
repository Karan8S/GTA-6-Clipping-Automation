"""Persistent hook banner generator for vertical Shorts & Reels."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("streamclip.hook_banner")


class HookBannerGenerator:
    """Generates a stylish, persistent center banner with text and emojis."""

    def __init__(
        self,
        font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        emoji_font_path: str = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    ):
        self.font_path = font_path
        self.emoji_font_path = emoji_font_path

    def _render_emoji(self, emoji_char: str, target_size: int = 44) -> Image.Image:
        """Render a single emoji at high resolution and resize."""
        try:
            if Path(self.emoji_font_path).exists():
                emoji_font = ImageFont.truetype(self.emoji_font_path, 109)
                canvas = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
                d = ImageDraw.Draw(canvas)
                d.text((10, 10), emoji_char, font=emoji_font, embedded_color=True)
                bbox = canvas.getbbox()
                if bbox:
                    canvas = canvas.crop(bbox)
                return canvas.resize((target_size, target_size), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.debug("Emoji rendering fallback: %s", e)
        return Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))

    def create_banner(
        self,
        text: str,
        emojis: List[str],
        output_path: Path | str,
        width: int = 1080,
        height: int = 110,
        fill_color: tuple = (14, 14, 20, 225),
        border_color: tuple = (255, 0, 127, 255),
        text_color: tuple = (255, 235, 20, 255),
    ) -> Path:
        """Create a transparent PNG containing the persistent center hook banner."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Load font
        try:
            font = ImageFont.truetype(self.font_path, 38)
        except Exception:
            font = ImageFont.load_default()

        # Measure text width
        t_bbox = draw.textbbox((0, 0), text, font=font)
        tw = t_bbox[2] - t_bbox[0]
        th = t_bbox[3] - t_bbox[1]

        # Emojis width
        e_size = 42
        e_gap = 10
        total_emoji_w = len(emojis) * e_size + max(0, len(emojis) - 1) * e_gap if emojis else 0
        spacing = 16 if emojis else 0

        content_w = tw + spacing + total_emoji_w
        padding_x = 34
        pill_w = content_w + (padding_x * 2)
        pill_h = 76

        pill_x = (width - pill_w) // 2
        pill_y = (height - pill_h) // 2

        # Rounded pill badge with neon stroke
        draw.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=20,
            fill=fill_color,
            outline=border_color,
            width=3,
        )

        # Draw text
        start_x = pill_x + padding_x
        ty = pill_y + (pill_h - th) // 2 - 3
        draw.text(
            (start_x, ty),
            text,
            font=font,
            fill=text_color,
            stroke_width=4,
            stroke_fill=(0, 0, 0, 255),
        )

        # Paste emojis
        curr_ex = start_x + tw + spacing
        for emo in emojis:
            e_img = self._render_emoji(emo, e_size)
            ey = pill_y + (pill_h - e_size) // 2
            img.paste(e_img, (int(curr_ex), int(ey)), e_img)
            curr_ex += e_size + e_gap

        img.save(str(out_p))
        return out_p
