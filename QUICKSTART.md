# Quick Start Guide

Get up and running with Computer Use Automation in 5 minutes.

## Prerequisites Check

```bash
# Verify uv is installed
uv --version

# Verify Docker is installed
docker --version

# Verify Python version
python3 --version  # Should be 3.10+
```

## Step 1: Clone and Setup

```bash
cd /home/azureuser/projects/cua-project

# Create environment file
cp .env.example .env

# Edit .env and add your API keys
nano .env
# or
vim .env
```

## Step 2: Add API Keys

Edit `.env` and add at minimum:

```bash
# For Claude
ANTHROPIC_API_KEY=sk-ant-your-key-here
PROVIDER=claude
DEFAULT_MODEL=claude-sonnet-4-5

# OR for OpenAI
OPENAI_API_KEY=sk-your-key-here
PROVIDER=openai
DEFAULT_MODEL=computer-use-preview
```

## Step 3: Install Dependencies

```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install the package
uv pip install -e .

# Install Playwright browsers (important!)
playwright install chromium
playwright install-deps chromium
```

## Step 4: Build Docker Container

```bash
cd docker

# Build the container
docker-compose build

# Start the container
docker-compose up -d

# Verify it's running
docker ps | grep cua-browser

# Check logs
docker-compose logs -f
```

Expected output:
```
cua-browser | Starting Computer Use Automation Browser Container...
cua-browser | Waiting for X server...
cua-browser | X server is ready!
cua-browser | Container is ready for automation!
```

## Step 5: Test Basic Functionality

### Test 1: Simple Screenshot

Create `test_basic.py`:

```python
from playwright.sync_api import sync_playwright
import base64

def test_screenshot():
    with sync_playwright() as p:
        # Connect to browser in Docker
        browser = p.chromium.launch(
            executable_path="/usr/bin/chromium-browser"
        )
        page = browser.new_page()
        page.goto("https://example.com")

        # Take screenshot
        screenshot = page.screenshot()

        print(f"Screenshot size: {len(screenshot)} bytes")
        print("✓ Basic screenshot test passed!")

        browser.close()

if __name__ == "__main__":
    test_screenshot()
```

Run it:
```bash
python test_basic.py
```

### Test 2: Simple Claude API Test

Create `test_claude.py`:

```python
import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

def test_claude_api():
    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": "Say 'API connection successful!' and nothing else."
        }]
    )

    print(f"Response: {response.content[0].text}")
    print("✓ Claude API test passed!")

if __name__ == "__main__":
    test_claude_api()
```

Run it:
```bash
python test_claude.py
```

### Test 3: OpenAI API Test (if using OpenAI)

Create `test_openai.py`:

```python
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def test_openai_api():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "user",
            "content": "Say 'API connection successful!' and nothing else."
        }],
        max_tokens=100
    )

    print(f"Response: {response.choices[0].message.content}")
    print("✓ OpenAI API test passed!")

if __name__ == "__main__":
    test_openai_api()
```

Run it:
```bash
python test_openai.py
```

## Step 6: Run Your First Task

### Example Task File

Create `example_task.py`:

```python
"""
Example Computer Use Automation Task

This demonstrates how to:
1. Navigate to a webpage
2. Fill out a form
3. Submit it
4. Verify completion
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Task configuration
TASK_CONFIG = {
    "url": "https://httpbin.org/forms/post",
    "prompt": """
    Navigate to the form on this page and complete the following steps:

    1. Take a screenshot to see the form
    2. Fill in the following information:
       - Customer name: John Doe
       - Telephone: 555-1234
       - Email: john.doe@example.com
       - Size: Medium
       - Topping: Cheese
       - Delivery time: ASAP
       - Comments: Please ring the doorbell

    3. Click the submit button
    4. Take a screenshot of the result page
    5. Verify that the submission was successful

    After each step, take a screenshot and verify it worked correctly
    before proceeding to the next step.
    """,
    "max_iterations": 20,
    "provider": os.getenv("PROVIDER", "claude"),
    "model": os.getenv("DEFAULT_MODEL", "claude-sonnet-4-5"),
}

if __name__ == "__main__":
    print("Example task configuration:")
    print(f"  URL: {TASK_CONFIG['url']}")
    print(f"  Provider: {TASK_CONFIG['provider']}")
    print(f"  Model: {TASK_CONFIG['model']}")
    print("\nTo run this task, use:")
    print(f"  python -m cua.main --url '{TASK_CONFIG['url']}' \\")
    print(f"      --prompt '{TASK_CONFIG['prompt'][:50]}...' \\")
    print(f"      --max-iterations {TASK_CONFIG['max_iterations']}")
```

## Step 7: View Agent in Action (Optional)

### Option A: VNC Viewer

On your local machine:

```bash
# Create SSH tunnel to Azure VM
ssh -L 5900:localhost:5900 azureuser@<your-azure-vm-ip>

# Keep this terminal open
```

Then connect with a VNC viewer:
- **Windows**: Download RealVNC Viewer, TightVNC, or UltraVNC
- **Mac**: Use built-in Screen Sharing (cmd+K in Finder: `vnc://localhost:5900`)
- **Linux**: `vncviewer localhost:5900`

Password: `changeme` (or what you set in `.env`)

### Option B: Session Recording

Recordings are automatically saved to `./recordings/` if enabled in `.env`:

```bash
# View recordings
ls -lh recordings/

# Play with VLC or any video player
vlc recordings/session_*.mp4
```

## Example Real-World Tasks

### Task 1: Search and Screenshot

```bash
python -m cua.main \
  --url "https://www.google.com" \
  --prompt "Search for 'anthropic claude' and take a screenshot of the results"
```

### Task 2: Form Filling

```bash
python -m cua.main \
  --url "https://httpbin.org/forms/post" \
  --prompt "Fill out the pizza order form with test data and submit it"
```

### Task 3: Multi-Page Navigation

```bash
python -m cua.main \
  --url "https://demo.playwright.dev/todomvc/" \
  --prompt "Add three todo items: 'Buy milk', 'Walk dog', 'Write code', then mark the first one as complete"
```

## Troubleshooting

### Issue: Docker container won't start

```bash
# Check logs
docker-compose -f docker/docker-compose.yml logs

# Rebuild
docker-compose -f docker/docker-compose.yml down
docker-compose -f docker/docker-compose.yml build --no-cache
docker-compose -f docker/docker-compose.yml up -d
```

### Issue: Can't connect to VNC

```bash
# Check if VNC is running
docker exec cua-browser ps aux | grep vnc

# Restart VNC
docker exec cua-browser supervisorctl restart x11vnc

# Check port forwarding
netstat -tuln | grep 5900
```

### Issue: API errors

```bash
# Verify API keys are set
source .env
echo $ANTHROPIC_API_KEY  # Should show your key
echo $OPENAI_API_KEY     # Should show your key

# Test API directly
python test_claude.py
python test_openai.py
```

### Issue: Playwright errors

```bash
# Reinstall Playwright
pip uninstall playwright
pip install playwright==1.48.0
playwright install chromium
playwright install-deps chromium
```

## Next Steps

1. **Read the full documentation**: See [README.md](./README.md)
2. **Understand the architecture**: See [CLAUDE.md](./CLAUDE.md)
3. **Create custom tasks**: Use the examples as templates
4. **Experiment with models**: Try different Claude models or OpenAI
5. **Monitor performance**: Check metrics and recordings

## Common Commands

```bash
# Start container
docker-compose -f docker/docker-compose.yml up -d

# Stop container
docker-compose -f docker/docker-compose.yml down

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# Restart container
docker-compose -f docker/docker-compose.yml restart

# Check status
docker ps

# Enter container for debugging
docker exec -it cua-browser bash

# View recordings
ls -lh recordings/

# Clean up old recordings
rm recordings/session_*.mp4
```

## Getting Help

- **Documentation**: [README.md](./README.md) and [CLAUDE.md](./CLAUDE.md)
- **API Docs**:
  - Claude: https://docs.anthropic.com/
  - OpenAI: https://platform.openai.com/docs/
- **Issues**: Check the project issues on GitHub
- **Community**: Join discussions in the project repository

---

**Ready to automate!** 🚀

If all tests passed, you're ready to run real automation tasks. Start with simple tasks and gradually increase complexity as you get familiar with the system.
