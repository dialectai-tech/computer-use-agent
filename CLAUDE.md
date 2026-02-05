# Computer Use Automation - Multi-Provider Implementation Guide

## Overview

This document provides comprehensive information for implementing an automated browser task completion system using both **Anthropic Claude** and **OpenAI** Computer Use APIs with a unified interface. The system will:

1. Run a browser within an isolated Docker container
2. Connect to specified URLs and read webpage instructions
3. Complete tasks defined on those pages (forms, navigation, data entry, etc.)
4. Use Claude's Computer Use API to determine next actions based on screenshots and web content
5. Loop until all tasks are completed

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Host Machine (Python Application)                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Agent Loop (Python)                                   │ │
│  │  - Calls Claude API with screenshots                  │ │
│  │  - Receives action commands                           │ │
│  │  - Executes actions via Docker API                    │ │
│  └────────────┬───────────────────────────▲───────────────┘ │
│               │                           │                 │
│               │ Send Actions              │ Return Results  │
│               ▼                           │                 │
│  ┌────────────────────────────────────────┴───────────────┐ │
│  │  Docker Container (Isolated Environment)              │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Xvfb (Virtual Display)                          │ │ │
│  │  │  - X11 display server                            │ │ │
│  │  │  - 1024x768 or 1280x720 resolution              │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Desktop Environment                             │ │ │
│  │  │  - Window manager (e.g., Mutter, Fluxbox)        │ │ │
│  │  │  - Firefox/Chromium browser                      │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Tool Implementations                            │ │ │
│  │  │  - Screenshot capture (via Xvfb)                 │ │ │
│  │  │  - Mouse/keyboard control (xdotool, pyautogui)   │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Claude Computer Use API

### Key Features

- **Beta Feature**: Requires beta header `computer-use-2025-01-24`
- **Model Support**: Claude Sonnet 4.5, Haiku 4.5, Opus 4.5, and others
- **Actions**: Screenshot, mouse clicks, keyboard input, scrolling, dragging
- **Tool Type**: `computer_20250124` (or `computer_20251124` for Opus 4.5)

### API Request Structure

```python
import anthropic

client = anthropic.Anthropic(api_key="YOUR_API_KEY")

response = client.beta.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    tools=[
        {
            "type": "computer_20250124",
            "name": "computer",
            "display_width_px": 1024,
            "display_height_px": 768,
            "display_number": 1,
        },
        {
            "type": "bash_20250124",
            "name": "bash"
        }
    ],
    messages=[{"role": "user", "content": "Navigate to example.com and fill the form"}],
    betas=["computer-use-2025-01-24"]
)
```

### Available Actions

#### Basic Actions (all versions)
- `screenshot` - Capture current display
- `left_click` - Click at coordinates `[x, y]`
- `type` - Type text string
- `key` - Press key or key combination (e.g., "ctrl+s")
- `mouse_move` - Move cursor to coordinates

#### Enhanced Actions (computer_20250124)
- `scroll` - Scroll in any direction with amount control
- `left_click_drag` - Click and drag between coordinates
- `right_click`, `middle_click` - Additional mouse buttons
- `double_click`, `triple_click` - Multiple clicks
- `left_mouse_down`, `left_mouse_up` - Fine-grained click control
- `hold_key` - Hold down a key for specified duration
- `wait` - Pause between actions

#### Example Actions

```json
// Take a screenshot
{"action": "screenshot"}

// Click at position
{"action": "left_click", "coordinate": [500, 300]}

// Type text
{"action": "type", "text": "Hello, world!"}

// Scroll down
{"action": "scroll", "coordinate": [500, 400], "scroll_direction": "down", "scroll_amount": 3}

// Press Enter key
{"action": "key", "text": "Return"}

// Keyboard shortcut
{"action": "key", "text": "ctrl+c"}
```

## Implementation Components

### 1. Docker Environment Setup

**Dockerfile Requirements:**
- Base: Ubuntu/Debian with X11 support
- Xvfb (virtual framebuffer)
- Desktop environment (lightweight: Fluxbox, OpenBox, or full: GNOME/KDE)
- Web browser (Firefox or Chromium)
- Python tools: pyautogui, xdotool, PIL (for screenshots)
- VNC server (optional, for debugging/viewing)

**Example Dockerfile structure:**
```dockerfile
FROM ubuntu:22.04

# Install X11, Xvfb, window manager
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    fluxbox \
    firefox \
    xdotool \
    scrot \
    python3 \
    python3-pip

# Install Python dependencies
RUN pip3 install pyautogui pillow

# Set display environment
ENV DISPLAY=:1
ENV DISPLAY_WIDTH=1024
ENV DISPLAY_HEIGHT=768

# Start Xvfb and window manager
CMD Xvfb :1 -screen 0 ${DISPLAY_WIDTH}x${DISPLAY_HEIGHT}x24 & \
    fluxbox & \
    firefox &
```

### 2. Tool Implementations

**Screenshot Tool:**
```python
import base64
from PIL import Image
import subprocess

def capture_screenshot():
    """Capture screenshot from Xvfb display"""
    # Use scrot or import command
    subprocess.run(["scrot", "/tmp/screenshot.png"], check=True)

    # Read and encode as base64
    with open("/tmp/screenshot.png", "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": image_data
        }
    }
```

**Mouse/Keyboard Control:**
```python
import pyautogui
import subprocess

def execute_action(action_type, params):
    """Execute computer use action"""
    if action_type == "left_click":
        x, y = params["coordinate"]
        subprocess.run(["xdotool", "mousemove", str(x), str(y)])
        subprocess.run(["xdotool", "click", "1"])
        return "Click executed"

    elif action_type == "type":
        text = params["text"]
        subprocess.run(["xdotool", "type", "--", text])
        return f"Typed: {text}"

    elif action_type == "key":
        key = params["text"]
        subprocess.run(["xdotool", "key", key])
        return f"Pressed key: {key}"

    elif action_type == "scroll":
        direction = params.get("scroll_direction", "down")
        amount = params.get("scroll_amount", 1)

        # Map scroll direction to button clicks
        button = "4" if direction == "up" else "5"
        for _ in range(amount):
            subprocess.run(["xdotool", "click", button])
        return f"Scrolled {direction} by {amount}"

    elif action_type == "screenshot":
        return capture_screenshot()

    else:
        return f"Unknown action: {action_type}"
```

### 3. Agent Loop Implementation

```python
import anthropic
import time

class ComputerUseAgent:
    def __init__(self, api_key, display_width=1024, display_height=768):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.display_width = display_width
        self.display_height = display_height
        self.messages = []

    def run_task(self, initial_prompt, max_iterations=20):
        """Main agent loop"""
        self.messages = [{"role": "user", "content": initial_prompt}]

        for iteration in range(max_iterations):
            print(f"\n=== Iteration {iteration + 1} ===")

            # Call Claude API
            response = self.client.beta.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                tools=[
                    {
                        "type": "computer_20250124",
                        "name": "computer",
                        "display_width_px": self.display_width,
                        "display_height_px": self.display_height,
                        "display_number": 1,
                    },
                    {
                        "type": "bash_20250124",
                        "name": "bash"
                    }
                ],
                messages=self.messages,
                betas=["computer-use-2025-01-24"]
            )

            # Add assistant response to messages
            self.messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Check for tool use
            tool_results = []
            has_tool_use = False

            for block in response.content:
                if block.type == "tool_use":
                    has_tool_use = True
                    print(f"Tool: {block.name}, Action: {block.input.get('action', 'N/A')}")

                    # Execute the tool
                    result = self.execute_tool(block.name, block.input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

                elif block.type == "text":
                    print(f"Claude: {block.text}")

            # If no tools used, task is complete
            if not has_tool_use:
                print("\n✓ Task completed!")
                return True

            # Add tool results for next iteration
            self.messages.append({
                "role": "user",
                "content": tool_results
            })

            # Small delay between actions
            time.sleep(0.5)

        print("\n✗ Max iterations reached")
        return False

    def execute_tool(self, tool_name, tool_input):
        """Execute tool and return results"""
        if tool_name == "computer":
            return execute_action(tool_input["action"], tool_input)

        elif tool_name == "bash":
            command = tool_input["command"]
            # Execute bash command in container
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True
            )
            return result.stdout + result.stderr

        return "Unknown tool"
```

### 4. Usage Example

```python
# Initialize agent
agent = ComputerUseAgent(api_key="your-api-key")

# Define task
task = """
Navigate to https://example.com/task-page
Read the instructions on the page carefully.
Complete all tasks listed on the page, which may include:
- Filling out forms
- Clicking buttons
- Navigating to other pages
- Copying and pasting data
- Submitting forms

After each step, take a screenshot and verify the action was successful.
Continue until all tasks are completed.
"""

# Run the task
agent.run_task(task)
```

## Best Practices

### 1. Prompting Tips

- **Be Explicit**: Specify step-by-step instructions
- **Request Verification**: Ask Claude to take screenshots after each action
- **Handle Errors**: Prompt Claude to verify success and retry if needed

Example prompt:
```
After each step, take a screenshot and carefully evaluate if you have achieved
the right outcome. Explicitly show your thinking: "I have evaluated step X..."
If not correct, try again. Only when you confirm a step was executed correctly
should you move on to the next one.
```

### 2. Security Considerations

- **Isolation**: Always run in Docker container with minimal privileges
- **No Sensitive Data**: Don't provide login credentials unless necessary
- **Allowlist Domains**: Limit internet access to trusted domains
- **Human Oversight**: Confirm actions with meaningful consequences

### 3. Coordinate Scaling

For high-resolution displays (>1568px), implement coordinate scaling:

```python
import math

def get_scale_factor(width, height):
    """Calculate scale factor for API constraints"""
    long_edge = max(width, height)
    total_pixels = width * height

    long_edge_scale = 1568 / long_edge
    total_pixels_scale = math.sqrt(1_150_000 / total_pixels)

    return min(1.0, long_edge_scale, total_pixels_scale)

# When capturing screenshot
scale = get_scale_factor(screen_width, screen_height)
scaled_width = int(screen_width * scale)
scaled_height = int(screen_height * scale)

# Resize before sending to Claude
screenshot = capture_and_resize(scaled_width, scaled_height)

# Scale coordinates back when executing clicks
def execute_click(x, y):
    screen_x = x / scale
    screen_y = y / scale
    perform_click(screen_x, screen_y)
```

### 4. Error Handling

```python
def execute_action_with_error_handling(action_type, params):
    try:
        result = execute_action(action_type, params)
        return result
    except Exception as e:
        return {
            "content": f"Error executing {action_type}: {str(e)}",
            "is_error": True
        }
```

## Limitations

### Current Beta Limitations

1. **Latency**: Higher than human-directed actions
2. **Coordinate Accuracy**: May make mistakes with precise clicks
3. **Tool Selection**: May choose unexpected tools for tasks
4. **Scrolling**: Improved in Sonnet 3.7 but may still have issues
5. **Prompt Injection**: Claude may follow instructions found in web content
6. **Account Creation**: Limited on social media platforms

### Mitigation Strategies

- Use thinking capability (extended reasoning) for complex tasks
- Add delays between actions for UI updates
- Implement retry logic for failed actions
- Validate critical actions before execution
- Keep human in the loop for important decisions

## Token Costs

### System Prompt Overhead
- Computer use beta: 466-499 tokens

### Tool Definition Costs
- Computer tool: 735 tokens per request
- Bash tool: Additional tokens (see bash tool docs)

### Additional Costs
- Screenshots: Based on image size (see Vision pricing)
- Tool results: Varies by output size

## Reference Implementation

Anthropic provides a complete reference implementation:
- **GitHub**: https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo
- **Includes**: Docker setup, tool implementations, web UI, agent loop

## Next Steps

1. **Set up Docker environment** with Xvfb and browser
2. **Implement tool handlers** for computer actions
3. **Create agent loop** with Claude API integration
4. **Test with simple tasks** (e.g., navigate to URL, take screenshot)
5. **Iterate and improve** based on results
6. **Add web content extraction** (HTML, text) for enhanced context

## Additional Enhancements

### Web Content Extraction

To provide Claude with both screenshots and web content:

```python
from selenium import webdriver

def get_page_content():
    """Extract HTML/text from current page"""
    driver = webdriver.Firefox()  # Running in Docker

    return {
        "html": driver.page_source,
        "text": driver.find_element_by_tag_name("body").text,
        "url": driver.current_url,
        "title": driver.title
    }

# Include in tool results
def capture_screenshot_with_content():
    screenshot = capture_screenshot()
    content = get_page_content()

    return {
        "screenshot": screenshot,
        "page_content": content
    }
```

### Enhanced Prompting

```python
initial_prompt = f"""
Navigate to {target_url} and complete the tasks listed on the page.

For each task:
1. Take a screenshot to see the current state
2. Read any instructions on the page
3. Determine the next action needed
4. Execute the action
5. Verify the action was successful
6. Proceed to the next task

Be methodical and verify each step before moving forward.
"""
```

## Questions to Address

1. **Target URL**: What is the specific URL you want to test with?
2. **Task Complexity**: What types of tasks are expected (simple forms, multi-page workflows)?
3. **Authentication**: Will the pages require login credentials?
4. **Success Criteria**: How do we know when all tasks are completed?
5. **Monitoring**: Do you need a UI to watch the progress, or is logging sufficient?

## Provider Comparison: Claude vs OpenAI

### API Differences

| Feature | Claude (Anthropic) | OpenAI |
|---------|-------------------|--------|
| **API Type** | Messages API (`beta.messages.create`) | Responses API (`responses.create`) |
| **Beta Header** | `computer-use-2025-01-24` | Not required |
| **Model Names** | `claude-sonnet-4-5`, `claude-opus-4-5`, `claude-haiku-4-5` | `computer-use-preview` |
| **Tool Type** | `computer_20250124` | `computer_use_preview` |
| **Display Params** | `display_width_px`, `display_height_px`, `display_number` | `display_width`, `display_height`, `environment` |
| **Environment Options** | X11 display number | `browser`, `mac`, `windows`, `ubuntu` |
| **Conversation Style** | Message turns with `role: assistant/user` | `previous_response_id` linking |
| **Tool Results** | `tool_result` content block | `computer_call_output` |
| **Screenshot Format** | Base64 in `tool_result` | Base64 in `input_image` |
| **Thinking/Reasoning** | Optional `thinking` parameter | Built-in `reasoning` items |

### Action Types Comparison

| Action | Claude | OpenAI | Notes |
|--------|--------|--------|-------|
| Screenshot | ✅ `screenshot` | ✅ `screenshot` | Same |
| Click | ✅ `left_click` | ✅ `click` | Similar |
| Double Click | ✅ `double_click` | ✅ `double_click` | Same |
| Right Click | ✅ `right_click` | ✅ `click` (with button param) | Different approach |
| Type Text | ✅ `type` | ✅ `type` | Same |
| Key Press | ✅ `key` | ✅ `keypress` | Different name |
| Scroll | ✅ `scroll` (direction + amount) | ✅ `scroll` (scrollX, scrollY) | Different params |
| Mouse Move | ✅ `mouse_move` | ⚠️ Implicit in actions | Different |
| Wait | ✅ `wait` | ✅ `wait` | Same |
| Drag | ✅ `left_click_drag` | ⚠️ Mouse events | Different |
| Zoom | ✅ `zoom` (Opus 4.5 only) | ❌ Not available | Claude exclusive |

### Code Examples: Same Task, Different Providers

#### Claude Implementation

```python
import anthropic

client = anthropic.Anthropic(api_key="sk-ant-...")

# Initial request
response = client.beta.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=2048,
    tools=[{
        "type": "computer_20250124",
        "name": "computer",
        "display_width_px": 1280,
        "display_height_px": 720,
        "display_number": 1,
    }],
    messages=[{
        "role": "user",
        "content": "Navigate to example.com and click the signup button"
    }],
    betas=["computer-use-2025-01-24"]
)

# Extract tool use
messages = [{"role": "user", "content": "..."}]
messages.append({"role": "assistant", "content": response.content})

# Execute action and get screenshot
screenshot_b64 = capture_screenshot()

# Continue conversation
messages.append({
    "role": "user",
    "content": [{
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": [{
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": screenshot_b64
            }
        }]
    }]
})

# Next iteration
response = client.beta.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=2048,
    tools=[...],
    messages=messages,
    betas=["computer-use-2025-01-24"]
)
```

#### OpenAI Implementation

```python
from openai import OpenAI

client = OpenAI(api_key="sk-...")

# Initial request
response = client.responses.create(
    model="computer-use-preview",
    tools=[{
        "type": "computer_use_preview",
        "display_width": 1280,
        "display_height": 720,
        "environment": "browser"
    }],
    input=[{
        "role": "user",
        "content": [{
            "type": "input_text",
            "text": "Navigate to example.com and click the signup button"
        }]
    }]
)

# Execute action and get screenshot
screenshot_b64 = capture_screenshot()

# Continue with previous_response_id
response = client.responses.create(
    model="computer-use-preview",
    previous_response_id=response.id,  # Key difference!
    tools=[{
        "type": "computer_use_preview",
        "display_width": 1280,
        "display_height": 720,
        "environment": "browser"
    }],
    input=[{
        "role": "tool",
        "content": [{
            "type": "computer_use_preview",
            "computer_call_id": call_id,
            "content": [{
                "type": "computer_call_output",
                "output": [{
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{screenshot_b64}"
                }]
            }]
        }]
    }]
)
```

### Unified Implementation Strategy

To support both providers with minimal code duplication:

```python
from abc import ABC, abstractmethod

class ComputerUseProvider(ABC):
    """Base class for computer use providers"""

    @abstractmethod
    def create_initial_request(self, prompt: str, screenshot: str = None):
        """Create initial API request"""
        pass

    @abstractmethod
    def create_continuation_request(self, screenshot: str, action_result: dict):
        """Create continuation request with tool results"""
        pass

    @abstractmethod
    def extract_actions(self, response) -> List[dict]:
        """Extract actions from API response"""
        pass

    @abstractmethod
    def is_complete(self, response) -> bool:
        """Check if task is complete"""
        pass

class ClaudeProvider(ComputerUseProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.messages = []

    def create_initial_request(self, prompt: str, screenshot: str = None):
        content = [{"type": "text", "text": prompt}]
        if screenshot:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot
                }
            })

        self.messages = [{"role": "user", "content": content}]

        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=2048,
            tools=[{
                "type": "computer_20250124",
                "name": "computer",
                "display_width_px": 1280,
                "display_height_px": 720,
                "display_number": 1,
            }],
            messages=self.messages,
            betas=["computer-use-2025-01-24"]
        )

    def extract_actions(self, response) -> List[dict]:
        actions = []
        for block in response.content:
            if block.type == "tool_use":
                actions.append({
                    "id": block.id,
                    "action": block.input.get("action"),
                    "params": block.input
                })
        return actions

class OpenAIProvider(ComputerUseProvider):
    def __init__(self, api_key: str, model: str = "computer-use-preview"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.last_response_id = None

    def create_initial_request(self, prompt: str, screenshot: str = None):
        content = [{"type": "input_text", "text": prompt}]
        if screenshot:
            content.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{screenshot}"
            })

        response = self.client.responses.create(
            model=self.model,
            tools=[{
                "type": "computer_use_preview",
                "display_width": 1280,
                "display_height": 720,
                "environment": "browser"
            }],
            input=[{"role": "user", "content": content}]
        )

        self.last_response_id = response.id
        return response

    def extract_actions(self, response) -> List[dict]:
        actions = []
        for item in response.output:
            if hasattr(item, 'action'):
                actions.append({
                    "id": item.computer_call_id,
                    "action": item.action.type,
                    "params": item.action.__dict__
                })
        return actions

# Usage
def run_task(provider: ComputerUseProvider, url: str, task_prompt: str):
    """Generic task runner for any provider"""
    prompt = f"Navigate to {url} and {task_prompt}"

    # Initial request
    response = provider.create_initial_request(prompt)

    while not provider.is_complete(response):
        # Extract and execute actions
        actions = provider.extract_actions(response)

        for action in actions:
            # Execute action
            result = execute_action(action)

            # Get screenshot
            screenshot = capture_screenshot()

            # Continue
            response = provider.create_continuation_request(screenshot, result)

    return response

# Use with either provider
claude = ClaudeProvider(api_key="sk-ant-...")
result = run_task(claude, "https://example.com", "fill the form")

openai = OpenAIProvider(api_key="sk-...")
result = run_task(openai, "https://example.com", "fill the form")
```

### Performance & Cost Comparison

Based on typical usage patterns:

| Metric | Claude Sonnet 4.5 | Claude Opus 4.5 | Claude Haiku 4.5 | OpenAI Computer Use |
|--------|------------------|-----------------|------------------|---------------------|
| **Speed** | Fast (~2-3s/action) | Slow (~4-5s/action) | Very Fast (~1-2s/action) | Fast (~2-3s/action) |
| **Accuracy** | High | Highest | Good | High |
| **Cost per Task** | Moderate | High | Low | Moderate |
| **Best For** | General purpose | Complex workflows | Simple tasks | OpenAI ecosystem users |

### Choosing the Right Provider

**Use Claude when:**
- Need extended thinking capability
- Require zoom functionality (Opus 4.5)
- Want flexible model selection (Haiku/Sonnet/Opus)
- Prefer conversational message history
- Need fine-grained action control

**Use OpenAI when:**
- Already in OpenAI ecosystem
- Prefer Responses API pattern
- Want built-in reasoning items
- Need different environment types (mac/windows/ubuntu)
- Comfortable with preview model

**Use Both (via Portkey/unified gateway) when:**
- Want to compare performance
- Need fallback options
- Testing which works better for your use case
- Want to optimize cost/performance

## Resources

- **Claude API Docs**: https://docs.anthropic.com/
- **OpenAI Computer Use Docs**: https://platform.openai.com/docs/guides/tools-computer-use
- **Claude Reference Implementation**: https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo
- **Portkey AI Gateway**: https://portkey.ai/
- **Playwright Docs**: https://playwright.dev/python/
