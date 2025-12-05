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


def validate_marks(marks: float, max_marks: int) -> bool:
    """Validate that marks_awarded is within acceptable range.
    
    Args:
        marks: The marks awarded
        max_marks: Maximum allowed marks for the question
        
    Returns:
        True if valid, raises ValueError if not
        
    Raises:
        ValueError: If marks exceed valid range
    """
    if marks < 0 or marks > max_marks:
        raise ValueError(
            f"Marks {marks} out of range [0, {max_marks}]"
        )
    
    return True
