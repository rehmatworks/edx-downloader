from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

CONFIG_DIR = Path.home() / ".edx-dl"
CONFIG_FILE = CONFIG_DIR / "config.json"

BASE_URL = "https://courses.edx.org"
OAUTH_CLIENT_ID = "brd4bg3iRGxsIUUKmXey339s1llgfFhc095Mxc8U"

class EdxAuthError(Exception):
    """Raised when authentication fails or the session has expired."""


class EdxNotEnrolledError(Exception):
    """Raised when the user is not enrolled in the requested course."""


def _save_config(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def _load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text())


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"JWT {token}"}


def _decode_jwt(token: str) -> dict[str, Any]:
    """Decode a JWT payload without signature verification."""
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return {}


def _is_token_expired(token: str, margin_seconds: int = 60) -> bool:
    """True if the JWT expires within *margin_seconds* from now."""
    claims = _decode_jwt(token)
    exp = claims.get("exp")
    if exp is None:
        return True
    return time.time() >= (exp - margin_seconds)


def login(email: str, password: str) -> dict[str, Any]:
    """Authenticate via the edX mobile OAuth2 endpoint and persist the token."""
    with httpx.Client(timeout=30) as http:
        resp = http.post(
            f"{BASE_URL}/oauth2/access_token",
            data={
                "grant_type": "password",
                "client_id": OAUTH_CLIENT_ID,
                "username": email,
                "password": password,
                "token_type": "JWT",
                "asymmetric_jwt": "1",
            },
        )
        resp.raise_for_status()
        payload = resp.json()

    claims = _decode_jwt(payload["access_token"])
    username = claims.get("preferred_username") or email

    config = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", ""),
        "username": username,
        "email": email,
    }
    _save_config(config)
    return config


def _refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Use a refresh token to obtain a new access token."""
    with httpx.Client(timeout=30) as http:
        resp = http.post(
            f"{BASE_URL}/oauth2/access_token",
            data={
                "grant_type": "refresh_token",
                "client_id": OAUTH_CLIENT_ID,
                "refresh_token": refresh_token,
                "token_type": "JWT",
                "asymmetric_jwt": "1",
            },
        )
        resp.raise_for_status()
        return resp.json()


def ensure_token() -> tuple[str, str]:
    """Return a valid (token, username) pair, refreshing automatically if needed.

    Raises EdxAuthError if the token cannot be refreshed.
    """
    cfg = _load_config()
    token = cfg.get("access_token", "")
    username = cfg.get("username", "")

    if not token or not username:
        raise EdxAuthError("Not logged in. Run `edx-dl login` first.")

    if not _is_token_expired(token):
        return token, username

    refresh = cfg.get("refresh_token", "")
    if not refresh:
        raise EdxAuthError(
            "Session expired and no refresh token available. Run `edx-dl login` again."
        )

    try:
        payload = _refresh_access_token(refresh)
    except httpx.HTTPStatusError:
        raise EdxAuthError(
            "Session expired and refresh failed. Run `edx-dl login` again."
        )

    new_token = payload["access_token"]
    claims = _decode_jwt(new_token)
    username = claims.get("preferred_username") or username

    cfg["access_token"] = new_token
    cfg["refresh_token"] = payload.get("refresh_token", refresh)
    cfg["username"] = username
    _save_config(cfg)

    return new_token, username


def fetch_enrollments(token: str, username: str) -> list[dict[str, Any]]:
    """Return every enrolled course (paginates automatically)."""
    courses: list[dict[str, Any]] = []
    url: str | None = (
        f"{BASE_URL}/api/mobile/v4/users/{username}/course_enrollments/"
    )
    with httpx.Client(timeout=30, headers=_auth_headers(token), follow_redirects=True) as http:
        while url:
            resp = http.get(url, params={"page_size": "50"})
            if resp.status_code == 401:
                raise EdxAuthError("Session expired. Run `edx-dl login` again.")
            resp.raise_for_status()
            data = resp.json()

            primary = data.get("primary")
            if primary and isinstance(primary, dict):
                courses.append(primary)

            enrollments = data.get("enrollments", {})
            results = enrollments.get("results", []) if isinstance(enrollments, dict) else []
            courses.extend(results)

            url = (enrollments.get("next") if isinstance(enrollments, dict) else None)
    return courses


def parse_course_id(url_or_id: str) -> str:
    """Accept a full edX URL or a raw course-v1:... id and return the id."""
    if url_or_id.startswith("course-v1:"):
        return url_or_id

    m = re.search(r"(course-v1:[^\s/&?]+)", url_or_id)
    if m:
        return m.group(1)

    m = re.search(r"courses/([^/]+/[^/]+/[^/]+)", url_or_id)
    if m:
        return m.group(1)

    raise ValueError(
        f"Cannot extract a course ID from: {url_or_id!r}. "
        "Provide a course-v1:Org+Number+Run string or a full edX course URL."
    )


def fetch_course_blocks(
    token: str, username: str, course_id: str
) -> dict[str, Any]:
    """Fetch the full block tree for a course."""
    with httpx.Client(timeout=60, headers=_auth_headers(token), follow_redirects=True) as http:
        resp = http.get(
            f"{BASE_URL}/api/mobile/v4/course_info/blocks/",
            params={
                "course_id": course_id,
                "username": username,
                "depth": "all",
                "nav_depth": "4",
                "requested_fields": (
                    "contains_gated_content,show_gated_sections,"
                    "special_exam_info,graded,format,"
                    "student_view_multi_device,due,completion,"
                    "assignment_progress"
                ),
                "student_view_data": "video,discussion,html",
                "block_counts": "video",
            },
        )
        if resp.status_code == 401:
            raise EdxAuthError("Session expired. Run `edx-dl login` again.")
        if resp.status_code in (403, 404):
            raise EdxNotEnrolledError(
                f"You are not enrolled in {course_id}, or the course does not exist."
            )
        resp.raise_for_status()
        return resp.json()
