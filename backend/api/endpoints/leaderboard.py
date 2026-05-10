"""Leaderboard endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from backend.database import get_db
from backend.models import Leaderboard, User
from backend.schemas import LeaderboardEntry

router = APIRouter()


@router.get("/", response_model=List[dict])
async def get_leaderboard(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get leaderboard"""
    try:
        result = await db.execute(
            select(Leaderboard)
            .order_by(desc(Leaderboard.accepted_count), Leaderboard.total_runtime_ms)
            .offset(skip)
            .limit(limit)
        )
        leaderboard = result.scalars().all()
        
        entries = []
        for idx, entry in enumerate(leaderboard, start=skip + 1):
            # Get user
            user_result = await db.execute(
                select(User).where(User.id == entry.user_id)
            )
            user = user_result.scalars().first()
            
            if user:
                entries.append({
                    "rank": idx,
                    "user": user,
                    "accepted_count": entry.accepted_count,
                    "submission_count": entry.submission_count,
                    "total_runtime_ms": entry.total_runtime_ms,
                    "last_accepted_at": entry.last_accepted_at,
                })
        
        return entries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}", response_model=dict)
async def get_user_rank(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get user rank on leaderboard"""
    try:
        result = await db.execute(
            select(Leaderboard).where(Leaderboard.user_id == user_id)
        )
        entry = result.scalars().first()
        
        if not entry:
            raise HTTPException(status_code=404, detail="User not on leaderboard")
        
        # Get user
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalars().first()
        
        return {
            "rank": entry.rank,
            "user": user,
            "accepted_count": entry.accepted_count,
            "submission_count": entry.submission_count,
            "total_runtime_ms": entry.total_runtime_ms,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
