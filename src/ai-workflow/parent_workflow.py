import asyncio
import textwrap
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
import json_repair
import json

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError
from temporalio.workflow import ParentClosePolicy

from prompts import _TRANSLATION_PROMPT, _REVISION_PROMPT

DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=3),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=4,
)

with workflow.unsafe.imports_passed_through():
    from activities import (
        call_llm, CallLLMInput,
    )
    from child_workflow import (
        PDFTranslationWorkflow,
        PDFTranslationInput
    )
@dataclass
class TranslationReviewInput:
    file_paths: list[str]
    max_concurrent_translations: Optional[int] = 3
@dataclass
class TranslationReviewOutput:
    report:str
    sources: list[str]
    approved_by: str
@workflow.defn
class TranslationReviewWorkflow:

    def __init__(self):
        self.status: str = "processing"
        self.summaries:list = []
        self.report: str = ""
    @workflow.run    
    async def run(self, params: TranslationReviewInput) -> TranslationReviewOutput:  
        self.status = "extraction"
        workflow_id = workflow.info().workflow_id

        workflow.logger.info(f"Starting Translation Review Workflow for files: {params.file_paths}")
        workflow_task_queue = workflow.info().task_queue

        raw_results = await asyncio.gather(*[
            workflow.execute_child_workflow(
                PDFTranslationWorkflow.run,
                PDFTranslationInput(drive_path=file_path),
                id=f"translation-pdf-{workflow_id}-{idx+1}",
                task_queue=workflow_task_queue,
                parent_close_policy=ParentClosePolicy.ABANDON,
            )
            for idx, file_path in enumerate(params.file_paths)
        ], return_exceptions=True)

        for i , res in enumerate(raw_results):
            if isinstance(res,Exception):
                workflow.logger.warning(f"PDF {i} failed {res}")
            else:
                self.summaries.append(
                    {
                        "local_path": res.local_path,
                        "translation": res.translation,
                        "confidence": res.confidence,
                        "notes": res.notes
                    }
                ) 
        if len(self.summaries) == 0:
            raise ApplicationError("All PDF translations failed. No summaries to generate report.")
        # Step 2: Generate a report based on the summaries
        self.status = "report_generation"
        workflow.logger.info("Generating report based on summaries.")

        combined_summary = "\n\n".join([

            f"**Contract {i+1}** (`{summary['local_path']}`):\n"
            f"translation: {summary['translation']}\n"
            f"Confidence: {summary['confidence']}\n"
            f"Notes: {summary['notes']}\n"

            for i, summary in enumerate(self.summaries)
        ])

        llm_prompt = _TRANSLATION_PROMPT.format(
            text=combined_summary
        )
        llm_result = await workflow.execute_activity(
        call_llm,
        CallLLMInput(
            prompt=llm_prompt
        ),
        start_to_close_timeout=timedelta(minutes=3),
        heartbeat_timeout=timedelta(seconds=180),
        retry_policy=DEFAULT_RETRY_POLICY,
        )
        self.report = json_repair.loads(llm_result.content)
        self.status = "completed"

        return TranslationReviewOutput(
            report=self.report,
            sources=[summary["local_path"] for summary in self.summaries],
            approved_by="pending",
        )


        
