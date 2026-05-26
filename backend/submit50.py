"""
Submission processor using Piston-based evaluator
Handles code evaluation for submitted solutions
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.evaluator import (
    CompetitiveProgrammingEvaluator,
    TestCase,
    Verdict,
    PistonClient,
    create_evaluator,
)
from backend.models import Submission, SubmissionStatus, Problem, ProblemSchema
from backend.database import AsyncSessionLocal, is_async

logger = logging.getLogger(__name__)


# ============================================================================
# Submission Processing
# ============================================================================

class SubmissionProcessor:
    """Process code submissions using Piston-based evaluator"""

    def __init__(self, evaluator: Optional[CompetitiveProgrammingEvaluator] = None):
        self.evaluator = evaluator

    async def initialize(self):
        """Initialize evaluator if not already done"""
        if self.evaluator is None:
            self.evaluator = await create_evaluator()

    async def process_submission(
        self,
        submission_id: int,
        db: AsyncSession,
        test_mode: str = "public",  # 'public', 'hidden', 'all'
    ) -> Dict[str, Any]:
        """
        Process a submission end-to-end

        Args:
            submission_id: ID of submission to process
            db: Database session
            test_mode: Which tests to run (public, hidden, or all)

        Returns:
            Dictionary with processing results
        """
        try:
            await self.initialize()

            # Fetch submission
            result = await db.execute(
                select(Submission).where(Submission.id == submission_id)
            )
            submission = result.scalars().first()

            if not submission:
                logger.error(f"Submission {submission_id} not found")
                return {"success": False, "error": "Submission not found"}

            # Fetch problem and test cases
            problem_result = await db.execute(
                select(Problem).where(Problem.id == submission.problem_id)
            )
            problem = problem_result.scalars().first()

            if not problem:
                logger.error(f"Problem {submission.problem_id} not found")
                return {"success": False, "error": "Problem not found"}

            # Get test schema
            schema_result = await db.execute(
                select(ProblemSchema).where(
                    (ProblemSchema.problem_id == submission.problem_id)
                    & (ProblemSchema.language == submission.language)
                )
            )
            schema = schema_result.scalars().first()

            if not schema:
                logger.error(
                    f"No schema found for problem {submission.problem_id} in {submission.language}"
                )
                return {
                    "success": False,
                    "error": f"No test cases configured for {submission.language}",
                }

            # Parse test cases
            test_cases = self._parse_test_cases(schema.schema_data)

            # Filter test cases based on mode
            if test_mode == "public":
                test_cases = [tc for tc in test_cases if not tc.is_hidden]
            elif test_mode == "hidden":
                test_cases = [tc for tc in test_cases if tc.is_hidden]
            # 'all' uses all test cases

            if not test_cases:
                logger.error(f"No test cases available for test_mode: {test_mode}")
                return {"success": False, "error": f"No test cases for mode: {test_mode}"}

            # Update status
            await self._update_submission_status(
                submission, db, SubmissionStatus.RUNNING, submitted_at=datetime.utcnow()
            )

            # Run evaluation
            logger.info(
                f"Evaluating submission {submission_id} ({submission.language})"
            )
            evaluation_report = await self.evaluator.evaluate(
                problem_title=problem.title,
                code=submission.code,
                language=submission.language,
                test_cases=test_cases,
                time_limit_ms=problem.time_limit * 1000,
                memory_limit_mb=problem.memory_limit,
            )

            # Store results in submission
            await self._store_evaluation_results(
                submission, evaluation_report, db, test_cases, test_mode
            )

            logger.info(
                f"Submission {submission_id} evaluation complete: {evaluation_report.verdict.value}"
            )

            return {
                "success": True,
                "verdict": evaluation_report.verdict.value,
                "passed_tests": evaluation_report.passed_tests,
                "total_tests": evaluation_report.total_tests,
                "report": evaluation_report.to_dict(),
            }

        except Exception as e:
            logger.exception(f"Error processing submission {submission_id}")
            # Mark as error
            if "submission" in locals() and submission:
                await self._update_submission_status(
                    submission, db, SubmissionStatus.SYSTEM_ERROR, error_msg=str(e)
                )
            return {"success": False, "error": str(e)}

    async def _update_submission_status(
        self,
        submission: Submission,
        db: AsyncSession,
        status: SubmissionStatus,
        error_msg: Optional[str] = None,
        submitted_at: Optional[datetime] = None,
    ):
        """Update submission status in database"""
        values = {"status": status, "error_message": error_msg}
        if submitted_at is not None:
            values["submitted_at"] = submitted_at
        await db.execute(
            update(Submission)
            .where(Submission.id == submission.id)
            .values(**values)
        )
        await db.commit()

    async def _store_evaluation_results(
        self,
        submission: Submission,
        evaluation_report,
        db: AsyncSession,
        test_cases: List[TestCase],
        test_mode: str,
    ):
        """Store evaluation results in submission"""
        # Calculate test statistics
        public_tests = [tc for tc in test_cases if not tc.is_hidden]
        hidden_tests = [tc for tc in test_cases if tc.is_hidden]

        # Prepare verdict string
        verdict_string = evaluation_report.verdict.value.lower().replace(" ", "_")
        status_map = {
            "accepted": SubmissionStatus.ACCEPTED,
            "wrong_answer": SubmissionStatus.WRONG_ANSWER,
            "runtime_error": SubmissionStatus.RUNTIME_ERROR,
            "compilation_error": SubmissionStatus.COMPILATION_ERROR,
            "time_limit_exceeded": SubmissionStatus.TIME_LIMIT_EXCEEDED,
            "memory_limit_exceeded": SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
        }
        passed_ids = {
            result.get("test_case_id")
            for result in evaluation_report.test_results
            if result.get("passed")
        }

        # Update submission
        await db.execute(
            update(Submission)
            .where(Submission.id == submission.id)
            .values(
                status=status_map.get(verdict_string, SubmissionStatus.SYSTEM_ERROR),
                verdict=evaluation_report.verdict.value,
                evaluation_report=evaluation_report.to_dict(),
                runtime_ms=int(evaluation_report.execution.get("avg_runtime_ms", 0)),
                memory_mb=int(evaluation_report.execution.get("max_memory_kb", 0) / 1024),
                compile_error=evaluation_report.compile_error,
                runtime_error=evaluation_report.runtime_error,
                public_test_passed=sum(1 for tc in public_tests if tc.id in passed_ids),
                public_test_total=len(public_tests),
                hidden_test_passed=sum(1 for tc in hidden_tests if tc.id in passed_ids),
                hidden_test_total=len(hidden_tests),
                time_complexity=evaluation_report.complexity.get("time"),
                space_complexity=evaluation_report.complexity.get("space"),
                code_issues=evaluation_report.analysis,
                optimization_suggestions=evaluation_report.optimization_suggestions,
                completed_at=datetime.utcnow(),
            )
        )
        await db.commit()

    def _parse_test_cases(self, schema_data: Dict[str, Any]) -> List[TestCase]:
        """Parse test cases from problem schema"""
        test_cases = []

        if isinstance(schema_data, list):
            # Direct list of test cases
            for i, tc in enumerate(schema_data):
                test_cases.append(
                    TestCase(
                        id=i + 1,
                        input=tc.get("input", ""),
                        expected=tc.get("expected", tc.get("expected_output", "")),
                        explanation=tc.get("explanation"),
                        is_hidden=tc.get("is_hidden", False),
                    )
                )
        elif isinstance(schema_data, dict) and "tests" in schema_data:
            # Dictionary with 'tests' key
            for i, tc in enumerate(schema_data["tests"]):
                test_cases.append(
                    TestCase(
                        id=i + 1,
                        input=tc.get("input", ""),
                        expected=tc.get("expected", tc.get("expected_output", "")),
                        explanation=tc.get("explanation"),
                        is_hidden=tc.get("is_hidden", False),
                    )
                )

        return test_cases


# ============================================================================
# Async Submission Handler (for background task)
# ============================================================================

async def handle_submission_async(
    submission_id: int,
    db_session=None,
    test_mode: str = "public",
):
    """
    Handle submission asynchronously (called from background task)

    Args:
        submission_id: ID of submission to process
        db_session: Database session
        test_mode: Which tests to run
    """
    processor = SubmissionProcessor()
    if db_session is not None:
        return await processor.process_submission(submission_id, db_session, test_mode)
    if not is_async:
        return {"success": False, "error": "Async submission processing requires async database configuration"}
    async with AsyncSessionLocal() as session:
        return await processor.process_submission(submission_id, session, test_mode)


# ============================================================================
# Quick Check Mode (for "Run" button)
# ============================================================================

async def quick_check_submission(
    code: str,
    problem_id: int,
    language: str,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Quick check mode - runs only public test cases
    Used for "Run" button

    Args:
        code: Source code to check
        problem_id: Problem ID
        language: Programming language
        db: Database session

    Returns:
        Quick evaluation results
    """
    try:
        # Fetch problem
        problem_result = await db.execute(
            select(Problem).where(Problem.id == problem_id)
        )
        problem = problem_result.scalars().first()

        if not problem:
            return {"success": False, "error": "Problem not found"}

        # Fetch test schema
        schema_result = await db.execute(
            select(ProblemSchema).where(
                (ProblemSchema.problem_id == problem_id)
                & (ProblemSchema.language == language)
            )
        )
        schema = schema_result.scalars().first()

        if not schema:
            return {"success": False, "error": f"No test cases for {language}"}

        # Parse and filter test cases (only public)
        processor = SubmissionProcessor()
        all_test_cases = processor._parse_test_cases(schema.schema_data)
        public_test_cases = [tc for tc in all_test_cases if not tc.is_hidden]

        # Evaluate
        evaluator = await create_evaluator()
        evaluation_report = await evaluator.evaluate(
            problem_title=problem.title,
            code=code,
            language=language,
            test_cases=public_test_cases,
            time_limit_ms=problem.time_limit * 1000,
            memory_limit_mb=problem.memory_limit,
        )

        return {
            "success": True,
            "verdict": evaluation_report.verdict.value,
            "passed_tests": evaluation_report.passed_tests,
            "total_tests": evaluation_report.total_tests,
            "report": evaluation_report.to_dict(),
        }

    except Exception as e:
        logger.exception("Error in quick_check_submission")
        return {"success": False, "error": str(e)}


# ============================================================================
# Submission Statistics
# ============================================================================

async def get_submission_stats(
    submission_id: int, db: AsyncSession
) -> Optional[Dict[str, Any]]:
    """Get statistics for a submission"""
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = result.scalars().first()

    if not submission:
        return None

    return {
        "id": submission.id,
        "verdict": submission.verdict,
        "public_passed": submission.public_test_passed,
        "public_total": submission.public_test_total,
        "hidden_passed": submission.hidden_test_passed,
        "hidden_total": submission.hidden_test_total,
        "runtime_ms": submission.runtime_ms,
        "memory_mb": submission.memory_mb,
        "time_complexity": submission.time_complexity,
        "space_complexity": submission.space_complexity,
        "code_issues": submission.code_issues,
        "optimization_suggestions": submission.optimization_suggestions,
        "completed_at": submission.completed_at,
    }
