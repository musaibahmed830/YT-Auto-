# 🚀 AutoTube AI: 100% Free Autonomous YouTube Video & Shorts Automation Engine

[![GitHub Stars](https://img.shields.io/github/stars/musaibahmed830/YT-Auto-?style=for-the-badge&logo=github)](https://github.com/musaibahmed830/YT-Auto-)
[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11-blue?style=for-the-badge&logo=python)](https://python.org)
[![100% Free API](https://img.shields.io/badge/Cost-100%25%20Free-brightgreen?style=for-the-badge)](https://github.com/musaibahmed830/YT-Auto-)
[![GitHub Actions](https://img.shields.io/badge/Runs%20On-GitHub%20Actions%20(Free)-orange?style=for-the-badge&logo=githubactions)](https://github.com/features/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

**AutoTube AI** is a state-of-the-art, **100% FREE** autonomous YouTube automation bot. It creates and publishes high-retention, faceless **Long-Form Videos (~60s)** and **YouTube Shorts (~20s)** on complete autopilot using **GitHub Actions**.

Built specifically for content creators, faceless YouTube channels, storytellers, and automation builders. **Zero paid APIs. Zero monthly subscriptions.**

---

## 🔍 Key SEO Highlights & Target Topics
> `youtube automation` • `ai video generator` • `youtube shorts automation` • `faceless youtube channel` • `text to video ai python` • `automated youtube uploader` • `free ai video generator` • `github actions youtube bot` • `ai storytelling channel` • `youtube shorts bot` • `tiktok to youtube automation`

---

## ✨ Features

- 🎭 **Story-Series Mode**: Give a single story prompt and the AI plans a multi-episode narrative series (Part 1, Part 2, etc.) with intense cliffhangers.
- 📱 **Dual Video Output**: Simultaneously generates both a **1-Minute Main Video (16:9 Widescreen)** and a **20-Second YouTube Short (9:16 Vertical)** for every episode.
- ⏰ **Scheduled 6 AM & 6 PM Auto-Upload**: Runs twice daily on autopilot via GitHub Actions free cron timers.
- 🗣️ **Ultra-Realistic Neural Voiceover**: Powered by Microsoft Edge-TTS neural engine (`en-US-ChristopherNeural`, `en-US-AndrewNeural`). No robotic voices, no ElevenLabs fees.
- 🎥 **Realistic Visuals & Motion**: Downloads 1080p real stock clips via Pexels, real biographical photos with Ken Burns zoom from Wikimedia Commons, and procedural cinematic background fallbacks.
- 📈 **Autonomous YouTube SEO**: Automatically generates high-CTR titles, keyword-optimized descriptions, tags, and custom 1280x720 thumbnails.
- 🛡️ **Bulletproof CI/CD**: Automatic fallback between Google Gemini and Groq, header sanitization, ffmpeg error recovery, and automatic state saving.

---

## 🛠️ The 100% Free Technology Stack

| Component | Free Provider | Cost |
|---|---|---|
| **LLM & Scriptwriting** | Google Gemini (`gemini-3.8-flash` / `gemini-2.5-flash`) & Groq (`llama-3.1-8b-instant`) | **$0.00** |
| **Voiceover / TTS** | Microsoft Edge-TTS Neural Voices | **$0.00** |
| **Stock Video Clips** | Pexels API (Free tier) + Wikimedia Commons | **$0.00** |
| **Video Assembly** | FFmpeg (GPU / CPU hardware accelerated) | **$0.00** |
| **Thumbnail Generation** | Pillow (PIL) | **$0.00** |
| **Automation & Hosting** | GitHub Actions (Ubuntu Runners, 2000 free min/mo) | **$0.00** |
| **YouTube Publishing** | YouTube Data API v3 (10,000 free quota units/day) | **$0.00** |

---

## 🚀 Quick Start Guide

### 1. Clone & Install Locally
```bash
git clone https://github.com/musaibahmed830/YT-Auto-.git
cd YT-Auto-
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Create a `.env` file in the project root:
```env
# Free LLM Key (Pick either one or both)
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key

# Free Stock Visuals
PEXELS_API_KEY=your_pexels_api_key

# YouTube OAuth (From Google Cloud Console)
YT_CLIENT_ID=your_client_id.apps.googleusercontent.com
YT_CLIENT_SECRET=your_client_secret
YT_REFRESH_TOKEN=your_refresh_token
```

---

## 📖 How to Use

### Mode A: Story Series (Episodic Generation)
Want to create a 5-part suspense story, historical mystery, or sci-fi drama?

#### 1. Plan the series:
```bash
python src/story_series.py plan "A suspense thriller about a 1940 ghost ship that reappears in 2026" 5
```
This generates `series_state.json` containing:
- 5 full 60s main video scripts with cliffhangers
- 5 fast-paced 20s YouTube Shorts scripts
- Concrete cinematic visual keywords for Pexels

#### 2. Check series progress anytime:
```bash
python src/story_series.py status
```

#### 3. Manual Editing:
You can open `series_state.json` directly in any text editor to customize scripts, edit narration, reorder parts, or tweak keywords.

#### 4. Run next episode:
```bash
python main.py
```
This uploads Episode 1 (both Long-Form + Short), marks it as completed, and advances the tracker for the next scheduled run.

---

### Mode B: Daily Trending Topics (Autonomous Fallback)
If no story series is active in `series_state.json`, the bot automatically:
1. Fetches real-time breakout trends from the **Google Trends RSS Feed**.
2. Researches high-intent YouTube search terms.
3. Produces and uploads the trending long-form video + companion short.

---

## ⏱️ Scheduling via GitHub Actions

The repository includes a pre-configured workflow [`.github/workflows/daily_video.yml`](.github/workflows/daily_video.yml):

- **Schedule**: Twice daily at **6:00 AM** and **6:00 PM PKT** (`0 1,13 * * *` UTC).
- **Manual Trigger**: Go to the **Actions** tab ➡️ Select **YouTube Automation** ➡️ Click **Run workflow**. You can also enter a new story prompt directly in the modal!
- **State Persistence**: GitHub Actions automatically commits `series_state.json` after every run to keep track of uploaded episodes.

---

## 🔑 One-Time YouTube API Token Setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com).
2. Enable **YouTube Data API v3**.
3. Create an **OAuth 2.0 Client ID** (Desktop Application) and download `client_secret.json` into this folder.
4. Run locally:
   ```bash
   python get_refresh_token.py
   ```
5. Authorize with your channel's Google account to receive your `YT_REFRESH_TOKEN`.
6. Add all keys to your repository under **Settings ➡️ Secrets and variables ➡️ Actions**.

---

## 🤝 Contributing
Contributions, stars ⭐, and feature requests are welcome! Feel free to open an issue or pull request.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
