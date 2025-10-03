#!/usr/bin/env python
"""
Standalone entry point for the LobbyLeaks template service.

This script can be run directly without package installation.
"""

import asyncio

if __name__ == "__main__":
    # Import the async main function
    from main import main
    exit(asyncio.run(main()))
