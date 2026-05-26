# Supabase Schema & Data Guide

## Backend Contract

- `POST /api/v1/check` reads the problem and public test cases from Supabase, then returns immediate feedback. It does not insert a submission row.
- `POST /api/v1/submissions` reads the problem plus public and hidden test cases from Supabase, evaluates the code, and inserts the final result into `submissions`.
- AI-generated problems must include `time_limit`, `memory_limit`, `public_tests`, and `hidden_tests`. The backend saves limits on `problems` and test cases in `problem_schemas.schema_data`.
- Problem limits should vary by difficulty and by problem. Defaults are Easy `1s/128MB`, Medium `2s/256MB`, Hard `3s/512MB`.
- For new Supabase projects, public schema tables may need explicit Data API grants in addition to RLS policies before REST calls can access them.

## Tables Overview

### 1. `problems` Table
Stores problem definitions with time/memory constraints.

**Columns:**
```sql
id (INT PRIMARY KEY)              -- Problem identifier
slug (VARCHAR UNIQUE)             -- URL-friendly name
title (VARCHAR)                   -- Problem title
description (TEXT)                -- Problem statement
difficulty (VARCHAR)              -- easy | medium | hard
points (INT)                      -- Points for solving
time_limit (INT)                  -- Seconds per test case
memory_limit (INT)                -- MB per test case
check_slug (VARCHAR)              -- Legacy check50 slug
sample_inputs (JSON)              -- Array of sample inputs
sample_outputs (JSON)             -- Array of sample outputs
hints (JSON)                       -- Array of hints
tags (JSON)                        -- Array of tags
is_active (BOOLEAN)               -- Whether problem is available
created_at (TIMESTAMP)
updated_at (TIMESTAMP)
```

These two columns are required for evaluation. The backend sends `time_limit * 1000` as the per-test runtime limit and stores `memory_limit` in every evaluation report.

**Example Row:**
```json
{
  "id": 1,
  "slug": "two-sum",
  "title": "Two Sum",
  "description": "Given an array of integers nums and an integer target...",
  "difficulty": "easy",
  "points": 100,
  "time_limit": 1,
  "memory_limit": 256,
  "check_slug": "github.com/club50/checks/problems/two_sum",
  "sample_inputs": ["[2,7,11,15], target=9", "[3,2,4], target=6"],
  "sample_outputs": ["[0,1]", "[1,2]"],
  "hints": ["Use a hash map for O(1) lookup"],
  "tags": ["array", "hash-table"],
  "is_active": true
}
```

---

### 2. `problem_templates` Table
Code templates for each language.

**Columns:**
```sql
id (INT PRIMARY KEY)
problem_id (INT FOREIGN KEY → problems.id)
language (VARCHAR)                -- java | c
starter_code (TEXT)               -- Template code with TODO comments
solution_code (TEXT)              -- Reference solution (optional)
created_at (TIMESTAMP)
```

**Example Rows:**
```json
{
  "id": 1,
  "problem_id": 1,
  "language": "java",
  "starter_code": "public class Solution {\n    public int[] twoSum(int[] nums, int target) {\n        // TODO: Implement solution\n        return new int[2];\n    }\n}"
},
{
  "id": 2,
  "problem_id": 1,
  "language": "c",
  "starter_code": "#include <stdlib.h>\n\nint* twoSum(int* nums, int numsSize, int target, int* returnSize) {\n    // TODO: Implement solution\n    *returnSize = 2;\n    return NULL;\n}"
}
```

---

### 3. `problem_schemas` Table
**MOST IMPORTANT FOR EVALUATION**
Contains all test cases for a problem in a specific language.

**Columns:**
```sql
id (INT PRIMARY KEY)
problem_id (INT FOREIGN KEY → problems.id)
language (VARCHAR)                -- java | c
schema_data (JSON)                -- Test cases array
created_at (TIMESTAMP)
updated_at (TIMESTAMP)
```

**schema_data Format:**
```json
{
  "tests": [
    {
      "id": 1,
      "name": "sample_1",
      "input": "nums = [2,7,11,15], target = 9",
      "expected": "[0,1]",
      "expected_output": "[0,1]",
      "explanation": "nums[0] + nums[1] = 2 + 7 = 9",
      "is_hidden": false
    },
    {
      "id": 2,
      "name": "hidden_1",
      "input": "nums = [3,2,4], target = 6",
      "expected": "[1,2]",
      "expected_output": "[1,2]",
      "explanation": "nums[1] + nums[2] = 2 + 4 = 6",
      "is_hidden": true
    }
  ]
}
```

**Key Fields:**
- `id` - Test case number (1-indexed)
- `input` - Raw input string (exactly as sent to stdin)
- `expected` - Expected output (exact string match, whitespace stripped)
- `expected_output` - Same value as `expected`, kept for frontend/evaluator compatibility
- `explanation` - Why this test case exists
- `is_hidden` - true for hidden tests, false for public tests

`check` uses only tests where `is_hidden` is false. `submit` uses all tests.

---

### 4. `submissions` Table
Stores all user code submissions with evaluation results.

**Columns:**
```sql
-- Identifiers
id (INT PRIMARY KEY)
user_id (INT FOREIGN KEY → users.id)
problem_id (INT FOREIGN KEY → problems.id)

-- Code
language (VARCHAR)                -- java | c
code (TEXT)                        -- Full source code

-- Evaluation Status
status (VARCHAR)                   -- queued | running | accepted | wrong_answer | compilation_error | runtime_error | time_limit_exceeded | memory_limit_exceeded | system_error
verdict (VARCHAR)                  -- "Accepted" | "Wrong Answer" | etc.

-- NEW: Piston Evaluator Fields
evaluation_report (JSON)           -- Full report from evaluator
compile_error (TEXT)               -- Compilation error message
runtime_error (TEXT)               -- Runtime error message
time_complexity (VARCHAR)          -- O(n), O(n²), etc.
space_complexity (VARCHAR)         -- O(1), O(n), etc.
code_issues (JSON)                 -- Array of detected issues
optimization_suggestions (JSON)    -- Array of suggestions

-- EXISTING: Test Statistics
public_test_passed (INT)           -- Number of public tests passed
public_test_total (INT)            -- Total number of public tests
hidden_test_passed (INT)           -- Number of hidden tests passed
hidden_test_total (INT)            -- Total number of hidden tests

-- Performance
runtime_ms (INT)                   -- Average runtime in milliseconds
memory_mb (INT)                    -- Peak memory in megabytes
error_message (TEXT)               -- General error message (legacy)

-- DEPRECATED: Old check50 format (kept for backward compatibility)
check50_output (JSON)              -- Old check50 format

-- Timestamps
created_at (TIMESTAMP)             -- When submitted
submitted_at (TIMESTAMP)           -- When evaluated started
completed_at (TIMESTAMP)           -- When evaluation completed
```

**Example Row:**
```json
{
  "id": 42,
  "user_id": 1,
  "problem_id": 1,
  "language": "java",
  "code": "public class Solution { public int[] twoSum(int[] nums, int target) { ... } }",
  "status": "accepted",
  "verdict": "Accepted",
  "evaluation_report": {
    "problem": "Two Sum",
    "language": "java",
    "verdict": "Accepted",
    "passed_tests": 10,
    "total_tests": 10,
    "success_rate": "100%",
    "compile_error": null,
    "runtime_error": null,
    "failed_testcase": null,
    "execution": {
      "avg_runtime_ms": 12.5,
      "max_runtime_ms": 15,
      "max_memory_kb": 2048
    },
    "complexity": {
      "time": "O(n)",
      "space": "O(1)"
    },
    "analysis": [
      "Clean and efficient implementation",
      "Proper use of HashMap"
    ],
    "optimization_suggestions": [
      "Already well optimized"
    ]
  },
  "compile_error": null,
  "runtime_error": null,
  "time_complexity": "O(n)",
  "space_complexity": "O(1)",
  "code_issues": [],
  "optimization_suggestions": ["Already optimized"],
  "public_test_passed": 5,
  "public_test_total": 5,
  "hidden_test_passed": 5,
  "hidden_test_total": 5,
  "runtime_ms": 12,
  "memory_mb": 2,
  "check50_output": null,
  "created_at": "2025-05-26T10:30:00Z",
  "submitted_at": "2025-05-26T10:30:01Z",
  "completed_at": "2025-05-26T10:30:05Z"
}
```

---

### 5. `users` Table
User accounts.

**Columns:**
```sql
id (INT PRIMARY KEY)
username (VARCHAR UNIQUE)
email (VARCHAR UNIQUE)
full_name (VARCHAR)
hashed_password (VARCHAR)
is_active (BOOLEAN)
is_admin (BOOLEAN)
created_at (TIMESTAMP)
updated_at (TIMESTAMP)
```

---

### 6. `user_profiles` Table
User profile and statistics.

**Columns:**
```sql
id (INT PRIMARY KEY)
user_id (INT UNIQUE FOREIGN KEY → users.id)
bio (TEXT)
github_username (VARCHAR)
country (VARCHAR)
avatar_url (VARCHAR)
accepted_problems (INT)           -- Count of problems solved
total_submissions (INT)            -- Count of all submissions
```

---

### 7. `leaderboards` Table
User rankings.

**Columns:**
```sql
id (INT PRIMARY KEY)
user_id (INT UNIQUE FOREIGN KEY → users.id)
accepted_count (INT)              -- Problems solved
submission_count (INT)            -- Total submissions
total_runtime_ms (INT)            -- Sum of all runtimes
rank (INT)                        -- Leaderboard position
last_accepted_at (TIMESTAMP)
updated_at (TIMESTAMP)
```

---

### 8. `execution_logs` Table (Optional)
Detailed execution logs for debugging.

**Columns:**
```sql
id (INT PRIMARY KEY)
submission_id (INT FOREIGN KEY → submissions.id)
stage (VARCHAR)                   -- compilation | execution | validation
output (TEXT)
error (TEXT)
created_at (TIMESTAMP)
```

---

## Data Query Examples

### Find a Problem
```sql
SELECT * FROM problems WHERE slug = 'two-sum';
```

### Get Test Cases for a Problem
```sql
SELECT schema_data FROM problem_schemas 
WHERE problem_id = 1 AND language = 'java';
```

### Get User's Submissions
```sql
SELECT id, verdict, status, public_test_passed, public_test_total, runtime_ms, created_at
FROM submissions
WHERE user_id = 1
ORDER BY created_at DESC
LIMIT 20;
```

### Get Accepted Submissions Only
```sql
SELECT COUNT(*) as accepted_count
FROM submissions
WHERE user_id = 1 AND verdict = 'Accepted';
```

### Get Failed Submission with Details
```sql
SELECT code, evaluation_report, compile_error, runtime_error
FROM submissions
WHERE id = 42;
```

### Extract Specific Data from evaluation_report
```sql
SELECT 
  id,
  verdict,
  evaluation_report->>'success_rate' as success_rate,
  evaluation_report->'complexity'->>'time' as time_complexity,
  evaluation_report->>'analysis' as issues
FROM submissions
WHERE user_id = 1;
```

---

## When Data is Saved

### Submit Flow Timeline
```
t=0: User clicks SUBMIT
     → POST /submissions/
     → Submission created (status=QUEUED)
     → ID returned to frontend

t=0.1s: Background task starts
        → Status updated to RUNNING

t=0.5-3s: Evaluator runs tests
          → Piston executes code
          → Results collected

t=3-5s: Analysis phase
        → CodeAnalyzer runs
        → Report generated

t=5s: Results saved
      → evaluation_report saved
      → verdict saved
      → time/space_complexity saved
      → code_issues saved
      → optimization_suggestions saved
      → public_test_passed/total saved
      → hidden_test_passed/total saved
      → runtime_ms, memory_mb saved
      → Status updated to ACCEPTED|WRONG_ANSWER|etc.
      → completed_at timestamp set

t=5-10s: Frontend polls GET /submissions/{id}
         → Returns updated submission with all data
```

### Run Flow Timeline
```
t=0: User clicks RUN
     → POST /submissions/run
     
t=0.1-3s: Evaluator runs PUBLIC tests only
          → Piston executes code
          → Results collected
          
t=3-5s: Analysis phase
        → CodeAnalyzer runs
        → Report generated
        
t=5s: Response sent (NO DATABASE SAVE)
      → verdict returned
      → passed_tests returned
      → failed_testcase returned
      → analysis returned
```

---

## Important Notes

### Test Case Input/Output Format

**Input Format:** Exactly as shown in schema
```
nums = [2,7,11,15], target = 9
```

**Output Format:** Exact string match (after stripping whitespace)
```
[0,1]
```

### Public vs Hidden Tests

- **Public tests** (`is_hidden=false`):
  - Shown to user in "Run" button
  - User can debug with these
  - Run limit: unlimited
  
- **Hidden tests** (`is_hidden=true`):
  - Only run on "Submit"
  - User doesn't see input/output
  - Used for final grading

### Verdict Mapping

| Verdict | Description | Save to DB |
|---------|-------------|-----------|
| Accepted | All tests passed | ✅ Yes |
| Wrong Answer | Output mismatch | ✅ Yes |
| Runtime Error | Code crashed | ✅ Yes |
| Compilation Error | Failed to compile | ✅ Yes |
| Time Limit Exceeded | Execution too slow | ✅ Yes |
| Memory Limit Exceeded | Used too much memory | ✅ Yes |
| Security Violation | Malicious code detected | ✅ Yes |

---

## Schema Diagram

```
users
  ├─→ user_profiles
  ├─→ submissions
  │    ├─→ problems
  │    │    ├─→ problem_templates (language → code)
  │    │    └─→ problem_schemas (language → test cases)
  │    └─→ execution_logs
  └─→ leaderboards
```

---

## Migration Checklist

Before deploying the new evaluator:

- [ ] Backup existing `submissions` table
- [ ] Add new columns to `submissions` table
- [ ] Verify `problem_schemas` table exists with test data
- [ ] Test Piston API connectivity
- [ ] Verify `problem_templates` table has starter code for both languages
- [ ] Update frontend to use new endpoints
- [ ] Test full submission flow (Submit → polling → view)
- [ ] Test quick check flow (Run → immediate response)
- [ ] Monitor first few submissions for errors

---

## Troubleshooting

### Submission stuck in "QUEUED"
- Check background task queue
- Verify Piston API is accessible
- Check server logs for exceptions

### Wrong Answer when expected Accepted
- Check test case formatting (whitespace)
- Verify expected output exact match
- Check if output normalization is needed

### Compilation Error
- Check code syntax
- Verify language version (Java 11, C11)
- Check included headers

### Slow Evaluations
- Monitor Piston API response time
- Check if multiple submissions running simultaneously
- Consider test case optimization

---

## Performance Optimization Tips

1. **Test Case Optimization**
   - Keep public tests small (< 1KB input)
   - Use hidden tests for edge cases

2. **Piston API**
   - Reuse client connection
   - Consider caching compiled code (future feature)

3. **Database**
   - Index on `user_id` and `problem_id` for submissions
   - Use pagination for listing (LIMIT + OFFSET)

4. **Analysis**
   - CodeAnalyzer is lightweight (< 10ms)
   - Consider caching complexity analysis results
