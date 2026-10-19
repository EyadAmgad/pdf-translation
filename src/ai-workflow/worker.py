# The Worker is the **process that runs your code**. 
# It connects to Temporal, polls for tasks, 
# and executes Workflows and Activities.

import asyncio
import logging
import os
from child_workflow import (
    PDFTranslationWorkflow

)
from parent_workflow import (
    TranslationReviewWorkflow
)
from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

from activities import (
    extract_pdf, call_llm
)

load_dotenv()

TEMPORAL_HOST = os.environ["TEMPORAL_HOST"]
TEMPORAL_NAMESPACE = os.environ["TEMPORAL_NAMESPACE"]
TEMPORAL_TASK_QUEUE = os.environ["TEMPORAL_TASK_QUEUE"]

async def main():
    temporal_client = await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
    )

    worker = Worker(
        temporal_client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[ TranslationReviewWorkflow , PDFTranslationWorkflow ],
        activities=[extract_pdf, call_llm],
    )

    print(f"Worker started. Polling task queue: '{TEMPORAL_TASK_QUEUE}'")

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())