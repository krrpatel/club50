"""Problems endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from backend.database import get_db
from backend.models import Problem, ProblemTemplate
from backend.schemas import ProblemResponse, ProblemDetailResponse, ProblemTemplateResponse

router = APIRouter()


@router.get("/", response_model=List[ProblemResponse])
async def get_problems(
    difficulty: str = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get list of problems"""
    try:
        query = select(Problem).where(Problem.is_active == True)
        if difficulty:
            query = query.where(Problem.difficulty == difficulty)
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        problems = result.scalars().all()
        return problems
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{problem_id}", response_model=ProblemDetailResponse)
async def get_problem(
    problem_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific problem with templates"""
    try:
        result = await db.execute(
            select(Problem).where(Problem.id == problem_id)
        )
        problem = result.scalars().first()
        
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")
        
        # Get templates
        templates_result = await db.execute(
            select(ProblemTemplate).where(ProblemTemplate.problem_id == problem_id)
        )
        templates = templates_result.scalars().all()
        
        # Convert to response format
        problem_dict = {
            "id": problem.id,
            "title": problem.title,
            "slug": problem.slug,
            "description": problem.description,
            "difficulty": problem.difficulty,
            "time_limit": problem.time_limit,
            "memory_limit": problem.memory_limit,
            "check_slug": problem.check_slug,
            "sample_inputs": problem.sample_inputs,
            "sample_outputs": problem.sample_outputs,
            "hints": problem.hints,
            "tags": problem.tags,
            "is_active": problem.is_active,
            "created_at": problem.created_at,
            "templates": [
                {
                    "id": t.id,
                    "language": t.language,
                    "starter_code": t.starter_code,
                }
                for t in templates
            ],
        }
        
        return problem_dict
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{problem_id}/template/{language}")
async def get_problem_template(
    problem_id: int,
    language: str,
    db: AsyncSession = Depends(get_db),
):
    """Get starter code for a specific language"""
    try:
        result = await db.execute(
            select(ProblemTemplate).where(
                (ProblemTemplate.problem_id == problem_id) &
                (ProblemTemplate.language == language)
            )
        )
        template = result.scalars().first()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return {
            "language": template.language,
            "starter_code": template.starter_code,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
