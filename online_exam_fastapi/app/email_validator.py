"""Email validation utilities with TLD checking."""

import re
from typing import Tuple


# List of valid top-level domains (TLDs)
# This includes common TLDs. For production, consider using the IANA TLD list
VALID_TLDS = {
    # Generic TLDs
    "com", "org", "net", "edu", "gov", "mil", "int",
    # Country code TLDs (common ones)
    "uk", "us", "ca", "au", "de", "fr", "it", "es", "nl", "be", "ch", "at", "se", "no", "dk", "fi",
    "pl", "cz", "ie", "pt", "gr", "ro", "hu", "bg", "hr", "sk", "si", "lt", "lv", "ee",
    "jp", "cn", "kr", "in", "sg", "my", "th", "ph", "id", "vn", "tw", "hk", "mo",
    "nz", "za", "br", "mx", "ar", "cl", "co", "pe", "ve", "ec", "uy", "py", "bo",
    "ae", "sa", "il", "tr", "eg", "ma", "dz", "tn", "jo", "lb", "kw", "qa", "bh", "om",
    "ru", "ua", "kz", "by", "ge", "am", "az",
    # New gTLDs (common ones)
    "io", "co", "ai", "app", "dev", "tech", "online", "site", "website", "store", "shop",
    "blog", "info", "biz", "name", "pro", "xyz", "me", "tv", "cc", "ws", "mobi",
    # Academic/Educational
    "ac", "sch",
    # Other common ones
    "asia", "tel", "jobs", "travel", "museum", "aero", "coop",
}

# Regex pattern for basic email format validation
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def is_valid_email(email: str) -> Tuple[bool, str]:
    """
    Validate email format and TLD.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if email is valid, False otherwise
        - error_message: Error message if invalid, empty string if valid
    """
    if not email:
        return False, "Email address is required."
    
    email = email.strip().lower()
    
    # Check length
    if len(email) > 255:
        return False, "Email address is too long."
    
    # Basic format check
    if not EMAIL_PATTERN.match(email):
        return False, "Please enter a valid email address format."
    
    # Extract domain and TLD
    try:
        local_part, domain = email.split("@", 1)
        
        # Check local part (before @)
        if not local_part or len(local_part) > 64:
            return False, "Invalid email address format."
        
        # Check domain part
        if not domain or "." not in domain:
            return False, "Invalid email address format."
        
        # Extract TLD (last part after the last dot)
        parts = domain.split(".")
        tld = parts[-1].lower()
        
        # Validate TLD
        if not tld:
            return False, "Email address must have a valid top-level domain (e.g., .com, .edu)."
        
        # Check TLD length (must be at least 2 characters)
        if len(tld) < 2:
            return False, "Email address must have a valid top-level domain (e.g., .com, .edu)."
        
        # Check TLD contains only letters (for most TLDs)
        # Some TLDs can have numbers, but we'll be strict for common cases
        if not tld.isalpha():
            return False, "Email address must have a valid top-level domain (e.g., .com, .edu)."
        
        # Check against known valid TLDs
        if tld not in VALID_TLDS:
            return False, f"Email address must use a valid top-level domain (e.g., .com, .edu, .org). '{tld}' is not recognized as a valid domain."
        
        return True, ""
        
    except ValueError:
        return False, "Invalid email address format."
    except Exception:
        return False, "Please enter a valid email address."


def validate_email_format(email: str) -> str:
    """
    Simple wrapper that returns error message or empty string.
    
    Args:
        email: Email address to validate
        
    Returns:
        Error message if invalid, empty string if valid
    """
    is_valid, error_message = is_valid_email(email)
    return error_message
