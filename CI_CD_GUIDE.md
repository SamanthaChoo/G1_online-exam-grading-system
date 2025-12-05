# CI/CD Setup Guide

## Overview

This project uses GitHub Actions for Continuous Integration (CI) with automated nightly builds, code quality checks, security scanning, and comprehensive testing.

## CI Pipeline Features (Option C - Comprehensive)

### 1. **Nightly Automated Builds**
- Runs automatically every night at 2:00 AM UTC
- Ensures the codebase remains bug-free
- Catches regressions early

### 2. **Code Quality Checks**
- **Flake8**: Linting and style checking
- **Black**: Code formatting verification
- **MyPy**: Type checking (informational, non-blocking)

### 3. **Security Scanning**
- **Safety**: Dependency vulnerability scanning
- **Bandit**: Code security issue detection

### 4. **Testing**
- **Pytest**: Unit and integration tests
- **Coverage**: Test coverage reporting
- Multiple Python versions (3.10, 3.11)

### 5. **Build Verification**
- Application import and initialization checks
- Ensures the app builds successfully

## Workflow Triggers

The CI pipeline runs automatically on:
- **Push** to `main`, `master`, or `kxy-dev` branches
- **Pull Requests** targeting `main`, `master`, or `kxy-dev` branches
- **Scheduled**: Every night at 2:00 AM UTC

## Acceptance Tests

Acceptance tests are organized by feature category:

### User Management (`test_acceptance_user_management.py`)
- SCRUM-97: Admin Login
- SCRUM-43: Admin Add New Lecturer
- SCRUM-7: Lecturer Login
- SCRUM-6: Student Registration
- SCRUM-95: Student Login
- SCRUM-8: Manage User Roles
- SCRUM-9: Reset Password

### Security & Anti-Cheating (`test_acceptance_security_anti_cheating.py`)
- SCRUM-98: Disable Right-Click Context Menu
- SCRUM-99: Block Copy/Paste Keyboard Shortcut
- SCRUM-100: Disable Text Selection
- SCRUM-101: Block Developer Tools Keyboard Shortcuts
- SCRUM-102: Detect Tab/Window Switching
- SCRUM-103: Encourage Fullscreen Mode
- SCRUM-105: Log Suspicious Activities to Database
- SCRUM-106: Lecturer Dashboard to View Activity Logs
- SCRUM-107: Activity Analytics and Automatic Flagging

### Course & Exam Management (`test_acceptance_course_exam_management.py`)
- SCRUM-108: Student Course List Page
- SCRUM-109: Student-Only Exam View

## Running Tests Locally

### Install Test Dependencies

```bash
pip install pytest pytest-cov black mypy safety bandit flake8
```

### Run All Tests

```bash
cd online_exam_fastapi
pytest -v
```

### Run Acceptance Tests Only

```bash
cd online_exam_fastapi
pytest -v tests/test_acceptance_*.py
```

### Run Tests with Coverage

```bash
cd online_exam_fastapi
pytest --cov=app --cov-report=term --cov-report=html
```

### Run Code Quality Checks

```bash
# Linting
flake8 online_exam_fastapi/app --config .flake8

# Formatting check
black --check online_exam_fastapi/app --line-length 120

# Type checking
mypy online_exam_fastapi/app --ignore-missing-imports

# Security scanning
safety check -r online_exam_fastapi/requirements.txt
bandit -r online_exam_fastapi/app -ll
```

## Viewing Test Results

### GitHub Actions
- Go to the "Actions" tab in your GitHub repository
- Click on a workflow run to see detailed results
- View test artifacts and coverage reports

### Local Test Output
When running tests with `-v` flag, you'll see output like:
```
test_admin_can_login_with_valid_credentials PASSED [ 10%]
test_admin_login_fails_with_invalid_username PASSED [ 20%]
test_admin_login_fails_with_invalid_password PASSED [ 30%]
...
```

Each test shows "PASSED" on its own line, making it easy to see which tests passed.

## Branch Protection Rules (Recommended)

To ensure code quality, set up branch protection rules in GitHub:

1. Go to Settings → Branches
2. Add rule for `main` branch
3. Enable:
   - ✅ Require pull request reviews before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Include administrators

## Commit Message Guidelines

Follow these guidelines for clear commit messages:

### Format
```
<type>: <subject>

<body>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `test`: Adding or updating tests
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `ci`: CI/CD changes
- `style`: Code style changes (formatting)

### Examples
```
feat: Add admin login functionality

- Implement admin authentication
- Add admin dashboard redirect
- Update user model with admin role

test: Add acceptance tests for admin login

- Test valid credentials
- Test invalid credentials
- Test dashboard redirect
```

## Team Workflow

### Daily Development
1. Create feature branch from `main`
2. Make changes and commit frequently (at least 2 commits per week)
3. Write/update tests for your changes
4. Run tests locally before pushing
5. Push to GitHub and create Pull Request

### Pull Request Process
1. Create PR with clear description
2. Ensure all CI checks pass
3. Request code review from team members
4. Address review comments
5. Merge after approval and passing CI

### Nightly Builds
- Automatic builds run every night at 2 AM UTC
- Review build results each morning
- Fix any failures immediately
- Keep the main branch always green

## Troubleshooting

### CI Fails on Linting
```bash
# Check linting errors locally
flake8 online_exam_fastapi/app --config .flake8

# Auto-fix formatting issues
black online_exam_fastapi/app --line-length 120
```

### CI Fails on Tests
```bash
# Run tests locally to see errors
cd online_exam_fastapi
pytest -v
```

### Security Vulnerabilities Found
```bash
# Check vulnerabilities
safety check -r online_exam_fastapi/requirements.txt

# Update vulnerable packages
pip install --upgrade <package-name>
```

## Best Practices

1. **Commit Frequently**: At least 2 code updates per week from each team member
2. **Write Tests**: Add acceptance tests for each user story
3. **Keep Main Green**: Never merge code that breaks CI
4. **Review Code**: Always get PR reviews before merging
5. **Clear Messages**: Write descriptive commit messages
6. **Update Tests**: Update tests when changing functionality

## Next Steps

1. ✅ CI pipeline with nightly builds configured
2. ✅ Acceptance tests created for all user stories
3. ⏳ Set up branch protection rules (manual step in GitHub)
4. ⏳ Configure deployment pipeline (when ready for deployment)

## Questions?

For CI/CD related questions, refer to:
- GitHub Actions documentation: https://docs.github.com/en/actions
- Pytest documentation: https://docs.pytest.org/
- Project README for general setup
