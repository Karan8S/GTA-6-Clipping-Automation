"""Multi-modal highlight detector combining audio energy peaks with speech analysis."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from src.analysis.audio_peaks import AudioPeak, AudioPeakDetector

logger = logging.getLogger("streamclip.highlight_detector")


@dataclass
class SubtitleWord:
    word: str
    start: float  # Relative to clip start in seconds
    end: float    # Relative to clip start in seconds
    probability: float = 1.0


@dataclass
class HighlightCandidate:
    clip_id: str
    start_sec: float
    end_sec: float
    duration_sec: float
    score: float
    transcript: str = ""
    words: List[SubtitleWord] = field(default_factory=list)
    key_moment_sec: float = 0.0


class HighlightDetector:
    """Finds viral stream moments using audio energy & Whisper transcription."""

    HIGH_ENGAGEMENT_WORDS = {
        "bro", "dude", "no", "way", "god", "omg", "what", "how", "insane",
        "clutch", "die", "killed", "run", "cops", "fast", "lets", "go",
        "chat", "wait", "dead", "wasted", "busted", "jump", "car", "heist",
        "shoot", "crazy", "unbelievable", "sheesh", "hack", "glitch"
    }

    def __init__(self, whisper_model_size: str = "base"):
        self.audio_detector = AudioPeakDetector()
        self.whisper_model_size = whisper_model_size
        self._whisper_model = None

    def _get_whisper(self):
        if self._whisper_model is None:
            try:
                import io
                import gc
                import av
                import numpy as np
                import faster_whisper.audio
                import faster_whisper.transcribe
                from faster_whisper import WhisperModel

                def safe_decode_audio(input_file, sampling_rate=16000, split_stereo=False):
                    resampler = av.audio.resampler.AudioResampler(
                        format="s16",
                        layout="mono" if not split_stereo else "stereo",
                        rate=sampling_rate,
                    )
                    raw_buffer = io.BytesIO()
                    dtype = None
                    with av.open(input_file, mode="r") as container:
                        frames = container.decode(audio=0)
                        frames = faster_whisper.audio._ignore_invalid_frames(frames)
                        frames = faster_whisper.audio._group_frames(frames, 500000)
                        frames = faster_whisper.audio._resample_frames(frames, resampler)
                        for frame in frames:
                            arr = frame.to_ndarray()
                            dtype = arr.dtype
                            raw_buffer.write(arr)
                    del resampler
                    gc.collect()
                    audio = np.frombuffer(raw_buffer.getbuffer(), dtype=dtype).astype(np.float32) / 32768.0
                    if split_stereo:
                        return audio[0::2], audio[1::2]
                    return audio

                faster_whisper.audio.decode_audio = safe_decode_audio
                faster_whisper.transcribe.decode_audio = safe_decode_audio

                logger.info("Loading faster-whisper model: %s", self.whisper_model_size)
                self._whisper_model = WhisperModel(
                    self.whisper_model_size, device="cpu", compute_type="int8"
                )
            except Exception as e:
                logger.warning("Failed to load faster-whisper model: %s. Continuing without transcription.", e)
                self._whisper_model = False
        return self._whisper_model

    def detect_highlights(
        self,
        wav_path: Path | str,
        target_duration_sec: float = 40.0,
        max_clips: int = 3,
        candidate_peaks: Optional[List[AudioPeak]] = None,
    ) -> List[HighlightCandidate]:
        """Detect top clips from audio track, transcribe them, and generate word-level timings."""
        import subprocess
        wav_path = Path(wav_path)

        if candidate_peaks is not None:
            audio_peaks = candidate_peaks
        else:
            # Step 1: Detect audio energy peaks
            audio_peaks = self.audio_detector.detect_peaks(
                wav_path, target_clip_duration=target_duration_sec, max_peaks=max_clips * 2
            )

        whisper = self._get_whisper()
        candidates: List[HighlightCandidate] = []

        for idx, peak in enumerate(audio_peaks):
            clip_id = f"clip_{idx + 1:02d}_{int(peak.start_sec)}s"
            transcript = ""
            words: List[SubtitleWord] = []
            keyword_score = 0.0

            # Step 2: Transcribe segment if Whisper is available
            if whisper:
                slice_wav = wav_path.parent / f"temp_{clip_id}.wav"
                try:
                    dur = peak.end_sec - peak.start_sec
                    subprocess.run([
                        "ffmpeg", "-y", "-ss", str(peak.start_sec), "-t", str(dur),
                        "-i", str(wav_path), "-vn", "-ar", "16000", "-ac", "1", str(slice_wav)
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    segments, info = whisper.transcribe(
                        str(slice_wav),
                        word_timestamps=True,
                    )
                    words_list = []
                    text_parts = []
                    for seg in segments:
                        text_parts.append(seg.text.strip())
                        if seg.words:
                            for w in seg.words:
                                rel_start = max(0.0, w.start)
                                rel_end = max(rel_start + 0.1, w.end)
                                clean_word = w.word.strip()
                                if clean_word:
                                    words_list.append(
                                        SubtitleWord(
                                            word=clean_word,
                                            start=round(rel_start, 3),
                                            end=round(rel_end, 3),
                                            probability=round(w.probability, 2),
                                        )
                                    )
                                    if clean_word.lower().strip("?!.,") in self.HIGH_ENGAGEMENT_WORDS:
                                        keyword_score += 0.25

                    transcript = " ".join(text_parts).strip()
                    words = words_list
                except Exception as e:
                    logger.debug("Whisper transcription error for segment %s: %s", clip_id, e)
                finally:
                    if slice_wav.exists():
                        slice_wav.unlink(missing_ok=True)

            # Combined score: audio energy + keyword engagement
            total_score = peak.energy_score + keyword_score

            candidates.append(
                HighlightCandidate(
                    clip_id=clip_id,
                    start_sec=peak.start_sec,
                    end_sec=peak.end_sec,
                    duration_sec=round(peak.end_sec - peak.start_sec, 2),
                    score=round(total_score, 4),
                    transcript=transcript,
                    words=words,
                    key_moment_sec=peak.peak_sec,
                )
            )

        # Sort by total score descending and take top N
        candidates.sort(key=lambda c: c.score, reverse=True)
        top_candidates = candidates[:max_clips]
        # Re-sort chronologically for intuitive stream order
        top_candidates.sort(key=lambda c: c.start_sec)
        return top_candidates
