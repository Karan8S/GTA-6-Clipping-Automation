"""Audio excitement and loudness peak analysis for stream highlights."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
import numpy as np
from scipy.io import wavfile


@dataclass
class AudioPeak:
    start_sec: float
    end_sec: float
    peak_sec: float
    energy_score: float


class AudioPeakDetector:
    """Detects excitement bursts (loud reactions, cheering, yelling, gunfire/action) in audio."""

    def __init__(
        self,
        window_size_sec: float = 0.5,
        hop_size_sec: float = 0.25,
        energy_threshold_multiplier: float = 1.6,
        min_silence_db: float = -42.0,
    ):
        self.window_size_sec = window_size_sec
        self.hop_size_sec = hop_size_sec
        self.energy_threshold_multiplier = energy_threshold_multiplier
        self.min_silence_db = min_silence_db

    def detect_peaks(
        self,
        wav_path: Path | str,
        target_clip_duration: float = 40.0,
        max_peaks: int = 5,
    ) -> List[AudioPeak]:
        """Process WAV audio and return top distinct high-energy moments."""
        sample_rate, samples = wavfile.read(str(wav_path))

        # Convert to float normalized [-1.0, 1.0] mono
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        if samples.dtype == np.int16:
            samples = samples.astype(np.float32) / 32768.0
        elif samples.dtype == np.int32:
            samples = samples.astype(np.float32) / 2147483648.0
        else:
            samples = samples.astype(np.float32)

        total_duration = len(samples) / float(sample_rate)
        if total_duration < 10.0:
            return [AudioPeak(0.0, total_duration, total_duration / 2.0, 1.0)]

        win_len = int(self.window_size_sec * sample_rate)
        hop_len = int(self.hop_size_sec * sample_rate)
        
        # Calculate Short-Time RMS Energy
        num_windows = max(1, (len(samples) - win_len) // hop_len)
        rms = np.zeros(num_windows, dtype=np.float32)

        for i in range(num_windows):
            start = i * hop_len
            chunk = samples[start : start + win_len]
            rms[i] = np.sqrt(np.mean(chunk**2) + 1e-9)

        # Baseline stats
        mean_rms = np.mean(rms)
        std_rms = np.std(rms)
        threshold = mean_rms + (self.energy_threshold_multiplier * std_rms)

        # Find timestamps where RMS exceeds threshold
        peak_times = []
        for i, val in enumerate(rms):
            if val > threshold:
                t = (i * hop_len) / sample_rate
                peak_times.append((t, float(val)))

        if not peak_times:
            # Fallback: take highest percentiles
            idx = np.argsort(rms)[-max_peaks:]
            peak_times = [((i * hop_len) / sample_rate, float(rms[i])) for i in idx]

        # Cluster peaks and formulate optimal clip boundaries
        clips = []
        half_dur = target_clip_duration / 2.0
        # Sort by energy descending
        peak_times.sort(key=lambda x: x[1], reverse=True)

        selected_centers: List[float] = []
        for center_t, energy in peak_times:
            # Prevent overlapping clips (at least target_clip_duration apart)
            if any(abs(center_t - prev) < (target_clip_duration * 0.7) for prev in selected_centers):
                continue

            if total_duration <= target_clip_duration:
                start_t = 0.0
                end_t = total_duration
            else:
                start_t = max(0.0, center_t - (half_dur * 0.8))
                end_t = min(total_duration, start_t + target_clip_duration)
                if end_t - start_t < target_clip_duration:
                    start_t = max(0.0, end_t - target_clip_duration)

            if end_t <= start_t:
                end_t = min(total_duration, start_t + 5.0)

            selected_centers.append(center_t)
            clips.append(AudioPeak(
                start_sec=round(start_t, 2),
                end_sec=round(end_t, 2),
                peak_sec=round(center_t, 2),
                energy_score=round(energy, 4)
            ))

            if len(clips) >= max_peaks:
                break

        # Sort clips chronologically
        clips.sort(key=lambda c: c.start_sec)
        return clips
