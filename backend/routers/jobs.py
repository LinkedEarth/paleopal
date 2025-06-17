from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional

from schemas.job import Job, JobCreate
from services.job_service import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("", response_model=Job, status_code=status.HTTP_201_CREATED)
async def create_job(job: JobCreate):
    return job_service.create_job(job)

@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str):
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("", response_model=List[Job])
async def list_jobs(conv_id: Optional[str] = Query(None, alias="conversation_id"), state: Optional[str] = None):
    return job_service.list_jobs(conv_id, state) 