"""
RUT (Rol Único Tributario) normalization and validation for Chile.

This module provides utilities to normalize and validate Chilean tax identification
numbers (RUT) using the official módulo 11 algorithm.

The implementation is designed with an adapter pattern to allow plugging in
external libraries (like python-rut) in the future if needed.
"""

import re
from typing import Optional, Protocol


class RUTAdapter(Protocol):
    """Protocol for pluggable RUT validation/normalization adapters."""

    def normalize(self, rut: str) -> Optional[str]:
        """Normalize a RUT string to canonical format."""
        ...

    def validate(self, rut: str) -> bool:
        """Validate a RUT string using módulo 11 algorithm."""
        ...


class DefaultRUTAdapter:
    """Default implementation of RUT normalization and validation."""

    def normalize(self, rut: str) -> Optional[str]:
        """
        Normalize a RUT string to canonical format: <body>-<DV>

        Args:
            rut: RUT string in any format (with/without dots, hyphens, spaces)

        Returns:
            Normalized RUT in format "12345678-9" or None if invalid format

        Examples:
            >>> adapter = DefaultRUTAdapter()
            >>> adapter.normalize("12.345.678-9")
            '12345678-9'
            >>> adapter.normalize("12345678-K")
            '12345678-K'
            >>> adapter.normalize("  12.345.678-k  ")
            '12345678-K'
            >>> adapter.normalize("invalid")
            None
        """
        if not rut or not isinstance(rut, str):
            return None

        # Remove spaces, dots, and convert to uppercase
        cleaned = rut.strip().replace(".", "").replace(" ", "").upper()

        # Check if it matches RUT pattern: digits + optional hyphen + DV
        match = re.match(r'^(\d{1,8})-?([0-9K])$', cleaned)
        if not match:
            return None

        body, dv = match.groups()
        return f"{body}-{dv}"

    def validate(self, rut: str) -> bool:
        """
        Validate a RUT using the Chilean módulo 11 algorithm.

        The Chilean RUT validation algorithm:
        1. Multiply each digit (from right to left) by sequence 2,3,4,5,6,7,2,3,4...
        2. Sum all products
        3. Calculate 11 - (sum % 11)
        4. If result is 11, DV is 0; if 10, DV is K; otherwise DV is the result

        Args:
            rut: RUT string (will be normalized first)

        Returns:
            True if RUT is valid according to módulo 11 algorithm

        Examples:
            >>> adapter = DefaultRUTAdapter()
            >>> adapter.validate("12.345.678-5")
            True
            >>> adapter.validate("12345678-K")
            False
            >>> adapter.validate("11111111-1")
            True
        """
        # Normalize first
        normalized = self.normalize(rut)
        if not normalized:
            return False

        # Split body and DV
        body, dv = normalized.split('-')

        # Calculate expected DV using módulo 11 algorithm
        total = 0
        multiplier = 2

        for digit in reversed(body):
            total += int(digit) * multiplier
            multiplier = 2 if multiplier == 7 else multiplier + 1

        expected_dv = 11 - (total % 11)

        # Special cases
        if expected_dv == 11:
            expected_dv = 0
        elif expected_dv == 10:
            expected_dv = 'K'

        return str(expected_dv) == dv


# Global adapter instance (can be replaced with external library)
_adapter: RUTAdapter = DefaultRUTAdapter()


def set_adapter(adapter: RUTAdapter) -> None:
    """
    Set a custom RUT adapter (e.g., to use python-rut library).

    Args:
        adapter: Custom adapter implementing RUTAdapter protocol

    Example:
        >>> # Future: plug in external library
        >>> # from external_lib import ExternalRUTAdapter
        >>> # set_adapter(ExternalRUTAdapter())
    """
    global _adapter
    _adapter = adapter


def normalize_rut(rut: str) -> Optional[str]:
    """
    Normalize a RUT string to canonical format.

    Uses the configured adapter (default: built-in implementation).

    Args:
        rut: RUT string in any format

    Returns:
        Normalized RUT in format "12345678-9" or None if invalid

    Examples:
        >>> normalize_rut("12.345.678-9")
        '12345678-9'
        >>> normalize_rut("12345678-K")
        '12345678-K'
    """
    return _adapter.normalize(rut)


def validate_rut(rut: str) -> bool:
    """
    Validate a RUT using módulo 11 algorithm.

    Uses the configured adapter (default: built-in implementation).

    Args:
        rut: RUT string (will be normalized first)

    Returns:
        True if RUT is valid

    Examples:
        >>> validate_rut("12.345.678-5")
        True
        >>> validate_rut("12345678-K")
        False
    """
    return _adapter.validate(rut)
