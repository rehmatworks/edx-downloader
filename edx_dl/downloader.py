from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from edx_dl import client as auth_client

console = Console()

QUALITY_PREF = {
    "high": ["desktop_mp4", "mobile_low"],
    "medium": ["mobile_low", "desktop_mp4"],
    "low": ["mobile_low"],
}

GENERIC_VIDEO_NAMES = {"video", "video 1", "video 2", "video 3"}


def _sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"_+", "_", name).strip("_. ")
    return name[:200] or "untitled"


def _pick_video_url(encoded_videos: dict[str, Any], quality: str) -> tuple[str, str] | None:
    """Return (url, label) for the best matching video quality."""
    prefs = QUALITY_PREF.get(quality, QUALITY_PREF["high"])
    for key in prefs:
        entry = encoded_videos.get(key)
        if entry and entry.get("url"):
            return entry["url"], key
    return None


def _get_youtube_id(encoded_videos: dict[str, Any]) -> str | None:
    """Extract a YouTube video ID if the block only has YouTube sources."""
    yt = encoded_videos.get("youtube")
    if not yt:
        return None
    url = yt.get("url", "")
    m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    return m.group(1) if m else None


def _download_file(
    client: httpx.Client,
    url: str,
    dest: Path,
    progress: Progress,
    label: str,
) -> bool:
    """Stream-download *url* to *dest*. Skips if file already exists with nonzero size."""
    if dest.exists() and dest.stat().st_size > 0:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    with client.stream("GET", url, follow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0)) or None
        task = progress.add_task(label, total=total)
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 64):
                f.write(chunk)
                progress.update(task, advance=len(chunk))
        progress.remove_task(task)

    tmp.rename(dest)
    return True


def _download_youtube(yt_id: str, dest: Path, quality: str) -> bool:
    """Download a YouTube video via yt-dlp. Returns False if yt-dlp is absent."""
    if dest.exists() and dest.stat().st_size > 0:
        return True

    if shutil.which("yt-dlp") is None:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]" if quality == "high" else "bestvideo[height<=360]+bestaudio/best[height<=360]"
    url = f"https://www.youtube.com/watch?v={yt_id}"

    try:
        subprocess.run(
            ["yt-dlp", "-f", fmt, "--merge-output-format", "mp4", "-o", str(dest), url],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _smart_display_name(
    display_name: str,
    section_label: str,
    index: int,
    total_in_section: int,
) -> str:
    """Use section name as fallback when the video block has a generic name like 'Video'."""
    if display_name.strip().lower() not in GENERIC_VIDEO_NAMES:
        return display_name

    section_clean = re.sub(r"^\d+\s*-\s*", "", section_label).strip()
    if total_in_section == 1:
        return section_clean
    return f"{section_clean} - Part {index}"


def build_course_tree(
    blocks: dict[str, Any], root_id: str
) -> list[dict[str, Any]]:
    """
    Walk the block tree and return a flat list of downloadable items, each
    annotated with chapter/sequential names for folder structure.
    """
    items: list[dict[str, Any]] = []
    root = blocks[root_id]
    course_name = _sanitize(root.get("display_name", "course"))

    chapter_idx = 0
    for child_id in root.get("descendants", []):
        child = blocks.get(child_id, {})
        if child.get("type") != "chapter":
            continue
        chapter_idx += 1
        chapter_name = _sanitize(child.get("display_name", f"Chapter {chapter_idx}"))
        chapter_label = f"{chapter_idx:02d} - {chapter_name}"

        seq_idx = 0
        for seq_id in child.get("descendants", []):
            seq = blocks.get(seq_id, {})
            if seq.get("type") != "sequential":
                continue
            seq_idx += 1
            seq_name = _sanitize(seq.get("display_name", f"Section {seq_idx}"))
            seq_label = f"{seq_idx:02d} - {seq_name}"

            section_items: list[dict[str, Any]] = []
            _collect_videos(
                blocks, seq, section_items, course_name,
                chapter_label, seq_label, counter=[0],
            )

            total = len(section_items)
            for item in section_items:
                item["display_name"] = _smart_display_name(
                    item["display_name"], seq_label, item["index"], total,
                )
            items.extend(section_items)

    return items


def _collect_videos(
    blocks: dict[str, Any],
    node: dict[str, Any],
    items: list[dict[str, Any]],
    course_name: str,
    chapter_label: str,
    seq_label: str,
    counter: list[int],
) -> None:
    """Recursively collect video blocks under *node*."""
    if node.get("type") == "video":
        counter[0] += 1
        svd = node.get("student_view_data", {})
        items.append(
            {
                "course": course_name,
                "chapter": chapter_label,
                "section": seq_label,
                "index": counter[0],
                "display_name": node.get("display_name", f"Video {counter[0]}"),
                "encoded_videos": svd.get("encoded_videos", {}),
                "transcripts": svd.get("transcripts", {}),
                "only_on_web": svd.get("only_on_web", False),
            }
        )
        return

    for desc_id in node.get("descendants", []):
        desc = blocks.get(desc_id, {})
        _collect_videos(blocks, desc, items, course_name, chapter_label, seq_label, counter)


def _ensure_transcript_client(
    current: httpx.Client | None,
    token_holder: list[str],
) -> httpx.Client:
    """Return a transcript client with a valid token, refreshing if needed.

    Closes the old client and creates a new one if the token was refreshed.
    """
    old_token = token_holder[0]

    try:
        new_token, _ = auth_client.ensure_token()
    except Exception:
        new_token = old_token

    if current is not None and new_token == old_token:
        return current

    if current is not None:
        current.close()

    token_holder[0] = new_token
    return httpx.Client(
        timeout=30,
        headers={"Authorization": f"JWT {new_token}"},
        follow_redirects=True,
    )


def download_course(
    items: list[dict[str, Any]],
    output_dir: Path,
    quality: str = "high",
    token: str = "",
    transcript_langs: list[str] | None = None,
) -> None:
    """Download all videos and transcripts for the collected items."""
    if not items:
        console.print("[yellow]No downloadable video content found.[/yellow]")
        return

    if transcript_langs is None:
        transcript_langs = ["en"]

    token_holder = [token]
    yt_dlp_available: bool | None = None
    yt_dlp_warned = False
    transcript_client: httpx.Client | None = None
    failed_transcripts: list[str] = []

    try:
        with (
            httpx.Client(timeout=httpx.Timeout(30, read=300), follow_redirects=True) as video_client,
            Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress,
        ):
            for item in items:
                folder = (
                    output_dir
                    / item["course"]
                    / item["chapter"]
                    / item["section"]
                )
                prefix = f"{item['index']:02d} - {_sanitize(item['display_name'])}"
                short = f"{item['chapter'][:30]}/{prefix[:40]}"

                pick = _pick_video_url(item["encoded_videos"], quality)
                if pick:
                    url, label = pick
                    dest = folder / f"{prefix}.mp4"
                    if dest.exists() and dest.stat().st_size > 0:
                        console.print(f"  [dim]skip (exists)[/dim] {short}")
                    else:
                        console.print(f"  [green]downloading[/green] {short}")
                        try:
                            _download_file(video_client, url, dest, progress, short)
                        except httpx.HTTPStatusError as exc:
                            console.print(f"  [red]failed ({exc.response.status_code})[/red] {short}")
                else:
                    yt_id = _get_youtube_id(item["encoded_videos"])
                    if yt_id:
                        dest = folder / f"{prefix}.mp4"
                        if dest.exists() and dest.stat().st_size > 0:
                            console.print(f"  [dim]skip (exists)[/dim] {short}")
                        else:
                            if yt_dlp_available is None:
                                yt_dlp_available = shutil.which("yt-dlp") is not None
                            if yt_dlp_available:
                                console.print(f"  [green]downloading (youtube)[/green] {short}")
                                if not _download_youtube(yt_id, dest, quality):
                                    console.print(f"  [red]yt-dlp failed[/red] {short}")
                            else:
                                if not yt_dlp_warned:
                                    console.print(
                                        "\n  [yellow]Some videos are YouTube-only. "
                                        "Install yt-dlp to download them:[/yellow]"
                                        "\n  [dim]  pip install yt-dlp[/dim]\n"
                                    )
                                    yt_dlp_warned = True
                                console.print(f"  [yellow]skip (youtube, no yt-dlp)[/yellow] {short}")
                    elif item.get("only_on_web"):
                        console.print(f"  [yellow]skip (web-only)[/yellow] {short}")
                    else:
                        console.print(f"  [yellow]no video URL[/yellow] {item['display_name']}")

                for lang in transcript_langs:
                    t_url = item["transcripts"].get(lang)
                    if not t_url:
                        continue
                    t_dest = folder / f"{prefix} [{lang}].srt"
                    if t_dest.exists() and t_dest.stat().st_size > 0:
                        continue
                    transcript_client = _ensure_transcript_client(transcript_client, token_holder)
                    try:
                        _download_file(transcript_client, t_url, t_dest, progress, f"transcript [{lang}]")
                    except httpx.HTTPStatusError as exc:
                        failed_transcripts.append(f"{prefix} [{lang}] ({exc.response.status_code})")
                    except httpx.TransportError:
                        failed_transcripts.append(f"{prefix} [{lang}] (network error)")
    finally:
        if transcript_client is not None:
            transcript_client.close()

    if failed_transcripts:
        console.print(f"\n[yellow]Failed to download {len(failed_transcripts)} transcript(s):[/yellow]")
        for name in failed_transcripts:
            console.print(f"  [dim]{name}[/dim]")

    console.print("\n[bold green]Download complete.[/bold green]")
