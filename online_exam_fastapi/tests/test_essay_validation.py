"""Tests for essay question and answer validation constraints."""

import sys
from pathlib import Path
from datetime import datetime

from sqlmodel import Session, select
from pydantic import BaseModel, Field, ValidationError
import pytest

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


# Define local schema copies to avoid app initialization during import
class CreateQuestionInTest(BaseModel):
    question_text: str = Field(min_length=1, max_length=5000)
    max_marks: int = Field(ge=1, le=1000)


class AnswerInTest(BaseModel):
    question_id: int
    answer_text: str | None = Field(default=None, max_length=50000)


class TestQuestionValidation:
    """Tests for ExamQuestion validation constraints."""

    def test_question_text_min_length(self):
        """Question text must have at least 1 character."""
        # Try to create question with empty text
        with pytest.raises(ValidationError):
            CreateQuestionInTest(question_text="", max_marks=5)

    def test_question_text_max_length(self):
        """Question text cannot exceed 5000 characters."""
        # Try to create question with text exceeding 5000 chars
        long_text = "a" * 5001
        with pytest.raises(ValidationError):
            CreateQuestionInTest(question_text=long_text, max_marks=5)

    def test_question_text_at_max_boundary(self):
        """Question text at exactly 5000 characters should be valid."""
        # Create question with text at 5000 chars
        text_at_max = "a" * 5000
        schema = CreateQuestionInTest(question_text=text_at_max, max_marks=5)
        assert schema.question_text == text_at_max
        assert len(schema.question_text) == 5000

    def test_max_marks_min_value(self):
        """max_marks must be at least 1."""
        # Try to create with 0 marks
        with pytest.raises(ValidationError):
            CreateQuestionInTest(question_text="Q?", max_marks=0)

    def test_max_marks_max_value(self):
        """max_marks cannot exceed 1000."""
        # Try to create with 1001 marks
        with pytest.raises(ValidationError):
            CreateQuestionInTest(question_text="Q?", max_marks=1001)

    def test_max_marks_at_boundaries(self):
        """max_marks at 1 and 1000 should be valid."""
        # Test lower boundary
        schema1 = CreateQuestionInTest(question_text="Q?", max_marks=1)
        assert schema1.max_marks == 1

        # Test upper boundary
        schema2 = CreateQuestionInTest(question_text="Q?", max_marks=1000)
        assert schema2.max_marks == 1000


class TestAnswerValidation:
    """Tests for EssayAnswer validation constraints."""

    def test_answer_text_max_length(self):
        """Answer text cannot exceed 50000 characters."""
        # Try to create answer with text exceeding 50000 chars
        long_text = "a" * 50001
        with pytest.raises(ValidationError):
            AnswerInTest(question_id=1, answer_text=long_text)

    def test_answer_text_at_max_boundary(self):
        """Answer text at exactly 50000 characters should be valid."""
        # Create answer with text at 50000 chars
        text_at_max = "a" * 50000
        schema = AnswerInTest(question_id=1, answer_text=text_at_max)
        assert schema.answer_text == text_at_max
        assert len(schema.answer_text) == 50000

    def test_answer_text_optional(self):
        """Answer text should be optional (None is allowed)."""
        # Create answer without text
        schema = AnswerInTest(question_id=1, answer_text=None)
        assert schema.answer_text is None

    def test_answer_text_empty_string(self):
        """Empty string should be allowed for answer_text."""
        # Create answer with empty string
        schema = AnswerInTest(question_id=1, answer_text="")
        assert schema.answer_text == ""
