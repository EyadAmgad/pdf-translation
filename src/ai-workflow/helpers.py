"""
Shared helpers for the Google Drive -> Markdown activities:
env/paths, Drive client, Drive I/O, and the activity input/output models.
"""

import io
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

# ── Config ───────────────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(SRC_DIR / ".env")


def _resolve_dir(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


# PDFs and generated Markdown files are both stored here
ASSETS_DIR = _resolve_dir(os.getenv("GOOGLE_DRIVE_EXPORT_DIRECTORY", "assets"))

_ID_PATTERN = re.compile(r"/file/d/([^/]+)|/d/([^/]+)|/folders/([^/]+)")


# ── Google Drive ─────────────────────────────────────────────────────────────
def parse_drive_path(value: str) -> str:
    """Accept a Drive file/folder URL or a raw ID and return the ID."""
    value = (value or "").strip()
    if not value:
        raise ValueError("A Google Drive URL or ID is required.")
    if not value.startswith(("http://", "https://")):
        return value

    parsed = urlparse(value)
    if "drive.google.com" in parsed.netloc.lower():
        match = _ID_PATTERN.search(parsed.path)
        if match:
            return next(g for g in match.groups() if g)
        ids = parse_qs(parsed.query).get("id")
        if ids:
            return ids[0]
    raise ValueError(f"Unsupported Google Drive URL: {value}")


def get_drive_client():
    """Drive API client from .env credentials, or None when none are configured."""
    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
    api_key = os.getenv("GOOGLE_DRIVE_API_KEY")
    if not key_path and not api_key:
        return None

    from googleapiclient.discovery import build

    if key_path:
        from google.oauth2 import service_account

        path = Path(key_path).expanduser()
        if not path.is_absolute():
            path = (SRC_DIR / path).resolve()
        creds = service_account.Credentials.from_service_account_file(
            str(path), scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    return build("drive", "v3", developerKey=api_key, cache_discovery=False)


def get_file_name(file_id: str) -> str:
    """File name from Drive metadata; falls back to '<file_id>.pdf' without API access."""
    client = get_drive_client()
    if client:
        meta = client.files().get(fileId=file_id, fields="name", supportsAllDrives=True).execute()
        return meta["name"]
    return f"{file_id}.pdf"


def download_drive_file(file_id: str, local_path: str) -> None:
    """Download a Drive file to local_path (API when configured, public link otherwise)."""
    client = get_drive_client()
    if client:
        from googleapiclient.http import MediaIoBaseDownload

        buffer = io.BytesIO()
        request = client.files().get_media(fileId=file_id, supportsAllDrives=True)
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        content = buffer.getvalue()
    else:
        response = requests.get(
            f"https://drive.google.com/uc?export=download&id={file_id}", timeout=120
        )
        response.raise_for_status()
        content = response.content

    if not content.startswith(b"%PDF"):
        raise ValueError(f"Drive file {file_id} is not a PDF.")
    Path(local_path).write_bytes(content)


def list_folder_pdfs(folder_id: str) -> list[str]:
    """IDs of PDFs in a Drive folder (API when configured, public-page scrape otherwise)."""
    client = get_drive_client()
    if client:
        files = client.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
            pageSize=1000, fields="files(id)",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute().get("files", [])
        return [f["id"] for f in files]

    page = requests.get(f"https://drive.google.com/drive/folders/{folder_id}", timeout=60)
    page.raise_for_status()
    ids = re.findall(r"/file/d/([A-Za-z0-9_-]+)", page.text)
    return list(dict.fromkeys(ids))


# ── Activity inputs / outputs ────────────────────────────────────────────────
@dataclass
class ListInput:
    folder_path: str


@dataclass
class ListOutput:
    file_ids: list[str]


@dataclass
class DownloadInput:
    drive_file_id: str


@dataclass
class DownloadOutput:
    local_path: str


@dataclass
class ExtractInput:
    local_path: str


@dataclass
class ExtractOutput:
    markdown_text: str
    local_path: str


@dataclass
class SaveInput:
    local_path: str             # the downloaded PDF; the .md gets the same name
    markdown_text: str


@dataclass
class SaveOutput:
    output_path: str