"""
Activities are the **individual steps**. Each one does exactly one thing.
"""

import asyncio
import logging
from pathlib import Path

import pymupdf4llm
from temporalio import activity

from helpers import (
    ASSETS_DIR, parse_drive_path, get_file_name, download_drive_file, list_folder_pdfs,
    ListInput, ListOutput,
    DownloadInput, DownloadOutput,
    ExtractInput, ExtractOutput,
    SaveInput, SaveOutput,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ── Step 0 (optional): List PDFs in a folder ─────────────────────────────────
@activity.defn
async def list_drive_pdfs(params: ListInput) -> ListOutput:
    """List PDF file IDs inside a Google Drive folder."""
    folder_id = parse_drive_path(params.folder_path)
    activity.logger.info(f"Listing PDFs in Drive folder: {folder_id}")
 
    file_ids = await asyncio.to_thread(list_folder_pdfs, folder_id)
 
    activity.logger.info(f"Found {len(file_ids)} PDF(s)")
    return ListOutput(file_ids=file_ids)
 
 
# ── Step 1: Download ─────────────────────────────────────────────────────────
@activity.defn
async def download_pdf(params: DownloadInput) -> DownloadOutput:
    """Download a PDF from Google Drive. Returns local file path."""
    file_id = params.drive_file_id
    filename = await asyncio.to_thread(get_file_name, file_id)
    local_path = str(ASSETS_DIR / filename)
 
    activity.logger.info(f"Downloading: drive:{file_id} => {local_path}")
 
    await asyncio.to_thread(download_drive_file, file_id, local_path)
 
    activity.logger.info(f"COMPLETED Downloading : {local_path} ")
 
    return DownloadOutput(local_path=local_path)
 
 
# ── Step 2: Extract to Markdown ───────────────────────────────────────────────
@activity.defn
async def extract_to_markdown(params: ExtractInput) -> ExtractOutput:
    """Extract text from PDF and convert to Markdown. Returns markdown string."""
    activity.logger.info(f"Extracting text from {params.local_path}")
    markdown_text = await asyncio.to_thread(pymupdf4llm.to_markdown, params.local_path)
 
    activity.logger.info(f"Extraction complete — {len(markdown_text)} characters")
    return ExtractOutput(markdown_text=markdown_text, local_path=params.local_path)
 
 
# ── Step 3: Save Markdown ────────────────────────────────────────────────────
@activity.defn
async def save_markdown(params: SaveInput) -> SaveOutput:
    """Save markdown content to assets/. Returns the output file path."""
    md_path = ASSETS_DIR / f"{Path(params.local_path).stem}.md"
 
    activity.logger.info(f"Saving markdown → {md_path}")
    md_path.write_text(params.markdown_text, encoding="utf-8")
 
    activity.logger.info(f"Save complete: {md_path}")
    return SaveOutput(output_path=str(md_path))
 