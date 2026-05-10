"""Submissions endpoints"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
from backend.database import get_db
from backend.models import Submission, Problem, SubmissionStatus
from backend.schemas import SubmissionCreate, SubmissionResponse, SubmissionDetailResponse

router = APIRouter()


@router.post("/", response_model=dict)
async def create_submission(
    submission: SubmissionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: int = 1,  # TODO: Replace with actual user auth
):
    """Create a new submission"""
    try:
        # Verify problem exists
        result = await db.execute(
            select(Problem).where(Problem.id == submission.problem_id)
        )
        problem = result.scalars().first()
        
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")
        
        # Create submission
        db_submission = Submission(
            user_id=user_id,
            problem_id=submission.problem_id,
            language=submission.language,
            code=submission.code,
            status=SubmissionStatus.QUEUED,
            created_at=datetime.utcnow(),
        )
        
        db.add(db_submission)
        await db.flush()
        await db.refresh(db_submission)
        
        # Queue for processing (in real implementation, this would be Celery task)
        # background_tasks.add_task(process_submission, db_submission.id)
        
        await db.commit()
        
        return {
            "id": db_submission.id,
            "status": db_submission.status,
            "message": "Submission queued for processing",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = 1,  # TODO: Replace with actual user auth
):
    """Get submission details"""
    try:
        result = await db.execute(
            select(Submission).where(Submission.id == submission_id)
        )
        submission = result.scalars().first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        # Check authorization
        if submission.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this submission")
        
        return submission
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=dict)
async def get_user_submissions(
    problem_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: int = 1,  # TODO: Replace with actual user auth
):
    """Get user submissions"""
    try:
        query = select(Submission).where(Submission.user_id == user_id)
        
        if problem_id:
            query = query.where(Submission.problem_id == problem_id)
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        submissions = result.scalars().all()
        
        return {
            "submissions": submissions,
            "count": len(submissions),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
