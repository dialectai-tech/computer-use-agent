# Comprehensive Optimization Plan

## Key Finding: A11y Tree May Be Hurting Performance

### Test Comparison
| Metric | With A11y Tree | Without A11y Tree | Difference |
|--------|---------------|-------------------|------------|
| Progress | Step 3 of 30 | Step 6 of 30 | **2x better** |
| Tokens | 4.03M | 4.74M | +18% worse |
| API Time | 5.29s | 6.91s | +30% slower |
| Total Time | 651s | 820s | +26% slower |

**Conclusion**: Removing a11y tree **doubled progress** despite being more expensive. This suggests:
1. A11y tree was adding **noise, not signal**
2. Page text alone is clearer for the AI
3. Complex tree structure confused the agent

## User's Key Questions & Answers

### 1. Why Only Mouse/Type/Keyboard? Can't We Manipulate DOM?

**YES, WE ABSOLUTELY CAN AND SHOULD!**

**Current Approach**:
- Take screenshot → AI sees pixels → AI guesses coordinates → click/type
- **Problem**: Inefficient, error-prone, requires visual reasoning

**Better Approach**: DOM Manipulation
```python
# Instead of this (current):
1. Search for "Submit button" in page text
2. Use browser_find to highlight it
3. Take screenshot
4. Extract coordinates [x, y]
5. Click at coordinates

# Do this (proposed):
1. Search for "Submit button" in DOM
2. Get CSS selector: "#submit-btn"
3. Execute: page.click("#submit-btn")
4. Done in ONE action!
```

**Benefits**:
- **10-100x faster** (no visual reasoning needed)
- **No scrolling needed** (direct element access)
- **No coordinate errors** (CSS selector is precise)
- **Fewer tokens** (no need for screenshots for every action)

### 2. Playwright MCP Analysis

I reviewed https://github.com/microsoft/playwright-mcp. Here's what it offers:

**Playwright MCP Capabilities**:
```json
{
  "tools": [
    "playwright_navigate",           // Navigate to URL
    "playwright_screenshot",         // Take screenshot
    "playwright_click",              // Click by selector (!)
    "playwright_fill",               // Fill input by selector (!)
    "playwright_select",             // Select option by selector (!)
    "playwright_hover",              // Hover by selector
    "playwright_evaluate",           // Run JS in page (!!)
    "playwright_press",              // Press keyboard key
    "playwright_locator_text",       // Get element text by selector
    "playwright_locator_attribute",  // Get element attribute
    "playwright_console_logs",       // Get console logs
    "playwright_network_logs"        // Get network activity
  ]
}
```

**Key Advantages Over Our Current Approach**:

1. **Selector-Based Actions** (vs coordinate-based)
   ```python
   # Current
   {"action": "left_click", "coordinate": [640, 480]}

   # MCP
   {"tool": "playwright_click", "selector": "#submit-btn"}
   ```

2. **Direct DOM Queries** (vs screenshot + vision)
   ```python
   # Current: Extract text from screenshot
   # MCP
   {"tool": "playwright_locator_text", "selector": ".code-display"}
   ```

3. **JavaScript Execution** (vs multi-step clicking)
   ```python
   # MCP can run arbitrary JS
   {"tool": "playwright_evaluate", "script": "document.querySelector('.modal').remove()"}
   ```

**Recommendation**:
- **YES, use Playwright MCP** for selector-based actions
- Keep our current approach as fallback when selectors don't work
- Hybrid: Use selectors when possible, coordinates when necessary

### 3. Two-Tier Agent Architecture

**Your idea about separate text reasoning agent is BRILLIANT!**

**Proposed Architecture**:
```
┌─────────────────────────────────────────────────────────┐
│  Planning Agent (Text-Only, No Context Limits)         │
│  - Analyzes HTML/DOM structure                          │
│  - Reasons about page structure                         │
│  - Plans actions using CSS selectors                    │
│  - Output: Action plan with selectors                   │
└────────────────────┬────────────────────────────────────┘
                     │ Action plan
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Execution Agent (Vision + Actions, Minimal Context)   │
│  - Takes screenshots for verification                   │
│  - Executes actions via selectors or coordinates        │
│  - Handles visual edge cases                            │
│  - Output: Action results                               │
└─────────────────────────────────────────────────────────┘
```

**Benefits**:
- **Planning agent**: Can analyze full HTML without context limits
- **Execution agent**: Only keeps recent history (fast, cheap)
- **Clear separation**: Text reasoning vs visual execution
- **Scalability**: Planning agent can handle complex pages

**Example Flow**:
```
User: "Complete Step 6 - drag and drop puzzle"

Planning Agent (analyzes HTML):
→ "I see 12 draggable pieces with data-letter attributes"
→ "I see 6 drop zones with data-slot-id attributes"
→ "The code must be assembled by dragging letters"
→ "Plan: 1) Get all pieces, 2) Try combinations, 3) Drag to slots"
→ Returns: [
    {action: "evaluate_js", script: "document.querySelectorAll('[data-letter]')..."},
    {action: "drag", from: "[data-letter='D']", to: "[data-slot-id='1']"},
    ...
  ]

Execution Agent:
→ Executes each action using playwright_* tools
→ Takes screenshots only for verification
→ Reports results back
```

## Implementation Plan

### Phase 1: Add Stats & Logging (Your Request)

#### A. Real-Time Token Stats on CLI
```python
# In loop.py, after each API call
def print_token_stats(iteration, stats):
    print(f"\n╭─ Token Usage (Iteration {iteration}) ─────────────────")
    print(f"│ Input Tokens:      {stats.input_tokens:>10,}")
    print(f"│   - System Prompt: {stats.system_tokens:>10,}")
    print(f"│   - Screenshots:   {stats.screenshot_tokens:>10,}")
    print(f"│   - Page Text:     {stats.page_text_tokens:>10,}")
    print(f"│   - A11y Tree:     {stats.tree_tokens:>10,}")
    print(f"│   - AI Responses:  {stats.response_tokens:>10,}")
    print(f"│ Output Tokens:     {stats.output_tokens:>10,}")
    print(f"│ Total Tokens:      {stats.total_tokens:>10,}")
    print(f"│ Cumulative Total:  {stats.cumulative_tokens:>10,}")
    print(f"╰────────────────────────────────────────────────────────")
```

#### B. Conversation Data Structure Dump
```python
# After each iteration, save to separate file
import json

def dump_conversation(iteration, messages, filename):
    dump = {
        "iteration": iteration,
        "timestamp": datetime.now().isoformat(),
        "message_count": len(messages),
        "messages": messages,
        "token_breakdown": calculate_tokens_per_message(messages)
    }

    with open(f"logs/conversation_{filename}_iter{iteration:03d}.json", "w") as f:
        json.dump(dump, f, indent=2)
```

#### C. Increase Viewport Height to 900px
```python
# In main.py, change default
@click.option(
    "--display-height",
    type=int,
    default=lambda: int(os.getenv("DISPLAY_HEIGHT", "900")),  # Changed from 768
    help="Display height in pixels (default: 900)"
)
```

### Phase 2: Implement Playwright MCP Integration

#### A. Add MCP Server Support
```python
# New file: src/cua/tools/playwright_mcp.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class PlaywrightMCPClient:
    """Client for Playwright MCP server."""

    async def __init__(self):
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@playwright/mcp@latest"],
            env=None
        )

        self.session = await stdio_client(server_params).__aenter__()

    async def click(self, selector: str):
        """Click element by selector."""
        return await self.session.call_tool("playwright_click", {
            "selector": selector
        })

    async def fill(self, selector: str, text: str):
        """Fill input by selector."""
        return await self.session.call_tool("playwright_fill", {
            "selector": selector,
            "value": text
        })

    async def evaluate(self, script: str):
        """Execute JavaScript."""
        return await self.session.call_tool("playwright_evaluate", {
            "script": script
        })

    async def get_text(self, selector: str):
        """Get element text."""
        return await self.session.call_tool("playwright_locator_text", {
            "selector": selector
        })
```

#### B. Hybrid Tool Selection
```python
# In provider, expose both approaches
tools = [
    # Option 1: Selector-based (MCP)
    {
        "name": "playwright_click",
        "description": "Click element using CSS selector (preferred)",
        "input_schema": {
            "selector": "CSS selector string"
        }
    },
    # Option 2: Coordinate-based (fallback)
    {
        "name": "computer",
        "type": "computer_20250124",
        "description": "Use mouse/keyboard (fallback when selector unknown)",
        ...
    }
]
```

### Phase 3: Two-Tier Agent Architecture

#### A. Planning Agent
```python
# New file: src/cua/agent/planner.py
class PlanningAgent:
    """Text-only agent for analyzing page structure and planning actions."""

    def __init__(self, provider):
        self.provider = provider
        # No context limits - can process full HTML

    def analyze_page(self, html: str, task: str) -> ActionPlan:
        """Analyze HTML and create action plan."""
        prompt = f"""
        Analyze this HTML and plan actions to complete the task.

        Task: {task}

        HTML Structure:
        {html[:50000]}  # Can send much more than current limit

        Create a step-by-step plan using CSS selectors.
        Format:
        1. Action type (click/fill/evaluate)
        2. CSS selector or JS script
        3. Expected outcome
        """

        response = self.provider.create_request(prompt)
        return self.parse_action_plan(response)
```

#### B. Execution Agent (Modified Current Agent)
```python
# Modified loop.py
class ExecutionAgent:
    """Executes action plan with visual verification."""

    def __init__(self, planner: PlanningAgent):
        self.planner = planner
        self.max_context = 3  # Keep only recent actions

    def execute_task(self, task: str):
        # Get full page HTML
        html = self.browser.get_html()

        # Planning phase (no context limits)
        plan = self.planner.analyze_page(html, task)

        # Execution phase (minimal context)
        for action in plan.actions:
            if action.type == "click_selector":
                self.browser.click_selector(action.selector)
            elif action.type == "fill_selector":
                self.browser.fill_selector(action.selector, action.text)
            elif action.type == "evaluate":
                self.browser.evaluate_js(action.script)

            # Take screenshot only for verification
            screenshot = self.browser.screenshot()

            # Verify with execution agent (small context)
            if not self.verify_action(screenshot, action):
                # Fallback to coordinate-based approach
                self.fallback_execute(action, screenshot)
```

### Phase 4: DOM Manipulation Tools

#### A. Direct DOM Actions
```python
# In playwright_controller.py
def click_selector(self, selector: str):
    """Click element by CSS selector."""
    self.page.click(selector)

def fill_selector(self, selector: str, text: str):
    """Fill input by CSS selector."""
    self.page.fill(selector, text)

def get_element_info(self, selector: str):
    """Get element information without screenshot."""
    return self.page.evaluate(f"""
        (selector) => {{
            const el = document.querySelector(selector);
            return {{
                text: el?.textContent,
                value: el?.value,
                visible: el?.offsetParent !== null,
                rect: el?.getBoundingClientRect()
            }};
        }}
    """, selector)

def find_selectors_by_text(self, text: str):
    """Find CSS selectors containing text."""
    return self.page.evaluate(f"""
        (text) => {{
            const elements = Array.from(document.querySelectorAll('*'));
            return elements
                .filter(el => el.textContent.includes(text))
                .map(el => {{
                    // Generate CSS selector
                    let selector = el.tagName.toLowerCase();
                    if (el.id) selector += '#' + el.id;
                    if (el.className) selector += '.' + el.className.split(' ')[0];
                    return selector;
                }});
        }}
    """, text)
```

## Realistic Options: Priority Matrix

### 🔥 **HIGH IMPACT, LOW EFFORT** (Do First)
1. **Disable A11y Tree by Default** (Already proven better)
   - Result: 2x progress, cleaner reasoning
   - Implementation: Change default flag

2. **Add CLI Token Stats** (Your request)
   - Result: Better visibility into costs
   - Implementation: ~1 hour

3. **Increase Viewport to 900px** (Your request)
   - Result: Better scrollbar visibility
   - Implementation: 5 minutes

4. **Add Conversation Dump** (Your request)
   - Result: Better debugging
   - Implementation: ~1 hour

### 🎯 **HIGH IMPACT, MEDIUM EFFORT** (Do Second)
5. **Add Direct DOM Actions** (CSS selectors)
   - Result: 10-100x faster navigation
   - Implementation: ~2-4 hours
   - No scrolling needed!

6. **Reduce Context to 3 Cycles**
   - Result: 30-40% token reduction
   - Implementation: 1 line change

7. **Remove Page Text from Tool Results**
   - Result: 25-30% token reduction
   - Implementation: ~1 hour

### 🚀 **VERY HIGH IMPACT, HIGH EFFORT** (Do Third)
8. **Integrate Playwright MCP**
   - Result: Simplified tool definitions, better actions
   - Implementation: ~4-8 hours

9. **Two-Tier Agent Architecture**
   - Result: No context limits, better reasoning
   - Implementation: ~8-16 hours
   - Game-changer for complex tasks

### ⚡ **MEDIUM IMPACT** (Do If Needed)
10. **Compress Screenshots More**
11. **Truncate Page Text to 4k chars**
12. **Optimize Prompt Length**

## Recommended Implementation Order

### Week 1: Quick Wins (Your Requests + Easy Optimizations)
1. Branch off ✅ (done)
2. Add CLI token stats (with content breakdown)
3. Add conversation dump to separate log file
4. Increase viewport to 900px
5. Disable a11y tree by default (proven to help)
6. Reduce context to 3 cycles
7. Test and measure improvements

**Expected Results**:
- Better visibility (stats + logs)
- 50% token reduction (no tree + less context)
- 2x progress (based on your test results)
- Better video quality (900px height)

### Week 2: DOM Manipulation
1. Add CSS selector-based click/fill methods
2. Add find_selectors_by_text helper
3. Update prompts to prefer selectors over coordinates
4. Test with same challenge

**Expected Results**:
- 10-100x faster for many actions (no scrolling!)
- Fewer errors (precise selectors vs coordinates)
- Better success rate

### Week 3: MCP Integration (If Week 2 Works Well)
1. Install Playwright MCP
2. Create MCP client wrapper
3. Expose MCP tools to AI
4. Hybrid approach: MCP preferred, coordinates fallback

**Expected Results**:
- Cleaner code (fewer tool definitions)
- Better tool usage by AI
- More powerful actions (JS evaluation)

### Week 4: Two-Tier Architecture (If Needed)
1. Implement planning agent
2. Modify execution agent
3. Add HTML analysis phase
4. Test with complex multi-step tasks

**Expected Results**:
- No context limits for reasoning
- Much better success on 30-step challenge
- Clearer separation of concerns

## Answer to "What Are Realistic Options?"

Based on your test results and questions, here are the **most realistic and impactful** options:

### Option A: Incremental Optimization (Safest)
1. Implement Week 1 changes (stats, logging, no a11y, smaller context)
2. Test and measure
3. If good, continue to Week 2 (DOM manipulation)
4. If excellent, continue to Week 3 (MCP)
5. Only do Week 4 if needed for very complex tasks

**Timeline**: 2-4 weeks
**Success Probability**: 80-90%
**Expected Completion**: 15-20 steps of 30

### Option B: DOM Manipulation First (Highest ROI)
1. Skip some Week 1 items
2. Focus on CSS selector-based actions
3. Add HTML structure analysis
4. Eliminate scrolling entirely

**Timeline**: 1-2 weeks
**Success Probability**: 70-80%
**Expected Completion**: 20-25 steps of 30

### Option C: Full MCP + Two-Tier (Most Ambitious)
1. Integrate Playwright MCP immediately
2. Build two-tier architecture
3. Planning agent analyzes full HTML
4. Execution agent just runs the plan

**Timeline**: 3-4 weeks
**Success Probability**: 60-70% (riskier)
**Expected Completion**: All 30 steps (if it works)

## My Recommendation

**Start with Option A (Week 1), then pivot to Option B (Week 2)**

Why:
1. Your test already proved a11y tree hurts more than helps
2. Stats/logging will give us better data
3. DOM manipulation is the key unlock (no more scrolling!)
4. MCP and two-tier are powerful but can wait
5. Get quick wins first, then tackle bigger changes

**Next Steps**:
1. Implement Week 1 changes (I can do this now)
2. Test with same challenge
3. Measure token reduction and progress
4. If successful, move to Week 2 (DOM manipulation)

What do you think? Should I proceed with Week 1 implementation?
