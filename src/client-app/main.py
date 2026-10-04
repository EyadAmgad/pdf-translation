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

TEMPORAL_HOST      = os.environ["TEMPORAL_HOST"]
TEMPORAL_NAMESPACE = os.environ["TEMPORAL_NAMESPACE"]
TEMPORAL_PDF_PROCESS_TASK_QUEUE = os.environ["TEMPORAL_PDF_PROCESS_TASK_QUEUE"]
TEMPORAL_CONTRACT_REVIEW_TASK_QUEUE = os.environ["TEMPORAL_CONTRACT_REVIEW_TASK_QUEUE"]

class ProcessPDFRequest(BaseModel):
    folder_path: str

class ProcessPDFExecuteResponse(BaseModel):
    workflow_id: str
    results: dict
 
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