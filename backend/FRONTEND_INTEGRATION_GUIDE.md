# Frontend Integration Guide - New Evaluator

## Overview
This guide explains how the frontend should interact with the new Piston-based evaluator system.

---

## Button Actions

### 1. "RUN" Button
**Purpose:** Quick check against public test cases only

**Flow:**
```
User clicks RUN
  ↓
Call: POST /api/submissions/run {problem_id, language, code}
  ↓
[Wait 1-5 seconds for response]
  ↓
Display:
  - Verdict (Accepted, Wrong Answer, etc.)
  - Passed tests: X/Y
  - Success rate: Z%
  - Failed test case (if any)
  - Code issues (if any)
  - Optimization suggestions (if any)
```

**Request:**
```javascript
const response = await fetch('/api/submissions/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    problem_id: 1,
    language: 'java',
    code: '...'  // Full source code
  })
});

const data = await response.json();
```

**Response:**
```json
{
  "success": true,
  "verdict": "Wrong Answer",
  "passed_tests": 2,
  "total_tests": 3,
  "success_rate": "66.7%",
  "failed_testcase": {
    "input": "nums = [1,2,3]",
    "expected": "[0,1,2]",
    "got": "[0,1]"
  },
  "execution": {
    "avg_runtime_ms": 8.5,
    "max_memory_kb": 1024
  },
  "analysis": [
    "Handles small arrays",
    "Fails on larger inputs"
  ]
}
```

**Display Logic:**
```javascript
if (data.verdict === "Accepted") {
  // Show green checkmark
  // Show all tests passed
} else if (data.verdict === "Wrong Answer") {
  // Show failed test case
  // Highlight input, expected, got
} else if (data.verdict === "Runtime Error") {
  // Show error message
  // Suggest debugging
} else if (data.verdict === "Compilation Error") {
  // Show compiler error
  // Suggest syntax fix
} else if (data.verdict === "Time Limit Exceeded") {
  // Show TLE message
  // Suggest optimization
}

// Always show analysis and suggestions
displayAnalysis(data.analysis);
displaySuggestions(data.optimization_suggestions);
```

---

### 2. "SUBMIT" Button
**Purpose:** Full evaluation against all tests (public + hidden)

**Flow:**
```
User clicks SUBMIT
  ↓
Call: POST /api/submissions/ {problem_id, language, code}
  ↓
[Wait ~1 second for response]
  ↓
Get submission_id back (status=QUEUED)
  ↓
Start polling GET /api/submissions/{id}
  ↓
Poll every 1-2 seconds until status != QUEUED
  ↓
When complete, display full results
```

**Request:**
```javascript
const submitResponse = await fetch('/api/submissions/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    problem_id: 1,
    language: 'java',
    code: '...'
  })
});

const submission = await submitResponse.json();
const submissionId = submission.id;
```

**Response (Immediate):**
```json
{
  "id": 42,
  "status": "queued",
  "message": "Submission queued for evaluation"
}
```

**Polling:**
```javascript
const pollInterval = setInterval(async () => {
  const viewResponse = await fetch(`/api/submissions/${submissionId}`);
  const data = await viewResponse.json();
  
  if (data.status !== 'queued') {
    clearInterval(pollInterval);
    displayFinalResults(data);
  } else {
    // Still evaluating, show spinner
  }
}, 2000);  // Poll every 2 seconds
```

**Response (When Complete):**
```json
{
  "id": 42,
  "status": "accepted",
  "verdict": "Accepted",
  "public_test_passed": 5,
  "public_test_total": 5,
  "hidden_test_passed": 5,
  "hidden_test_total": 5,
  "runtime_ms": 12,
  "memory_mb": 2,
  "time_complexity": "O(n)",
  "space_complexity": "O(1)",
  "code_issues": [],
  "optimization_suggestions": [],
  "evaluation_report": { ... },
  "created_at": "2025-05-26T10:30:00Z",
  "completed_at": "2025-05-26T10:30:05Z"
}
```

**Display Logic:**
```javascript
function displayFinalResults(submission) {
  // Show verdict with visual indicator
  showVerdict(submission.verdict);
  
  // Show test statistics
  showStats(
    submission.public_test_passed,
    submission.public_test_total,
    submission.hidden_test_passed,
    submission.hidden_test_total
  );
  
  // Show performance metrics
  showMetrics(submission.runtime_ms, submission.memory_mb);
  
  // Show complexity analysis
  showComplexity(submission.time_complexity, submission.space_complexity);
  
  // Show code analysis
  if (submission.code_issues.length > 0) {
    showIssues(submission.code_issues);
  }
  
  // Show suggestions
  if (submission.optimization_suggestions.length > 0) {
    showSuggestions(submission.optimization_suggestions);
  }
  
  // For debugging - show full report
  if (DEVELOPMENT_MODE) {
    showFullReport(submission.evaluation_report);
  }
}
```

---

### 3. "SUBMIT" → Display Results

**When Accepted:**
```
✅ Accepted
All tests passed!

Test Statistics:
- Public Tests: 5/5 ✓
- Hidden Tests: 5/5 ✓

Performance:
- Runtime: 12 ms
- Memory: 2 MB

Complexity Analysis:
- Time: O(n)
- Space: O(1)

Great job! Optimal solution.
```

**When Wrong Answer:**
```
❌ Wrong Answer
Some tests failed.

Test Statistics:
- Public Tests: 2/5 ✗
- Hidden Tests: 0/5 ✗

Failed Test Case:
Input:  nums = [1,2,3], target = 5
Expected: [1,2]
Got:     [0,1]

Issues Detected:
- Off-by-one error
- Doesn't handle all cases

Suggestions:
- Check boundary conditions
- Test with different inputs
```

**When Runtime Error:**
```
💥 Runtime Error
Code crashed during execution.

Error Message:
java.lang.ArrayIndexOutOfBoundsException at line 15

Issues Detected:
- Potential null pointer
- Missing bounds check

Suggestions:
- Verify array access
- Add null checks
```

**When Compilation Error:**
```
🔴 Compilation Error
Code didn't compile.

Compiler Error:
error: ';' expected
    public int solve(int[] nums
           ^

Suggestions:
- Check syntax
- Verify imports
```

**When Time Limit Exceeded:**
```
⏱️ Time Limit Exceeded
Code ran too slow.

Performance:
- Timeout after 3000 ms
- Passed: 1/5 tests

Time Complexity: O(n²)

Suggestions:
- Use HashMap for O(1) lookups
- Consider binary search
- Optimize nested loops
```

---

## Viewing Submission History

### "SUBMISSIONS" Tab

**Request:**
```javascript
const response = await fetch(`/api/submissions?problem_id=${problemId}&limit=20`);
const data = await response.json();
```

**Response:**
```json
{
  "submissions": [
    {
      "id": 42,
      "problem_id": 1,
      "language": "java",
      "status": "accepted",
      "verdict": "Accepted",
      "public_test_passed": 5,
      "public_test_total": 5,
      "runtime_ms": 12,
      "created_at": "2025-05-26T10:30:00Z",
      "completed_at": "2025-05-26T10:30:05Z"
    },
    {
      "id": 41,
      "problem_id": 1,
      "language": "java",
      "status": "wrong_answer",
      "verdict": "Wrong Answer",
      "public_test_passed": 2,
      "public_test_total": 5,
      "runtime_ms": 8,
      "created_at": "2025-05-26T10:25:00Z",
      "completed_at": "2025-05-26T10:25:05Z"
    }
  ],
  "count": 2
}
```

**Display as Table:**
```
Submission # | Language | Verdict      | Tests  | Runtime | Date/Time
42          | Java     | ✅ Accepted  | 5/5    | 12 ms   | 10:30:00
41          | Java     | ❌ Wrong Ans | 2/5    | 8 ms    | 10:25:00
```

### Click to View Details

**Request:**
```javascript
const response = await fetch(`/api/submissions/${submissionId}`);
const submission = await response.json();
```

**Display:**
- Full source code (editable or read-only)
- All test statistics
- Verdict and analysis
- Full evaluation report
- Option to resubmit code

---

## UI Components Needed

### 1. Code Editor
- Syntax highlighting (Java, C)
- Line numbers
- Auto-indent
- Keyboard shortcuts

### 2. Run/Submit Buttons
```
[RUN] [SUBMIT] [RESET]
```
- RUN: Show green when hovered
- SUBMIT: Show blue when hovered
- Show spinner while executing

### 3. Output Panel
- Display verdict with color coding
- Show test case details if failed
- Show analysis and suggestions
- Collapsible sections

### 4. Verdict Badge
```
Color coding:
- Accepted: Green ✅
- Wrong Answer: Red ❌
- Runtime Error: Purple 💥
- Compilation Error: Dark Red 🔴
- Time Limit Exceeded: Orange ⏱️
- Memory Limit Exceeded: Brown 💾
```

### 5. Statistics Panel
```
Tests: 5/5 ✓
Time Complexity: O(n)
Space Complexity: O(1)
Runtime: 12 ms
Memory: 2 MB
```

### 6. Issues & Suggestions Panel
```
Issues Detected:
- String concatenation in loop

Optimization Suggestions:
- Use StringBuilder for strings
- Consider HashMap for faster lookups
```

---

## Error Handling

### Network Error
```javascript
try {
  const response = await fetch('/api/submissions/run', {...});
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = await response.json();
} catch (error) {
  showError('Network error. Please try again.');
  console.error(error);
}
```

### Language Not Supported
```json
{
  "detail": "Unsupported language. Only 'c' and 'java' are supported."
}
```

**Display:**
```
Error: Only C and Java are supported.
Please select a different language.
```

### Problem Not Found
```json
{
  "detail": "Problem not found"
}
```

### Test Cases Not Configured
```json
{
  "detail": "No test cases configured for java"
}
```

**Display:**
```
Error: This problem doesn't have test cases configured yet.
Please contact an instructor.
```

### Timeout
```
The submission is taking longer than expected.
Please wait... (spinner)
```

---

## Performance Optimization

### Debounce Run Button
```javascript
let runTimeout;
runButton.addEventListener('click', () => {
  clearTimeout(runTimeout);
  runTimeout = setTimeout(() => {
    performRun();
  }, 300);  // Wait 300ms before executing
});
```

### Limit Polling Frequency
```javascript
const pollInterval = setInterval(() => {
  // Poll every 2 seconds, max 30 seconds
  if (elapsed > 30000) {
    clearInterval(pollInterval);
    showError('Submission taking too long');
  }
}, 2000);
```

### Cache Recent Results
```javascript
const submissionCache = {};

function cacheSubmission(id, data) {
  submissionCache[id] = data;
}

function getCachedSubmission(id) {
  return submissionCache[id] || null;
}
```

### Preload Problem Templates
```javascript
// Load problem template when problem loads
async function loadProblem(problemId) {
  const problem = await fetch(`/api/problems/${problemId}`);
  const data = await problem.json();
  
  // Preload code template for selected language
  codeEditor.setValue(data.templates[selectedLanguage].starter_code);
}
```

---

## Code Examples

### Complete Run Implementation
```javascript
async function handleRunClick() {
  const code = codeEditor.getValue();
  const language = languageSelect.value;
  const problemId = getCurrentProblemId();
  
  if (!code.trim()) {
    showError('Please write some code first');
    return;
  }
  
  showSpinner('Running tests...');
  
  try {
    const response = await fetch('/api/submissions/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem_id: problemId, language, code })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    const result = await response.json();
    displayRunResults(result);
  } catch (error) {
    showError(`Error: ${error.message}`);
  } finally {
    hideSpinner();
  }
}

function displayRunResults(result) {
  if (result.success === false) {
    showError(result.error);
    return;
  }
  
  const verdictColor = {
    'Accepted': 'green',
    'Wrong Answer': 'red',
    'Runtime Error': 'purple',
    'Compilation Error': 'darkred',
    'Time Limit Exceeded': 'orange'
  }[result.verdict] || 'gray';
  
  resultPanel.innerHTML = `
    <div class="verdict" style="color: ${verdictColor}">
      ${result.verdict}
    </div>
    <div class="stats">
      Tests: ${result.passed_tests}/${result.total_tests}
      Success: ${result.success_rate}
    </div>
    ${result.failed_testcase ? `
      <div class="failed-test">
        <h4>Failed Test Case:</h4>
        <pre>Input: ${result.failed_testcase.input}</pre>
        <pre>Expected: ${result.failed_testcase.expected}</pre>
        <pre>Got: ${result.failed_testcase.got}</pre>
      </div>
    ` : ''}
    ${result.analysis.length > 0 ? `
      <div class="analysis">
        <h4>Analysis:</h4>
        <ul>${result.analysis.map(a => `<li>${a}</li>`).join('')}</ul>
      </div>
    ` : ''}
  `;
}
```

### Complete Submit Implementation
```javascript
async function handleSubmitClick() {
  const code = codeEditor.getValue();
  const language = languageSelect.value;
  const problemId = getCurrentProblemId();
  
  if (!code.trim()) {
    showError('Please write some code first');
    return;
  }
  
  if (!confirm('Are you sure you want to submit?')) {
    return;
  }
  
  showSpinner('Submitting...');
  
  try {
    // Create submission
    const submitResponse = await fetch('/api/submissions/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem_id: problemId, language, code })
    });
    
    if (!submitResponse.ok) {
      throw new Error('Failed to create submission');
    }
    
    const submission = await submitResponse.json();
    const submissionId = submission.id;
    
    hideSpinner();
    showSpinner('Evaluating submission...');
    
    // Poll for results
    await pollSubmission(submissionId);
  } catch (error) {
    showError(`Error: ${error.message}`);
  } finally {
    hideSpinner();
  }
}

async function pollSubmission(submissionId) {
  return new Promise((resolve, reject) => {
    const maxAttempts = 30;
    let attempts = 0;
    
    const interval = setInterval(async () => {
      attempts++;
      
      try {
        const response = await fetch(`/api/submissions/${submissionId}`);
        if (!response.ok) throw new Error('Failed to fetch submission');
        
        const submission = await response.json();
        
        if (submission.status !== 'queued') {
          clearInterval(interval);
          displaySubmitResults(submission);
          resolve();
        }
        
        if (attempts >= maxAttempts) {
          clearInterval(interval);
          reject(new Error('Evaluation timed out'));
        }
      } catch (error) {
        clearInterval(interval);
        reject(error);
      }
    }, 2000);  // Poll every 2 seconds
  });
}

function displaySubmitResults(submission) {
  const verdictColor = getVerdictColor(submission.verdict);
  
  resultPanel.innerHTML = `
    <div class="verdict" style="color: ${verdictColor}">
      ${submission.verdict}
    </div>
    <div class="stats">
      <div>Public Tests: ${submission.public_test_passed}/${submission.public_test_total}</div>
      <div>Hidden Tests: ${submission.hidden_test_passed}/${submission.hidden_test_total}</div>
      <div>Runtime: ${submission.runtime_ms} ms</div>
      <div>Memory: ${submission.memory_mb} MB</div>
      <div>Time Complexity: ${submission.time_complexity}</div>
      <div>Space Complexity: ${submission.space_complexity}</div>
    </div>
    ${submission.code_issues?.length > 0 ? `
      <div class="issues">
        <h4>Issues Found:</h4>
        <ul>${submission.code_issues.map(i => `<li>${i}</li>`).join('')}</ul>
      </div>
    ` : ''}
    ${submission.optimization_suggestions?.length > 0 ? `
      <div class="suggestions">
        <h4>Suggestions:</h4>
        <ul>${submission.optimization_suggestions.map(s => `<li>${s}</li>`).join('')}</ul>
      </div>
    ` : ''}
  `;
  
  // Update user profile if accepted
  if (submission.verdict === 'Accepted') {
    showSuccess('Congratulations! Problem solved!');
    updateLeaderboard();
  }
}
```

---

## Testing Checklist

- [ ] Run button shows immediate feedback
- [ ] Submit button queues and polls correctly
- [ ] Failed test case displayed properly
- [ ] Compilation errors shown clearly
- [ ] Runtime errors explained
- [ ] Code issues detected and displayed
- [ ] Optimization suggestions helpful
- [ ] Submission history loads correctly
- [ ] Clicking submission shows full details
- [ ] Error messages are helpful
- [ ] Network timeouts handled gracefully
- [ ] Language validation works (C/Java only)
