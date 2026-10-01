# Alarm Breaker - Remote Video Library

This repository contains the remote video library and catalog automation for WakeForge / Alarm Breaker friend and self alarms.

## How It Works
1. Upload an MP4 video to `videos/<category>/<name>.mp4`.
2. When pushed to `main`, the GitHub Actions workflow automatically:
   - Re-encodes videos to **480x854 vertical H.264 + AAC 96kbps + faststart** (target <= 1 MB) if larger than 1.5 MB or non-standard resolution.
   - Generates high-quality thumbnails in `thumbs/<category>/<name>.jpg` (240px wide JPEG).
   - Computes SHA-256 checksums, durations, tags, and generates an updated `catalog.json`.
   - Purges the jsDelivr CDN cache so all user apps receive the new video instantly without updating the APK!

## File Naming & Organization Rules
- **Folder = Category**: The category is determined by the folder name (e.g. `challenge`, `motivation`, `roast`, `love`, `cricket`, `gaming`, `birthday`, `meeting`, `family`, `travel`, `pets`, `study`).
- **File Name**: Use lowercase letters, digits, and underscores (e.g. `pushup_challenge.mp4`).
- **Hindi Language Indicator**: Append `_hi` before `.mp4` for Hindi content (e.g. `rooster_chaos_hi.mp4`). By default, videos are marked as English (`en`).
- **Never Rename or Change an ID**: Video IDs are derived as `<category>_<name>`. Never rename a file after publishing, as scheduled friend alarms reference this immutable ID. If a video is deleted, its ID will be preserved in `catalog.json` with `"removed": true`.

## CDN Endpoints
- **Catalog**: `https://cdn.jsdelivr.net/gh/VaibhavBajpaij/alarm-breaker-media@main/catalog.json`
- **Immutable Files**: `https://cdn.jsdelivr.net/gh/VaibhavBajpaij/alarm-breaker-media@<commit>/<file_path>`
