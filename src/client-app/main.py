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
curl -X POST http://localhost:8080/translation-review/start \
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

curl http://localhost:8080/translation-review/translation-review-ec592df1-6a2a-4c4d-93f5-3384ca9e347e/status




curl -X POST http://localhost:8080/translation-review/translation-review-ec592df1-6a2a-4c4d-93f5-3384ca9e347e/assign \
  -H "Content-Type: application/json" \
  -d '{"name": "Eyad Amgad"}'

curl -X POST http://localhost:8080/translation-review/translation-review-ec592df1-6a2a-4c4d-93f5-3384ca9e347e/revise \
  -H "Content-Type: application/json" \
  -d '{"feedback": "Please write quick summary of the translation and highlight any areas that may need further review."}'

curl http://localhost:8080/translation-review/translation-review-ec592df1-6a2a-4c4d-93f5-3384ca9e347e/approve
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
class AssignRequest(BaseModel):
    name: str     

class ReviseRequest(BaseModel):
    feedback: str      
 
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
@app.get("/translation-review/{workflow_id}/status") 
async def get_review_status(workflow_id: str):
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    desc = await handle.describe()

    workflow_status = None
    if desc.status == WES.RUNNING:
        try:
            workflow_status = await handle.query("get_status",result_type=dict)

        except Exception as e:
            pass
    return {
        "workflow_id": workflow_id,
        "execution_status": desc.status.name,
        "workflow_status": workflow_status,
    }
@app.post("/translation-review/{workflow_id}/assign")
async def assign_reviewer(workflow_id: str, request: AssignRequest):
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    await handle.signal (
        "assign_reviewer", request.name
    )
    return {
        "status": "ok",
        "message": f"Reviewer '{request.name}' assigned to workflow '{workflow_id}'."
    }

@app.post("/translation-review/{workflow_id}/revise")
async def submit_revise(workflow_id: str, request: ReviseRequest):

    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    result = await handle.execute_update(
        "submit_decision", args=[
            "revise", request.feedback
        ]
    )

    return {"ok": True, "message": result}


@app.get("/translation-review/{workflow_id}/approve")
async def submit_approve(workflow_id: str):

    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    result = await handle.execute_update(
        "submit_decision", args=[
            "approve", ""
        ]
    )

    return {"ok": True, "message": result}