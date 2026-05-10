"""API router initialization"""
from fastapi import APIRouter
from backend.api.endpoints import problems, submissions, users, leaderboard

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(problems.router, prefix="/problems", tags=["problems"])
api_router.include_router(submissions.router, prefix="/submissions", tags=["submissions"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(leaderboard.router, prefix="/leaderboard", tags=["leaderboard"])
