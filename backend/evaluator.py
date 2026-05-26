"""
Advanced Competitive Programming Evaluator
Executes code using Piston API and validates against test cases.
Supports C and Java only.
"""
import json
import re
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import httpx
import asyncio

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

SUPPORTED_LANGUAGES = {"c", "java"}
PISTON_API_URL = "https://emkc.org/api/v2/piston/execute"
DEFAULT_COMPILE_TIMEOUT = 10000  # 10 seconds
DEFAULT_RUN_TIMEOUT = 3000  # 3 seconds
DEFAULT_MEMORY_LIMIT = 256  # MB


class Verdict(str, Enum):
    """Possible verdicts for code evaluation"""
    ACCEPTED = "Accepted"
    WRONG_ANSWER = "Wrong Answer"
    RUNTIME_ERROR = "Runtime Error"
    COMPILATION_ERROR = "Compilation Error"
    TIME_LIMIT_EXCEEDED = "Time Limit Exceeded"
    MEMORY_LIMIT_EXCEEDED = "Memory Limit Exceeded"
    SECURITY_VIOLATION = "Security Violation"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TestCase:
    """Single test case with input and expected output"""
    id: int
    input: str
    expected: str
    explanation: Optional[str] = None
    is_hidden: bool = False


@dataclass
class ExecutionResult:
    """Result of code execution"""
    stdout: str
    stderr: str
    exit_code: int
    compile_error: Optional[str] = None
    runtime_ms: float = 0
    memory_mb: float = 0


@dataclass
class TestCaseResult:
    """Result of a single test case"""
    test_case_id: int
    verdict: Verdict
    execution: ExecutionResult
    expected: str
    got: str
    passed: bool


@dataclass
class EvaluationReport:
    """Complete evaluation report"""
    problem: str
    language: str
    verdict: Verdict
    passed_tests: int
    total_tests: int
    success_rate: str
    compile_error: Optional[str]
    runtime_error: Optional[str]
    failed_testcase: Optional[Dict[str, str]]
    execution: Dict[str, Any]
    complexity: Dict[str, str]
    analysis: List[str]
    optimization_suggestions: List[str]
    test_results: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary"""
        return {
            "problem": self.problem,
            "language": self.language,
            "verdict": self.verdict.value,
            "passed_tests": self.passed_tests,
            "total_tests": self.total_tests,
            "success_rate": self.success_rate,
            "compile_error": self.compile_error,
            "runtime_error": self.runtime_error,
            "failed_testcase": self.failed_testcase,
            "execution": self.execution,
            "complexity": self.complexity,
            "analysis": self.analysis,
            "optimization_suggestions": self.optimization_suggestions,
            "test_results": self.test_results,
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


# ============================================================================
# Piston API Client
# ============================================================================

class PistonClient:
    """Client for Piston API code execution"""

    def __init__(self, api_url: str = PISTON_API_URL, timeout: int = 30):
        self.api_url = api_url
        self.timeout = timeout

    async def execute(
        self,
        language: str,
        code: str,
        stdin: str = "",
        version: str = "*",
        compile_timeout: int = DEFAULT_COMPILE_TIMEOUT,
        run_timeout: int = DEFAULT_RUN_TIMEOUT,
        compile_memory_limit: int = -1,
        run_memory_limit: int = -1,
    ) -> ExecutionResult:
        """
        Execute code using Piston API

        Args:
            language: Programming language (c, java)
            code: Source code to execute
            stdin: Input to pass to the program
            version: Language version (default: *)
            compile_timeout: Compilation timeout in ms
            run_timeout: Execution timeout in ms
            compile_memory_limit: Memory limit for compilation (-1 = unlimited)
            run_memory_limit: Memory limit for execution (-1 = unlimited)

        Returns:
            ExecutionResult with output and metadata
        """
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}")

        payload = {
            "language": language,
            "version": version,
            "files": [{"content": code}],
            "stdin": stdin,
            "compile_timeout": compile_timeout,
            "run_timeout": run_timeout,
            "compile_memory_limit": compile_memory_limit,
            "run_memory_limit": run_memory_limit,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                data = response.json()

                return self._parse_response(data)
        except httpx.TimeoutException:
            return ExecutionResult(
                stdout="",
                stderr="HTTP request timeout",
                exit_code=-1,
                compile_error=None,
                runtime_ms=run_timeout,
            )
        except Exception as e:
            return ExecutionResult(
                stdout="",
                stderr=f"Piston API error: {str(e)}",
                exit_code=-1,
                compile_error=str(e),
            )

    def _parse_response(self, data: Dict[str, Any]) -> ExecutionResult:
        """Parse Piston API response"""
        compile_stage = data.get("compile", {})
        run_stage = data.get("run", {})

        compile_error = None
        if compile_stage and compile_stage.get("stderr"):
            compile_error = compile_stage["stderr"]

        runtime_ms = 0
        # Try to extract runtime from Piston response
        if run_stage and "output" in run_stage:
            # Piston returns output as a string
            pass

        return ExecutionResult(
            stdout=run_stage.get("stdout", "") if run_stage else "",
            stderr=run_stage.get("stderr", "") if run_stage else "",
            exit_code=run_stage.get("code", 0) if run_stage else 0,
            compile_error=compile_error,
            runtime_ms=runtime_ms,
            memory_mb=0,
        )


# ============================================================================
# Code Analyzer
# ============================================================================

class CodeAnalyzer:
    """Analyze code for complexity and potential issues"""

    @staticmethod
    def analyze_time_complexity(code: str, language: str) -> str:
        """Estimate time complexity from code analysis"""
        # Simple heuristic analysis
        nested_loop_count = 0
        if language == "java":
            nested_loop_count = code.count("for") + code.count("while")
        elif language == "c":
            nested_loop_count = code.count("for") + code.count("while")

        if nested_loop_count >= 3:
            return "O(n³)"
        elif nested_loop_count >= 2:
            return "O(n²)"
        elif nested_loop_count >= 1:
            return "O(n)"
        else:
            return "O(1)"

    @staticmethod
    def analyze_space_complexity(code: str, language: str) -> str:
        """Estimate space complexity from code analysis"""
        # Simple heuristic: check for array declarations, recursion
        has_recursion = "recursion" in code.lower() or code.count("(") > code.count("static")
        has_arrays = "[" in code and "]" in code

        if has_recursion and has_arrays:
            return "O(n)"
        elif has_arrays:
            return "O(n)"
        elif has_recursion:
            return "O(log n)"
        else:
            return "O(1)"

    @staticmethod
    def detect_issues(code: str, language: str) -> List[str]:
        """Detect potential issues in code"""
        issues = []

        if language == "java":
            # Check for common Java issues
            if "System.exit" in code:
                issues.append("Uses System.exit() which may terminate abnormally")
            if code.count("new ") > 100:
                issues.append("Excessive object allocation may cause memory issues")
            if "Thread" in code:
                issues.append("Uses threading which may cause timing issues")
            if "String concatenation in loop" in code or (
                ("for" in code or "while" in code) and "+= \"" in code
            ):
                issues.append("String concatenation in loop (consider StringBuilder)")

        elif language == "c":
            # Check for common C issues
            if "gets(" in code or "strcpy(" in code:
                issues.append("Uses unsafe function (gets/strcpy) - buffer overflow risk")
            if "#define" in code:
                issues.append("Uses macros which may complicate debugging")
            if "malloc" in code and "free" not in code:
                issues.append("Memory allocated with malloc but not freed - potential memory leak")
            if code.count("goto") > 0:
                issues.append("Uses goto statement (considered bad practice)")

        # General checks
        if len(code) > 10000:
            issues.append("Code is quite long - may indicate inefficiency")

        return issues

    @staticmethod
    def suggest_optimizations(code: str, language: str) -> List[str]:
        """Suggest optimizations for code"""
        suggestions = []

        time_complexity = CodeAnalyzer.analyze_time_complexity(code, language)
        space_complexity = CodeAnalyzer.analyze_space_complexity(code, language)

        if "O(n²)" in time_complexity:
            suggestions.append("Consider using a hash map/set to reduce time complexity from O(n²) to O(n)")
            suggestions.append("Look for opportunities to use binary search instead of linear search")

        if "O(n³)" in time_complexity:
            suggestions.append("Time complexity is O(n³) - significant optimization potential")
            suggestions.append("Consider dynamic programming or divide-and-conquer approaches")

        if language == "java" and "+= \"" in code:
            suggestions.append("Replace string concatenation with StringBuilder for better performance")

        if language == "c" and "strcpy" in code:
            suggestions.append("Replace strcpy with strncpy to prevent buffer overflow")

        if len(code) > 500:
            suggestions.append("Code could potentially be refactored into smaller functions")

        return suggestions


# ============================================================================
# Evaluator
# ============================================================================

class CompetitiveProgrammingEvaluator:
    """Main evaluator class for competitive programming submissions"""

    def __init__(self, piston_client: Optional[PistonClient] = None):
        self.piston_client = piston_client or PistonClient()

    async def evaluate(
        self,
        problem_title: str,
        code: str,
        language: str,
        test_cases: List[TestCase],
        time_limit_ms: int = DEFAULT_RUN_TIMEOUT,
        memory_limit_mb: int = DEFAULT_MEMORY_LIMIT,
    ) -> EvaluationReport:
        """
        Evaluate submitted code against test cases

        Args:
            problem_title: Title of the problem being solved
            code: Source code to evaluate
            language: Programming language (c, java)
            test_cases: List of test cases
            time_limit_ms: Time limit per test case in milliseconds
            memory_limit_mb: Memory limit per test case in MB

        Returns:
            Complete evaluation report
        """
        if language not in SUPPORTED_LANGUAGES:
            return self._security_violation_report(problem_title, language, "Unsupported language")

        if self._is_malicious_code(code):
            return self._security_violation_report(problem_title, language, "Potentially malicious code detected")

        # Run test cases
        results = await self._run_test_cases(code, language, test_cases, time_limit_ms, memory_limit_mb)

        # Analyze results
        return self._analyze_results(
            problem_title, language, code, test_cases, results, time_limit_ms
        )

    async def _run_test_cases(
        self,
        code: str,
        language: str,
        test_cases: List[TestCase],
        time_limit_ms: int,
        memory_limit_mb: int,
    ) -> List[TestCaseResult]:
        """Run all test cases"""
        results = []

        for test_case in test_cases:
            result = await self._run_single_test(
                code, language, test_case, time_limit_ms, memory_limit_mb
            )
            results.append(result)

        return results

    async def _run_single_test(
        self,
        code: str,
        language: str,
        test_case: TestCase,
        time_limit_ms: int,
        memory_limit_mb: int,
    ) -> TestCaseResult:
        """Run a single test case"""
        try:
            # Execute with Piston API
            start_time = time.time()
            execution = await self.piston_client.execute(
                language=language,
                code=code,
                stdin=test_case.input,
                compile_timeout=DEFAULT_COMPILE_TIMEOUT,
                run_timeout=time_limit_ms,
                run_memory_limit=memory_limit_mb * 1024,  # Convert MB to KB
            )
            elapsed_ms = (time.time() - start_time) * 1000

            execution.runtime_ms = elapsed_ms

            # Determine verdict
            verdict = self._determine_verdict(execution, test_case, time_limit_ms, memory_limit_mb)

            # Compare output
            expected_output = test_case.expected.strip()
            actual_output = execution.stdout.strip()
            passed = (verdict == Verdict.ACCEPTED) and (expected_output == actual_output)

            return TestCaseResult(
                test_case_id=test_case.id,
                verdict=verdict,
                execution=execution,
                expected=expected_output,
                got=actual_output,
                passed=passed,
            )

        except Exception as e:
            return TestCaseResult(
                test_case_id=test_case.id,
                verdict=Verdict.RUNTIME_ERROR,
                execution=ExecutionResult(
                    stdout="",
                    stderr=str(e),
                    exit_code=-1,
                ),
                expected=test_case.expected,
                got="",
                passed=False,
            )

    def _determine_verdict(
        self, execution: ExecutionResult, test_case: TestCase, time_limit_ms: int, memory_limit_mb: int
    ) -> Verdict:
        """Determine verdict for a test case execution"""
        if execution.compile_error:
            return Verdict.COMPILATION_ERROR

        if execution.exit_code != 0 and execution.stderr:
            return Verdict.RUNTIME_ERROR

        if execution.runtime_ms > time_limit_ms:
            return Verdict.TIME_LIMIT_EXCEEDED

        if execution.memory_mb > memory_limit_mb:
            return Verdict.MEMORY_LIMIT_EXCEEDED

        expected = test_case.expected.strip()
        actual = execution.stdout.strip()

        if expected != actual:
            return Verdict.WRONG_ANSWER

        return Verdict.ACCEPTED

    def _analyze_results(
        self,
        problem_title: str,
        language: str,
        code: str,
        test_cases: List[TestCase],
        results: List[TestCaseResult],
        time_limit_ms: int,
    ) -> EvaluationReport:
        """Analyze test results and generate report"""
        passed_tests = sum(1 for r in results if r.passed)
        total_tests = len(results)
        success_rate = f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%"

        # Determine overall verdict
        if results:
            first_result = results[0]
            if first_result.verdict == Verdict.COMPILATION_ERROR:
                overall_verdict = Verdict.COMPILATION_ERROR
                compile_error = first_result.execution.compile_error
                runtime_error = None
            elif any(r.verdict == Verdict.COMPILATION_ERROR for r in results):
                overall_verdict = Verdict.COMPILATION_ERROR
                compile_error = next(
                    (r.execution.compile_error for r in results if r.execution.compile_error),
                    None,
                )
                runtime_error = None
            elif all(r.passed for r in results):
                overall_verdict = Verdict.ACCEPTED
                compile_error = None
                runtime_error = None
            else:
                failed = next((r for r in results if not r.passed), None)
                overall_verdict = failed.verdict if failed else Verdict.WRONG_ANSWER
                compile_error = None
                runtime_error = (
                    failed.execution.stderr if failed and failed.execution.stderr else None
                )
        else:
            overall_verdict = Verdict.WRONG_ANSWER
            compile_error = None
            runtime_error = None

        # Find first failed test case
        failed_testcase = None
        if passed_tests < total_tests:
            failed = next((r for r in results if not r.passed), None)
            if failed:
                failed_testcase = {
                    "input": failed.execution.stdout if failed.execution.stdout else test_cases[failed.test_case_id - 1].input,
                    "expected": failed.expected,
                    "got": failed.got,
                }

        # Calculate execution stats
        execution_stats = {
            "avg_runtime_ms": (
                sum(r.execution.runtime_ms for r in results) / len(results)
                if results
                else 0
            ),
            "max_runtime_ms": (
                max(r.execution.runtime_ms for r in results) if results else 0
            ),
            "max_memory_kb": max(r.execution.memory_mb * 1024 for r in results) if results else 0,
        }

        # Complexity analysis
        complexity = {
            "time": CodeAnalyzer.analyze_time_complexity(code, language),
            "space": CodeAnalyzer.analyze_space_complexity(code, language),
        }

        # Code analysis
        issues = CodeAnalyzer.detect_issues(code, language)
        analysis = issues if issues else ["Code structure looks reasonable"]

        # Optimization suggestions
        suggestions = CodeAnalyzer.suggest_optimizations(code, language)

        return EvaluationReport(
            problem=problem_title,
            language=language,
            verdict=overall_verdict,
            passed_tests=passed_tests,
            total_tests=total_tests,
            success_rate=success_rate,
            compile_error=compile_error,
            runtime_error=runtime_error,
            failed_testcase=failed_testcase,
            execution=execution_stats,
            complexity=complexity,
            analysis=analysis,
            optimization_suggestions=suggestions,
            test_results=[
                {
                    "test_case_id": result.test_case_id,
                    "passed": result.passed,
                    "verdict": result.verdict.value,
                    "expected": result.expected,
                    "got": result.got,
                    "runtime_ms": result.execution.runtime_ms,
                    "memory_kb": result.execution.memory_mb * 1024,
                    "error": result.execution.stderr or result.execution.compile_error,
                }
                for result in results
            ],
        )

    def _is_malicious_code(self, code: str) -> bool:
        """Check if code contains potentially malicious patterns"""
        dangerous_patterns = [
            "exec(",
            "eval(",
            "os.system",
            "subprocess",
            "open(",
            "import os",
            "__import__",
        ]

        for pattern in dangerous_patterns:
            if pattern in code.lower():
                return True

        return False

    def _security_violation_report(
        self, problem_title: str, language: str, reason: str
    ) -> EvaluationReport:
        """Generate a security violation report"""
        return EvaluationReport(
            problem=problem_title,
            language=language,
            verdict=Verdict.SECURITY_VIOLATION,
            passed_tests=0,
            total_tests=0,
            success_rate="0%",
            compile_error=None,
            runtime_error=reason,
            failed_testcase=None,
            execution={"avg_runtime_ms": 0, "max_memory_kb": 0},
            complexity={"time": "Unknown", "space": "Unknown"},
            analysis=[reason],
            optimization_suggestions=[],
            test_results=[],
        )


# ============================================================================
# Factory Functions
# ============================================================================

async def create_evaluator() -> CompetitiveProgrammingEvaluator:
    """Factory function to create evaluator instance"""
    piston_client = PistonClient()
    return CompetitiveProgrammingEvaluator(piston_client)
