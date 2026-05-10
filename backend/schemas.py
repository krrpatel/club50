"""Pydantic schemas for API request/response validation"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SubmissionStatusEnum(str, Enum):
    """Submission status"""
    QUEUED = "queued"
    COMPILING = "compiling"
    RUNNING = "running"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    SYSTEM_ERROR = "system_error"


# User Schemas
class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """User update schema"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(UserBase):
    """User response schema"""
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    """User profile response"""
    id: int
    bio: Optional[str] = None
    github_username: Optional[str] = None
    country: Optional[str] = None
    avatar_url: Optional[str] = None
    accepted_problems: int
    total_submissions: int
    
    class Config:
        from_attributes = True


# Problem Schemas
class ProblemBase(BaseModel):
    """Base problem schema"""
    title: str
    slug: str
    description: str
    difficulty: str
    time_limit: int = 1
    memory_limit: int = 256
    check_slug: str


class ProblemCreate(ProblemBase):
    """Problem creation schema"""
    sample_inputs: Optional[List[str]] = None
    sample_outputs: Optional[List[str]] = None
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ProblemResponse(ProblemBase):
    """Problem response schema"""
    id: int
    is_active: bool
    sample_inputs: Optional[List[str]] = None
    sample_outputs: Optional[List[str]] = None
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProblemTemplateResponse(BaseModel):
    """Problem template response"""
    id: int
    language: str
    starter_code: str
    
    class Config:
        from_attributes = True


class ProblemDetailResponse(ProblemResponse):
    """Problem detail response with templates"""
    templates: List[ProblemTemplateResponse] = []


# Submission Schemas
class SubmissionCreate(BaseModel):
    """Submission creation schema"""
    problem_id: int
    language: str = Field(..., min_length=2, max_length=20)
    code: str = Field(..., min_length=1)


class Check50Result(BaseModel):
    """check50 result entry"""
    name: str
    description: str
    passed: bool
    log: Optional[str] = None
    cause: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    dependency: Optional[bool] = None


class SubmissionResponse(BaseModel):
    """Submission response schema"""
    id: int
    user_id: int
    problem_id: int
    language: str
    status: SubmissionStatusEnum
    verdict: Optional[str] = None
    runtime_ms: Optional[int] = None
    memory_mb: Optional[int] = None
    public_test_passed: int
    public_test_total: int
    hidden_test_passed: int
    hidden_test_total: int
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SubmissionDetailResponse(SubmissionResponse):
    """Detailed submission response"""
    code: str
    check50_output: Optional[List[Check50Result]] = None


# Leaderboard Schemas
class LeaderboardEntry(BaseModel):
    """Leaderboard entry schema"""
    rank: int
    user: UserResponse
    accepted_count: int
    submission_count: int
    total_runtime_ms: int
    last_accepted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# API Response Schemas
class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Generic error response"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# Check Running Schemas
class RunCheckSchema(BaseModel):
    """Run check on code"""
    problem_id: int
    code: str
    language: str


class CheckResponseSchema(BaseModel):
    """Check execution response"""
    problem_id: int
    language: str
    results: List[Check50Result]
    passed: int
    total: int
    output: str
    exit_code: int


# Leaderboard Stats
class UserStatsSchema(BaseModel):
    """User statistics"""
    total_submissions: int
    accepted_count: int
    problems_attempted: int
    success_rate: float
    rank: Optional[int] = None


# Problem Stats
class ProblemStatsSchema(BaseModel):
    """Problem statistics"""
    total_submissions: int
    accepted_count: int
    acceptance_rate: float
    average_attempts: float


# Problem Schema Management
class TestCaseSchema(BaseModel):
    """Test case for problem schema"""
    id: Optional[int] = None
    input: str = Field(..., min_length=1)
    expected: str = Field(..., min_length=1)
    explanation: Optional[str] = None


class ProblemSchemaCreateSchema(BaseModel):
    """Create/update problem schema"""
    problem_id: int
    language: str = Field(..., pattern="^(java|c)$")
    tests: List[TestCaseSchema]


class ProblemSchemaResponseSchema(BaseModel):
    """Problem schema response"""
    id: Optional[int] = None
    problem_id: int
    language: str
    tests: List[TestCaseSchema]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ProblemSchemasResponseSchema(BaseModel):
    """All schemas for a problem"""
    problem_id: int
    schemas: Dict[str, ProblemSchemaResponseSchema]
