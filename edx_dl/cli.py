from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from edx_dl import client, downloader
from edx_dl.client import EdxAuthError, EdxNotEnrolledError

app = typer.Typer(
    name="edx-dl",
    help="Download videos and transcripts from your edX courses.",
    add_completion=False,
)
console = Console()


def _get_auth() -> tuple[str, str]:
    """Return (token, username), printing a friendly error on failure."""
    try:
        return client.ensure_token()
    except EdxAuthError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)


@app.command()
def login(
    email: str = typer.Option(..., prompt=True, help="edX account email"),
    password: str = typer.Option(
        ..., prompt=True, hide_input=True, help="edX account password"
    ),
) -> None:
    """Authenticate with edX and save credentials locally."""
    try:
        cfg = client.login(email, password)
        console.print(
            f"\n[bold green]Logged in as [cyan]{cfg['username']}[/cyan][/bold green]"
        )
        console.print(f"Token saved to {client.CONFIG_FILE}")
    except Exception as exc:
        console.print(f"\n[bold red]Login failed:[/bold red] {exc}")
        raise typer.Exit(1)


@app.command()
def courses() -> None:
    """List all courses you are enrolled in."""
    token, username = _get_auth()

    with console.status("Fetching enrolled courses..."):
        try:
            enrollments = client.fetch_enrollments(token, username)
        except EdxAuthError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1)

    if not enrollments:
        console.print("[yellow]No enrolled courses found.[/yellow]")
        raise typer.Exit()

    table = Table(title="Enrolled Courses", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Course ID", style="cyan", max_width=50)
    table.add_column("Name", style="green")
    table.add_column("Org", style="magenta")

    seen: set[str] = set()
    idx = 0
    for enrollment in enrollments:
        course = enrollment.get("course", {})
        cid = course.get("id", "")
        if cid in seen:
            continue
        seen.add(cid)
        idx += 1
        table.add_row(
            str(idx),
            cid,
            course.get("name", ""),
            course.get("org", ""),
        )

    console.print(table)
    console.print(
        "\n[dim]Use the Course ID above with the download command:[/dim]"
    )
    console.print("[dim]  edx-dl download <course-id>[/dim]\n")


@app.command()
def download(
    course: str = typer.Argument(
        help=(
            "Course ID (e.g. course-v1:HarvardX+CS50+X) or a full edX course URL."
        )
    ),
    output: Path = typer.Option(
        Path("./downloads"),
        "--output", "-o",
        help="Base output directory for downloaded files.",
    ),
    quality: str = typer.Option(
        "high",
        "--quality", "-q",
        help="Video quality: high (720p mp4), medium (360p mp4), or low (360p).",
    ),
    subtitles: str = typer.Option(
        "en",
        "--subs", "-s",
        help="Comma-separated transcript language codes (e.g. en,es,fr). Use 'all' for every available language.",
    ),
) -> None:
    """Download all videos and transcripts for a course."""
    token, username = _get_auth()

    try:
        course_id = client.parse_course_id(course)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)

    console.print(f"\n[bold]Course:[/bold] [cyan]{course_id}[/cyan]")

    with console.status("Fetching course structure..."):
        try:
            data = client.fetch_course_blocks(token, username, course_id)
        except EdxNotEnrolledError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1)
        except EdxAuthError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1)

    blocks = data.get("blocks", {})
    root_id = data.get("root", "")
    if not blocks or not root_id:
        console.print("[red]Could not retrieve course blocks.[/red]")
        raise typer.Exit(1)

    items = downloader.build_course_tree(blocks, root_id)

    video_count = len(items)
    root_name = blocks.get(root_id, {}).get("display_name", course_id)
    console.print(f"[bold]Title:[/bold] {root_name}")
    console.print(f"[bold]Videos:[/bold] {video_count}")

    if video_count == 0:
        console.print("[yellow]No videos found in this course.[/yellow]")
        raise typer.Exit()

    sub_langs: list[str] | None
    if subtitles.strip().lower() == "all":
        sub_langs = None
        console.print("[bold]Subtitles:[/bold] all available languages")
    else:
        sub_langs = [s.strip() for s in subtitles.split(",") if s.strip()]
        console.print(f"[bold]Subtitles:[/bold] {', '.join(sub_langs)}")

    console.print(f"[bold]Quality:[/bold] {quality}")
    console.print(f"[bold]Output:[/bold] {output.resolve()}\n")

    all_sub_langs = sub_langs
    if all_sub_langs is None:
        all_langs: set[str] = set()
        for item in items:
            all_langs.update(item.get("transcripts", {}).keys())
        all_sub_langs = sorted(all_langs)

    downloader.download_course(
        items,
        output_dir=output,
        quality=quality,
        token=token,
        transcript_langs=all_sub_langs,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
