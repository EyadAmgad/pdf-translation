import os
import math
import tempfile
from pathlib import Path
from dataclasses import dataclass

import fitz                  # PyMuPDF — page-by-page extraction
import pymupdf4llm
from dotenv import load_dotenv
from openai import OpenAI
from temporalio import activity
import asyncio
from helpers import (
    ASSETS_DIR,
    parse_drive_path, get_file_name, download_drive_file, list_folder_pdfs
)
load_dotenv()

# ── Dataclasses ───────────────────────────────────────────────────────────────
    
@dataclass
class ExtractPDFInput:
    drive_path: str
    batch_size: int = 2

@dataclass
class ExtractPDFOutput:
    drive_path: str
    file_id: str
    local_path: str
    markdown_text: str
    page_count: int

@dataclass
class CallLLMInput:
    prompt: str

@dataclass
class CallLLMOutput:
    content: str
# 1- extract_pdf: Downloads a PDF from Google Drive, extracts its text in batches, and returns the full Markdown content along with metadata.
@activity.defn
async def extract_pdf(params: ExtractPDFInput) -> ExtractPDFOutput:

    activity.logger.info(f"Starting extraction: {params.drive_path}")

    activity.heartbeat({
        "stage": "downloading",
        "drive_path": params.drive_path,
        "pages_done": 0,
        "chars_extracted": 0,
    })

    # Resolve the Drive ID and a safe local filename
    file_id = parse_drive_path(params.drive_path)
    filename = await asyncio.to_thread(get_file_name, file_id)
    safe_name = Path(filename).name.replace("/", "_")
    local_path = str(ASSETS_DIR / f"{file_id}_{safe_name}")

    # Download (blocking I/O -> run in a thread so heartbeats keep working)
    await asyncio.to_thread(download_drive_file, file_id, local_path)

    with fitz.open(local_path) as doc:
        total_pages = doc.page_count

    activity.logger.info(f"Downloaded {total_pages}-page PDF: {params.drive_path}")

    all_text_chunks = []
    total_chars_num = 0
    num_batches = math.ceil(total_pages / params.batch_size)

    for batch_idx in range(num_batches):

        start_page = batch_idx * params.batch_size
        end_page = min(start_page + params.batch_size, total_pages)

        batch_md = await asyncio.to_thread(
            pymupdf4llm.to_markdown,
            local_path,
            pages=list(range(start_page, end_page)),
        )

        all_text_chunks.append(batch_md)
        total_chars_num += len(batch_md)

        activity.heartbeat({
            "stage":           "extracting",
            "drive_path":      params.drive_path,
            "pages_done":      end_page,
            "total_pages":     total_pages,
            "batch":           f"{start_page + 1}–{end_page}",
            "chars_extracted": total_chars_num,
            "progress_pct":    round(end_page / total_pages * 100),
        })

    full_md = "\n\n".join(all_text_chunks)

    # Optional: keep the Markdown next to the PDF (your helpers store both in ASSETS_DIR)
    md_path = Path(local_path).with_suffix(".md")
    md_path.write_text(full_md, encoding="utf-8")

    activity.heartbeat({
        "stage": "done",
        "drive_path": params.drive_path,
        "pages_done": total_pages,
        "chars_extracted": total_chars_num,
    })

    return ExtractPDFOutput(
        drive_path=params.drive_path,
        file_id=file_id,
        local_path=local_path,
        markdown_text=full_md,
        page_count=total_pages,
    )

# 2 - call_llm: Sends a prompt to the OpenAI API and returns the response content.

@activity.defn
async def call_llm(params: CallLLMInput) -> CallLLMOutput:
    activity.logger.info("Calling LLM")
    activity.heartbeat({"stage": "calling_llm",
                         "prompt_chars": len(params.prompt)})


    llm_client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )

    response = llm_client.chat.completions.create(
        model=os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        messages=[{"role": "user", "content": params.prompt}],
        max_tokens=8000,
    )

    content = response.choices[0].message.content

    activity.logger.info(f"LLM returned {len(content)} chars")

    return CallLLMOutput(
        content=content
    )