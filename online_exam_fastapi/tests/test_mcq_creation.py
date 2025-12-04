"""Comprehensive tests for MCQ creation validation (schema-level without TestClient)."""

import pytest
from pydantic import BaseModel, Field, ValidationError


# Local schema copies to test validation constraints
class MCQQuestionCreateTest(BaseModel):
    """Test schema for MCQ question creation with validation constraints."""

    question_text: str = Field(min_length=1, max_length=5000)
    option_a: str = Field(min_length=1, max_length=1000)
    option_b: str = Field(min_length=1, max_length=1000)
    option_c: str = Field(min_length=1, max_length=1000)
    option_d: str = Field(min_length=1, max_length=1000)
    correct_option: str = Field(pattern="^[A-D]$")  # Must be A, B, C, or D

    @staticmethod
    def validate_no_duplicates(options: list[str]) -> bool:
        """Check that options are unique (case-insensitive)."""
        normalized = [opt.strip().lower() for opt in options]
        return len(normalized) == len(set(normalized))


class TestMCQCreationValidation:
    """Tests for MCQ creation validation rules at schema level."""

    def test_create_mcq_missing_option_empty_string(self):
        """Test that empty option strings are rejected."""
        with pytest.raises(ValidationError):
            MCQQuestionCreateTest(
                question_text="What is 2+2?",
                option_a="",  # Empty
                option_b="2",
                option_c="3",
                option_d="4",
                correct_option="A",
            )

    def test_create_mcq_missing_question_text(self):
        """Test that missing question text is rejected."""
        with pytest.raises(ValidationError):
            MCQQuestionCreateTest(
                question_text="",  # Empty
                option_a="1",
                option_b="2",
                option_c="3",
                option_d="4",
                correct_option="A",
            )

    def test_create_mcq_question_exceeds_max_length(self):
        """Test that questions exceeding 5000 characters are rejected."""
        long_question = "Q" * 5001
        with pytest.raises(ValidationError):
            MCQQuestionCreateTest(
                question_text=long_question,
                option_a="Option 1",
                option_b="Option 2",
                option_c="Option 3",
                option_d="Option 4",
                correct_option="A",
            )

    def test_create_mcq_option_exceeds_max_length(self):
        """Test that options exceeding 1000 characters are rejected."""
        long_option = "O" * 1001
        with pytest.raises(ValidationError):
            MCQQuestionCreateTest(
                question_text="What is 2+2?",
                option_a=long_option,
                option_b="Option B",
                option_c="Option C",
                option_d="Option D",
                correct_option="A",
            )

    def test_create_mcq_invalid_correct_option(self):
        """Test that invalid correct_option values are rejected."""
        with pytest.raises(ValidationError):
            MCQQuestionCreateTest(
                question_text="What is 2+2?",
                option_a="1",
                option_b="2",
                option_c="3",
                option_d="4",
                correct_option="E",  # Invalid
            )

    def test_create_mcq_duplicate_options(self):
        """Test that duplicate options are detected."""
        options = ["Same", "Same", "Different1", "Different2"]
        assert not MCQQuestionCreateTest.validate_no_duplicates(options)

    def test_create_mcq_duplicate_options_case_insensitive(self):
        """Test that duplicate options are detected case-insensitively."""
        options = ["same", "SAME", "different1", "different2"]
        assert not MCQQuestionCreateTest.validate_no_duplicates(options)

    def test_create_mcq_at_max_question_length_boundary(self):
        """Test MCQ creation with question at exactly 5000 characters."""
        question_at_max = "Q" * 5000
        mcq = MCQQuestionCreateTest(
            question_text=question_at_max,
            option_a="Option A",
            option_b="Option B",
            option_c="Option C",
            option_d="Option D",
            correct_option="A",
        )
        assert len(mcq.question_text) == 5000

    def test_create_mcq_at_max_option_length_boundary(self):
        """Test MCQ creation with options at exactly 1000 characters."""
        option_at_max = "O" * 1000
        mcq = MCQQuestionCreateTest(
            question_text="Question",
            option_a=option_at_max,
            option_b=option_at_max,
            option_c=option_at_max,
            option_d=option_at_max,
            correct_option="A",
        )
        assert len(mcq.option_a) == 1000

    def test_create_mcq_success_valid_input(self):
        """Test successfully creating a valid MCQ question."""
        mcq = MCQQuestionCreateTest(
            question_text="What is 2+2?",
            option_a="2",
            option_b="3",
            option_c="4",
            option_d="5",
            correct_option="C",
        )
        assert mcq.question_text == "What is 2+2?"
        assert mcq.correct_option == "C"

    def test_create_mcq_with_special_characters(self):
        """Test MCQ creation with special characters in question and options."""
        mcq = MCQQuestionCreateTest(
            question_text="What is 2+2? (It's simple!)",
            option_a="2&3",
            option_b="3|4",
            option_c="4@5",
            option_d="5#6",
            correct_option="D",
        )
        assert "@" in mcq.option_c
        assert "&" in mcq.option_a

    def test_create_mcq_with_long_question(self):
        """Test MCQ creation with a long but valid question text."""
        long_question = "Q" * 4999  # Just under the limit
        mcq = MCQQuestionCreateTest(
            question_text=long_question,
            option_a="Option A",
            option_b="Option B",
            option_c="Option C",
            option_d="Option D",
            correct_option="A",
        )
        assert len(mcq.question_text) == 4999

    def test_create_mcq_uppercase_correct_option(self):
        """Test that correct_option must be uppercase A-D."""
        # This should succeed (uppercase)
        mcq = MCQQuestionCreateTest(
            question_text="Question",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="A",
        )
        assert mcq.correct_option == "A"

    def test_create_mcq_lowercase_correct_option_fails(self):
        """Test that lowercase correct_option is rejected."""
        with pytest.raises(ValidationError):
            MCQQuestionCreateTest(
                question_text="Question",
                option_a="A",
                option_b="B",
                option_c="C",
                option_d="D",
                correct_option="a",  # Lowercase not allowed
            )

    def test_create_mcq_whitespace_preserved_in_question(self):
        """Test that leading/trailing whitespace in question is preserved."""
        # Note: Pydantic doesn't auto-trim; that's a router responsibility
        question_with_spaces = "  Question  "
        mcq = MCQQuestionCreateTest(
            question_text=question_with_spaces,  # Will pass, includes spaces in length
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="A",
        )
        assert mcq.question_text == "  Question  "

    def test_create_mcq_whitespace_preserved_in_options(self):
        """Test that whitespace in options is preserved."""
        option_with_spaces = "  Option A  "
        mcq = MCQQuestionCreateTest(
            question_text="Question",
            option_a=option_with_spaces,
            option_b="Option B",
            option_c="Option C",
            option_d="Option D",
            correct_option="A",
        )
        assert mcq.option_a == "  Option A  "

    def test_create_mcq_one_char_question(self):
        """Test MCQ creation with minimum question length."""
        mcq = MCQQuestionCreateTest(
            question_text="Q",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="A",
        )
        assert len(mcq.question_text) == 1

    def test_create_mcq_one_char_option(self):
        """Test MCQ creation with minimum option length."""
        mcq = MCQQuestionCreateTest(
            question_text="Question",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="A",
        )
        assert len(mcq.option_a) == 1

    def test_create_mcq_numeric_options(self):
        """Test MCQ creation with numeric option text."""
        mcq = MCQQuestionCreateTest(
            question_text="What is 2+2?",
            option_a="2",
            option_b="3",
            option_c="4",
            option_d="5",
            correct_option="C",
        )
        assert mcq.option_c == "4"
