"""Session-based path management for test artifacts.

Provides consistent directory structure for all test outputs:
test_artifacts/{session_id}/
    ├── logs/
    ├── screenshots/
    └── recordings/
"""

from datetime import datetime
from pathlib import Path
from typing import Optional


def get_session_id() -> str:
    """Generate unique session ID based on timestamp.

    Returns:
        Session ID in format YYYYMMDD_HHMMSS
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_session_dir(session_id: Optional[str] = None) -> Path:
    """Get or create session directory under test_artifacts.

    Args:
        session_id: Session ID (generates new if not provided)

    Returns:
        Path to session directory
    """
    if session_id is None:
        session_id = get_session_id()

    session_dir = Path("test_artifacts") / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    return session_dir


def get_logs_dir(session_id: Optional[str] = None) -> Path:
    """Get logs directory for session.

    Args:
        session_id: Session ID

    Returns:
        Path to logs directory
    """
    logs_dir = get_session_dir(session_id) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_screenshots_dir(session_id: Optional[str] = None) -> Path:
    """Get screenshots directory for session.

    Args:
        session_id: Session ID

    Returns:
        Path to screenshots directory
    """
    screenshots_dir = get_session_dir(session_id) / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir


def get_recordings_dir(session_id: Optional[str] = None) -> Path:
    """Get recordings directory for session.

    Args:
        session_id: Session ID

    Returns:
        Path to recordings directory
    """
    recordings_dir = get_session_dir(session_id) / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return recordings_dir


def get_snapshots_dir(session_id: Optional[str] = None) -> Path:
    """Get snapshots directory for session (accessibility trees, etc).

    Args:
        session_id: Session ID

    Returns:
        Path to snapshots directory
    """
    snapshots_dir = get_session_dir(session_id) / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    return snapshots_dir
