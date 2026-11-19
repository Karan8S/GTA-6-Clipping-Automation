# 🎬 GTA 6 Clipping: YouTube Stream to Scheduled Shorts Pipeline

An end-to-end autonomous pipeline that ingests long GTA 6 and gaming streams, extracts top viral highlights, crops the streamer facecam using neural face tracking (OpenCV YuNet), formats 9:16 vertical split videos with animated hooks, generates algorithmic SEO tags, and **schedules publishing to YouTube Shorts at a healthy 2 Shorts/day cadence**.

Ready to run standalone or install directly inside **Google Antigravity**.

---

## ✨ Key Features

1. **Remote Stream Ingestion (`yt-dlp`):**
   - Ingests multi-hour live streams without downloading gigabytes of video upfront.
   - Extracts audio track first to locate highlight moments and uses remote HTTP range seeking (`-seekable 1`) to cut exact clip frames instantly.

2. **Viral Excitement Detection:**
   - Multi-modal detection combining **Short-Time RMS Audio Energy** (laughter, screaming, clutch moments) with speech activity.
   - Ranks candidates by energy and engagement density.

3. **Neural Facecam Tracking & Split Canvas (9:16 - 1080x1920):**
   - **Upper Half (1080x960):** Streamer facecam framed using OpenCV's neural YuNet detector (`models/yunet.onnx`) or corner presets.
   - **Lower Half (1080x960):** Centered high-action gameplay.
   - **Divider & Hook:** Neon magenta accent border with persistent viral emoji badge.

4. **Algorithmic Channel Growth Scheduler (2 Shorts/Day):**
   - Automatically schedules uploads at peak audience traffic hours (Midday: 1:00 PM & Prime Evening: 7:00 PM).
   - Enforces healthy channel pacing to prevent audience fatigue and maximize recommendation on the Shorts feed.
   - Sets YouTube Data API `status.publishAt` and `privacyStatus: private` for automated publishing.

5. **Antigravity Skill & Plugin:**
   - Fully compatible with Google Antigravity (`plugin.json` and `.agents/skills/gta-6-clipping/SKILL.md`).
   - Run end-to-end clipping and scheduling directly through Antigravity chat.

---

## 🚀 Quick Start

### 1. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Credentials
Copy template files to set up your environment:
```bash
cp config.example.yaml config.yaml
cp client_secrets.json.template client_secrets.json  # Fill in your Google Cloud OAuth keys
```

### 3. One-Click Run
```bash
./clip_stream.sh "https://www.youtube.com/live/<STREAM_URL>" --schedule
```

### 4. Standalone Test (No Network Needed)
```bash
python3 -m src.cli demo --duration 25
```

---

## 📖 Complete Setup & Installation Guide
For a comprehensive step-by-step setup walkthrough including Google Cloud Console configuration, OAuth consent setup, Antigravity installation, and custom settings, please refer to:
👉 **[SETUP_GUIDE.md](SETUP_GUIDE.md)**

---

## 🔒 Privacy & Cleanliness
This repository contains **NO** private credentials, tokens, or personal account data. All tokens and OAuth credentials stay strictly local on your machine and are excluded via `.gitignore`.
