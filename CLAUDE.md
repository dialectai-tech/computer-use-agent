# Computer Use Automation - Simplified MCP Multi-Agent Architecture

## Overview

A simplified, production-ready implementation of autonomous browser automation using **Claude (Haiku/Sonnet) via AWS Bedrock** with **MCP (Model Context Protocol)** servers and a **multi-agent coordinator** pattern.

**Key Principles:**
- ✅ **Start minimal, expand when needed** - No premature abstraction
- ✅ **Direct MCP integration** - No unnecessary wrapper layers
- ✅ **AWS Bedrock only** - Claude Haiku/Sonnet via AWS
- ✅ **Coordinator pattern** - Simple delegation to MCP servers
- ✅ **2-3 MCP servers max** - Focus on essential tools

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Host Machine (Python Application)                          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  CoordinatorAgent                                      │ │
│  │  - Maintains conversation state                        │ │
│  │  - Tracks critical facts (codes, selectors)           │ │
│  │  - Delegates to MCP servers (no worker wrappers)      │ │
│  │  - Context-aware recovery                             │ │
│  └───────────┬────────────────────────────────────────────┘ │
│              │                                               │
│              │  Tool Calls                                   │
│              ▼                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  MCP Servers (2-3 max)                                 │ │
│  │  ┌──────────────────┐  ┌──────────────────┐          │ │
│  │  │ Playwright MCP   │  │ Filesystem MCP   │          │ │
│  │  │ - Browser actions│  │ - Read/write     │          │ │
│  │  │ - Screenshots    │  │ - Session state  │          │ │
│  │  │ - Navigation     │  │ (optional)       │          │ │
│  │  └──────────────────┘  └──────────────────┘          │ │
│  └────────────────────────────────────────────────────────┘ │
│              │                                               │
│              │  Results                                      │
│              ▼                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  AWS Bedrock (Claude Haiku/Sonnet)                     │ │
│  │  - Sonnet: Better reasoning, complex tasks             │ │
│  │  - Haiku: Faster, cheaper, simple tasks               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Why This Architecture?

### Lessons from Previous Implementation

**Previous approach (Phase 1-3):**
- ❌ Created 5 workers upfront (BrowserWorker, MemoryWorker, AnalysisWorker, DiffWorker, etc.)
- ❌ Multiple abstraction layers (BrowserInterface, custom tool wrappers)
- ❌ Custom tools (DOMTool, SearchTool) wrapping MCP
- ❌ Workers created but never used
- ❌ Complex before proven necessary

**New approach (Simplified):**
- ✅ No workers initially - direct MCP calls
- ✅ Zero abstraction layers - call MCP native APIs
- ✅ Use MCP servers directly (Playwright, Filesystem)
- ✅ Add workers only when delegation needed
- ✅ Simple before complex

---

## Components

### 1. CoordinatorAgent (Simple)

**Responsibilities:**
- Maintain conversation with Claude
- Track critical facts (codes, selectors, completed steps)
- Execute tool calls via MCP servers
- Provide context-aware recovery prompts

**NOT responsible for:**
- Worker delegation (no workers yet)
- Complex state management
- Inter-agent communication

```python
class CoordinatorAgent:
    def __init__(self, bedrock_client, mcp_servers):
        self.bedrock = bedrock_client
        self.mcp_servers = mcp_servers
        self.critical_facts = {
            "codes": [],
            "selectors": {},
            "completed": []
        }
        self.conversation = []

    async def run_task(self, goal: str):
        while not done:
            # Get Claude response
            response = await self.bedrock.generate(self.conversation)

            # Execute tool calls via MCP
            for tool_call in response.tool_calls:
                result = await self.execute_mcp_tool(tool_call)

            # Extract and track critical facts
            self.extract_facts(result)
```

### 2. MCP Servers (2-3 Maximum)

**Primary: Playwright MCP** (`@playwright/mcp`)
- Browser automation (click, type, navigate)
- DOM queries and manipulation
- Screenshot capture
- Accessibility tree access
- Native Playwright tools - no wrappers

**Optional: Filesystem MCP**
- Read/write files
- Store session state
- Log results

**Optional: Memory MCP (custom)**
- Simple key-value storage
- Persistent facts across sessions

### 3. AWS Bedrock Integration

**Models:**
- **Haiku** (`claude-3-5-haiku-20241022-v1:0`): Fast, cheap, good for simple tasks
- **Sonnet** (`claude-sonnet-4-5`): Smart, better reasoning, complex tasks

**Authentication:**
- AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
- AWS_BEARER_TOKEN_BEDROCK
- IAM role (EC2/ECS)

---

## File Structure

```
src/cua/
├── coordinator/
│   ├── __init__.py
│   ├── agent.py              # CoordinatorAgent
│   └── facts_tracker.py      # Critical facts extraction
├── mcp/
│   ├── __init__.py
│   ├── client.py             # Generic MCP client
│   └── playwright_client.py  # Playwright-specific helpers
├── providers/
│   ├── __init__.py
│   ├── base.py               # Base provider interface
│   └── bedrock.py            # AWS Bedrock provider
├── prompts/
│   ├── system.py             # System prompts
│   └── recovery.py           # Recovery prompts
└── main.py                   # CLI entry point
```

**Total: ~8 files** (vs 20+ in previous implementation)

---

## Usage

### Basic Command

```bash
cua --url "https://example.com" \
    --prompt "Fill out the contact form" \
    --model haiku \
    --max-iterations 50
```

### With Sonnet

```bash
cua --url "https://complex-app.com" \
    --prompt "Complete multi-step workflow" \
    --model sonnet \
    --max-iterations 100
```

### Full Options

```bash
cua --url "https://example.com" \
    --prompt "Complete task" \
    --model haiku \
    --max-iterations 50 \
    --display-width 1280 \
    --display-height 720 \
    --zoom 100 \
    --record-video \
    --enable-caching
```

---

## Critical Facts Tracking

Simple pattern matching to extract and persist important information:

```python
critical_facts = {
    "codes": ["ABC123", "XYZ789"],           # Alphanumeric codes
    "selectors": {
        "inputs": ["input#email", "input#name"],
        "buttons": ["button#submit"]
    },
    "completed": ["Step 1", "Step 2"]         # Completed tasks
}
```

**Extraction logic:**
- Codes: Regex `[A-Z0-9]{4,10}`
- Input fields: Search context contains "input", "field", "enter"
- Buttons: Search context contains "submit", "button", "continue"

---

## Recovery Strategy

### Context-Aware Recovery Prompts

**When AI has all pieces:**
```
⚠️ NO ACTIONS PROVIDED - You have ALL the pieces!

✓ Code found: ABC123
✓ Input selector: input#code-field
✓ Submit button: button#submit

EXECUTE NOW:
1. Fill: fill_selector(selector="input#code-field", text="ABC123")
2. Click: click_selector(selector="button#submit")
```

**When AI has partial info:**
```
⚠️ NO ACTIONS PROVIDED

Your last action: Found "Submit" button

NEXT STEPS:
- If found popup: Use find_selectors(search_text="X") to find close button
- If found button: Use click_selector to click it
- If stuck: Try coordinate click at visible button position
```

---

## MCP Server Setup

### Install Playwright MCP

```bash
npm install -g @playwright/mcp
```

### Configure in main.py

```python
from mcp import MCPClient

# Initialize Playwright MCP client
playwright_mcp = MCPClient("playwright")
await playwright_mcp.connect("npx @playwright/mcp")

# Available tools from Playwright MCP:
# - browser_navigate
# - browser_click
# - browser_type
# - browser_screenshot
# - browser_find_selectors
# - browser_evaluate_js
```

### Direct Tool Calls (No Wrappers)

```python
# Before (Phase 1-3): Custom wrapper
from cua.tools.dom_tool import DOMTool
dom_tool = DOMTool(browser)
result = dom_tool.find_selectors("Submit")

# After (Simplified): Direct MCP call
result = await playwright_mcp.call_tool("browser_find_selectors", {
    "search_text": "Submit"
})
```

---

## Development Phases

### Phase 1: Minimal Viable (Day 1-2)
- ✅ CoordinatorAgent with basic loop
- ✅ Bedrock integration (Haiku/Sonnet)
- ✅ Direct Playwright MCP client
- ✅ Simple critical facts tracking
- ✅ ONE simple task working (form fill)

### Phase 2: Enhanced (Day 3-4)
- ✅ Context-aware recovery prompts
- ✅ Improved fact extraction
- ✅ Token usage optimization
- ✅ Test with 3+ different tasks

### Phase 3: Production (Day 5+)
- ✅ Add workers IF delegation needed
- ✅ Add more MCP servers IF needed
- ✅ Production logging and monitoring
- ✅ Documentation complete

---

## Testing Strategy

### Start Simple

**Test 1: Simple Form Fill**
- Navigate to form
- Find input fields
- Fill fields
- Submit
- **Goal:** Validate basic flow works

**Test 2: Login Flow**
- Find username/password fields
- Enter credentials
- Click login
- Verify success
- **Goal:** Multi-step validation

**Test 3: Search & Extract**
- Navigate to site
- Search for term
- Extract results
- **Goal:** Read + write operations

### Then Scale

**Test 4+: Complex Workflows**
- Multi-step processes
- Error recovery
- Edge cases

---

## Configuration

### Environment Variables

```bash
# AWS Bedrock (Required)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# Optional
BEDROCK_MODEL=haiku  # or sonnet
MAX_ITERATIONS=50
DISPLAY_WIDTH=1280
DISPLAY_HEIGHT=720
BROWSER_ZOOM=100
```

### .env Example

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1

# Model Selection
BEDROCK_MODEL=haiku

# Browser Settings
DISPLAY_WIDTH=1280
DISPLAY_HEIGHT=720
BROWSER_ZOOM=100

# Automation Settings
MAX_ITERATIONS=50
CONTEXT_WINDOW_SIZE=10
```

---

## Key Differences from Phase 1-3

| Aspect | Phase 1-3 | Simplified |
|--------|-----------|------------|
| **Workers** | 5 created upfront | 0 (direct MCP) |
| **Abstraction** | Multiple layers | None |
| **Tool Wrappers** | Custom (DOMTool, etc.) | MCP native |
| **Models** | Haiku via custom loop | Haiku/Sonnet via Bedrock |
| **MCP Integration** | Wrapper classes | Direct calls |
| **Files** | 20+ new files | 8 files |
| **LOC** | 2000+ | ~500 |
| **Complexity** | High upfront | Low, expand as needed |

---

## Future Enhancements (When Needed)

### Add Workers
- Only when delegation truly needed
- Start with one worker (e.g., BrowserWorker)
- Add more only if proven necessary

### Add MCP Servers
- Memory server for persistence
- Custom domain-specific servers
- Only when current servers insufficient

### Add Monitoring
- Token usage tracking
- Performance metrics
- Error analytics

---

## References

### MCP Resources
- Playwright MCP: `@playwright/mcp`
- MCP Protocol: https://modelcontextprotocol.io
- MCP Servers: https://github.com/modelcontextprotocol/servers

### AWS Bedrock
- Bedrock Documentation: https://docs.aws.amazon.com/bedrock/
- Claude Models: Haiku 3.5, Sonnet 4.5
- Authentication: IAM roles, access keys

### Previous Implementation
- Branch: `phase-1-multi-agent-foundation`
- Documentation: `PHASE1_FINAL_STATE.md`
- Preserved for reference

---

## Philosophy

> "Make it work, make it right, make it fast" - Kent Beck

This implementation focuses on **making it work first** with minimal complexity, then iterating based on real needs rather than imagined requirements.

**Principles:**
- YAGNI (You Aren't Gonna Need It)
- Start simple, add complexity when proven necessary
- Direct integration over abstraction
- Real problems over theoretical solutions
