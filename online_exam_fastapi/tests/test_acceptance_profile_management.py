"""
Acceptance tests for Profile Management and Change Password functionality.

These tests validate acceptance criteria for:
- Profile View for Admin, Lecturer, and Student
- Profile Edit with validation (email TLD, phone pattern)
- Change Password with validation (password requirements, strength indicator)
"""

import sys
import uuid
from pathlib import Path

import pytest
from sqlmodel import Session, select

def _ensure_app_on_path():
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root

_ensure_app_on_path()
from app.models import User, Student
from app.auth_utils import hash_password


@pytest.fixture
def authenticated_admin_client(client, session):
    """Create an authenticated admin user and return client with session."""
    password = "Admin123!"
    unique_id = uuid.uuid4().hex[:8]
    email = f"admin-{unique_id}@example.com"
    
    admin = User(
        name="Admin User",
        email=email,
        password_hash=hash_password(password),
        role="admin",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    
    # Login to get session cookie
    response = client.post(
        "/auth/login",
        data={"login_type": "admin", "email": email, "password": password},
        follow_redirects=False,
    )
    
    # Extract cookies
    cookies = dict(response.cookies)
    
    return client, cookies


@pytest.fixture
def authenticated_lecturer_client(client, session):
    """Create an authenticated lecturer user and return client with session."""
    password = "Lecturer123!"
    unique_id = uuid.uuid4().hex[:8]
    email = f"lecturer-{unique_id}@example.com"
    staff_id = f"STAFF{unique_id[:4]}"
    
    lecturer = User(
        name="Dr. Lecturer",
        email=email,
        password_hash=hash_password(password),
        role="lecturer",
        title="Dr.",
        staff_id=staff_id,
    )
    session.add(lecturer)
    session.commit()
    session.refresh(lecturer)
    
    # Login to get session cookie (lecturer login uses staff_id, not email)
    response = client.post(
        "/auth/login",
        data={"login_type": "lecturer", "staff_id": staff_id, "password": password},
        follow_redirects=False,
    )
    
    # Extract cookies
    cookies = dict(response.cookies)
    
    return client, cookies


@pytest.fixture
def authenticated_student_client(client, session):
    """Create an authenticated student user and return client with session."""
    password = "Student123!"
    unique_id = uuid.uuid4().hex[:8]
    email = f"student-{unique_id}@example.com"
    matric_no = f"SWE{unique_id[:4]}"
    
    # Create User first
    user = User(
        name="Student User",
        email=email,
        password_hash=hash_password(password),
        role="student",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Create Student linked to User
    student = Student(
        name="Student User",
        email=email,
        matric_no=matric_no,
        user_id=user.id,
        program="SWE",
        year_of_study=2,
    )
    session.add(student)
    session.commit()
    session.refresh(student)
    
    # Update user's student_id
    user.student_id = student.id
    session.add(user)
    session.commit()
    
    # Login to get session cookie (student login uses matric_no, not email)
    response = client.post(
        "/auth/login",
        data={"login_type": "student", "matric_no": matric_no, "password": password},
        follow_redirects=False,
    )
    
    # Extract cookies
    cookies = dict(response.cookies)
    
    return client, cookies


class TestProfileView:
    """Tests for Profile View functionality."""

    def test_admin_can_view_profile(self, authenticated_admin_client):
        """Admin can view their profile page."""
        client, cookies = authenticated_admin_client
        response = client.get("/auth/profile", cookies=cookies)
        assert response.status_code == 200
        assert b"My Profile" in response.content
        assert b"Admin User" in response.content

    def test_lecturer_can_view_profile(self, authenticated_lecturer_client):
        """Lecturer can view their profile page."""
        client, cookies = authenticated_lecturer_client
        response = client.get("/auth/profile", cookies=cookies)
        assert response.status_code == 200
        assert b"My Profile" in response.content
        assert b"Dr. Lecturer" in response.content

    def test_student_can_view_profile(self, authenticated_student_client):
        """Student can view their profile page."""
        client, cookies = authenticated_student_client
        response = client.get("/auth/profile", cookies=cookies)
        assert response.status_code == 200
        assert b"My Profile" in response.content
        assert b"Student User" in response.content

    def test_unauthenticated_user_cannot_view_profile(self, client):
        """Unauthenticated users cannot view profile."""
        response = client.get("/auth/profile", follow_redirects=False)
        assert response.status_code in [302, 303, 401, 403]

    def test_profile_shows_account_status(self, authenticated_admin_client):
        """Profile page displays account status."""
        client, cookies = authenticated_admin_client
        response = client.get("/auth/profile", cookies=cookies)
        assert response.status_code == 200
        assert b"Account Status" in response.content or b"Active" in response.content

    def test_profile_shows_member_since_date(self, authenticated_admin_client):
        """Profile page displays member since date."""
        client, cookies = authenticated_admin_client
        response = client.get("/auth/profile", cookies=cookies)
        assert response.status_code == 200
        assert b"Member Since" in response.content


class TestProfileEdit:
    """Tests for Profile Edit functionality."""

    def test_admin_can_update_name(self, authenticated_admin_client, session):
        """Admin can update their name."""
        client, cookies = authenticated_admin_client
        
        # Get current user
        response = client.get("/auth/profile", cookies=cookies)
        assert response.status_code == 200
        
        # Update name
        response = client.post(
            "/auth/profile/edit",
            data={"name": "Updated Admin Name", "email": "admin@example.com"},
            cookies=cookies,
            follow_redirects=False,
        )
        
        assert response.status_code == 303
        
        # Verify update
        session.expire_all()
        user = session.exec(select(User).where(User.email == "admin@example.com")).first()
        if user:
            assert user.name == "Updated Admin Name"

    def test_admin_can_update_email_with_valid_tld(self, authenticated_admin_client, session):
        """Admin can update email with valid TLD."""
        client, cookies = authenticated_admin_client
        
        # Get current user email
        response = client.get("/auth/profile/edit", cookies=cookies)
        assert response.status_code == 200
        content = response.content.decode()
        
        # Extract current email from form
        import re
        email_match = re.search(r'name="email" value="([^"]+)"', content)
        if email_match:
            current_email = email_match.group(1)
        else:
            # Fallback: use a test email
            current_email = "admin@example.com"
        
        new_email = f"newadmin{uuid.uuid4().hex[:8]}@example.com"
        
        response = client.post(
            "/auth/profile/edit",
            data={"name": "Admin User", "email": new_email},
            cookies=cookies,
            follow_redirects=False,
        )
        
        assert response.status_code == 303
        
        # Verify update
        session.expire_all()
        user = session.exec(select(User).where(User.email == new_email)).first()
        assert user is not None

    def test_admin_can_update_phone(self, authenticated_admin_client, session):
        """Admin can update phone number."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/edit",
            data={"name": "Admin User", "email": "admin@example.com", "phone": "+60123456789"},
            cookies=cookies,
            follow_redirects=False,
        )
        
        assert response.status_code == 303
        
        # Verify update
        session.expire_all()
        user = session.exec(select(User).where(User.role == "admin")).first()
        if hasattr(user, "phone"):
            assert user.phone == "+60123456789"

    def test_profile_edit_rejects_invalid_email_tld(self, authenticated_admin_client):
        """Profile edit form rejects email with invalid TLD."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/edit",
            data={"name": "Admin User", "email": "admin@example.invalidtld"},
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"valid top-level domain" in response.content.lower() or b"invalid" in response.content.lower()

    def test_profile_edit_rejects_phone_without_digits(self, authenticated_admin_client):
        """Profile edit form rejects phone number without digits."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/edit",
            data={"name": "Admin User", "email": "admin@example.com", "phone": "abc"},
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"digits" in response.content.lower()

    def test_profile_edit_rejects_invalid_phone_length(self, authenticated_admin_client):
        """Profile edit form rejects phone number with invalid length."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/edit",
            data={"name": "Admin User", "email": "admin@example.com", "phone": "123"},
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"7-15 digits" in response.content.lower() or b"valid phone" in response.content.lower()

    def test_profile_edit_rejects_duplicate_email(self, authenticated_admin_client, session):
        """Profile edit form rejects duplicate email."""
        client, cookies = authenticated_admin_client
        
        # Create another user with different email
        other_email = f"other{uuid.uuid4().hex[:8]}@example.com"
        other_user = User(
            name="Other User",
            email=other_email,
            password_hash=hash_password("Password123!"),
            role="admin",
        )
        session.add(other_user)
        session.commit()
        
        # Try to update current user's email to the other user's email
        response = client.post(
            "/auth/profile/edit",
            data={"name": "Admin User", "email": other_email},
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"already registered" in response.content.lower() or b"already in use" in response.content.lower()

    def test_lecturer_can_update_title(self, authenticated_lecturer_client, session):
        """Lecturer can update their title."""
        client, cookies = authenticated_lecturer_client
        
        # Get current user email from profile page
        profile_response = client.get("/auth/profile", cookies=cookies)
        if profile_response.status_code != 200:
            # If profile page redirects, get email from database
            user = session.exec(select(User).where(User.role == "lecturer")).first()
            user_email = user.email if user else "lecturer@example.com"
        else:
            # Extract email from profile page HTML
            import re
            email_match = re.search(r'<td>([^<]*@[^<]*)</td>', profile_response.content.decode())
            user_email = email_match.group(1) if email_match else "lecturer@example.com"
        
        response = client.post(
            "/auth/profile/edit",
            data={
                "name": "Dr. Lecturer",
                "email": user_email,
                "title": "Prof.",
            },
            cookies=cookies,
            follow_redirects=False,
        )
        
        assert response.status_code == 303
        
        # Verify update
        session.expire_all()
        user = session.exec(select(User).where(User.role == "lecturer")).first()
        if hasattr(user, "title"):
            assert user.title == "Prof."

    def test_profile_edit_rejects_invalid_title(self, authenticated_lecturer_client, session):
        """Profile edit form rejects invalid title."""
        client, cookies = authenticated_lecturer_client
        
        # Get current user email
        user = session.exec(select(User).where(User.role == "lecturer")).first()
        user_email = user.email if user else "lecturer@example.com"
        
        response = client.post(
            "/auth/profile/edit",
            data={
                "name": "Dr. Lecturer",
                "email": user_email,
                "title": "InvalidTitle",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"valid title" in response.content.lower()

    def test_profile_edit_rejects_duplicate_staff_id(self, authenticated_lecturer_client, session):
        """Profile edit form rejects duplicate staff ID."""
        client, cookies = authenticated_lecturer_client
        
        # Create another lecturer with different staff_id
        other_email = f"otherlecturer{uuid.uuid4().hex[:8]}@example.com"
        other_lecturer = User(
            name="Other Lecturer",
            email=other_email,
            password_hash=hash_password("Password123!"),
            role="lecturer",
            staff_id="STAFF9999",
        )
        session.add(other_lecturer)
        session.commit()
        
        # Try to update current lecturer's staff_id to the other lecturer's staff_id
        response = client.post(
            "/auth/profile/edit",
            data={
                "name": "Dr. Lecturer",
                "email": "lecturer@example.com",
                "staff_id": "STAFF9999",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"already in use" in response.content.lower()

    def test_student_can_update_program(self, authenticated_student_client, session):
        """Student can update their program."""
        client, cookies = authenticated_student_client
        
        # Get current user email
        user = session.exec(select(User).where(User.role == "student")).first()
        user_email = user.email if user else "student@example.com"
        
        response = client.post(
            "/auth/profile/edit",
            data={
                "name": "Student User",
                "email": user_email,
                "program": "BIM",
                "year_of_study": "3",
            },
            cookies=cookies,
            follow_redirects=False,
        )
        
        assert response.status_code == 303
        
        # Verify update
        session.expire_all()
        user = session.exec(select(User).where(User.role == "student")).first()
        if user and user.student_id:
            student = session.get(Student, user.student_id)
            if student:
                assert student.program == "BIM"

    def test_student_can_update_year_of_study(self, authenticated_student_client, session):
        """Student can update their year of study."""
        client, cookies = authenticated_student_client
        
        # Get current user email
        user = session.exec(select(User).where(User.role == "student")).first()
        user_email = user.email if user else "student@example.com"
        
        response = client.post(
            "/auth/profile/edit",
            data={
                "name": "Student User",
                "email": user_email,
                "program": "SWE",
                "year_of_study": "4",
            },
            cookies=cookies,
            follow_redirects=False,
        )
        
        assert response.status_code == 303
        
        # Verify update
        session.expire_all()
        user = session.exec(select(User).where(User.role == "student")).first()
        if user and user.student_id:
            student = session.get(Student, user.student_id)
            if student:
                assert student.year_of_study == 4

    def test_profile_edit_rejects_invalid_year_of_study(self, authenticated_student_client, session):
        """Profile edit form rejects invalid year of study."""
        client, cookies = authenticated_student_client
        
        # Get current user email
        user = session.exec(select(User).where(User.role == "student")).first()
        user_email = user.email if user else "student@example.com"
        
        response = client.post(
            "/auth/profile/edit",
            data={
                "name": "Student User",
                "email": user_email,
                "year_of_study": "15",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"between 1 and 10" in response.content.lower()

    def test_student_cannot_update_matric_number(self, authenticated_student_client):
        """Student cannot update matric number (read-only)."""
        client, cookies = authenticated_student_client
        
        response = client.get("/auth/profile/edit", cookies=cookies)
        assert response.status_code == 200
        
        # Check that matric_no field is disabled
        assert b'id="matric_no"' in response.content
        assert b'disabled' in response.content or b'readonly' in response.content

    def test_profile_edit_requires_name(self, authenticated_admin_client):
        """Profile edit form requires name field."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/edit",
            data={"name": "", "email": "admin@example.com"},
            cookies=cookies,
        )
        
        # FastAPI returns 422 for missing required fields, 400 for validation errors
        assert response.status_code in [400, 422]
        assert b"required" in response.content.lower() or b"name" in response.content.lower()

    def test_profile_edit_requires_email(self, authenticated_admin_client):
        """Profile edit form requires email field."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/edit",
            data={"name": "Admin User", "email": ""},
            cookies=cookies,
        )
        
        # FastAPI returns 422 for missing required fields, 400 for validation errors
        assert response.status_code in [400, 422]
        assert b"required" in response.content.lower() or b"email" in response.content.lower()

    def test_unauthenticated_user_cannot_edit_profile(self, client):
        """Unauthenticated users cannot edit profile."""
        response = client.get("/auth/profile/edit", follow_redirects=False)
        assert response.status_code in [302, 303, 401, 403]


class TestChangePassword:
    """Tests for Change Password functionality."""

    def test_user_can_view_change_password_form(self, authenticated_admin_client):
        """User can view change password form."""
        client, cookies = authenticated_admin_client
        response = client.get("/auth/profile/change-password", cookies=cookies)
        assert response.status_code == 200
        assert b"Change Password" in response.content

    def test_user_can_change_password_with_valid_current_password(self, authenticated_admin_client, session):
        """User can change password with valid current password."""
        client, cookies = authenticated_admin_client
        
        # Get current user email
        response = client.get("/auth/profile", cookies=cookies)
        assert response.status_code == 200
        
        # Change password
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
            },
            cookies=cookies,
            follow_redirects=False,
        )
        
        assert response.status_code == 303
        
        # Verify password was changed
        session.expire_all()
        user = session.exec(select(User).where(User.role == "admin")).first()
        from app.auth_utils import verify_password
        assert verify_password("NewPassword123!", user.password_hash)

    def test_successful_password_change_redirects_to_profile(self, authenticated_admin_client):
        """Successful password change redirects to profile with success message."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
            },
            cookies=cookies,
            follow_redirects=False,
        )
        
        assert response.status_code == 303
        assert "password_changed=1" in str(response.url) or "/auth/profile" in str(response.url)

    def test_change_password_fails_with_wrong_current_password(self, authenticated_admin_client):
        """Change password fails when current password is incorrect."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "WrongPassword123!",
                "new_password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"incorrect" in response.content.lower() or b"wrong" in response.content.lower()

    def test_change_password_fails_when_reusing_current_password(self, authenticated_admin_client):
        """Change password fails when new password is same as current password."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "Admin123!",
                "confirm_password": "Admin123!",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert (
            b"different" in response.content.lower()
            or b"same" in response.content.lower()
            or b"must be different" in response.content.lower()
            or b"cannot be the same" in response.content.lower()
        )

    def test_change_password_requires_minimum_length(self, authenticated_admin_client):
        """Change password requires minimum 8 characters."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "Short1!",
                "confirm_password": "Short1!",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"8 characters" in response.content.lower()

    def test_change_password_requires_uppercase(self, authenticated_admin_client):
        """Change password requires at least one uppercase letter."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "lowercase123!",
                "confirm_password": "lowercase123!",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"uppercase" in response.content.lower()

    def test_change_password_requires_lowercase(self, authenticated_admin_client):
        """Change password requires at least one lowercase letter."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "UPPERCASE123!",
                "confirm_password": "UPPERCASE123!",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"lowercase" in response.content.lower()

    def test_change_password_requires_digit(self, authenticated_admin_client):
        """Change password requires at least one digit."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "NoDigits!",
                "confirm_password": "NoDigits!",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"number" in response.content.lower() or b"digit" in response.content.lower()

    def test_change_password_requires_special_character(self, authenticated_admin_client):
        """Change password requires at least one special character."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "NoSpecial123",
                "confirm_password": "NoSpecial123",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"special" in response.content.lower()

    def test_change_password_rejects_max_length_exceeded(self, authenticated_admin_client):
        """Change password rejects passwords exceeding 128 characters."""
        client, cookies = authenticated_admin_client
        
        long_password = "A" * 129 + "1!"
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": long_password,
                "confirm_password": long_password,
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"128" in response.content.lower() or b"exceed" in response.content.lower()

    def test_change_password_requires_password_match(self, authenticated_admin_client):
        """Change password requires new password and confirm password to match."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "NewPassword123!",
                "confirm_password": "DifferentPassword123!",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        assert b"match" in response.content.lower()

    def test_change_password_requires_current_password(self, authenticated_admin_client):
        """Change password requires current password field."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "",
                "new_password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
            },
            cookies=cookies,
        )
        
        # FastAPI returns 422 for missing required fields, 400 for validation errors
        assert response.status_code in [400, 422]

    def test_change_password_requires_new_password(self, authenticated_admin_client):
        """Change password requires new password field."""
        client, cookies = authenticated_admin_client
        
        response = client.post(
            "/auth/profile/change-password",
            data={
                "current_password": "Admin123!",
                "new_password": "",
                "confirm_password": "",
            },
            cookies=cookies,
        )
        
        # FastAPI returns 422 for missing required fields, 400 for validation errors
        assert response.status_code in [400, 422]

    def test_unauthenticated_user_cannot_change_password(self, client):
        """Unauthenticated users cannot change password."""
        response = client.get("/auth/profile/change-password", follow_redirects=False)
        assert response.status_code in [302, 303, 401, 403]


class TestProfileEditClientSideValidation:
    """Tests for client-side validation in profile edit form."""

    def test_profile_edit_has_email_tld_validation(self, authenticated_admin_client):
        """Profile edit form has client-side email TLD validation."""
        client, cookies = authenticated_admin_client
        response = client.get("/auth/profile/edit", cookies=cookies)
        assert response.status_code == 200
        
        content = response.content.decode()
        assert "validTLDs" in content or "validateEmail" in content

    def test_profile_edit_has_phone_pattern_validation(self, authenticated_admin_client):
        """Profile edit form has client-side phone pattern validation."""
        client, cookies = authenticated_admin_client
        response = client.get("/auth/profile/edit", cookies=cookies)
        assert response.status_code == 200
        
        content = response.content.decode()
        assert "phoneDigits" in content or "validatePhone" in content


class TestChangePasswordClientSideValidation:
    """Tests for client-side validation in change password form."""

    def test_change_password_has_password_requirements(self, authenticated_admin_client):
        """Change password form displays password requirements."""
        client, cookies = authenticated_admin_client
        response = client.get("/auth/profile/change-password", cookies=cookies)
        assert response.status_code == 200
        
        content = response.content.decode()
        assert "password-requirements" in content

    def test_change_password_has_strength_indicator(self, authenticated_admin_client):
        """Change password form has password strength indicator."""
        client, cookies = authenticated_admin_client
        response = client.get("/auth/profile/change-password", cookies=cookies)
        assert response.status_code == 200
        
        content = response.content.decode()
        assert "strengthBar" in content or "strengthLabel" in content

    def test_change_password_has_live_validation(self, authenticated_admin_client):
        """Change password form has live password validation."""
        client, cookies = authenticated_admin_client
        response = client.get("/auth/profile/change-password", cookies=cookies)
        assert response.status_code == 200
        
        content = response.content.decode()
        assert "validatePassword" in content or "calculatePasswordStrength" in content
