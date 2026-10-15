import os
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.client import WorkflowExecutionStatus as WES
load_dotenv()
'''
curl -X POST http://localhost:8000/process-pdf/execute \
  -H "Content-Type: application/json" \
    -d '{"folder_path": "https://drive.google.com/drive/u/0/folders/1VR9Ly2CHaUtkJZ2qYAvc-V9JGNLj_0wl"}'
'''
'''
curl -X POST http://localhost:8001/translation-review/start \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
    "https://drive.google.com/file/d/18HsEUOHusjDrIFnSSs3DZuJRkKMZNqJf/view?usp=drive_link",
    "https://drive.google.com/file/d/1UppWOt2evYsJ0x96YW4PMtGDR_awABe_/view?usp=drive_link"
    ]
  }'

'''
'''
"https://drive.google.com/file/d/1i2KmUNljxfMTlAalj8y4ivvNFQ2bm3qr/view?usp=drive_link"
"https://drive.google.com/drive/u/0/folders/1VR9Ly2CHaUtkJZ2qYAvc-V9JGNLj_0wl"
"https://drive.google.com/file/d/1k6TnpfpwW8PVkyo3NTnNiBBkEmwfnChd/view?usp=drive_link"
'''
TEMPORAL_HOST      = os.environ["TEMPORAL_HOST"]
TEMPORAL_NAMESPACE = os.environ["TEMPORAL_NAMESPACE"]
TEMPORAL_PDF_PROCESS_TASK_QUEUE = os.environ["TEMPORAL_PDF_PROCESS_TASK_QUEUE"]
TEMPORAL_TASK_QUEUE= os.environ["TEMPORAL_TASK_QUEUE"]

class ProcessPDFRequest(BaseModel):
    folder_path: str

class ProcessPDFExecuteResponse(BaseModel):
    workflow_id: str
    results: dict
class StartReviewRequest(BaseModel):
    file_paths: list[str]
    max_concurrent_translations: int = 3    
 
app = FastAPI(
    title="PDF Translation API",
    description="Submits PDF processing jobs to Temporal and returns the result.",
    version="1.0.0",
)


async def get_temporal_client() -> Client:
    return await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/process-pdf/execute", response_model=ProcessPDFExecuteResponse)
async def process_pdf(request: ProcessPDFRequest):
    
    workflow_id = f"pdf-pipeline-{uuid.uuid4()}"

    client = await get_temporal_client()

    results = await client.execute_workflow(
        "PDFPipelineWorkflow",
        args=[
            {
                "folder_path": request.folder_path,
            }
        ],
        id=workflow_id,
        task_queue=TEMPORAL_PDF_PROCESS_TASK_QUEUE,
        result_type=dict,
    )

    return ProcessPDFExecuteResponse(
        workflow_id=workflow_id,
        results=results
    )
@app.post("/translation-review/start", response_model=StartReviewRequest)
async def start_translation_review(request: StartReviewRequest):
    workflow_id = f"translation-review-{uuid.uuid4()}"

    client = await get_temporal_client()

    results = await client.execute_workflow(
        "TranslationReviewWorkflow",
        args=[
            {
                "file_paths": request.file_paths,
                "max_concurrent_translations": request.max_concurrent_translations
            }
        ],
        id=workflow_id,
        task_queue=TEMPORAL_TASK_QUEUE
,
        result_type=dict,
    )

    return {
        "workflow_id": workflow_id,
        "results": results
    }