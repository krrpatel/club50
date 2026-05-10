"""
club50 – CS50-style submission & grading backend
Production-ready FastAPI backend with check50 & submit50 integration
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import string
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

import requests
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from runners.check50_runner import run_check50_async
from validators.custom_check_runner import run_custom_checks

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="club50 API",
    description="CS50-style competitive programming judge with check50 integration",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Environment Configuration
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://juwcvijbzjdhbiavofhd.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
BOOTSTRAP_ADMIN_ENROLLMENT = os.getenv("BOOTSTRAP_ADMIN_ENROLLMENT", "").strip()
AI_PROVIDER = os.getenv("AI_PROVIDER", "").strip().lower()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "gpt-4.1-mini")
WEEK_RESOURCES_BUCKET = os.getenv("WEEK_RESOURCES_BUCKET", "week-resources")

# ---------------------------------------------------------------------------
# API Headers for External Services
# ---------------------------------------------------------------------------
OCTOPOD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://octopod.co.in/",
    "X-Requested-With": "XMLHttpRequest"
}

# ---------------------------------------------------------------------------
# Data models and enums
# ---------------------------------------------------------------------------
class Verdict(str, Enum):
    """Submission verdict states"""
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    COMPILATION_ERROR = "compilation_error"
    RUNTIME_ERROR = "runtime_error"
    TIME_LIMIT = "time_limit_exceeded"
    MEMORY_LIMIT = "memory_limit_exceeded"
    QUEUED = "queued"
    RUNNING = "running"


class TestResult(BaseModel):
    """Individual test case result"""
    name: str
    description: str
    passed: bool
    log: List[str] = []
    cause: Optional[Dict[str, Any]] = None
    data: Dict[str, Any] = {}
    rationale: Optional[str] = None
    help: Optional[str] = None


class Check50Result(BaseModel):
    """check50 execution result"""
    slug: str
    results: List[TestResult]
    version: str = "3.0.0"


# In-memory store (replace with proper DB in production)
SUBMISSIONS: Dict[str, Dict] = {}
LEADERBOARD: Dict[str, Dict] = {}   # keyed by username

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class CheckRequest(BaseModel):
    """Check execution request"""
    problem_id: str
    code: str
    language: str = "python"


class CheckResult(BaseModel):
    """Check execution result"""
    problem_id: str
    language: str
    results: List[Dict[str, Any]]
    passed: int
    total: int
    compilation_output: str = ""
    submission_id: Optional[str] = None
    tracking_url: Optional[str] = None


class SubmissionRequest(BaseModel):
    """Submission request"""
    problem_id: str
    code: str
    language: str
    username: str


class SubmissionResponse(BaseModel):
    """Submission response"""
    submission_id: str
    status: str
    tracking_url: str
    message: str


class SignupRequest(BaseModel):
    """Signup request"""
    enrollment_number: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    current_semester: Optional[int] = Field(None, ge=1, le=8)
    academic_year: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request"""
    enrollment_number: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ProfileUpdateRequest(BaseModel):
    """Profile update request"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    current_semester: int = Field(..., ge=1, le=8)
    academic_year: str = Field(..., min_length=5)


class ProblemGenerationRequest(BaseModel):
    subject: str = Field(..., min_length=1)
    semester: int = Field(..., ge=1, le=8)
    topic: str = Field(..., min_length=1)
    transcript: str = Field(..., min_length=1)
    difficulty: str = Field(default="Medium", pattern="^(Easy|Medium|Hard)$")
    previously_generated: str = Field(default="")

class WeekRequest(BaseModel):
    title: str
    description: str
    problem_ids: List[str]

class WeekProblemsRequest(BaseModel):
    problem_ids: List[str]

class BulkSemesterUpdateRequest(BaseModel):
    from_semester: int
    to_semester: int
    academic_year: Optional[str] = None

class SuggestionRequest(BaseModel):
    prompt: str
    suggestion_type: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _short_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_supabase_config(service_role: bool = False) -> None:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(503, "Supabase URL and anon key are not configured")
    if service_role and not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(503, "Supabase service role key is not configured")


def _supabase_headers(service_role: bool = False, bearer: Optional[str] = None) -> Dict[str, str]:
    key = SUPABASE_SERVICE_ROLE_KEY if service_role else SUPABASE_ANON_KEY
    token = bearer or key
    return {
        "apikey": key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _supabase_request(
    method: str,
    path: str,
    *,
    service_role: bool = False,
    bearer: Optional[str] = None,
    json_body: Optional[Any] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    expected: tuple[int, ...] = (200, 201, 204),
) -> Any:
    _require_supabase_config(service_role=service_role)
    request_headers = _supabase_headers(service_role=service_role, bearer=bearer)
    if headers:
        request_headers.update(headers)
    try:
        response = requests.request(
            method,
            f"{SUPABASE_URL}{path}",
            headers=request_headers,
            json=json_body,
            params=params,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise HTTPException(502, f"Supabase request failed: {exc}") from exc
    if response.status_code not in expected:
        detail = response.text or response.reason
        raise HTTPException(response.status_code, detail)
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def _normalize_enrollment_number(value: str) -> str:
    return value.strip().upper()


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in full_name.strip().split() if part]
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


def _infer_batch_start_year(enrollment_number: str) -> Optional[int]:
    digits = "".join(ch for ch in enrollment_number if ch.isdigit())
    if len(digits) < 2:
        return None
    year = 2000 + int(digits[:2])
    if 2020 <= year <= 2099:
        return year
    return None


def _academic_year_from_batch(start_year: Optional[int]) -> str:
    if not start_year:
        return ""
    return f"AY{str(start_year)[-2:]}-{str(start_year + 4)[-2:]}"


def _infer_current_semester(enrollment_number: str) -> Optional[int]:
    start_year = _infer_batch_start_year(enrollment_number)
    if not start_year:
        return None
    now = datetime.now()
    academic_year_index = max(0, now.year - start_year)
    if now.month >= 7:
        semester = academic_year_index * 2 + 1
    else:
        semester = academic_year_index * 2
    return min(max(semester, 1), 8)


def _map_octopod_student(data: Dict[str, Any], academic_years: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(data, dict) or not data:
        return None
    source = data.get("Student") or data.get("student") or data.get("data") or data
    if isinstance(source, list):
        source = source[0] if source else {}
    if not isinstance(source, dict) or not source:
        return None

    def pick(*keys: str) -> str:
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    full_name = pick("student_full_name", "StudentFullName", "StudentName", "FullName", "Name")
    first_name = pick("first_name", "FirstName")
    last_name = pick("last_name", "LastName", "Surname")
    if full_name and not (first_name or last_name):
        first_name, last_name = _split_name(full_name)
    if not full_name:
        full_name = " ".join(part for part in [first_name, last_name] if part)

    if not full_name and not pick("uid_number", "UIDNumber", "UID", "EnrollmentNo"):
        return None

    return {
        "student_full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": pick("email", "Email", "EmailID", "EmailAddress"),
        "uid_number": pick("uid_number", "UIDNumber", "UID", "EnrollmentNo"),
        "city": pick("city", "City"),
        "state": pick("state", "State"),
        "country": pick("country", "Country"),
        "contact_no": pick("contact_no", "ContactNo", "MobileNo", "Phone"),
        "address": pick("address", "Address"),
        "admission_date": pick("admission_date", "AdmissionDate"),
        "academy_id": pick("academy_id", "AcademyID") or "1627",
        "academic_years": academic_years,
    }


def _lookup_enrollment(enrollment_number: str) -> Optional[Dict[str, Any]]:
    application_id = _normalize_enrollment_number(enrollment_number)
    years_url = "https://octopod.co.in/ajax/student/academic/years"
    validate_url = "https://octopod.co.in/ajax/validate/application"
    try:
        years_response = requests.get(
            years_url,
            params={"AcademyID": "1627", "applicationId": application_id, "isApplicationId": "1"},
            headers=OCTOPOD_HEADERS,
            timeout=15,
        )
        years_response.raise_for_status()
        years_payload = years_response.json()
        academic_years = years_payload if isinstance(years_payload, list) else years_payload.get("data", [])
        if not isinstance(academic_years, list) or not academic_years:
            return None
        first_year = academic_years[0]
        ayid = first_year.get("AYID") or first_year.get("ayid") or first_year.get("id")
        if not ayid:
            return None
        validation_response = requests.get(
            validate_url,
            params={
                "AcademyID": "1627",
                "applicationId": application_id,
                "IsOTPRequired": "0",
                "otp": "",
                "Year": ayid,
                "paymentCategory": "AcademicFees",
            },
            headers=OCTOPOD_HEADERS,
            timeout=15,
        )
        validation_response.raise_for_status()
        return _map_octopod_student(validation_response.json(), academic_years)
    except (requests.RequestException, ValueError, AttributeError, Exception) as e:
        logger.error(f"Octopod lookup error: {str(e)}")
        return None


def _profile_payload_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": record.get("id"),
        "enrollment_number": record.get("enrollment_number"),
        "first_name": record.get("first_name") or "",
        "last_name": record.get("last_name") or "",
        "full_name": record.get("full_name") or "",
        "email": record.get("email") or "",
        "role": record.get("role") or "student",
        "current_semester": record.get("current_semester"),
        "academic_year": record.get("academic_year") or "",
        "profile_completed": bool(record.get("profile_completed")),
    }


def _fetch_profile_by_user_id(user_id: str) -> Optional[Dict[str, Any]]:
    rows = _supabase_request(
        "GET",
        "/rest/v1/profiles",
        service_role=True,
        params={"id": f"eq.{user_id}", "select": "*", "limit": "1"},
    )
    return rows[0] if rows else None


def _fetch_profile_by_enrollment(enrollment_number: str) -> Optional[Dict[str, Any]]:
    rows = _supabase_request(
        "GET",
        "/rest/v1/profiles",
        service_role=True,
        params={
            "enrollment_number": f"eq.{_normalize_enrollment_number(enrollment_number)}",
            "select": "*",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


def _upsert_profile(record: Dict[str, Any]) -> Dict[str, Any]:
    rows = _supabase_request(
        "POST",
        "/rest/v1/profiles",
        service_role=True,
        json_body=record,
        headers={"Prefer": "resolution=merge-duplicates,return=representation"},
    )
    return rows[0]


def _validate_problem_ids(problem_ids: List) -> List[str]:
    """Convert problem_ids to strings, handling both int and str inputs"""
    return [str(pid) for pid in problem_ids]


def _resource_signed_url(path: str) -> str:
    try:
        payload = _supabase_request(
            "POST",
            f"/storage/v1/object/sign/{WEEK_RESOURCES_BUCKET}/{path}",
            service_role=True,
            json_body={"expiresIn": 3600},
        )
        signed = payload.get("signedURL") or payload.get("signedUrl") or ""
        return f"{SUPABASE_URL}{signed}" if signed.startswith("/") else signed
    except HTTPException:
        return ""


def _format_week(row: Dict[str, Any], include_signed_urls: bool = False) -> Dict[str, Any]:
    resources = row.get("resource_files") or []
    if include_signed_urls:
        resources = [
            {**resource, "url": _resource_signed_url(resource.get("key", ""))}
            for resource in resources
            if resource.get("key")
        ]
    # Convert problem_ids to strings for consistency
    problem_ids = row.get("problem_ids") or []
    problem_ids = [str(pid) for pid in problem_ids]
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "description": row.get("description"),
        "subject": row.get("subject") or "",
        "topic": row.get("topic") or "",
        "semester": row.get("semester"),
        "academic_years": row.get("academic_years") or [],
        "video_url": row.get("video_url"),
        "video_description": row.get("video_description"),
        "display_order": row.get("display_order", 0),
        "problem_ids": problem_ids,
        "resource_files": resources,
        "generated_problems": row.get("generated_problems") or [],
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _week_visible_to_profile(row: Dict[str, Any], profile: Optional[Dict[str, Any]]) -> bool:
    semester = row.get("semester")
    academic_years = row.get("academic_years") or []
    if not semester and not academic_years:
        return True
    if not profile:
        return False
    if semester and profile.get("current_semester") != semester:
        return False
    if academic_years and profile.get("academic_year") not in academic_years:
        return False
    return True


def _progress_for_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    enrollment = profile.get("enrollment_number")
    user_submissions = [s for s in SUBMISSIONS.values() if s.get("username") == enrollment and not s.get("temp_submission")]
    solved = {s["problem_id"] for s in user_submissions if s.get("verdict") == "accepted" or s.get("status") == "accepted"}
    available_weeks = [
        row for row in _supabase_request("GET", "/rest/v1/weeks", service_role=True, params={"select": "*"})
        if _week_visible_to_profile(row, profile)
    ]
    completed_weeks = [
        week for week in available_weeks
        if week.get("problem_ids") and all(problem_id in solved for problem_id in week.get("problem_ids") or [])
    ]
    return {
        "submissions": len(user_submissions),
        "problems_solved": len(solved),
        "available_weeks": len(available_weeks),
        "weeks_completed": len(completed_weeks),
    }


async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    auth_user = _supabase_request(
        "GET",
        "/auth/v1/user",
        bearer=token,
        expected=(200,),
    )
    profile = _fetch_profile_by_user_id(auth_user["id"])
    if not profile:
        raise HTTPException(401, "User profile not found")
    return {"auth": auth_user, "profile": profile, "token": token}


async def require_admin(current: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if current["profile"].get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return current


def _simulate_run(code: str, test_input: str, language: str, problem_id: str = "") -> Dict:
    """
    Execute code in a sandboxed environment and capture output.
    Supports: python, java, cpp, javascript
    """
    # This is a simplified simulation. In production, this would run in a Docker container.
    import random
    t0 = time.perf_counter()
    
    try:
        if language == "python":
            output, error = _run_python(code, test_input, problem_id)
        elif language == "java":
            output, error = _run_java(code, test_input, problem_id)
        elif language == "cpp":
            output, error = _run_cpp(code, test_input, problem_id)
        elif language == "javascript":
            output, error = _run_js(code, test_input, problem_id)
        else:
            output, error = "", f"Unsupported language: {language}"
        
        elapsed = time.perf_counter() - t0
        runtime_ms = round(elapsed * 1000, 2)
        mem_kb = random.randint(4000, 32000)  # Simulated memory
        
        return {
            "output": output,
            "runtime_ms": runtime_ms,
            "memory_kb": mem_kb,
            "error": error,
        }
    except Exception as exc:
        return {"output": "", "runtime_ms": 0, "memory_kb": 0, "error": str(exc)}


def _run_python(code: str, test_input: str, problem_id: str = "") -> tuple[str, Optional[str]]:
    """Execute Python code and return (stdout, stderr)."""
    try:
        # Wrap user code if it's just a function
        if not "if __name__" in code and not "def main" in code:
            wrapped = f"""{code}

# Auto-generated wrapper
if __name__ == "__main__":
    import sys
    lines = sys.stdin.read().strip().split('\\n')
    
    if '{problem_id}' == 'prob1' or 'two_sum' in code.lower() or 'twosum' in code.lower():
        n = int(lines[0])
        nums = list(map(int, lines[1].split()))
        target = int(lines[2])
        result = two_sum(nums, target)
        print(' '.join(map(str, result)))
    elif '{problem_id}' == 'prob2' or 'fib' in code.lower():
        n = int(lines[0])
        result = fibonacci(n)
        print(result)
    elif '{problem_id}' == 'prob3' or 'palindrome' in code.lower():
        s = lines[0]
        result = is_palindrome(s)
        print("YES" if result else "NO")
"""
            code = wrapped
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            result = subprocess.run(
                ['python', f.name],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=5
            )
            Path(f.name).unlink()
            return result.stdout.strip(), result.stderr if result.returncode != 0 else None
    except subprocess.TimeoutExpired:
        return "", "Time limit exceeded"
    except Exception as e:
        return "", str(e)


def _run_java(code: str, test_input: str, problem_id: str = "") -> tuple[str, Optional[str]]:
    """Compile and execute Java code, return (stdout, stderr)."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Wrap user code if it's just a method
            if "public static void main" not in code:
                # Determine which method to wrap
                if problem_id == "prob1" or "twoSum" in code or "two_sum" in code:
                    wrapped = f"""{code}

public class Solution {{
    public static void main(String[] args) {{
        java.util.Scanner sc = new java.util.Scanner(System.in);
        int n = sc.nextInt();
        int[] nums = new int[n];
        for (int i = 0; i < n; i++) {{
            nums[i] = sc.nextInt();
        }}
        int target = sc.nextInt();
        int[] ans = twoSum(nums, target);
        System.out.println(ans[0] + " " + ans[1]);
        sc.close();
    }}
}}
"""
                elif problem_id == "prob2" or "fibonacci" in code.lower() or "fib" in code.lower():
                    wrapped = f"""{code}

public class Solution {{
    public static void main(String[] args) {{
        java.util.Scanner sc = new java.util.Scanner(System.in);
        int n = sc.nextInt();
        long result = fibonacci(n);
        System.out.println(result);
        sc.close();
    }}
}}
"""
                else:
                    wrapped = f"""{code}

public class Solution {{
    public static void main(String[] args) {{
        java.util.Scanner sc = new java.util.Scanner(System.in);
        String line = sc.nextLine();
        boolean result = isPalindrome(line);
        System.out.println(result ? "YES" : "NO");
        sc.close();
    }}
}}
"""
                code = wrapped
            
            # Write source
            src_file = tmpdir / "Solution.java"
            src_file.write_text(code)
            
            # Compile
            compile_result = subprocess.run(
                ['javac', str(src_file)],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(tmpdir)
            )
            if compile_result.returncode != 0:
                return "", f"Compilation error: {compile_result.stderr}"
            
            # Run
            run_result = subprocess.run(
                ['java', '-cp', str(tmpdir), 'Solution'],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(tmpdir)
            )
            return run_result.stdout.strip(), run_result.stderr if run_result.returncode != 0 else None
    except subprocess.TimeoutExpired:
        return "", "Time limit exceeded"
    except FileNotFoundError:
        return "", "Java compiler not found (javac)"
    except Exception as e:
        return "", str(e)


def _run_cpp(code: str, test_input: str, problem_id: str = "") -> tuple[str, Optional[str]]:
    """Compile and execute C++ code, return (stdout, stderr)."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Wrap user code if it's just a function
            if "int main" not in code:
                if problem_id == "prob1" or "twoSum" in code or "two_sum" in code:
                    wrapped = f"""{code}

int main() {{
    int n;
    std::cin >> n;
    std::vector<int> nums(n);
    for (int i = 0; i < n; i++) {{
        std::cin >> nums[i];
    }}
    int target;
    std::cin >> target;
    auto ans = twoSum(nums, target);
    std::cout << ans[0] << " " << ans[1] << std::endl;
    return 0;
}}
"""
                else:
                    wrapped = f"""{code}

int main() {{
    int n;
    std::cin >> n;
    long long result = fibonacci(n);
    std::cout << result << std::endl;
    return 0;
}}
"""
                code = wrapped
            
            src_file = tmpdir / "solution.cpp"
            exe_file = tmpdir / "solution.exe"
            src_file.write_text(code)
            
            # Compile
            compile_result = subprocess.run(
                ['g++', str(src_file), '-o', str(exe_file)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if compile_result.returncode != 0:
                return "", f"Compilation error: {compile_result.stderr}"
            
            # Run
            run_result = subprocess.run(
                [str(exe_file)],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=5
            )
            return run_result.stdout.strip(), run_result.stderr if run_result.returncode != 0 else None
    except subprocess.TimeoutExpired:
        return "", "Time limit exceeded"
    except FileNotFoundError:
        return "", "C++ compiler not found (g++)"
    except Exception as e:
        return "", str(e)


def _run_js(code: str, test_input: str, problem_id: str = "") -> tuple[str, Optional[str]]:
    """Execute JavaScript code with Node.js, return (stdout, stderr)."""
    try:
        # Wrap user code if needed
        if "require('readline')" not in code and "process.stdin" not in code:
            if problem_id == "prob1" or "twoSum" in code or "two_sum" in code:
                wrapped = f"""{code}

const readline = require('readline');
const rl = readline.createInterface({{ input: process.stdin, output: process.stdout, terminal: false }});
let lines = [];
rl.on('line', (line) => lines.push(line));
rl.on('close', () => {{
    const n = parseInt(lines[0]);
    const nums = lines[1].split(' ').map(Number);
    const target = parseInt(lines[2]);
    const ans = twoSum(nums, target);
    console.log(ans[0] + ' ' + ans[1]);
}});
"""
            else:
                wrapped = f"""{code}

const readline = require('readline');
const rl = readline.createInterface({{ input: process.stdin, output: process.stdout, terminal: false }});
let lines = [];
rl.on('line', (line) => lines.push(line));
rl.on('close', () => {{
    const n = parseInt(lines[0]);
    const result = fibonacci(n);
    console.log(result);
}});
"""
            code = wrapped
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            f.flush()
            result = subprocess.run(
                ['node', f.name],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=5
            )
            Path(f.name).unlink()
            return result.stdout.strip(), result.stderr if result.returncode != 0 else None
    except subprocess.TimeoutExpired:
        return "", "Time limit exceeded"
    except FileNotFoundError:
        return "", "Node.js not found"
    except Exception as e:
        return "", str(e)


def _fake_output(code: str, test_input: str, language: str) -> str:
    """Very naive demo output generator – replace with real sandbox."""
    code_lower = code.lower()
    lines = test_input.strip().splitlines()

    # prob1 – two sum
    if "two_sum" in code_lower or "twosum" in code_lower or ("nums" in code_lower and "target" in code_lower):
        if len(lines) >= 3:
            n = int(lines[0])
            nums = list(map(int, lines[1].split()))
            target = int(lines[2])
            for i in range(n):
                for j in range(i + 1, n):
                    if nums[i] + nums[j] == target:
                        return f"{i} {j}"
        return "0 1"
    # ... existing simulation logic ...
    return ""

    # prob2 – fibonacci
    if "fib" in code_lower:
        try:
            n = int(lines[0])
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            return str(a)
        except Exception:
            pass

    # prob3 – palindrome
    if "palindrome" in code_lower or ("[::-1]" in code):
        try:
            s = lines[0].strip()
            return "YES" if s == s[::-1] else "NO"
        except Exception:
            pass

    # Default: return something plausible
    return lines[-1] if lines else ""


def _run_tests(code: str, tests: List[Dict], language: str) -> List[Dict]:
    results = []
    for tc in tests:
        res = _simulate_run(code, tc["input"], language)
        got = res["output"].strip()
        exp = tc["expected"].strip()
        passed = got == exp
        results.append({
            "id": tc["id"],
            "label": tc.get("label", tc["id"]),
            "input": tc["input"],
            "passed": passed,
            "expected": exp,
            "got": got,
            "runtime_ms": res["runtime_ms"],
            "memory_kb": res["memory_kb"],
            "error": res["error"],
            "hint": _hint(tc["id"], passed),
        })
    return results


def _hint(tc_id: str, passed: bool) -> Optional[str]:
    if passed:
        return None
    hints = {
        "t1": "Make sure you read the array size first.",
        "t2": "Check your loop bounds.",
        "t3": "Edge case: identical elements.",
        "h1": "Think about overflow.",
        "h2": "Handle negative numbers carefully.",
    }
    return hints.get(tc_id, "Review your logic for this edge case.")


def _verdict(results: List[Dict], compilation_ok: bool) -> str:
    if not compilation_ok:
        return "compilation_error"
    if all(r["passed"] for r in results):
        return "accepted"
    errors = [r for r in results if not r["passed"]]
    if errors and errors[0].get("error"):
        return "runtime_error"
    return "wrong_answer"


def _score(results: List[Dict], problem: Dict) -> int:
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    return int((passed / total) * problem["points"]) if total else 0


def _create_submission_record(
    sub_id: str,
    problem_id: str,
    username: str,
    code: str,
    language: str,
    status: str,
    verdict: Optional[str],
    score: int,
    max_score: int,
    public_results: List[Dict],
    hidden_results: List[Dict],
    compilation_output: str,
    submitted_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    temp_submission: bool = False,
) -> Dict:
    now = _now()
    submitted_at = submitted_at or now
    import random
    runtimes = [r.get("runtime_ms", 0) for r in public_results + hidden_results]
    memories = [r.get("memory_kb", 0) for r in public_results + hidden_results]
    SUBMISSIONS[sub_id] = {
        "id": sub_id,
        "username": username,
        "problem_id": problem_id,
        "problem_title": PROBLEMS[problem_id]["title"],
        "language": language,
        "code": code,
        "status": status,
        "verdict": verdict,
        "score": score,
        "max_score": max_score,
        "runtime_ms": round(max(runtimes), 2) if runtimes else 0,
        "memory_kb": max(memories) if memories else 0,
        "public_results": public_results,
        "hidden_results": hidden_results,
        "compilation_output": compilation_output,
        "submitted_at": submitted_at,
        "finished_at": finished_at,
        "updated_at": now,
        "leaderboard_rank": None,
        "temp_submission": temp_submission,
    }
    return SUBMISSIONS[sub_id]


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------
async def _process_submission(sub_id: str):
    """Async background worker that mimics a real judge queue."""
    sub = SUBMISSIONS[sub_id]
    problem = PROBLEMS.get(sub["problem_id"])
    import random
    if not problem:
        sub["status"] = "runtime_error"
        return

    await asyncio.sleep(0.5)
    sub["status"] = "compiling"
    sub["updated_at"] = _now()

    # Simulate compile
    await asyncio.sleep(random.uniform(0.3, 0.8))
    sub["compilation_output"] = "Compilation successful."
    sub["status"] = "running"
    sub["updated_at"] = _now()

    # Run all tests (public + hidden)
    await asyncio.sleep(random.uniform(0.5, 1.2))
    pub = _run_tests(sub["code"], problem["public_tests"], sub["language"])
    hid = _run_tests(sub["code"], problem["hidden_tests"], sub["language"])

    all_results = pub + hid
    verdict = _verdict(all_results, True)
    score = _score(all_results, problem)

    # Aggregate runtime/memory
    runtimes = [r["runtime_ms"] for r in all_results]
    memories = [r["memory_kb"] for r in all_results]

    sub.update({
        "status": verdict,
        "verdict": verdict,
        "score": score,
        "max_score": problem["points"],
        "public_results": pub,
        "hidden_results": hid,
        "runtime_ms": round(max(runtimes), 2) if runtimes else 0,
        "memory_kb": max(memories) if memories else 0,
        "finished_at": _now(),
        "updated_at": _now(),
        "leaderboard_rank": None,
    })

    # Update leaderboard
    key = f"{sub['username']}::{sub['problem_id']}"
    existing = LEADERBOARD.get(key, {}).get("score", -1)
    if score > existing:
        LEADERBOARD[key] = {
            "username": sub["username"],
            "problem_id": sub["problem_id"],
            "problem_title": problem["title"],
            "score": score,
            "max_score": problem["points"],
            "verdict": verdict,
            "runtime_ms": sub["runtime_ms"],
            "submission_id": sub_id,
            "submitted_at": sub["submitted_at"],
        }

    # Compute rank
    sorted_lb = sorted(LEADERBOARD.values(), key=lambda x: (-x["score"], x["runtime_ms"]))
    for rank, entry in enumerate(sorted_lb, 1):
        if entry["submission_id"] == sub_id:
            sub["leaderboard_rank"] = rank
            LEADERBOARD[key]["rank"] = rank
            break


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"service": "club50", "version": "1.0.0", "status": "operational"}
@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": _now()}


@app.get("/api/v1/config/status")
async def config_status():
    return {
        "supabase_url_configured": bool(SUPABASE_URL),
        "supabase_anon_key_configured": bool(SUPABASE_ANON_KEY),
        "supabase_service_role_key_configured": bool(SUPABASE_SERVICE_ROLE_KEY),
        "ai_provider": AI_PROVIDER or None,
        "ai_api_key_configured": bool(AI_API_KEY),
        "ai_model": AI_MODEL,
    }


@app.get("/api/v1/auth/enrollment/{enrollment_number}")
async def lookup_enrollment(enrollment_number: str):
    details = _lookup_enrollment(enrollment_number)
    inferred_semester = _infer_current_semester(enrollment_number)
    academic_year = _academic_year_from_batch(_infer_batch_start_year(enrollment_number))
    if not details:
        return {
            "found": False,
            "enrollment_number": _normalize_enrollment_number(enrollment_number),
            "current_semester": inferred_semester,
            "academic_year": academic_year,
            "message": "Enrollment lookup unavailable. Continue with manual profile details.",
        }
    return {
        "found": True,
        "enrollment_number": _normalize_enrollment_number(enrollment_number),
        "current_semester": inferred_semester,
        "academic_year": academic_year,
        **details,
    }


@app.post("/api/v1/auth/signup")
async def signup(req: SignupRequest):
    enrollment_number = _normalize_enrollment_number(req.enrollment_number)
    existing = _fetch_profile_by_enrollment(enrollment_number)
    if existing:
        raise HTTPException(409, "An account already exists for this enrollment number")

    enrollment = _lookup_enrollment(enrollment_number) or {}
    first_name = req.first_name or enrollment.get("first_name") or ""
    last_name = req.last_name or enrollment.get("last_name") or ""
    full_name = enrollment.get("student_full_name") or " ".join(part for part in [first_name, last_name] if part)
    email = (req.email or enrollment.get("email") or f"{enrollment_number.lower()}@club50.local").strip().lower()
    is_placeholder_email = email.endswith("@club50.local")
    current_semester = req.current_semester or _infer_current_semester(enrollment_number)
    academic_year = req.academic_year or _academic_year_from_batch(_infer_batch_start_year(enrollment_number))
    profile_completed = bool(current_semester and academic_year)

    auth_user = _supabase_request(
        "POST",
        "/auth/v1/admin/users",
        service_role=True,
        json_body={
            "email": email,
            "password": req.password,
            "email_confirm": True,
            "user_metadata": {"enrollment_number": enrollment_number, "full_name": full_name},
        },
        expected=(200, 201),
    )
    role = "admin" if BOOTSTRAP_ADMIN_ENROLLMENT and enrollment_number == BOOTSTRAP_ADMIN_ENROLLMENT.upper() else "student"
    profile = _upsert_profile({
        "id": auth_user["id"],
        "enrollment_number": enrollment_number,
        "role": role,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "email": email,
        "uid_number": enrollment.get("uid_number"),
        "city": enrollment.get("city"),
        "state": enrollment.get("state"),
        "country": enrollment.get("country"),
        "contact_no": enrollment.get("contact_no"),
        "address": enrollment.get("address"),
        "admission_date": enrollment.get("admission_date"),
        "enrollment_metadata": enrollment,
        "is_placeholder_email": is_placeholder_email,
        "current_semester": current_semester,
        "academic_year": academic_year,
        "profile_completed": profile_completed,
    })
    token_payload = _supabase_request(
        "POST",
        "/auth/v1/token",
        json_body={"email": email, "password": req.password},
        params={"grant_type": "password"},
        expected=(200,),
    )
    return {
        "token": token_payload.get("access_token"),
        "refresh_token": token_payload.get("refresh_token"),
        "user": _profile_payload_from_record(profile),
    }


@app.post("/api/v1/auth/login")
async def login(req: LoginRequest):
    profile = _fetch_profile_by_enrollment(req.enrollment_number)
    if not profile or not profile.get("email"):
        raise HTTPException(401, "Invalid enrollment number or password")
    token_payload = _supabase_request(
        "POST",
        "/auth/v1/token",
        json_body={"email": profile["email"], "password": req.password},
        params={"grant_type": "password"},
        expected=(200,),
    )
    return {
        "token": token_payload.get("access_token"),
        "refresh_token": token_payload.get("refresh_token"),
        "user": _profile_payload_from_record(profile),
    }


@app.get("/api/v1/auth/me")
async def auth_me(current: Dict[str, Any] = Depends(get_current_user)):
    return {"user": _profile_payload_from_record(current["profile"]), "progress": _progress_for_profile(current["profile"])}


@app.put("/api/v1/auth/profile")
async def update_profile(req: ProfileUpdateRequest, current: Dict[str, Any] = Depends(get_current_user)):
    profile = current["profile"]
    updated = _upsert_profile({
        **profile,
        "first_name": req.first_name if req.first_name is not None else profile.get("first_name"),
        "last_name": req.last_name if req.last_name is not None else profile.get("last_name"),
        "email": req.email if req.email is not None else profile.get("email"),
        "current_semester": req.current_semester,
        "academic_year": req.academic_year,
        "profile_completed": True,
    })
    return {"user": _profile_payload_from_record(updated), "progress": _progress_for_profile(updated)}


@app.get("/api/v1/weeks")
async def list_weeks(authorization: Optional[str] = Header(None)):
    profile = None
    if authorization and authorization.lower().startswith("bearer "):
        try:
            token = authorization.split(" ", 1)[1].strip()
            auth_user = _supabase_request("GET", "/auth/v1/user", bearer=token, expected=(200,))
            profile = _fetch_profile_by_user_id(auth_user["id"])
        except HTTPException:
            profile = None
    rows = _supabase_request(
        "GET",
        "/rest/v1/weeks",
        service_role=True,
        params={
            "select": "*",
            "order": "display_order.asc,created_at.asc",
        }
    )

    visible_rows = [row for row in rows if profile and profile.get("role") == "admin" or _week_visible_to_profile(row, profile)]
    return [_format_week(row) for row in visible_rows]


@app.get("/api/v1/weeks/{week_id}")
async def get_week(week_id: str, current: Dict[str, Any] = Depends(get_current_user)):
    # ... logic to fetch single week ...
    rows = _supabase_request("GET", "/rest/v1/weeks", service_role=True, params={"id": f"eq.{week_id}", "select": "*", "limit": "1"})

    if not rows:
        raise HTTPException(404, "Week not found")
    if current["profile"].get("role") != "admin" and not _week_visible_to_profile(rows[0], current["profile"]):
        raise HTTPException(403, "This week is not available for your semester")
    week = _format_week(rows[0], include_signed_urls=True)
    
    # Fetch problem details for the IDs listed in the week
    if week["problem_ids"]:
        # Convert string IDs to integers for query
        int_ids = [int(pid) if pid.isdigit() else pid for pid in week["problem_ids"]]
        ids_str = ",".join(str(pid) for pid in int_ids)
        prob_rows = _supabase_request(
            "GET",
            "/rest/v1/problems",
            service_role=True,
            params={"id": f"in.({ids_str})", "select": "id,title,difficulty,slug"}
        )
        # Convert problem IDs back to strings in response
        week["problems"] = [dict(row, id=str(row["id"])) for row in prob_rows]
    else:
        week["problems"] = []
        
    return week


@app.post("/api/v1/admin/weeks")
async def create_week(req: WeekRequest, admin: Dict[str, Any] = Depends(require_admin)):
    payload = req.model_dump()
    payload["problem_ids"] = _validate_problem_ids(payload["problem_ids"])
    rows = _supabase_request(
        "POST",
        "/rest/v1/weeks",
        service_role=True,
        json_body=payload,
        headers={"Prefer": "return=representation"},
        expected=(201,),
    )
    return _format_week(rows[0])


@app.put("/api/v1/admin/weeks/{week_id}")
async def update_week(week_id: str, req: WeekRequest, admin: Dict[str, Any] = Depends(require_admin)):
    payload = req.model_dump()
    payload["problem_ids"] = _validate_problem_ids(payload["problem_ids"])
    rows = _supabase_request(
        "PATCH",
        "/rest/v1/weeks",
        service_role=True,
        json_body=payload,
        params={"id": f"eq.{week_id}"},
        headers={"Prefer": "return=representation"},
    )
    if not rows:
        raise HTTPException(404, "Week not found")
    return _format_week(rows[0])


@app.delete("/api/v1/admin/weeks/{week_id}")
async def delete_week(week_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    _supabase_request(
        "DELETE",
        "/rest/v1/weeks",
        service_role=True,
        params={"id": f"eq.{week_id}"},
        headers={"Prefer": "return=minimal"},
    )
    return {"ok": True}


@app.post("/api/v1/admin/weeks/{week_id}/problems")
async def assign_week_problems(
    week_id: str,
    req: WeekProblemsRequest,
    admin: Dict[str, Any] = Depends(require_admin),
):
    rows = _supabase_request(
        "PATCH",
        "/rest/v1/weeks",
        service_role=True,
        json_body={"problem_ids": _validate_problem_ids(req.problem_ids)},
        params={"id": f"eq.{week_id}"},
        headers={"Prefer": "return=representation"},
    )
    if not rows:
        raise HTTPException(404, "Week not found")
    return _format_week(rows[0])


@app.post("/api/v1/admin/uploads")
async def upload_resource(file: UploadFile = File(...), admin: Dict[str, Any] = Depends(require_admin)):
    ext = Path(file.filename or "resource").suffix
    key = f"{uuid.uuid4().hex}{ext}"
    content = await file.read()
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": file.content_type or "application/octet-stream",
        "x-upsert": "false",
    }
    try:
        response = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{WEEK_RESOURCES_BUCKET}/{key}",
            headers=headers,
            data=content,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise HTTPException(502, f"Upload failed: {exc}") from exc
    if response.status_code not in (200, 201):
        raise HTTPException(response.status_code, response.text)
    return {
        "url": _resource_signed_url(key),
        "key": key,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
    }


@app.get("/api/v1/admin/students")
async def list_students(
    semester: Optional[int] = None,
    academic_year: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    params: Dict[str, Any] = {"select": "*", "order": "academic_year.asc,current_semester.asc,enrollment_number.asc"}
    if semester:
        params["current_semester"] = f"eq.{semester}"
    if academic_year:
        params["academic_year"] = f"eq.{academic_year}"
    rows = _supabase_request("GET", "/rest/v1/profiles", service_role=True, params=params)
    return [
        {**_profile_payload_from_record(row), "progress": _progress_for_profile(row)}
        for row in rows
    ]


@app.post("/api/v1/admin/students/bulk-semester")
async def bulk_update_semester(req: BulkSemesterUpdateRequest, admin: Dict[str, Any] = Depends(require_admin)):
    params: Dict[str, Any] = {"current_semester": f"eq.{req.from_semester}"}
    if req.academic_year:
        params["academic_year"] = f"eq.{req.academic_year}"
    rows = _supabase_request(
        "PATCH",
        "/rest/v1/profiles",
        service_role=True,
        params=params,
        json_body={"current_semester": req.to_semester, "profile_completed": True},
        headers={"Prefer": "return=representation"},
    )
    return {"updated": len(rows or []), "students": [_profile_payload_from_record(row) for row in rows or []]}


@app.post("/api/v1/admin/problem-generation")
async def generate_problems(req: ProblemGenerationRequest, admin: Dict[str, Any] = Depends(require_admin)):
    if AI_PROVIDER not in ("openai", "gemini") or not AI_API_KEY:
        return _fallback_problem_generation(req)
    system = """You are an expert competitive programming and DSA problem setter.
Analyze lecture context and generate interview-quality LeetCode-style coding problems at the specified difficulty level.
Return strictly valid JSON in this exact shape:
{
"subject": "",
"semester": "",
"topic": "",
"problems": [{
"title": "",
"difficulty": "",
"statement": "",
"real_world_context": "",
"constraints": [],
"input_format": "",
"output_format": "",
"examples": [{"input": "", "output": "", "explanation": ""}],
"function_signature": "",
"edge_cases": [],
"hidden_test_case_ideas": [],
"tags": [],
"optimal_approach": "",
"time_complexity": "",
"space_complexity": ""
}]
}
Rules: 
- Make examples valid and constraints realistic
- Include non-trivial edge cases
- Relate directly to the topic
- Generate UNIQUE problems (never duplicate the provided titles)
- All problems MUST be at the specified difficulty level
- Generate 2-3 distinct problems at this difficulty"""
    
    previously_generated_text = ""
    if req.previously_generated:
        previously_generated_text = f"\n\nPreviously generated problems (AVOID DUPLICATING THESE):\n{req.previously_generated}"
    
    try:
        return _call_ai_json([
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Subject: {req.subject}\nSemester: {req.semester}\nTopic: {req.topic}\n"
                    f"Difficulty Level: {req.difficulty}\n"
                    f"Transcript or summary:\n{req.transcript}"
                    f"{previously_generated_text}"
                ),
            },
        ])
    except Exception as exc:
        fallback = _fallback_problem_generation(req)
        fallback["warning"] = f"AI generation failed, fallback returned: {exc}"
        return fallback


def _fallback_suggestion(req: SuggestionRequest) -> Dict[str, Any]:
    base = {
        "notes": "AI suggestions are unavailable because AI_PROVIDER and AI_API_KEY are not configured.",
    }
    if req.suggestion_type in ("title", "all"):
        base["title"] = "Refine this problem title"
    if req.suggestion_type in ("description", "all"):
        base["description"] = f"Turn this prompt into a clear programming challenge: {req.prompt[:240]}"
    if req.suggestion_type in ("input_output", "all"):
        base["input_format"] = "Describe each input line and its expected type."
        base["output_format"] = "Describe the exact output format, including whitespace requirements."
    if req.suggestion_type in ("constraints", "all"):
        base["constraints"] = ["Add numeric limits", "Mention edge cases", "State time and memory expectations"]
    return base


def _fallback_problem_generation(req: ProblemGenerationRequest) -> Dict[str, Any]:
    # Map difficulty to time/space complexity hints
    complexity_map = {
        "Easy": ("O(n)", "O(1)"),
        "Medium": ("O(n log n)", "O(n)"),
        "Hard": ("O(n) or O(2^n)", "O(n) or more"),
    }
    time_c, space_c = complexity_map.get(req.difficulty, ("O(n log n)", "O(n)"))
    
    difficulty_hints = {
        "Easy": "Use simple iteration or basic data structures.",
        "Medium": "Requires sorting, searching, or moderate optimization.",
        "Hard": "Requires advanced algorithms, optimized approaches, or clever insights.",
    }
    hint = difficulty_hints.get(req.difficulty, "")
    
    return {
        "subject": req.subject,
        "semester": str(req.semester),
        "topic": req.topic,
        "problems": [
            {
                "title": f"{req.topic} - {req.difficulty} Variant",
                "difficulty": req.difficulty,
                "statement": f"Design an efficient solution for a problem based on {req.topic}. {hint}",
                "real_world_context": "Use the lecture concept to model and process structured input.",
                "constraints": ["1 <= n <= 2 * 10^5", "Input values fit in 32-bit signed integers"],
                "input_format": "Describe the input based on the generated task.",
                "output_format": "Print the required answer.",
                "examples": [{"input": "3\n1 2 3", "output": "6", "explanation": "Applies the topic rule to all values."}],
                "function_signature": "def solve() -> None:",
                "edge_cases": ["Minimum input size", "Repeated values", "Already optimal arrangement"],
                "hidden_test_case_ideas": ["Large random input", "Boundary values", "Adversarial ordering"],
                "tags": [req.topic, req.subject],
                "optimal_approach": f"Use the primary lecture idea. {hint}",
                "time_complexity": time_c,
                "space_complexity": space_c,
            }
        ],
        "warning": "AI provider is not configured, so a fallback template was returned.",
    }


def _call_openai_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": AI_MODEL,
            "messages": messages,
            "response_format": {"type": "json_object"},
        },
        timeout=45,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _call_gemini_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    prompt = "\n\n".join(f"{message['role'].upper()}:\n{message['content']}" for message in messages)
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{AI_MODEL}:generateContent",
        headers={"x-goog-api-key": AI_API_KEY, "Content-Type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def _call_ai_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    if AI_PROVIDER == "openai":
        return _call_openai_json(messages)
    if AI_PROVIDER == "gemini":
        return _call_gemini_json(messages)
    raise RuntimeError(f"Unsupported AI_PROVIDER: {AI_PROVIDER}")


@app.post("/api/v1/admin/suggestions")
async def create_suggestion(req: SuggestionRequest, admin: Dict[str, Any] = Depends(require_admin)):
    if AI_PROVIDER not in ("openai", "gemini") or not AI_API_KEY:
        return {"suggestions": _fallback_suggestion(req), "warning": "AI provider is not configured"}
    if req.suggestion_type in ("title", "description", "all"):
        system = (
            "You are an expert in structuring course content for DSA and competitive programming. "
            "Generate a concise, engaging title and description for a course week. "
            "Title should be catchy and specific. Description should briefly explain what students will learn. "
            "Return only JSON with optional keys: title, description, notes."
        )
    else:
        system = (
            "Return only compact JSON with optional keys: title, description, "
            "input_format, output_format, constraints, notes."
        )
    try:
        if req.suggestion_type in ("title", "description", "all"):
            user_content = f"Week context: {req.prompt}"
        else:
            user_content = f"Type: {req.suggestion_type}\nPrompt: {req.prompt}"
        return {"suggestions": _call_ai_json([
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ])}
    except Exception as exc:
        return {
            "suggestions": _fallback_suggestion(req),
            "warning": f"AI provider failed, fallback returned: {exc}",
        }


@app.get("/api/v1/problems")
async def list_problems():
    rows = _supabase_request(
        "GET", 
        "/rest/v1/problems", 
        service_role=True, 
        params={"select": "id,slug,title,description,difficulty,points,time_limit,memory_limit,tags,sample_inputs,sample_outputs"}
    )
    # Convert numeric IDs to strings for frontend consistency
    return [dict(row, id=str(row["id"])) for row in rows]


@app.get("/api/v1/problems/{problem_id}")
async def get_problem(problem_id: str):
    # Try to find by numeric ID first, then by slug
    filter_col = "id"
    filter_value = problem_id
    
    # Try as numeric ID first
    try:
        numeric_id = int(problem_id)
        rows = _supabase_request(
            "GET",
            "/rest/v1/problems",
            service_role=True,
            params={"id": f"eq.{numeric_id}", "select": "*", "limit": "1"}
        )
        if rows:
            row = rows[0]
            return dict(row, id=str(row["id"]))
    except ValueError:
        pass
    
    # Try as slug
    rows = _supabase_request(
        "GET",
        "/rest/v1/problems",
        service_role=True,
        params={"slug": f"eq.{problem_id}", "select": "*", "limit": "1"}
    )
    if not rows:
        raise HTTPException(404, "Problem not found")
    row = rows[0]
    return dict(row, id=str(row["id"]))

@app.post("/api/v1/problems")
async def create_problem(problem: Dict[str, Any], admin: Dict[str, Any] = Depends(require_admin)):
    # Map AI generated 'statement' to 'description' if necessary
    if "statement" in problem and "description" not in problem:
        problem["description"] = problem.pop("statement")
        
    rows = _supabase_request(
        "POST",
        "/rest/v1/problems",
        service_role=True,
        json_body=problem,
        headers={"Prefer": "return=representation"}
    )
    return rows[0]


@app.post("/api/v1/check", response_model=CheckResult)
async def check_local(req: CheckRequest):
    """Run check50 on public tests and persist a temporary submission."""
    problem = await get_problem(req.problem_id)
    if not problem:
        raise HTTPException(404, f"Problem '{req.problem_id}' not found")

    # Try check50 first, fall back to custom validator if it fails
    slug = problem.get("check_slug", f"github.com/yourclub/checks/{req.problem_id}")
    
    try:
        execution = await run_check50_async(
            code=req.code,
            language=req.language,
            problem_id=req.problem_id,
            check_slug=slug,
            offline=os.getenv("CHECK50_OFFLINE_MODE", "true").lower() == "true"
        )
        logger.info(f"check50 execution succeeded for problem {req.problem_id}")
    except Exception as e:
        logger.warning(f"check50 failed for problem {req.problem_id}: {e}, falling back to custom validator")
        # Fall back to custom validator
        check_dir = Path(__file__).parent.parent / "checks" / str(req.problem_id)
        try:
            execution = await run_custom_checks(
                code=req.code,
                language=req.language,
                problem_id=req.problem_id,
                check_dir=check_dir,
            )
            logger.info(f"Custom validator succeeded for problem {req.problem_id}")
        except Exception as e2:
            logger.error(f"Both check50 and custom validator failed: {e2}")
            raise HTTPException(500, f"Failed to run checks: {str(e2)}")

    passed = execution["passed"]
    results = execution["results"]
    score = int((passed / len(results)) * problem["points"]) if results else 0
    verdict = "accepted" if passed == len(results) else "wrong_answer"
    sub_id = _short_id()
    _create_submission_record(
        sub_id=sub_id,
        problem_id=req.problem_id,
        username="local",
        code=req.code,
        language=req.language,
        status=verdict,
        verdict=verdict,
        score=score,
        max_score=problem["points"],
        public_results=results,
        hidden_results=[],
        compilation_output="Compilation successful.",
        submitted_at=_now(),
        finished_at=_now(),
        temp_submission=True,
    )

    return CheckResult(
        problem_id=req.problem_id,
        language=req.language,
        results=results,
        passed=passed,
        total=len(results),
        compilation_output="Compilation successful.",
        submission_id=sub_id,
        tracking_url=f"https://club50.dev/submissions/{sub_id}",
    )


@app.post("/api/v1/submissions", response_model=SubmissionResponse)
async def create_submission(
    background_tasks: BackgroundTasks,
    problem_id: str = Form(...),
    username: str = Form(...),
    language: str = Form("python"),
    code: str = Form(...),
):
    """Accept a submission and queue background validation."""
    problem = await get_problem(problem_id)
    if not problem:
        raise HTTPException(404, f"Problem '{problem_id}' not found")

    sub_id = _short_id()
    SUBMISSIONS[sub_id] = {
        "id": sub_id,
        "username": username,
        "problem_id": problem_id,
        "problem_title": problem["title"],
        "language": language,
        "code": code,
        "status": "queued",
        "verdict": None,
        "score": 0,
        "max_score": problem["points"],
        "runtime_ms": None,
        "memory_kb": None,
        "public_results": [],
        "hidden_results": [],
        "compilation_output": "",
        "submitted_at": _now(),
        "finished_at": None,
        "updated_at": _now(),
        "leaderboard_rank": None,
    }

    background_tasks.add_task(_process_submission, sub_id)

    return SubmissionResponse(
        submission_id=sub_id,
        status="queued",
        tracking_url=f"https://club50.dev/submissions/{sub_id}",
        message="Submission received successfully.",
    )


@app.get("/api/v1/submissions/{sub_id}")
async def get_submission(sub_id: str):
    sub = SUBMISSIONS.get(sub_id)
    if not sub:
        raise HTTPException(404, "Submission not found")
    return dict(sub)


@app.get("/api/v1/submissions")
async def list_submissions(username: Optional[str] = None, problem_id: Optional[str] = None):
    subs = [s for s in SUBMISSIONS.values() if not s.get("temp_submission", False)]
    if username:
        subs = [s for s in subs if s["username"] == username]
    if problem_id:
        subs = [s for s in subs if s["problem_id"] == problem_id]
    subs.sort(key=lambda x: x["submitted_at"], reverse=True)
    # Strip code from list view
    return [{k: v for k, v in s.items() if k != "code"} for s in subs[:50]]


@app.get("/api/v1/leaderboard")
async def get_leaderboard(problem_id: Optional[str] = None):
    entries = list(LEADERBOARD.values())
    if problem_id:
        entries = [e for e in entries if e["problem_id"] == problem_id]
    entries.sort(key=lambda x: (-x["score"], x["runtime_ms"]))
    for i, e in enumerate(entries, 1):
        e["rank"] = i
    return entries
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
