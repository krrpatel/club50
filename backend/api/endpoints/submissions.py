"""Submissions endpoints with Piston-based evaluator"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
import logging

from backend.database import get_db
from backend.models import Submission, Problem, SubmissionStatus
from backend.schemas import SubmissionCreate, SubmissionResponse, EvaluationReportSchema, SubmissionEvaluationResponse
from backend.submit50 import (
    SubmissionProcessor,
    handle_submission_async,
    quick_check_submission,
    get_submission_stats,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=dict)
async def create_submission(
    submission: SubmissionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: int = 1,  # TODO: Replace with actual user auth
):
    """
    Create a new submission and queue for evaluation
    
    Runs FULL evaluation (public + hidden test cases)
    """
    try:
        # Validate language
        if submission.language not in {"c", "java"}:
            raise HTTPException(
                status_code=400, detail="Unsupported language. Only 'c' and 'java' are supported."
            )

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
        
        await db.commit()

        # Queue for background processing with a fresh DB session.
        background_tasks.add_task(
            handle_submission_async, db_submission.id, None, test_mode="all"
        )
        
        return {
            "id": db_submission.id,
            "status": db_submission.status,
            "message": "Submission queued for evaluation",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creating submission")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{submission_id}", response_model=dict)
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = 1,  # TODO: Replace with actual user auth
):
    """Get submission details with evaluation report"""
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
        
        response = {
            "id": submission.id,
            "user_id": submission.user_id,
            "problem_id": submission.problem_id,
            "language": submission.language,
            "status": submission.status,
            "verdict": submission.verdict,
            "code": submission.code,
            "public_test_passed": submission.public_test_passed,
            "public_test_total": submission.public_test_total,
            "hidden_test_passed": submission.hidden_test_passed,
            "hidden_test_total": submission.hidden_test_total,
            "runtime_ms": submission.runtime_ms,
            "memory_mb": submission.memory_mb,
            "compile_error": submission.compile_error,
            "runtime_error": submission.runtime_error,
            "time_complexity": submission.time_complexity,
            "space_complexity": submission.space_complexity,
            "code_issues": submission.code_issues,
            "optimization_suggestions": submission.optimization_suggestions,
            "evaluation_report": submission.evaluation_report,
            "created_at": submission.created_at,
            "completed_at": submission.completed_at,
        }
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching submission {submission_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=dict)
async def get_user_submissions(
    problem_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: int = 1,  # TODO: Replace with actual user auth
):
    """Get user submissions with pagination"""
    try:
        query = select(Submission).where(Submission.user_id == user_id)
        
        if problem_id:
            query = query.where(Submission.problem_id == problem_id)
        
        query = query.offset(skip).limit(limit).order_by(Submission.created_at.desc())
        result = await db.execute(query)
        submissions = result.scalars().all()
        
        return {
            "submissions": [
                {
                    "id": s.id,
                    "problem_id": s.problem_id,
                    "language": s.language,
                    "status": s.status,
                    "verdict": s.verdict,
                    "public_test_passed": s.public_test_passed,
                    "public_test_total": s.public_test_total,
                    "runtime_ms": s.runtime_ms,
                    "created_at": s.created_at,
                    "completed_at": s.completed_at,
                }
                for s in submissions
            ],
            "count": len(submissions),
        }
    except Exception as e:
        logger.exception("Error fetching user submissions")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Run (Quick Check) Endpoint
# ============================================================================

@router.post("/run", response_model=dict)
async def run_quick_check(
    data: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = 1,
):
    """
    Quick check mode - runs code against PUBLIC test cases only
    Used for "Run" button
    
    Does NOT save submission to database
    Returns immediate feedback
    """
    try:
        # Validate language
        if data.language not in {"c", "java"}:
            raise HTTPException(
                status_code=400, detail="Unsupported language. Only 'c' and 'java' are supported."
            )
        
        # Check if problem exists
        result = await db.execute(
            select(Problem).where(Problem.id == data.problem_id)
        )
        problem = result.scalars().first()
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")
        
        # Run quick check
        check_result = await quick_check_submission(
            code=data.code,
            problem_id=data.problem_id,
            language=data.language,
            db=db,
        )
        
        if not check_result["success"]:
            raise HTTPException(status_code=400, detail=check_result["error"])
        
        return {
            "success": True,
            "verdict": check_result["verdict"],
            "passed_tests": check_result["passed_tests"],
            "total_tests": check_result["total_tests"],
            "success_rate": check_result["report"]["success_rate"],
            "failed_testcase": check_result["report"].get("failed_testcase"),
            "execution": check_result["report"]["execution"],
            "analysis": check_result["report"]["analysis"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in quick check")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Check Endpoint (Alias for Run)
# ============================================================================

@router.post("/check", response_model=dict)
async def check_code(
    data: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = 1,
):
    """
    Check endpoint - same as run, for compatibility
    Runs against PUBLIC test cases only
    """
    return await run_quick_check(data, db, user_id)
