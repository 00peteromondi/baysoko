import re

def normalize_phone(phone, max_length=15):
    """Normalize phone numbers to a compact canonical form suitable for DB storage.

    Examples:
    - '0712345678' -> '+254712345678'
    - '712345678' -> '+254712345678'
    - '254712345678' -> '+254712345678'
    - '+254712345678' -> '+254712345678'

    The function strips spaces, punctuation and keeps a leading '+'. If the result
    would exceed `max_length`, it will be truncated preserving a leading '+' if present.
    """
    if not phone:
        return phone

    # Strip surrounding whitespace
    s = str(phone).strip()

    # Remove common separators
    s = re.sub(r"[\s()\-\.]+", "", s)

    # If it starts with +, keep plus then digits only
    if s.startswith('+'):
        digits = re.sub(r"\D", "", s[1:])
        normalized = '+' + digits
    else:
        # Remove any nondigits
        digits = re.sub(r"\D", "", s)

        # Handle common local Kenyan formats
        if digits.startswith('0') and len(digits) in (10, 9, 12):
            # e.g., 0712345678 -> +254712345678
            if digits.startswith('0') and len(digits) >= 9:
                normalized = '+254' + digits.lstrip('0')
            else:
                normalized = '+' + digits
        elif digits.startswith('7') and len(digits) == 9:
            normalized = '+254' + digits
        elif digits.startswith('254'):
            normalized = '+' + digits
        else:
            # Fallback to adding + if plausible, otherwise keep digits
            normalized = ('+' + digits) if digits else s

    # Truncate if exceeds max_length while preserving leading +
    if len(normalized) > max_length:
        if normalized.startswith('+'):
            normalized = '+' + normalized[1: max_length]
        else:
            normalized = normalized[:max_length]

    return normalized
