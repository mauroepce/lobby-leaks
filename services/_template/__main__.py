"""
Entry point for running the template service as a module.

Usage:
    python -m main [args]

Or when installed as a package:
    python -m <package_name> [args]
"""

from .main import main

if __name__ == "__main__":
    exit(main())
