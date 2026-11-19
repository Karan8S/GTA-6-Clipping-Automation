# GTA 6 Clipping: Setup & Installation Guide

An end-to-end automated pipeline that ingests GTA 6 and gaming YouTube streams, detects audio peaks and highlights, crops streamer facecam using neural face detection (OpenCV YuNet), renders 9:16 vertical video with animated hook badges, generates viral SEO tags, and **schedules publishing to YouTube Shorts at a healthy 2 Shorts/day cadence**.

---

## Table of Contents
1. [Why 2 Shorts/Day? (Channel Growth Strategy)](#1-why-2-shortsday-channel-growth-strategy)
2. [Prerequisites](#2-prerequisites)
3. [Installing inside Antigravity](#3-installing-inside-antigravity)
4. [Setting Up YouTube Data API v3 (Google Cloud)](#4-setting-up-youtube-data-api-v3-google-cloud)
5. [Running the Automation](#5-running-the-automation)
6. [Configuration Reference (`config.yaml`)](#6-configuration-reference-configyaml)
7. [Troubleshooting & FAQ](#7-troubleshooting--faq)

---

## 1. Why 2 Shorts/Day? (Channel Growth Strategy)

Uploading all generated Shorts simultaneously harms channel growth because:
1. **Viewer Attention Fragmentation:** The YouTube Shorts Shelf algorithm recommends one short at a time to test viewer retention. Uploading multiple shorts at once forces your own videos to compete against each other for initial impressions.
2. **Algorithmic Velocity:** Consistent daily activity signals an active, healthy channel, boosting subscriber conversion and browse features.

### The Automated Release Cadence:
The built-in `ChannelGrowthScheduler` automatically spaces out your clips across consecutive days:
- **Slot 1 (1:00 PM / 13:00 Local Time):** Captures the midday lunch break mobile audience.
- **Slot 2 (7:00 PM / 19:00 Local Time):** Captures the prime evening leisure/gaming screen time.
- **RFC 3339 UTC Format:** Each clip is uploaded with `privacyStatus: "private"` and `publishAt: "<ISO_8601_TIMESTAMP>"`. YouTube automatically makes each short public at the scheduled second.

---

## 2. Prerequisites

### System Tools
1. **FFmpeg & FFprobe:**
   - **Linux (Ubuntu/Debian):** `sudo apt update && sudo apt install -y ffmpeg`
   - **macOS:** `brew install ffmpeg`
   - **Windows:** Install via `winget install Gyan.FFmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html).
2. **Python 3.10+**:
   Verify with `python3 --version`.

### Environment Setup
Create a virtual environment and install the required packages:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Installing inside Antigravity

GTA 6 Clipping is fully integrated with Google Antigravity. You can install it in two ways:

### Method A: Workspace Installation (Recommended)
1. Extract the `gta-6-clipping-automation.zip` file into a directory of your choice.
2. Open Antigravity and select this folder as your active workspace.
3. Antigravity automatically detects the skill defined at `.agents/skills/gta-6-clipping/SKILL.md` and `plugin.json`.
4. You can now simply ask Antigravity:
   > *"Clip this 5-hour GTA 6 stream and schedule the top 4 shorts to YouTube: https://www.youtube.com/live/..."*

### Method B: Global Antigravity Skill
To make GTA 6 Clipping available across all your Antigravity projects:
1. Copy the `skills/gta-6-clipping` folder into your global Antigravity skills directory:
   ```bash
   mkdir -p ~/.gemini/config/skills
   cp -r skills/gta-6-clipping ~/.gemini/config/skills/
   ```
2. Antigravity will now recognize `gta-6-clipping` across any workspace.

---

## 4. Setting Up YouTube Data API v3 (Google Cloud)

To allow the automation to upload and schedule videos on your YouTube channel, set up a free Google Cloud project:

### Step 4.1: Create Project & Enable API
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select a project** > **New Project**, name it (e.g. `StreamClip-Publisher`), and click **Create**.
3. In the search bar, search for **YouTube Data API v3**, click it, and click **Enable**.

### Step 4.2: Configure OAuth Consent Screen
1. Go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** and click **Create**.
3. Fill in:
   - **App name:** `StreamClip Auto`
   - **User support email:** Your email address
   - **Developer contact information:** Your email address
4. Click **Save and Continue** through Scopes.
5. Under **Test Users**, click **+ Add Users** and enter your Google account email (the one that owns or manages your YouTube channel).
   > [!IMPORTANT]
   > Unverified Google Cloud apps in "Testing" mode reject authentication unless your Google account is explicitly listed under **Test Users**.

### Step 4.3: Generate OAuth Client Credentials
1. Go to **APIs & Services** > **Credentials**.
2. Click **+ Create Credentials** > **OAuth client ID**.
3. Select Application type: **Desktop app**. Name it `StreamClip CLI`.
4. Click **Create**.
5. Click **Download JSON** on the created client ID.
6. Rename the downloaded file to `client_secrets.json` and place it in the root of the StreamClip project folder:
   ```
   streamclip/
   ├── client_secrets.json   <-- Place your downloaded file here
   ├── clip_stream.sh
   ├── config.yaml
   ...
   ```

### Step 4.4: One-Time Authorization
The first time an upload runs, StreamClip will open a browser window asking you to authorize the application to manage your YouTube videos:
- Log in with the Google account you added as a test user.
- If you see a *"Google hasn't verified this app"* warning, click **Advanced** > **Go to StreamClip Auto (unsafe)**.
- Click **Allow**.
- StreamClip automatically saves your permanent refresh token to `.credentials/youtube_token.json`. Future uploads will run 100% autonomously without prompting.

---

## 5. Running the Automation

### One-Click Processing & Scheduling
Run the master script with your YouTube stream link:
```bash
./clip_stream.sh "https://www.youtube.com/live/<STREAM_URL>" --schedule
```

### What happens automatically:
1. **Remote Indexing:** Uses HTTP byte-range requests with `-seekable 1` to index the 10+ hour stream without downloading the full multi-gigabyte video.
2. **Highlight Detection:** Analyzes audio energy variance, volume peaks, and continuous speech to detect top viral moments.
3. **Facecam Auto-Tracking:** Uses OpenCV's neural YuNet detector (`models/yunet.onnx`) to locate and track the streamer's facecam box.
4. **Vertical Split Canvas:** Composites 1080x1920 video (streamer facecam on top 1080x960, centered gameplay on bottom 1080x960, neon divider line, and emoji hook badge).
5. **SEO Bundle Generation:** Generates viral titles, high-retention descriptions, and algorithmic tags.
6. **Growth Scheduling:** Spaces the clips at 2 Shorts per day (1:00 PM and 7:00 PM in your local timezone) and uploads them to YouTube with `status.publishAt`.

### Useful CLI Commands
```bash
# Test run with synthetic gaming stream (no external network needed)
python3 -m src.cli demo --duration 25

# Publish or schedule existing rendered shorts from output directory
python3 scripts/publish_shorts.py --schedule --shorts-per-day 2 --timezone "Asia/Kolkata"

# Dry run (simulates scheduling and uploads without hitting live YouTube)
python3 scripts/publish_shorts.py --dry-run
```

---

## 6. Configuration Reference (`config.yaml`)

Copy `config.example.yaml` to `config.yaml` to customize your preferences:

```yaml
layout:
  output_width: 1080
  output_height: 1920
  upper_height: 960         # Facecam vertical height
  lower_height: 960         # Gameplay vertical height
  facecam_mode: "auto"      # "auto" (neural YuNet detection) or "preset"
  facecam_preset: "top-right" # Fallback position: top-right, top-left, bottom-right, bottom-left
  divider_color: "0xFF007F" # Neon magenta border

highlights:
  min_clip_duration_sec: 25.0
  max_clip_duration_sec: 58.0 # Must be under 60s for YouTube Shorts
  target_clips_per_stream: 4

publishing:
  dry_run: false
  youtube_enabled: true
  youtube_client_secrets_path: "client_secrets.json"
  
  # Growth Scheduling:
  youtube_schedule_mode: true
  youtube_shorts_per_day: 2
  youtube_schedule_timezone: "Asia/Kolkata" # Change to your channel's timezone
  youtube_schedule_times:
    - "13:00"               # Slot 1: Midday lunch break
    - "19:00"               # Slot 2: Prime evening
  youtube_schedule_start_days_ahead: 1 # Start tomorrow (1) or today (0)
```

---

## 7. Troubleshooting & FAQ

### Q: YouTube API returns `403 Developer Denied` or `access_denied`?
**Fix:** In Google Cloud Console, go to **APIs & Services** > **OAuth consent screen** > **Audience** / **Test users**. Add the exact Google email address you are signing in with.

### Q: YouTube API returns `invalidPublishAt`?
**Fix:** YouTube Data API requires that scheduled videos have `privacyStatus: "private"`. StreamClip handles this automatically when `--schedule` is enabled. Also ensure the scheduled time is at least 15 minutes in the future.

### Q: How do I change the facecam position if auto-detection misses it?
**Fix:** In `config.yaml`, set `facecam_mode: "preset"` and choose `facecam_preset: "top-right"` (or `top-left`, `bottom-right`, `bottom-left`).

### Q: How do I change the target tags or game name?
**Fix:** Edit the `seo:` section in `config.yaml` or pass `--game "GTA 6"` to the CLI.

---

## Privacy & Security Guarantee
This distribution package contains **zero** personal credentials, tokens, account identifiers, or private data. All OAuth secrets and tokens are generated locally on your machine and stored only in `.credentials/` (which is excluded via `.gitignore`).
