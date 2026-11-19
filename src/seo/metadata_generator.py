"""Generates SEO-optimized titles, descriptions, keywords, and hashtags for Shorts & Reels."""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional
import requests

from src.config import SEOConfig

logger = logging.getLogger("streamclip.seo")


@dataclass
class ShortSEOMetadata:
    youtube_title: str
    youtube_description: str
    youtube_tags: List[str]
    instagram_caption: str
    instagram_hashtags: List[str]


class SEOGenerator:
    """Produces viral social metadata optimized for YouTube algorithm and Instagram Reels."""

    def __init__(self, config: SEOConfig):
        self.config = config
        self.api_key = config.gemini_api_key or os.getenv("GEMINI_API_KEY")

    def generate_metadata(
        self,
        stream_title: str,
        transcript: str,
        game_title: Optional[str] = None,
        streamer_name: Optional[str] = None,
    ) -> ShortSEOMetadata:
        """Generate tailored titles, descriptions, and hashtags using AI or rule-based heuristics."""
        game = game_title or self.config.game_title or "GTA 6"
        streamer = streamer_name or self.config.streamer_name or "Gamer"

        # Attempt Gemini API first if key exists
        if self.api_key:
            try:
                ai_meta = self._call_gemini_api(stream_title, transcript, game, streamer)
                if ai_meta:
                    return ai_meta
            except Exception as e:
                logger.warning("Gemini SEO API call failed: %s. Using heuristic generator.", e)

        return self._generate_heuristic_metadata(stream_title, transcript, game, streamer)

    def _call_gemini_api(
        self, stream_title: str, transcript: str, game: str, streamer: str
    ) -> Optional[ShortSEOMetadata]:
        """Query Gemini API for viral SEO packaging."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        prompt = f"""
You are a viral YouTube Shorts and Instagram Reels growth expert.
Generate SEO metadata for a vertical gaming short from a {game} stream by {streamer}.

Stream Title: {stream_title}
Clip Transcript: "{transcript}"

Return ONLY valid JSON matching this exact structure:
{{
  "youtube_title": "Hook title under 60 chars with emojis and curiosity gap",
  "youtube_description": "2-3 engaging SEO paragraphs with keywords, summary, and call to action",
  "youtube_tags": ["list", "of", "15", "search", "keywords", "tags"],
  "instagram_caption": "Engaging reel caption with hook, emojis, story context, and question for comments",
  "instagram_hashtags": ["#shorts", "#reels", "#gta6", "#gaming", "#viral", "#gamingclips"]
}}
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}
        }
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            return ShortSEOMetadata(
                youtube_title=parsed.get("youtube_title", "INSANE GAMING MOMENT! 😱"),
                youtube_description=parsed.get("youtube_description", ""),
                youtube_tags=parsed.get("youtube_tags", self.config.default_tags),
                instagram_caption=parsed.get("instagram_caption", ""),
                instagram_hashtags=parsed.get("instagram_hashtags", self.config.default_hashtags),
            )
        return None

    def _generate_heuristic_metadata(
        self, stream_title: str, transcript: str, game: str, streamer: str
    ) -> ShortSEOMetadata:
        """Deterministic viral copywriting engine when AI API is unavailable."""
        # Detect emotion or theme from transcript
        lowered = transcript.lower()
        if any(w in lowered for w in ("cops", "chase", "busted", "star", "wanted")):
            hook = f"THE MOST ILLEGAL ESCAPE IN {game.upper()}?! 🚨"
            theme = "police chase escape"
        elif any(w in lowered for w in ("no way", "how", "omg", "impossible", "insane")):
            hook = f"HE ACTUALLY PULLED THIS OFF?! 😱"
            theme = "impossible clutch play"
        elif any(w in lowered for w in ("kill", "headshot", "dead", "fight")):
            hook = f"WHEN THE INSTINCTS KICK IN... 🔥"
            theme = "epic combat moment"
        elif any(w in lowered for w in ("laugh", "funny", "fail", "wasted", "stupid")):
            hook = f"I CANNOT STOP LAUGHING AT THIS 💀"
            theme = "hilarious gaming fail"
        else:
            hook = f"HE WAS NOT EXPECTING THIS TO HAPPEN! 🤯"
            theme = "unexpected stream highlight"

        yt_title = f"{hook} #Shorts"
        if len(yt_title) > 65:
            yt_title = yt_title[:65]

        # SEO Description
        yt_desc = (
            f"{hook}\n\n"
            f"Watch {streamer} experience this wild {theme} in {game}! "
            f"From the live stream: \"{stream_title}\".\n\n"
            f"🎮 Game: {game}\n"
            f"👤 Streamer: {streamer}\n"
            f"💬 Clip Quote: \"{transcript[:140]}...\"\n\n"
            f"🔔 Subscribe for more daily {game} clips, stream highlights, and epic gaming moments!\n\n"
            f"#shorts #gaming #{game.lower().replace(' ', '')} #streamhighlights #viralshorts"
        )

        # High-traffic SEO Tags
        clean_game = game.lower()
        tags = [
            clean_game,
            f"{clean_game} shorts",
            f"{clean_game} gameplay",
            f"{clean_game} funny moments",
            f"{clean_game} clips",
            "gaming shorts",
            "stream highlights",
            "twitch clips",
            "viral gaming",
            "funny gaming moments",
            streamer.lower(),
            "shorts",
            "trending gaming",
            "gaming reels",
        ]

        # Instagram Hashtags
        ig_hashtags = [
            f"#{clean_game.replace(' ', '')}",
            "#gamingreels",
            "#streamer",
            "#gamingclips",
            "#viralreels",
            "#gamingcommunity",
            "#reelsinstagram",
            "#funnygaming",
            "#gamingmemes",
            "#reelsviral",
            "#explorepage",
            "#fyp",
        ]

        # Instagram Caption
        ig_caption = (
            f"{hook}\n\n"
            f"Bro really thought he could get away with this 😂 Tag a friend who plays {game} like this!\n\n"
            f"Stream: {stream_title}\n\n"
            + " ".join(ig_hashtags)
        )

        return ShortSEOMetadata(
            youtube_title=yt_title,
            youtube_description=yt_desc,
            youtube_tags=tags,
            instagram_caption=ig_caption,
            instagram_hashtags=ig_hashtags,
        )
