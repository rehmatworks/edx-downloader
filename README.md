# edx-downloader

A CLI tool to download videos and transcripts from your [edX](https://www.edx.org) courses.

> **v2.0** is a complete rewrite. It uses the official edX mobile API instead of
> HTML scraping, making it faster, more reliable, and capable of downloading
> transcripts in any language. See the [v1 branch](https://github.com/rehmatworks/edx-downloader/tree/v1)
> for the legacy version.

## Installation

```bash
pip install edx-downloader
```

Or install from source:

```bash
git clone https://github.com/rehmatworks/edx-downloader.git
cd edx-downloader
pip install .
```

To also download YouTube-hosted videos (some courses use them):

```bash
pip install "edx-downloader[youtube]"
```

## Quick Start

```bash
# 1. Log in (you'll be prompted for credentials)
edx-dl login

# 2. List your enrolled courses
edx-dl courses

# 3. Download a course
edx-dl download "course-v1:HarvardX+CS50+X"
```

## Commands

### `edx-dl login`

Authenticate with edX. Your JWT token is saved to `~/.edx-dl/config.json`
and refreshed automatically when it expires.

```bash
edx-dl login
# Email: you@example.com
# Password: ****
```

### `edx-dl courses`

List all courses you are enrolled in, showing Course IDs you can use
with the download command.

```bash
edx-dl courses
```

### `edx-dl download`

Download all videos and transcripts for a course.

```bash
# By course ID
edx-dl download "course-v1:HarvardX+CS50+X"

# By full URL
edx-dl download "https://courses.edx.org/courses/course-v1:HarvardX+CS50+X/course/"
```

#### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--output` | `./downloads` | Output directory |
| `-q`, `--quality` | `high` | Video quality: `high` (720p) or `medium` (360p) |
| `-s`, `--subs` | `en` | Transcript languages (comma-separated, or `all`) |

#### Examples

```bash
# Download with English + Spanish subtitles to a custom folder
edx-dl download "course-v1:HarvardX+CS50+X" -s "en,es" -o ~/courses

# Download all available transcript languages at 360p
edx-dl download "course-v1:HarvardX+CS50+X" -q medium -s all

# Resume an interrupted download (already-downloaded files are skipped)
edx-dl download "course-v1:HarvardX+CS50+X"
```

## Output Structure

```
downloads/
└── CS50s Introduction to Computer Science/
    ├── 01 - Week 0/
    │   ├── 01 - Lecture/
    │   │   ├── 01 - Introduction.mp4
    │   │   ├── 01 - Introduction [en].srt
    │   │   └── 01 - Introduction [es].srt
    │   └── 02 - Problem Set/
    │       └── ...
    └── 02 - Week 1/
        └── ...
```

## Features

- **Fast**: Single API call retrieves the entire course structure (no HTML scraping)
- **Reliable**: Uses the stable edX mobile API with JWT authentication
- **Transcripts**: Download subtitles in any available language
- **Quality choice**: Pick between 720p and 360p MP4 downloads
- **Resume support**: Re-run the same command to skip already-downloaded files
- **YouTube fallback**: Automatically uses `yt-dlp` for YouTube-hosted videos (if installed)
- **Auto token refresh**: JWT tokens are refreshed automatically, even during long downloads
- **Smart naming**: Falls back to section names when video blocks have generic titles

## Requirements

- Python 3.10+
- An [edX](https://www.edx.org) account enrolled in the course(s) you want to download

## Disclaimer

This tool is intended to help learners download course videos for offline study.
Do not use it to redistribute copyrighted content. You are responsible for
complying with edX's terms of service.

## License

MIT
