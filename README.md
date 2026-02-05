# Computer Use Automation (CUA) - Multi-Provider Agent

A generic, provider-agnostic computer use automation tool that supports both **Anthropic Claude** and **OpenAI** models with easy model switching, browser automation in Docker, and comprehensive monitoring capabilities.

## 🎯 Project Overview

This tool enables AI agents to:
- Navigate to user-provided URLs
- Read and understand webpage instructions
- Complete tasks like form filling, data entry, clicking, scrolling, navigation
- Handle multi-page workflows
- Track performance metrics (time per page, total session time)
- Record sessions for playback and analysis

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Host Machine (Azure VM)                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Python Agent Controller                               │ │
│  │  - Multi-provider support (Claude/OpenAI)              │ │
│  │  - Unified API interface                               │ │
│  │  - Session recording & metrics                         │ │
│  │  - VNC viewer (optional)                               │ │
│  └────────────┬───────────────────────────▲───────────────┘ │
│               │ Commands                  │ Results         │
│               ▼                           │                 │
│  ┌────────────────────────────────────────┴───────────────┐ │
│  │  Docker Container (Isolated Browser Environment)      │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Xvfb (Virtual Display :1)                       │ │ │
│  │  │  Resolution: 1280x720                            │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Playwright (Chromium)                           │ │ │
│  │  │  - Browser automation                            │ │ │
│  │  │  - Screenshot capture                            │ │ │
│  │  │  - Action execution                              │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  VNC Server (port 5900)                          │ │ │
│  │  │  - Real-time viewing                             │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Features

### Multi-Provider Support
- **Claude (Anthropic)**: Sonnet 4.5, Haiku 4.5, Opus 4.5
- **OpenAI**: computer-use-preview model
- **Easy Switching**: Toggle via environment variable or runtime config
- **Unified Interface**: Same code works with both providers

### Browser Automation
- Isolated Docker container with Chromium browser
- Playwright for reliable browser control
- Screenshot capture at each step
- Full DOM/HTML access for enhanced context

### Monitoring & Recording
- Real-time VNC viewing (optional)
- Session video recording
- Per-page timing metrics
- Total session duration tracking
- Action logs with timestamps

### Generic Task Handling
- User-provided URLs and prompts
- Multi-page form workflows
- Dynamic task completion detection
- Semantic understanding of "task complete" states

## 📋 Prerequisites

### System Requirements
- Python 3.10+
- Docker (already installed)
- uv (already installed)
- 2GB+ RAM recommended
- Internet connectivity

### API Keys Required

Create a `.env` file in the project root:

```bash
# Choose your provider
PROVIDER=claude  # Options: claude, openai, or both

# Anthropic Claude API Key
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenAI API Key
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Portkey for unified gateway (if using both providers)
PORTKEY_API_KEY=your-portkey-key
PORTKEY_VIRTUAL_KEY_CLAUDE=your-claude-virtual-key
PORTKEY_VIRTUAL_KEY_OPENAI=your-openai-virtual-key

# Agent Configuration
DEFAULT_MODEL=claude-sonnet-4-5  # or computer-use-preview for OpenAI
DISPLAY_WIDTH=1280
DISPLAY_HEIGHT=720
MAX_ITERATIONS=30
SCREENSHOT_INTERVAL=1.0  # seconds between actions

# VNC Configuration (for viewing)
ENABLE_VNC=true
VNC_PORT=5900
VNC_PASSWORD=changeme

# Recording Configuration
ENABLE_RECORDING=true
RECORDING_FPS=2
RECORDINGS_DIR=./recordings
```

### Getting API Keys

**Anthropic Claude:**
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key

**OpenAI:**
1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key

**Portkey (Optional - for unified gateway):**
1. Go to https://portkey.ai/
2. Sign up for free
3. Create virtual keys for both providers
4. Use single endpoint for both models

## 🛠️ Installation

```bash
# Clone or navigate to project
cd /home/azureuser/projects/cua-project

# Create virtual environment using uv
uv venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -e .
```

## 📦 Project Structure

```
cua-project/
├── README.md                 # This file
├── CLAUDE.md                 # Detailed Claude implementation guide
├── pyproject.toml            # Python package configuration
├── .env                      # Environment variables (create this)
├── .env.example              # Example environment file
├── docker/
│   ├── Dockerfile           # Browser container definition
│   └── docker-compose.yml   # Container orchestration
├── src/
│   └── cua/
│       ├── __init__.py
│       ├── main.py          # CLI entry point
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py      # Base provider interface
│       │   ├── claude.py    # Claude implementation
│       │   ├── openai.py    # OpenAI implementation
│       │   └── portkey.py   # Portkey gateway (optional)
│       ├── browser/
│       │   ├── __init__.py
│       │   ├── docker_manager.py    # Docker container management
│       │   └── playwright_controller.py  # Playwright automation
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── loop.py      # Main agent loop
│       │   └── actions.py   # Action execution
│       ├── monitoring/
│       │   ├── __init__.py
│       │   ├── recorder.py  # Session recording
│       │   └── metrics.py   # Performance tracking
│       └── utils/
│           ├── __init__.py
│           ├── screenshot.py
│           └── logger.py
├── recordings/              # Session recordings (generated)
├── logs/                    # Log files (generated)
└── tests/                   # Unit tests
```

## 🎮 Usage

### Basic Usage

```bash
# Run with default settings (from .env)
python -m cua.main \
  --url "https://example.com/task-page" \
  --prompt "Complete the registration form"

# Specify provider explicitly
python -m cua.main \
  --provider claude \
  --model claude-sonnet-4-5 \
  --url "https://forms.gle/example" \
  --prompt "Fill out the survey"

# Use OpenAI
python -m cua.main \
  --provider openai \
  --model computer-use-preview \
  --url "https://example.com" \
  --prompt "Navigate and complete checkout"

# Enable VNC viewing
python -m cua.main \
  --url "https://example.com" \
  --prompt "Complete task" \
  --enable-vnc \
  --vnc-port 5900
```

### Advanced Usage

```bash
# With recording and custom settings
python -m cua.main \
  --url "https://complex-form.com" \
  --prompt "Fill out multi-step form" \
  --provider claude \
  --max-iterations 50 \
  --enable-recording \
  --recording-fps 5 \
  --enable-vnc \
  --vnc-password "secure123"

# Compare models on same task
python -m cua.main \
  --url "https://test-site.com" \
  --prompt "Complete task X" \
  --provider both \
  --compare-models
```

### Viewing Agent in Action

#### Option 1: VNC Viewer (Real-time)

```bash
# On your local machine, create SSH tunnel
ssh -L 5900:localhost:5900 azureuser@<azure-vm-ip>

# Then connect with VNC client to localhost:5900
# Use password from .env (VNC_PASSWORD)
```

#### Option 2: Session Recording (Post-analysis)

```bash
# Recordings saved to ./recordings/ directory
# View with any video player
vlc recordings/session_2025-02-05_14-30-45.mp4
```

### Python API

```python
from cua import ComputerUseAgent
from cua.providers import ClaudeProvider, OpenAIProvider

# Initialize agent with Claude
agent = ComputerUseAgent(
    provider=ClaudeProvider(api_key="your-key"),
    display_width=1280,
    display_height=720,
    enable_recording=True,
    enable_vnc=True
)

# Run task
result = agent.run_task(
    url="https://example.com/form",
    prompt="Complete the contact form with test data",
    max_iterations=30
)

# Get metrics
print(f"Task completed: {result.success}")
print(f"Total time: {result.total_time:.2f}s")
print(f"Pages visited: {len(result.page_metrics)}")
for page in result.page_metrics:
    print(f"  {page.url}: {page.time:.2f}s")
```

## 🔧 Configuration Options

### Provider Selection

**Claude Models:**
- `claude-sonnet-4-5` (recommended for speed/cost)
- `claude-opus-4-5` (best quality, slower)
- `claude-haiku-4-5` (fastest, cheapest)

**OpenAI Models:**
- `computer-use-preview` (only option currently)

### Display Settings

| Setting | Default | Range | Notes |
|---------|---------|-------|-------|
| `DISPLAY_WIDTH` | 1280 | 800-1920 | Higher uses more tokens |
| `DISPLAY_HEIGHT` | 720 | 600-1080 | Keep aspect ratio ~16:9 |
| `MAX_ITERATIONS` | 30 | 10-100 | Safety limit for loops |

### Performance Tuning

```python
# Fast & cheap (for simple tasks)
agent = ComputerUseAgent(
    provider=ClaudeProvider(model="claude-haiku-4-5"),
    display_width=1024,
    display_height=768,
    screenshot_interval=0.5
)

# High quality (for complex tasks)
agent = ComputerUseAgent(
    provider=ClaudeProvider(model="claude-opus-4-5"),
    display_width=1920,
    display_height=1080,
    screenshot_interval=2.0
)
```

## 📊 Example Task Scenarios

### Scenario 1: Multi-Page Form

```bash
python -m cua.main \
  --url "https://multi-step-form.com" \
  --prompt "Complete the 3-page registration form:
    Page 1: Fill basic info (name, email, phone)
    Page 2: Select preferences and interests
    Page 3: Review and submit
    Take screenshot after each page to verify."
```

### Scenario 2: Data Entry Task

```bash
python -m cua.main \
  --url "https://data-entry-system.com" \
  --prompt "Enter the following customer records:
    1. John Doe, john@example.com, 555-1234
    2. Jane Smith, jane@example.com, 555-5678
    Continue until all records are entered and saved."
```

### Scenario 3: Research & Navigation

```bash
python -m cua.main \
  --url "https://news-site.com" \
  --prompt "Find articles about AI from the past week,
    click on the top 3 results, and take screenshots
    of each article page."
```

## 🎯 Task Completion Detection

The agent uses semantic understanding to detect completion:

**Completion Signals:**
- "Task completed successfully"
- "Thank you for your submission"
- "Form submitted"
- "Registration complete"
- "Order confirmed"
- URL contains `/success`, `/complete`, `/thank-you`
- Presence of confirmation message/modal

**Error Detection:**
- "Error", "Failed", "Invalid"
- Red error messages
- Validation failures
- 404/500 error pages

## 📈 Performance Metrics

After each session, you'll see:

```
=== Session Summary ===
Task: Complete registration form
Provider: Claude (claude-sonnet-4-5)
Status: ✓ Completed successfully

Time Breakdown:
  Page 1 (landing): 2.3s
  Page 2 (form): 8.7s
  Page 3 (verification): 3.1s
  Page 4 (success): 1.2s
  Total: 15.3s

Actions Taken: 23
  - Screenshots: 8
  - Clicks: 7
  - Type: 6
  - Scroll: 2

API Costs (estimated):
  Input tokens: 12,450
  Output tokens: 3,210
  Estimated cost: $0.23

Recording: recordings/session_2025-02-05_14-30-45.mp4
```

## 🐛 Troubleshooting

### Docker Container Issues

```bash
# Check container status
docker ps -a

# View container logs
docker logs cua-browser

# Restart container
docker-compose -f docker/docker-compose.yml restart

# Rebuild container
docker-compose -f docker/docker-compose.yml up --build -d
```

### VNC Connection Issues

```bash
# Check if VNC server is running
docker exec cua-browser ps aux | grep vnc

# Test VNC port
nc -zv localhost 5900

# Restart VNC
docker exec cua-browser supervisorctl restart x11vnc
```

### API Issues

```bash
# Test Claude API
python -c "
from anthropic import Anthropic
client = Anthropic()
print(client.messages.create(
    model='claude-sonnet-4-5',
    max_tokens=10,
    messages=[{'role':'user','content':'Hi'}]
))
"

# Test OpenAI API
python -c "
from openai import OpenAI
client = OpenAI()
print(client.chat.completions.create(
    model='gpt-4',
    messages=[{'role':'user','content':'Hi'}],
    max_tokens=10
))
"
```

## 🔐 Security Considerations

### Container Isolation
- Runs in isolated Docker container
- No access to host filesystem
- Network access limited to allowlist (optional)
- No persistent storage of sensitive data

### API Key Safety
- Never commit `.env` file
- Use environment variables only
- Rotate keys regularly
- Monitor API usage

### Task Safety
- Human approval for high-risk actions (optional)
- Confirm before financial transactions
- Review before account creation
- Limit to trusted domains

## 📚 Additional Resources

- [CLAUDE.md](./CLAUDE.md) - Detailed Claude implementation guide
- [Anthropic Computer Use Docs](https://docs.anthropic.com/claude/docs/computer-use)
- [OpenAI Computer Use Docs](https://platform.openai.com/docs/guides/tools-computer-use)
- [Playwright Documentation](https://playwright.dev/python/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional providers (Azure OpenAI, AWS Bedrock)
- Enhanced task detection algorithms
- Better error recovery
- More comprehensive metrics
- UI dashboard for monitoring

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Built on [Anthropic's Computer Use Reference Implementation](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo)
- Inspired by OpenAI's Computer Use capabilities
- Uses Playwright for reliable browser automation
