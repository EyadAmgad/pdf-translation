from prompts import _TRANSLATION_PROMPT
from dataclasses import dataclass
from datetime import timedelta

import json_repair
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import (
        extract_pdf, ExtractPDFInput,
        call_llm, CallLLMInput,
    )

@dataclass
class PDFTranslationInput:
    drive_path: str

@dataclass(frozen=True)
class PDFTranslationOutput:
    local_path: str
    translation: str
    confidence: str
    notes: str
    
DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=3),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=4,
)

@workflow.defn
class PDFTranslationWorkflow:
    
    @workflow.run
    async def run(self, params: PDFTranslationInput) -> PDFTranslationOutput:
        
        # execute: extract_pdf
        extracted_md = await workflow.execute_activity(
            extract_pdf,
            ExtractPDFInput(
                drive_path=params.drive_path
            ),
            retry_policy=DEFAULT_RETRY_POLICY,
            start_to_close_timeout=timedelta(minutes=20),
            heartbeat_timeout=timedelta(seconds=30),
        )


        # execute: call_llm
        prompt = _TRANSLATION_PROMPT.format(
            text=extracted_md.markdown_text[:5_000]
        )

        llm_result = await workflow.execute_activity(
            call_llm,
            CallLLMInput(
                prompt=prompt
            ),
            retry_policy=DEFAULT_RETRY_POLICY,
            start_to_close_timeout=timedelta(minutes=5),
            heartbeat_timeout=timedelta(seconds=180),
        )

        parsed_output = json_repair.loads(llm_result.content)

        return PDFTranslationOutput(
            local_path=extracted_md.local_path,
            translation=parsed_output.get("translation", ""),
            confidence=parsed_output.get("confidence", ""),
            notes=parsed_output.get("review_notes", "")
        )
    