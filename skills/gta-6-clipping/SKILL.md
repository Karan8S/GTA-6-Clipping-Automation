---
name: gta-6-clipping
description: Automated GTA 6 & gaming stream clipping, vertical 9:16 layout composition (with OpenCV YuNet facecam tracking), viral SEO metadata generation, and scheduled publishing (2 Shorts/day peak growth cadence) using official YouTube Data API v3.
---

# GTA 6 Clipping: YouTube Stream to Scheduled Shorts Automation

This skill teaches Antigravity how to automatically ingest long GTA 6 and gaming live streams (or local MP4s), extract high-energy highlight moments, composite them into 9:16 vertical split videos (facecam top, gameplay bottom, animated subtitle hook), generate viral SEO tags, and schedule publishing at a healthy **2 Shorts per day** cadence on YouTube.

---

## When to Use This Skill
Use this skill when:
- The user provides a YouTube stream URL or local video and wants vertical GTA 6 Shorts/Reels created.
- The user wants to schedule YouTube Shorts to grow their channel sustainably without algorithmic penalty or spam flags.
- The user wants automatic facecam detection, framing, and centering.
- The user wants to batch-publish generated bundles using the YouTube Data API v3.

---

## Quick Start Runbooks

### 1. One-Click Stream Processing & Scheduling
Run the master script:
```bash
./clip_stream.sh "https://www.youtube.com/live/<STREAM_ID>" --schedule
```
This executes:
1. Ingests stream audio/video indices via fast remote HTTP range seeks.
2. Identifies audio energy peaks & speech segments.
3. Automatically tracks and crops streamer facecam using OpenCV YuNet neural detector.
4. Centers gameplay into a vertical 1080x1920 layout with neon divider & hook badge.
5. Generates viral title, description, and hashtag bundles tailored for GTA 6.
6. Calculates optimal schedule slots (2 Shorts/day at 1:00 PM and 7:00 PM local time).
7. Uploads via YouTube Data API v3 with `status.publishAt` and `privacyStatus: private`.

### 2. Standalone Scheduling of Existing Clips
If clips are already rendered in `output/shorts/`:
```bash
python3 scripts/publish_shorts.py --schedule --shorts-per-day 2 --timezone "Asia/Kolkata"
```
Or for a test run without uploading:
```bash
python3 scripts/publish_shorts.py --dry-run
```

### 3. Running Synthetic Demo (No External Network Needed)
To test the full video rendering and scheduling pipeline locally:
```bash
python3 -m src.cli demo --duration 25
```

---

## YouTube Growth Pacing Rules (2 Shorts / Day)
The scheduler enforces algorithmic best practices for channel growth:
- **Daily Cap:** Maximum 2 Shorts per calendar day. Uploading more than 2 Shorts per day causes YouTube's recommendation engine to divide viewer retention across multiple videos, suppressing viral distribution on the Shorts feed.
- **Midday Slot (Slot 1):** 1:00 PM local time (`07:30 UTC` for IST). Captures lunch break mobile traffic.
- **Evening Slot (Slot 2):** 7:00 PM local time (`13:30 UTC` for IST). Captures prime evening gaming & leisure audience.
- **Private -> Scheduled Transition:** Videos are uploaded with `privacyStatus: "private"` and `publishAt: "<ISO_8601_TIMESTAMP>"`. YouTube automatically transitions them to public at the scheduled second.

---

## Configuration Reference (`config.yaml`)
Key settings in `config.yaml`:
```yaml
layout:
  output_width: 1080
  output_height: 1920
  upper_height: 960         # Streamer Facecam vertical slice height
  lower_height: 960         # Gameplay vertical slice height
  facecam_mode: "auto"      # "auto" (YuNet neural detector) or "preset"
  facecam_preset: "top-right"

seo:
  streamer_name: "Streamer"
  game_title: "GTA 6"

publishing:
  dry_run: false
  youtube_enabled: true
  youtube_client_secrets_path: "client_secrets.json"
  youtube_schedule_mode: true
  youtube_shorts_per_day: 2
  youtube_schedule_timezone: "Asia/Kolkata"
  youtube_schedule_times:
    - "13:00"
    - "19:00"
```

---

## OAuth Setup Checklist for New Users
1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable **YouTube Data API v3** in APIs & Services.
4. In OAuth Consent Screen, set user type to **External**, add app name, and add your Google email to the **Test Users** list.
5. In Credentials, create **OAuth Client ID** (type: **Desktop Application**).
6. Download client secret JSON and rename it to `client_secrets.json` in the project root.
7. Run `./clip_stream.sh <URL>` — the browser will open once to authenticate your channel, saving permanent tokens to `.credentials/youtube_token.json`.
