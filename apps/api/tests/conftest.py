"""Optional read-only fixture root for isolated worktrees lacking TASK-001 files."""
import os
from pathlib import Path


def pytest_configure(config):
    root = os.getenv('WITNESS_TEST_FOUNDATION_ROOT')
    if root:
        import witness_api.main
        witness_api.main.ROOT = Path(root).resolve(strict=True)
