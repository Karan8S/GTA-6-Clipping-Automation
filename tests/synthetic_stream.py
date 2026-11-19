"""Synthetic stream generator for reproducible testing and verification."""
from __future__ import annotations

import subprocess
from pathlib import Path
import cv2
import numpy as np
from scipy.io import wavfile


def create_synthetic_stream(output_path: Path | str, duration_sec: int = 15) -> Path:
    """Generate a realistic 16:9 gaming video with streamer facecam and audio peaks."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_video = output_path.parent / "temp_video.mp4"
    temp_audio = output_path.parent / "temp_audio.wav"

    w, h = 1280, 720
    fps = 25
    total_frames = duration_sec * fps

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(temp_video), fourcc, fps, (w, h))

    for frame_idx in range(total_frames):
        t = frame_idx / fps
        # 1. Gameplay Background: dark asphalt + moving lane markings + cars
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:] = (30, 30, 45)  # Night city road color

        # Draw road perspective lines
        cv2.line(img, (w // 2, h // 3), (100, h), (80, 80, 80), 3)
        cv2.line(img, (w // 2, h // 3), (w - 100, h), (80, 80, 80), 3)

        # Moving dash line
        dash_y = int((frame_idx * 15) % (h * 0.6) + h * 0.4)
        cv2.line(img, (w // 2, dash_y), (w // 2, min(h, dash_y + 40)), (255, 255, 255), 5)

        # Animated gameplay car
        car_x = int(w // 2 + np.sin(t * 3) * 120)
        car_y = int(h * 0.75)
        cv2.rectangle(img, (car_x - 35, car_y - 20), (car_x + 35, car_y + 40), (0, 0, 220), -1)
        cv2.putText(img, "GTA 6 LIVE STREAM", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        # 2. Streamer Facecam Overlay (Bottom-Right: x=900, y=480, w=340, h=210)
        cam_x, cam_y, cam_w, cam_h = 920, 480, 330, 210
        # Background of webcam room
        cv2.rectangle(img, (cam_x, cam_y), (cam_x + cam_w, cam_y + cam_h), (50, 40, 60), -1)
        # Neon webcam border
        cv2.rectangle(img, (cam_x, cam_y), (cam_x + cam_w, cam_y + cam_h), (255, 0, 180), 3)
        cv2.putText(img, "STREAMER CAM", (cam_x + 10, cam_y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Streamer Face (Head & Shoulders)
        center_head_x = cam_x + cam_w // 2
        center_head_y = cam_y + cam_h // 2 + 10
        # Head
        cv2.ellipse(img, (center_head_x, center_head_y), (35, 45), 0, 0, 360, (180, 190, 240), -1)
        # Eyes
        cv2.circle(img, (center_head_x - 12, center_head_y - 8), 5, (50, 50, 50), -1)
        cv2.circle(img, (center_head_x + 12, center_head_y - 8), 5, (50, 50, 50), -1)
        # Mouth: reacting / opening during peak (e.g. t between 6s and 9s)
        if 6.0 <= t <= 9.0:
            cv2.ellipse(img, (center_head_x, center_head_y + 20), (12, 16), 0, 0, 360, (20, 20, 20), -1)
            cv2.putText(img, "OMG WHAT?!", (cam_x + 40, cam_y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            cv2.line(img, (center_head_x - 10, center_head_y + 20), (center_head_x + 10, center_head_y + 20), (50, 50, 50), 3)

        out.write(img)

    out.release()

    # 3. Generate Audio with Excitement Peak between t=6s and t=9s
    sample_rate = 16000
    total_samples = duration_sec * sample_rate
    t_audio = np.linspace(0, duration_sec, total_samples, endpoint=False)

    # Ambient low gameplay hum (car engine)
    audio = 0.15 * np.sin(2 * np.pi * 80 * t_audio) + 0.05 * np.random.normal(0, 0.1, total_samples)

    # Loud excitement burst / yell during 6s to 9s
    peak_mask = (t_audio >= 6.0) & (t_audio <= 9.0)
    audio[peak_mask] += 0.85 * np.sin(2 * np.pi * 440 * t_audio[peak_mask]) + 0.3 * np.random.normal(0, 0.2, np.sum(peak_mask))

    # Normalize to int16
    audio_int16 = (audio / np.max(np.abs(audio)) * 32767 * 0.95).astype(np.int16)
    wavfile.write(str(temp_audio), sample_rate, audio_int16)

    # 4. Mux into final output MP4 with AAC audio
    mux_cmd = [
        "ffmpeg", "-y",
        "-i", str(temp_video),
        "-i", str(temp_audio),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(mux_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Clean up temp files
    temp_video.unlink(missing_ok=True)
    temp_audio.unlink(missing_ok=True)

    return output_path
