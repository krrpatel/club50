# Base44 / CodeForge Frontend Prompt

Update the Club50 frontend to match the latest FastAPI backend in `D:\club50new\backend\main.py`.

Base API URL:
- Local: `http://localhost:8000`
- Production: use an environment variable such as `VITE_API_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL`, or the equivalent Base44 project setting.

Important integration rules:
- Active routes use `/api/v1`.
- Do not use the older `/api/submissions/run` contract.
- Store the `token` returned by login/signup and send it as `Authorization: Bearer <token>` for authenticated/admin endpoints.
- The frontend should call the backend API, not read Supabase tables directly.
- Hidden tests live in Supabase `problem_schemas`; never expose hidden input/output in the UI.
- `POST /api/v1/check` is the Run button and uses JSON.
- `POST /api/v1/submissions` is the Submit button and uses `multipart/form-data`.

## Health And Config

`GET /`

Returns:
```json
{ "service": "club50", "version": "1.0.0", "status": "operational" }
```

`GET /health`

Returns:
```json
{ "status": "healthy", "timestamp": "ISO timestamp" }
```

`GET /api/v1/config/status`

Returns:
```json
{
  "supabase_url_configured": true,
  "supabase_anon_key_configured": true,
  "supabase_service_role_key_configured": true,
  "ai_provider": "openai|gemini|null",
  "ai_api_key_configured": true,
  "ai_model": "gpt-4.1-mini"
}
```

## Auth

`GET /api/v1/auth/enrollment/{enrollment_number}`

Use before signup to prefill student data.

`POST /api/v1/auth/signup`

JSON:
```json
{
  "enrollment_number": "string",
  "password": "min 8 chars",
  "email": "optional",
  "first_name": "optional",
  "last_name": "optional",
  "current_semester": 1,
  "academic_year": "optional"
}
```

If approval is required, response has `token: null` and a message. Show a pending approval screen.

`POST /api/v1/auth/login`

JSON:
```json
{
  "enrollment_number": "string",
  "password": "string"
}
```

Response:
```json
{
  "token": "jwt",
  "refresh_token": "jwt",
  "user": {
    "id": "uuid",
    "enrollment_number": "string",
    "full_name": "string",
    "email": "string",
    "role": "student|admin",
    "current_semester": 1,
    "academic_year": "AY24-28",
    "profile_completed": true,
    "approval_status": "approved"
  }
}
```

`GET /api/v1/auth/me`

Auth required. Response:
```json
{
  "user": {},
  "progress": {
    "submissions": 0,
    "problems_solved": 0,
    "available_weeks": 0,
    "weeks_completed": 0
  }
}
```

`PUT /api/v1/auth/profile`

Auth required. JSON:
```json
{ "first_name": "optional", "last_name": "optional", "email": "optional" }
```

## Weeks

`GET /api/v1/weeks`

Auth required. Returns lightweight cards:
```json
[{ "id": "string", "title": "string" }]
```

`GET /api/v1/weeks/{week_id}`

Auth required. Returns:
```json
{
  "id": "string",
  "title": "string",
  "description": "string",
  "subject": "string",
  "topic": "string",
  "semester": 1,
  "academic_years": ["AY24-28"],
  "video_url": "string",
  "video_description": "string",
  "videos": [{ "url": "string", "title": "string" }],
  "display_order": 0,
  "problem_ids": ["1"],
  "problems": [{ "id": "1", "title": "Problem", "difficulty": "Easy", "slug": "problem" }],
  "resource_files": [],
  "generated_problems": [],
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

## Problems

`GET /api/v1/problems`

Public. Returns list:
```json
[
  {
    "id": "1",
    "slug": "two-sum",
    "title": "Two Sum",
    "description": "string",
    "difficulty": "Easy|Medium|Hard",
    "points": 100,
    "time_limit": 1,
    "memory_limit": 128,
    "tags": [],
    "sample_inputs": [],
    "sample_outputs": []
  }
]
```

`GET /api/v1/problems/{problem_id_or_slug}`

Public. Returns full problem:
```json
{
  "id": "1",
  "slug": "two-sum",
  "title": "Two Sum",
  "description": "string",
  "difficulty": "Easy",
  "points": 100,
  "time_limit": 1,
  "memory_limit": 128,
  "sample_inputs": [],
  "sample_outputs": [],
  "templates": [{ "id": 1, "language": "java", "starter_code": "..." }],
  "starter_code": { "c": "...", "java": "..." },
  "function_signature": "string",
  "input_format": "string",
  "output_format": "string",
  "constraints": [],
  "real_world_context": "string",
  "edge_cases": [],
  "hidden_test_case_ideas": [],
  "optimal_approach": "string",
  "time_complexity": "string",
  "space_complexity": "string"
}
```

`POST /api/v1/problems`

Admin required. JSON can include:
```json
{
  "title": "string",
  "slug": "optional",
  "description": "string",
  "difficulty": "Easy|Medium|Hard",
  "points": 100,
  "time_limit": 1,
  "memory_limit": 128,
  "tags": [],
  "sample_inputs": [],
  "sample_outputs": [],
  "input_format": "string",
  "output_format": "string",
  "constraints": [],
  "function_signature": "string",
  "starter_code": {
    "c": "...",
    "java": "..."
  },
  "public_tests": [
    { "input": "stdin", "expected": "stdout", "explanation": "shown test" }
  ],
  "hidden_tests": [
    { "input": "stdin", "expected": "stdout", "explanation": "hidden test" }
  ]
}
```

`PUT /api/v1/problems/{problem_id}`

Admin required. Same body as create.

`POST /api/v1/problems/{problem_id}/verify-solution`

JSON:
```json
{
  "problem_id": "same as path",
  "solution": "source code",
  "language": "c|java|python|cpp|javascript"
}
```

`POST /api/v1/problems/starter-code`

Admin required. JSON:
```json
{
  "problem_name": "string",
  "input_format": "string",
  "output_format": "string",
  "description": "optional",
  "function_signature": "optional"
}
```

Returns:
```json
{ "c": "starter code", "java": "starter code", "slug_hint": "optional" }
```

## Run Button

Call `POST /api/v1/check` with JSON.

Request:
```json
{
  "problem_id": "1",
  "code": "source code",
  "language": "c|java|python|cpp|javascript"
}
```

Response:
```json
{
  "problem_id": "1",
  "language": "java",
  "results": [
    {
      "name": "public_1",
      "input": "stdin",
      "expected_output": "stdout",
      "expected": "stdout",
      "received_output": "actual stdout",
      "got": "actual stdout",
      "output": "actual stdout",
      "passed": true,
      "error": null,
      "hint": null,
      "reason": "string",
      "is_hidden": false,
      "runtime_ms": 10,
      "memory_kb": 4096
    }
  ],
  "passed": 1,
  "total": 1,
  "compilation_output": "summary or notes",
  "submission_id": "temp id",
  "tracking_url": "https://club50.dev/submissions/temp"
}
```

UI behavior:
- Show immediate result.
- Show public failed test input, expected, got, and error.
- Do not save this as a real submission in the UI history unless the backend later changes.

## Submit Button

Call `POST /api/v1/submissions` with `FormData`, not JSON.

```ts
const form = new FormData();
form.append("problem_id", problemId);
form.append("username", user.enrollment_number);
form.append("language", language);
form.append("code", code);

const res = await fetch(`${API_BASE}/api/v1/submissions`, {
  method: "POST",
  body: form
});
const data = await res.json();
```

Response:
```json
{
  "submission_id": "string",
  "status": "accepted|wrong_answer|runtime_error|time_limit_exceeded|memory_limit_exceeded",
  "tracking_url": "https://club50.dev/submissions/id",
  "message": "Submission checked and stored successfully."
}
```

After submit, immediately fetch:

`GET /api/v1/submissions/{submission_id}`

Response:
```json
{
  "id": "string",
  "username": "user id or username",
  "problem_id": "1",
  "language": "java",
  "code": "source code",
  "status": "accepted",
  "verdict": "accepted",
  "runtime_ms": 12,
  "memory_kb": 2048,
  "memory_mb": 2,
  "public_results": [],
  "hidden_results": [],
  "evaluation_report": {
    "problem": "Problem title",
    "language": "java",
    "verdict": "accepted",
    "passed_tests": 10,
    "total_tests": 10,
    "success_rate": "100.0%",
    "compile_error": null,
    "runtime_error": null,
    "failed_testcase": null,
    "execution": {
      "avg_runtime_ms": 12,
      "max_runtime_ms": 15,
      "max_memory_kb": 2048
    },
    "limits": {
      "time_limit_seconds": 1,
      "memory_limit_mb": 128
    },
    "analysis": ["Evaluation completed."],
    "test_cases": []
  },
  "compilation_output": "string",
  "submitted_at": "timestamp",
  "finished_at": "timestamp",
  "updated_at": "timestamp"
}
```

`GET /api/v1/submissions`

Optional query params:
- `username`
- `problem_id`

Returns latest submissions without source code.

`GET /api/v1/leaderboard`

Optional query:
- `problem_id`

## Admin

`POST /api/v1/admin/weeks`

`PUT /api/v1/admin/weeks/{week_id}`

JSON:
```json
{
  "title": "string",
  "description": "string",
  "subject": "string",
  "topic": "string",
  "semester": 1,
  "academic_years": ["AY24-28"],
  "video_url": "optional",
  "video_description": "optional",
  "videos": [{ "url": "string", "title": "optional" }],
  "display_order": 0,
  "problem_ids": ["1", "2"],
  "resource_files": [],
  "generated_problems": []
}
```

`DELETE /api/v1/admin/weeks/{week_id}`

`POST /api/v1/admin/weeks/{week_id}/problems`

JSON:
```json
{ "problem_ids": ["1", "2"] }
```

`POST /api/v1/admin/uploads`

Admin required. `multipart/form-data` with field `file`.

`GET /api/v1/admin/students`

Optional query:
- `semester`
- `academic_year`

`GET /api/v1/admin/students/pending-approval`

`POST /api/v1/admin/students/{student_id}/approve`

JSON:
```json
{ "notes": "optional" }
```

`POST /api/v1/admin/students/bulk-semester`

JSON:
```json
{ "from_semester": 1, "to_semester": 2, "academic_year": "optional" }
```

`POST /api/v1/admin/problem-generation`

JSON:
```json
{
  "subject": "string",
  "semester": 1,
  "topic": "string",
  "transcript": "string",
  "difficulty": "Easy|Medium|Hard",
  "previously_generated": "optional"
}
```

`POST /api/v1/admin/suggestions`

JSON:
```json
{ "prompt": "string", "suggestion_type": "title|description|input_output|constraints|all" }
```

`POST /api/v1/videos/generate-title`

Admin required. JSON:
```json
{ "url": "video url" }
```

## UI Requirements

Build:
- Login/signup with pending approval state.
- Week list and week detail.
- Problem list and problem detail.
- Code editor with language selector.
- Run button using `/api/v1/check`.
- Submit button using `/api/v1/submissions` FormData.
- Submission detail and history.
- Admin screens for weeks, uploads, students, problem generation, starter code, suggestions, and problem create/update.

Verdict colors:
- `accepted`: green
- `wrong_answer`: red
- `compilation_error`: dark red
- `runtime_error`: purple
- `time_limit_exceeded`: orange
- `memory_limit_exceeded`: brown
- unknown/system errors: gray

Error handling:
- `401`: clear token and show login.
- `403`: show blocked/admin/pending approval state.
- `404`: show not found.
- `422`: show validation errors from FastAPI.
- Network error: show retry message.

Acceptance checks:
- Run on a problem shows public test results.
- Submit stores a submission and then shows full result.
- Hidden tests are counted but not exposed as editable data.
- Admin create/update problem saves public and hidden tests, limits, and starter code.
- Problem detail renders `starter_code.c` and `starter_code.java`.
