"""Utility functions for sanitization and validation."""

import bleach


def sanitize_question_text(text: str) -> str:
    """Sanitize essay question text to prevent XSS attacks.
    
    Allows basic formatting tags but removes script/dangerous content.
    """
    allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'code', 'pre', 'ul', 'ol', 'li']
    allowed_attributes = {}
    
    sanitized = bleach.clean(text, tags=allowed_tags, attributes=allowed_attributes, strip=True)
    return sanitized.strip()


def sanitize_feedback(text: str) -> str:
    """Sanitize grader feedback text.
    
    Allows basic text but removes any HTML/script content.
    """
    # For feedback, we strip all HTML to plain text
    sanitized = bleach.clean(text, tags=[], strip=True)
    return sanitized.strip()


def validate_marks(marks: float, max_marks: int, allow_negative: bool = False) -> bool:
    """Validate that marks_awarded is within acceptable range.
    
    Args:
        marks: The marks awarded
        max_marks: Maximum allowed marks for the question
        allow_negative: Whether negative marks are allowed
        
    Returns:
        True if valid, raises ValueError if not
        
    Raises:
        ValueError: If marks exceed valid range
    """
    min_marks = 0 if not allow_negative else -max_marks
    
    if marks < min_marks or marks > max_marks:
        raise ValueError(
            f"Marks {marks} out of range [{min_marks}, {max_marks}]"
        )
    
    return True
