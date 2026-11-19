#!/usr/bin/env bash
set -e

STREAM_URL="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -z "$STREAM_URL" ]; then
    echo "=================================================================="
    echo "GTA 6 Clipping: YouTube Stream -> Scheduled Viral Shorts Pipeline"
    echo "=================================================================="
    echo "Usage: ./clip_stream.sh <YOUTUBE_STREAM_URL> [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --schedule            Schedule 2 Shorts/day at peak traffic hours (default)"
    echo "  --immediate           Publish immediately as public"
    echo "  --shorts-per-day <N>  Number of shorts to schedule per day (default: 2)"
    echo "  --timezone <TZ>       Channel timezone (default: Asia/Kolkata)"
    echo "  --dry-run             Simulate uploads without hitting live YouTube"
    echo ""
    echo "Example:"
    echo "  ./clip_stream.sh https://www.youtube.com/live/LMbea5SozeM --schedule"
    echo "=================================================================="
    exit 1
fi

shift || true
EXTRA_ARGS="$@"

echo "=================================================================="
echo "GTA 6 CLIPPING: Processing Stream -> Viral Shorts"
echo "Target URL: $STREAM_URL"
echo "Schedule Mode: 2 Shorts/Day (Healthy Channel Growth)"
echo "=================================================================="

# 1. Ensure Python Virtual Environment
if [ -d ".venv" ]; then
    PYTHON_BIN=".venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
else
    echo "Error: Python 3 not found. Please run setup first."
    exit 1
fi

# 2. Run master clipping and composition pipeline
echo ""
echo ">>> [1/2] Slicing Highlights, Tracking Facecam & Generating 9:16 Shorts..."
$PYTHON_BIN -m src.pipeline "$STREAM_URL"

# 3. Publish and schedule YouTube Shorts with 2/day healthy growth pacing
echo ""
echo ">>> [2/2] Publishing & Scheduling to YouTube Shorts..."
$PYTHON_BIN scripts/publish_shorts.py --schedule $EXTRA_ARGS

echo ""
echo "=================================================================="
echo "GTA 6 Clipping Pipeline Completed Successfully!"
echo "Check output/shorts/ for generated MP4s and schedule records."
echo "=================================================================="
