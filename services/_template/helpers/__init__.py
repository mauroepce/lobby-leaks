"""
Helper utilities for data normalization and validation.

This module provides utilities for normalizing and validating Chilean
identification numbers (RUT) and names, with support for pluggable adapters.
"""

from .rut import normalize_rut, validate_rut
from .name import normalize_name

__all__ = [
    "normalize_rut",
    "validate_rut",
    "normalize_name",
]
