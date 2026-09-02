# Computer Use Automation (CUA)

Autonomous browser automation using **Claude on AWS Bedrock** and **Playwright MCP**. An agent navigates to a URL, reads the page, and completes multi-step tasks — form fills, navigation challenges, data entry — without human intervention.

## How it works

The default mode (`step`) keeps a single Playwright browser session alive for the entire task but resets the LLM conversation context after each logical step, carrying forward only structured state (current URL, discovered facts, completed steps). This eliminates the quadratic token growth that accumulates when one conversation handles hundreds of tool calls.

```
cua --url "https://example.com" --prompt "Complete all steps of the challenge"
      │
      ▼
StepCoordinator
  ├─ PlaywrightMCPSession  (browser stays open throughout)
  └─ per step:
       ├─ dismiss overlays via JS (no LLM tokens wasted)
       ├─ BedrockEngine  →  Converse API  →  Claude Haiku/Sonnet
       │    mini-conversation: snapshot → act → repeat until step done
       └─ carry forward: URL + facts + completed_steps only
```

**Token economics (vs. prior single-conversation approach):**

| Approach | Tokens for 5 steps |
|---|---|
| Single conversation (old) | ~3.3M |
| Per-step reset (current) | ~630K |

## Requirements

- Python 3.10+
- Node.js (for Playwright MCP — `npx @playwright/mcp`)
- AWS account with Bedrock access in `us-east-1` (or set `AWS_REGION`)
  - Model access required: `claude-haiku-4-5` and/or `claude-sonnet-4-5`

## Installation

```bash
# Install Python dependencies
uv venv && source .venv/bin/activate
uv pip install -e .

# Playwright MCP (Node.js)
npm install -g @playwright/mcp
```

## Configuration

Create a `.env` file:

```bash
# Required — one of:
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Or for short-lived tokens:
AWS_BEARER_TOKEN_BEDROCK=...   # mapped to AWS_SESSION_TOKEN automatically

# Optional defaults
BEDROCK_MODEL=haiku            # haiku | sonnet
MAX_TOOL_CALLS=150
DISPLAY_WIDTH=1280
DISPLAY_HEIGHT=720
```

## Usage

```bash
# Basic
cua --url "https://example.com" --prompt "Complete the task"

# With video recording
cua --url "https://example.com" --prompt "Complete the task" --record-video

# Use Sonnet for harder tasks
cua --url "https://example.com" --prompt "Complete the task" --model sonnet

# Headed browser (requires display)
cua --url "https://example.com" --prompt "Complete the task" --no-headless
```

### All options

| Flag | Default | Description |
|---|---|---|
| `--url` | required | URL to navigate to |
| `--prompt` | required | Task description |
| `--model` | `haiku` | `haiku` or `sonnet` |
| `--mode` | `step` | `step` (best), `efficient`, `agno`, `classic` |
| `--max-tool-calls` | `150` | Hard cap on total Playwright calls |
| `--display-width` | `1280` | Viewport width |
| `--display-height` | `720` | Viewport height |
| `--record-video` | off | Save `.webm` + `.mp4` to session dir |
| `--headless/--no-headless` | headless | Headed mode needs a display |

### Models

| Alias | Bedrock inference profile |
|---|---|
| `haiku` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `haiku-3.5` | `us.anthropic.claude-3-5-haiku-20241022-v1:0` |
| `sonnet` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |

Uses cross-region inference profiles (`us.` prefix). Requires Bedrock model access to be enabled in your AWS account.

## Session output

Each run writes to `test_artifacts/{session_id}/`:

```
test_artifacts/20260223_144851/
├── REPORT.md          # human-readable summary with timeline
├── logs/
│   ├── timeline.json  # machine-readable event log
│   └── session.log    # plain-text timeline
├── screenshots/       # per-step screenshots
├── snapshots/         # accessibility tree snapshots
└── recordings/        # video (if --record-video)
```

## Architecture modes

| Mode | Class | Notes |
|---|---|---|
| `step` *(default)* | `StepCoordinator` | Per-step context reset, best results |
| `efficient` | `SoloCoordinator` | Single Agno agent, single conversation |
| `agno` | `AgnoCoordinator` | 4-agent Agno team (legacy) |
| `classic` | `CoordinatorAgent` | Original loop (legacy) |

The `step` and `efficient` modes both use the same `BedrockMCPModel` + Playwright MCP stack. The `agno` and `classic` modes are preserved for reference but not actively maintained.

## Docker (optional)

A `docker/` directory contains a Dockerfile and compose file for running the browser in an isolated Xvfb + Chromium environment with VNC access. This is not required for the default setup — Playwright MCP manages its own Chromium.

```bash
docker compose -f docker/docker-compose.yml up --build
```

## License

MIT
