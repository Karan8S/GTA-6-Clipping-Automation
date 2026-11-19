"""YouTube stream & VOD downloader using yt-dlp with precision segment clipping."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from dataclasses import dataclass
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import requests
import yt_dlp

logger = logging.getLogger("streamclip.downloader")


class HttpStreamBridge:
    """Proxies HTTPS YouTube stream chunks over local HTTP for FFmpeg."""

    def __init__(self, video_url: str, audio_url: str):
        self.video_url = video_url
        self.audio_url = audio_url
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.port: int = 0

    def start(self) -> str:
        outer = self

        class MultiProxyHandler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                target = outer.video_url if "video" in self.path else outer.audio_url
                try:
                    r = requests.head(target, timeout=12)
                    self.send_response(r.status_code)
                    for h in ("Content-Type", "Content-Range", "Content-Length", "Accept-Ranges"):
                        if h in r.headers:
                            self.send_header(h, r.headers[h])
                    self.end_headers()
                except Exception:
                    self.send_error(500)

            def do_GET(self):
                target = outer.video_url if "video" in self.path else outer.audio_url
                req_headers = {}
                if "Range" in self.headers:
                    req_headers["Range"] = self.headers["Range"]
                try:
                    r = requests.get(target, headers=req_headers, stream=True, timeout=20)
                    self.send_response(r.status_code)
                    for h in ("Content-Type", "Content-Range", "Content-Length", "Accept-Ranges"):
                        if h in r.headers:
                            self.send_header(h, r.headers[h])
                    self.end_headers()
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception:
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), MultiProxyHandler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server = None


@dataclass
class StreamMetadata:
    url: str
    video_id: str
    title: str
    uploader: str
    duration: float
    description: str
    thumbnail: str
    categories: List[str]
    tags: List[str]
    is_live: bool


class StreamDownloader:
    """Manages metadata retrieval and fast timestamp-based segment downloads."""

    def __init__(self, cache_dir: Path | str = ".cache/streamclip"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._formats_cache: Dict[str, Tuple[str, str]] = {}

    def extract_info(self, url_or_path: str) -> StreamMetadata:
        """Fetch stream metadata without downloading the video payload."""
        # Check if local file
        local_p = Path(url_or_path)
        if local_p.is_file():
            duration = self._get_local_duration(local_p)
            return StreamMetadata(
                url=str(local_p.resolve()),
                video_id=local_p.stem,
                title=local_p.stem.replace("_", " ").title(),
                uploader="Streamer",
                duration=duration,
                description="Local stream capture",
                thumbnail="",
                categories=["Gaming"],
                tags=["gaming", "stream", "gta6"],
                is_live=False,
            )

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url_or_path, download=False)
            if info is None:
                raise ValueError(f"Could not extract info for URL: {url_or_path}")

            return StreamMetadata(
                url=url_or_path,
                video_id=info.get("id", "stream"),
                title=info.get("title", "Untitled Stream"),
                uploader=info.get("uploader", "Streamer"),
                duration=float(info.get("duration", 0.0) or 0.0),
                description=info.get("description", ""),
                thumbnail=info.get("thumbnail", ""),
                categories=info.get("categories", ["Gaming"]),
                tags=info.get("tags", []),
                is_live=bool(info.get("is_live", False)),
            )

    def download_audio(self, url_or_path: str, max_duration: Optional[float] = None) -> Path:
        """Download fast lightweight 16kHz mono audio for transcription and peak analysis."""
        local_p = Path(url_or_path)
        output_wav = self.cache_dir / f"audio_{Path(url_or_path).stem}.wav"
        if output_wav.exists() and output_wav.stat().st_size > 0:
            return output_wav

        if local_p.is_file():
            # Extract audio from local video using ffmpeg
            cmd = [
                "ffmpeg", "-y", "-i", str(local_p),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            ]
            if max_duration:
                cmd.extend(["-t", str(max_duration)])
            cmd.append(str(output_wav))
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return output_wav

        # Remote stream / YouTube video: download audio stream via yt-dlp
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(self.cache_dir / f"audio_raw_{output_wav.stem}.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }],
            "postprocessor_args": [
                "-ar", "16000", "-ac", "1"
            ]
        }
        if max_duration:
            ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(None, [(0, max_duration)])

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_or_path])

        # Locate converted wav
        candidates = list(self.cache_dir.glob(f"audio_raw_{output_wav.stem}*.wav"))
        if candidates:
            candidates[0].rename(output_wav)
            return output_wav
        raise FileNotFoundError(f"Failed to produce audio for {url_or_path}")

    def _get_stream_urls(self, url: str) -> Tuple[str, str]:
        """Extract direct HTTP video and audio playback URLs."""
        if url in self._formats_cache:
            return self._formats_cache[url]

        ydl_opts = {"quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])

            # Target 720p/1080p H.264 video
            v_url = None
            for fid in ("298", "136", "135", "22", "18"):
                for f in formats:
                    if f.get("format_id") == fid and f.get("url") and not f.get("url").endswith(".m3u8"):
                        v_url = f["url"]
                        break
                if v_url:
                    break
            if not v_url:
                for f in formats:
                    if f.get("vcodec") != "none" and f.get("acodec") == "none" and f.get("url") and "m3u8" not in f.get("url"):
                        v_url = f["url"]
                        break

            # Target AAC/M4A audio
            a_url = None
            for fid in ("140", "251", "139"):
                for f in formats:
                    if f.get("format_id") == fid and f.get("url") and not f.get("url").endswith(".m3u8"):
                        a_url = f["url"]
                        break
                if a_url:
                    break
            if not a_url:
                for f in formats:
                    if f.get("acodec") != "none" and f.get("url") and "m3u8" not in f.get("url"):
                        a_url = f["url"]
                        break

            if not v_url or not a_url:
                raise ValueError(f"Could not find valid stream URLs for video/audio on {url}")

            self._formats_cache[url] = (v_url, a_url)
            return v_url, a_url

    def download_clip_segment(
        self,
        url_or_path: str,
        start_sec: float,
        end_sec: float,
        output_path: Path
    ) -> Path:
        """Download or trim an exact segment [start_sec, end_sec]."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        local_p = Path(url_or_path)

        duration = max(1.0, end_sec - start_sec)
        if local_p.is_file():
            # Local trim using ffmpeg high-quality reencode
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(max(0.0, start_sec)),
                "-t", str(duration),
                "-i", str(local_p),
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path)
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return output_path

        # Stream trimming via local HTTP bridge to bypass FFmpeg TLS limitation
        v_url, a_url = self._get_stream_urls(url_or_path)
        bridge = HttpStreamBridge(v_url, a_url)
        base_url = bridge.start()
        try:
            cmd = [
                "ffmpeg", "-y",
                "-seekable", "1",
                "-ss", str(max(0.0, start_sec)), "-t", str(duration),
                "-i", f"{base_url}/video.mp4",
                "-seekable", "1",
                "-ss", str(max(0.0, start_sec)), "-t", str(duration),
                "-i", f"{base_url}/audio.m4a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path)
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
        finally:
            bridge.stop()

        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        raise FileNotFoundError(f"Failed to produce clip segment {start_sec}-{end_sec}")

    def _get_local_duration(self, file_path: Path) -> float:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip() or 0.0)
