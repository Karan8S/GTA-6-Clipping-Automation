"""Facecam detection and auto-framing using OpenCV."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("streamclip.face_tracker")


@dataclass
class CropBox:
    x: int
    y: int
    width: int
    height: int

    def to_ffmpeg_crop(self) -> str:
        """Returns ffmpeg crop filter string: crop=w:h:x:y"""
        return f"crop={self.width}:{self.height}:{self.x}:{self.y}"


class FaceTracker:
    """Detects and isolates streamer facecam box from a 16:9 gaming stream."""

    PRESETS = {
        "top-left": (0.02, 0.0, 0.28, 0.42),
        "top-right": (0.73, 0.0, 0.27, 0.42),
        "bottom-left": (0.02, 0.58, 0.28, 0.42),
        "bottom-right": (0.72, 0.67, 0.26, 0.30),
    }

    def __init__(self, model_path: Optional[str | Path] = None):
        self.yunet = None
        self.face_cascade = None

        # Check for YuNet neural face detector
        m_path = Path(model_path) if model_path else Path("models/yunet.onnx")
        if not m_path.exists():
            m_path = Path("/tmp/yunet.onnx")
        if m_path.exists() and hasattr(cv2, "FaceDetectorYN_create"):
            try:
                self.yunet = cv2.FaceDetectorYN_create(str(m_path), "", (320, 320), score_threshold=0.5)
            except Exception as e:
                logger.debug("Failed to init FaceDetectorYN: %s", e)

        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if Path(cascade_path).exists():
                try:
                    self.face_cascade = cv2.CascadeClassifier(cascade_path)
                except Exception:
                    self.face_cascade = None

    def detect_facecam_box(
        self,
        video_path: Path | str,
        sample_frames_count: int = 20,
        preset_fallback: str = "top-right",
    ) -> CropBox:
        """Scan video frames to detect consistent streamer facecam position."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.warning("Could not open video file for face detection. Using fallback preset.")
            return self.get_preset_box(1920, 1080, preset_fallback)

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        # Try YuNet neural face detector first
        if self.yunet and frame_count > 0:
            step = max(1, frame_count // sample_frames_count)
            detected_faces = []
            for f_idx in range(0, frame_count, step):
                cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue
                self.yunet.setInputSize((frame.shape[1], frame.shape[0]))
                _, faces = self.yunet.detect(frame)
                if faces is not None and len(faces) > 0:
                    for f in faces:
                        x, y, w, h = int(f[0]), int(f[1]), int(f[2]), int(f[3])
                        detected_faces.append((x, y, w, h))
            cap.release()

            if detected_faces:
                cxs = [f[0] + f[2] // 2 for f in detected_faces]
                cys = [f[1] + f[3] // 2 for f in detected_faces]
                med_cx = int(np.median(cxs))
                med_cy = int(np.median(cys))
                crop_w = int(frame_width * 0.27)
                crop_h = int(crop_w * 960 / 1080)
                box_x = max(0, min(frame_width - crop_w, med_cx - crop_w // 2))
                box_y = max(0, min(frame_height - crop_h, med_cy - crop_h // 2))
                return CropBox(x=box_x, y=box_y, width=crop_w, height=crop_h)
            return self.get_preset_box(frame_width, frame_height, preset_fallback)

        if not self.face_cascade or frame_count <= 0:
            cap.release()
            return self.get_preset_box(frame_width, frame_height, preset_fallback)

        step = max(1, frame_count // sample_frames_count)
        detected_faces = []

        for f_idx in range(0, frame_count, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Detect faces with scaleFactor and minNeighbors
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.15, minNeighbors=5, minSize=(60, 60)
            )
            for (x, y, w, h) in faces:
                detected_faces.append((x, y, w, h))

        cap.release()

        if not detected_faces:
            logger.info("No face detected automatically in samples; using preset: %s", preset_fallback)
            return self.get_preset_box(frame_width, frame_height, preset_fallback)

        # Find the most frequent face region (streamers usually stay stationary in their webcam frame)
        # Group detections by spatial proximity
        best_cluster = self._cluster_faces(detected_faces, frame_width, frame_height)
        return best_cluster

    def get_preset_box(self, frame_w: int, frame_h: int, preset_name: str) -> CropBox:
        """Get pre-calculated crop box for common streamer camera positions."""
        preset = self.PRESETS.get(preset_name, self.PRESETS["bottom-right"])
        norm_x, norm_y, norm_w, norm_h = preset
        x = int(norm_x * frame_w)
        y = int(norm_y * frame_h)
        w = int(norm_w * frame_w)
        h = int(norm_h * frame_h)
        return CropBox(x=x, y=y, width=w, height=h)

    def get_gameplay_box(self, frame_w: int, frame_h: int, crop_ratio: float = 0.75) -> CropBox:
        """Get centered gameplay crop box suitable for bottom half (filling 1080x960)."""
        # Take center area of gameplay
        w = int(frame_w * crop_ratio)
        h = int(frame_h * crop_ratio)
        x = (frame_w - w) // 2
        y = (frame_h - h) // 2
        return CropBox(x=x, y=y, width=w, height=h)

    def _cluster_faces(self, faces: List[Tuple[int, int, int, int]], frame_w: int, frame_h: int) -> CropBox:
        """Average face detections and expand to include head/body framing."""
        # Convert to numpy array
        arr = np.array(faces)
        # Use median for robustness against false positive outliers in gameplay
        med_x = float(np.median(arr[:, 0]))
        med_y = float(np.median(arr[:, 1]))
        med_w = float(np.median(arr[:, 2]))
        med_h = float(np.median(arr[:, 3]))

        # Expand box for nice webcam framing: 1.5x width, 1.8x height
        expand_w = med_w * 1.6
        expand_h = med_h * 1.9

        center_x = med_x + med_w / 2.0
        center_y = med_y + med_h / 2.0

        crop_x = int(max(0, center_x - expand_w / 2.0))
        crop_y = int(max(0, center_y - expand_h / 2.0))
        crop_w = int(min(frame_w - crop_x, expand_w))
        crop_h = int(min(frame_h - crop_y, expand_h))

        # Ensure minimum size
        crop_w = max(160, crop_w)
        crop_h = max(160, crop_h)

        return CropBox(x=crop_x, y=crop_y, width=crop_w, height=crop_h)
