"""Analysis modules for audio, face tracking, and highlight detection."""
from src.analysis.audio_peaks import AudioPeak, AudioPeakDetector
from src.analysis.face_tracker import CropBox, FaceTracker
from src.analysis.highlight_detector import HighlightCandidate, HighlightDetector, SubtitleWord

__all__ = [
    "AudioPeak",
    "AudioPeakDetector",
    "CropBox",
    "FaceTracker",
    "HighlightCandidate",
    "HighlightDetector",
    "SubtitleWord",
]
