# How to Push Changes to GitHub and Test CI

## Quick Steps

### 1. Check Your Current Branch
```powershell
git branch --show-current
```

You should be on `test-ci-pipeline` branch (based on your earlier git status).

### 2. Stage Your Changes
```powershell
# Stage all modified files
git add .

# OR stage specific files
git add online_exam_fastapi/app/main.py
git add online_exam_fastapi/app/routers/exams.py
```

### 3. Commit Your Changes
```powershell
git commit -m "fix: Fix flake8 linting errors

- Move pathlib import to top of file in main.py
- Remove unused sqlalchemy imports from exams.py
- Remove duplicate json import from exams.py
- Fix bare except clause in exams.py"
```

### 4. Push to GitHub
```powershell
# Push to your current branch (test-ci-pipeline)
git push origin test-ci-pipeline

# OR if this is the first push for this branch
git push -u origin test-ci-pipeline
```

### 5. Check CI Status on GitHub
1. Go to your GitHub repository: `https://github.com/SamanthaChoo/G1_online-exam-grading-system`
2. Click on the **"Actions"** tab
3. You'll see your latest workflow run
4. Click on it to see detailed results
5. Or go to your Pull Request and check the **"Checks"** tab

## What to Expect

### ✅ CI Should Pass If:
- ✅ Flake8 passes (you fixed these!)
- ✅ Black formatting check passes
- ✅ Pytest tests pass
- ✅ Build verification passes

### ⚠️ Non-Blocking (Won't Fail CI):
- MyPy type errors (informational only)
- Safety warnings (informational only)
- Bandit warnings (informational only)

## If CI Fails

### Check the Error Messages
1. Click on the failed job in GitHub Actions
2. Expand the failed step to see error details
3. Fix the issues locally
4. Commit and push again

### Common Issues:
- **Black formatting errors**: Run `.\format-code.bat` to auto-fix
- **Flake8 errors**: Run `python -m flake8 online_exam_fastapi/app --config .flake8` to see issues
- **Test failures**: Run `cd online_exam_fastapi && pytest -v` to see which tests failed

## Alternative: Create a New Commit on Existing PR

If you already have a PR open:
```powershell
# Make sure you're on the right branch
git checkout test-ci-pipeline

# Stage and commit your fixes
git add .
git commit -m "fix: Fix flake8 linting errors"

# Push (this will update your existing PR)
git push origin test-ci-pipeline
```

The PR will automatically update and CI will re-run!

## Verify Locally Before Pushing (Recommended)

Run these checks first to catch issues early:

```powershell
# From project root
cd C:\Users\pylai\Downloads\G1_online-exam-grading-system

# 1. Format check
python -m black --check online_exam_fastapi/app --line-length 120

# 2. Linting (most important!)
python -m flake8 online_exam_fastapi/app --config .flake8

# 3. Tests
cd online_exam_fastapi
pytest -v
```

If all three pass locally, CI should pass too! ✅
