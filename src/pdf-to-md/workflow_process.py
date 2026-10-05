from datetime import timedelta
from dataclasses import dataclass

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities — use the string-based import pattern to keep
# the workflow sandbox clean (required by Temporal Python SDK)
with workflow.unsafe.imports_passed_through():
    from download_pdf import (
        list_drive_pdfs,
        download_pdf,
        extract_to_markdown,
        save_markdown,
    )

    from helpers import (
        ListInput, ListOutput,
        DownloadInput, DownloadOutput,
        ExtractInput, ExtractOutput,
        SaveInput, SaveOutput,
    )

@dataclass
class PDFPipelineInput:
    folder_path: str

@dataclass
class PDFPipelineOutput:
    md_local_paths: list[str]




DEFAULT_RETRY = RetryPolicy(    
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0, # double the wait each retry: 2s, 4s, 8s
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=5
)



@workflow.defn
class PDFPipelineWorkflow:

    @workflow.run
    async def run(self, params: PDFPipelineInput) -> PDFPipelineOutput:

        workflow.logger.info(f"Starting PDF folder pipeline for: {params.folder_path}")

        list_result = await workflow.execute_activity(
            list_drive_pdfs,
            ListInput(folder_path=params.folder_path),
            retry_policy=DEFAULT_RETRY,
            start_to_close_timeout=timedelta(minutes=3),
            result_type=ListOutput,
        )

        markdown_paths: list[str] = []
        for file_id in list_result.file_ids:
            download_result = await workflow.execute_activity(
                download_pdf,
                DownloadInput(drive_file_id=file_id),
                retry_policy=DEFAULT_RETRY,
                start_to_close_timeout=timedelta(minutes=3),
                result_type=DownloadOutput,
            )

            extract_result = await workflow.execute_activity(
                extract_to_markdown,
                ExtractInput(local_path=download_result.local_path),
                retry_policy=DEFAULT_RETRY,
                start_to_close_timeout=timedelta(minutes=10),
                result_type=ExtractOutput,
            )

            save_result = await workflow.execute_activity(
                save_markdown,
                SaveInput(
                    markdown_text=extract_result.markdown_text,
                    local_path=extract_result.local_path,
                ),
                retry_policy=DEFAULT_RETRY,
                start_to_close_timeout=timedelta(minutes=3),
                result_type=SaveOutput,
            )
            markdown_paths.append(save_result.output_path)

        workflow.logger.info(f"Pipeline complete. Output files: {len(markdown_paths)}")

        return PDFPipelineOutput(md_local_paths=markdown_paths)
