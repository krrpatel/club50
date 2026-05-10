"""Database models for Club50 platform"""
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum
from backend.database import Base


class SubmissionStatus(str, PyEnum):
    """Submission status states"""
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


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    submissions = relationship("Submission", back_populates="user", cascade="all, delete-orphan")
    profile = relationship("UserProfile", back_populates="user", uselist=False)


class UserProfile(Base):
    """User profile details"""
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    bio = Column(Text, nullable=True)
    github_username = Column(String, nullable=True)
    country = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    accepted_problems = Column(Integer, default=0)
    total_submissions = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User", back_populates="profile")


class Problem(Base):
    """Problem definition"""
    __tablename__ = "problems"
    
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    difficulty = Column(String)  # easy, medium, hard
    points = Column(Integer, default=100)
    time_limit = Column(Integer, default=1)  # seconds
    memory_limit = Column(Integer, default=256)  # MB
    check_slug = Column(String)  # e.g., "github.com/club50/checks/problems/two_sum"
    sample_inputs = Column(JSON)  # Array of sample inputs
    sample_outputs = Column(JSON)  # Array of sample outputs
    hints = Column(JSON)  # Array of hints
    tags = Column(JSON)  # Array of tags
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    submissions = relationship("Submission", back_populates="problem", cascade="all, delete-orphan")


class ProblemTemplate(Base):
    """Code templates for different languages"""
    __tablename__ = "problem_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"))
    language = Column(String)  # java, c
    starter_code = Column(Text)
    solution_code = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ProblemSchema(Base):
    """Language-specific test schemas for problems"""
    __tablename__ = "problem_schemas"
    
    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), index=True)
    language = Column(String)  # java, c
    schema_data = Column(JSON)  # Contains test cases: [{input: ..., expected: ..., explanation: ...}]
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    problem = relationship("Problem", backref="schemas")


class Submission(Base):
    """Code submission"""
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), index=True)
    language = Column(String)
    code = Column(Text)
    status = Column(String, default=SubmissionStatus.QUEUED)
    verdict = Column(String, nullable=True)  # accepted, wrong_answer, tle, mle, rte, ce
    check50_output = Column(JSON, nullable=True)  # Full check50 JSON output
    runtime_ms = Column(Integer, nullable=True)
    memory_mb = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    public_test_passed = Column(Integer, default=0)
    public_test_total = Column(Integer, default=0)
    hidden_test_passed = Column(Integer, default=0)
    hidden_test_total = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="submissions")
    problem = relationship("Problem", back_populates="submissions")


class Leaderboard(Base):
    """Leaderboard entry"""
    __tablename__ = "leaderboards"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    accepted_count = Column(Integer, default=0)
    submission_count = Column(Integer, default=0)
    total_runtime_ms = Column(Integer, default=0)
    rank = Column(Integer, index=True)
    last_accepted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExecutionLog(Base):
    """Log for code execution and debugging"""
    __tablename__ = "execution_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), index=True)
    stage = Column(String)  # compilation, execution, validation
    output = Column(Text)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
