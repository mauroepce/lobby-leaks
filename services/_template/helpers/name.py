"""
Name normalization utilities for Chilean names.

This module provides utilities to normalize names by removing honorifics,
normalizing unicode characters, and standardizing capitalization.
"""

import re
import unicodedata


# Chilean honorifics to remove (case-insensitive)
# Each pattern will match the honorific at the start of the string followed by space
HONORIFICS = [
    # General (with optional dot)
    r'sr\.?',              # señor
    r'sra\.?',             # señora
    r'srta\.?',            # señorita
    r'don',                # don
    r'doña',               # doña
    # Professional (with optional dot)
    r'dr\.?',              # doctor
    r'dra\.?',             # doctora
    r'prof\.?',            # profesor
    r'profa\.?',           # profesora
    r'ing\.?',             # ingeniero
    r'inga\.?',            # ingeniera
    r'abog\.?',            # abogado
    r'aboga\.?',           # abogada
    # Political (with optional dot)
    r'dip\.?',             # diputado
    r'diputado',
    r'diputada',
    r'sen\.?',             # senador
    r'senador',
    r'senadora',
    r'ministro',
    r'ministra',
    r'alcalde',
    r'alcaldesa',
    r'concejal',
    r'concejala',
]


def normalize_name(name: str) -> str:
    """
    Normalize a person's name by removing honorifics and standardizing format.

    Normalization steps:
    1. Strip leading/trailing whitespace
    2. Normalize unicode to NFC form (canonical composition)
    3. Remove common Chilean honorifics from the beginning
    4. Collapse multiple spaces into single space
    5. Convert to title case

    Args:
        name: Name string to normalize

    Returns:
        Normalized name in title case

    Examples:
        >>> normalize_name("  JUAN   PÉREZ  ")
        'Juan Pérez'
        >>> normalize_name("Sr. Juan Pérez")
        'Juan Pérez'
        >>> normalize_name("Dip. María González")
        'María González'
        >>> normalize_name("José  López  Díaz")
        'José López Díaz'
        >>> normalize_name("DR. PEDRO SÁNCHEZ")
        'Pedro Sánchez'
        >>> normalize_name("sen. Ana María Silva")
        'Ana María Silva'
    """
    if not name or not isinstance(name, str):
        return ""

    # Step 1: Strip whitespace
    result = name.strip()

    # Step 2: Normalize unicode to NFC (canonical composition)
    # This ensures consistent representation of accented characters
    result = unicodedata.normalize('NFC', result)

    # Step 3: Remove honorifics from the beginning
    # Build pattern to match any honorific at the start (case-insensitive)
    pattern = r'^(?:' + '|'.join(HONORIFICS) + r')\s+'
    result = re.sub(pattern, '', result, flags=re.IGNORECASE)

    # Step 4: Collapse multiple spaces into single space
    result = re.sub(r'\s+', ' ', result)

    # Step 5: Convert to title case
    result = result.title()

    return result
