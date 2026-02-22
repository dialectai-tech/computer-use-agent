# Test Artifacts

This directory contains all test outputs organized by session timestamp.

## Structure

All outputs from a single run are consolidated into one timestamped directory:

```
test_artifacts/
├── YYYYMMDD_HHMMSS/           # Timestamped test session
│   ├── logs/                   # Session logs
│   │   └── session.log         # JSON-structured log file
│   ├── recordings/             # Video recordings (if enabled)
│   │   └── session.webm        # Browser session recording
│   ├── screenshots/            # Screenshots captured during testing
│   │   ├── step_01.png
│   │   ├── step_02.png
│   │   └── ...
│   └── snapshots/              # Accessibility tree snapshots
│       ├── step_01_snapshot.md
│       ├── step_02_snapshot.md
│       └── ...
└── README.md                   # This file
```

## Session Organization

Each test run creates a new timestamped directory (`YYYYMMDD_HHMMSS`) containing:
- **logs/** - Structured JSON logs of agent interactions
- **recordings/** - Video recordings of browser automation (if `--record-video` enabled)
- **screenshots/** - Screenshots captured by browser agent
- **snapshots/** - Accessibility tree snapshots for analysis

This consolidates what were previously separate directories:
- ~~test_runs/~~ (now: test_artifacts/{session_id}/)
- ~~logs/sessions/~~ (now: test_artifacts/{session_id}/logs/)
- ~~screenshots/~~ (now: test_artifacts/{session_id}/screenshots/)

## Cleanup

This directory is excluded from git (see .gitignore).
To clean old artifacts:

```bash
# Remove artifacts older than 7 days
find test_artifacts/ -name "2026*" -mtime +7 -exec rm -rf {} \;
```
