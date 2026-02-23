# CUA Pipeline — Architecture & Flow Report

**Branch:** `efficient-single-agent`
**Date:** 2026-02-23
**Purpose:** Reference document for pipeline review and improvement suggestions.

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Entry Point & CLI Options](#2-entry-point--cli-options)
3. [Full Sequence of Events](#3-full-sequence-of-events)
4. [Agent Tools Reference](#4-agent-tools-reference)
5. [Bedrock Model Layer](#5-bedrock-model-layer)
6. [Artifact Organization](#6-artifact-organization)
7. [Logging & Timeline](#7-logging--timeline)
8. [Token Economics](#8-token-economics)
9. [Known Issues & Limitations](#9-known-issues--limitations)
10. [Configuration Reference](#10-configuration-reference)

---

## 1. High-Level Architecture

```
User CLI Command
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  main.py  (Click CLI)                                           │
│  Parses args → selects mode → creates coordinator              │
└──────────────────────┬──────────────────────────────────────────┘
                       │ mode = "efficient" (default)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  SoloCoordinator  (coordinator/solo_coordinator.py)             │
│  - Creates session ID + directories                             │
│  - Starts TimelineLogger                                        │
│  - Calls create_solo_agent()                                    │
│  - Calls agent.arun(prompt)  ← single async call               │
│  - Post-run: organizes artifacts, writes REPORT.md             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
┌──────────────────┐  ┌─────────────────────────┐
│  BedrockMCPModel │  │  Playwright MCP Server   │
│  (agno_config/)  │  │  (npx @playwright/mcp)   │
│                  │  │                          │
│  Extends Agno's  │  │  Separate Node.js process│
│  AwsBedrock with │  │  communicating via stdio │
│  - Grouped tool  │  │  Exposes 30+ browser     │
│    results       │  │  tools to the agent      │
│  - 2000-char     │  └─────────────────────────┘
│    result cap    │
│  - Image format  │
│    handling      │
└──────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  AWS Bedrock  (boto3 → Converse API)                            │
│  claude-haiku-4-5 or claude-sonnet-4-5                         │
│  Region: us-east-1 (default)                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Three Modes (for context)

| Mode | Class | When to Use |
|------|-------|-------------|
| `efficient` (default) | `SoloCoordinator` | All new usage — single agent, direct tools |
| `agno` (legacy) | `AgnoCoordinator` | 4-agent Team: Orchestrator + Browser + Memory + Analysis |
| `classic` (legacy) | `CoordinatorAgent` | Original loop with custom browser controller |

**This report covers the `efficient` mode only.** The other two modes exist in the codebase but are not actively maintained.

---

## 2. Entry Point & CLI Options

**File:** `src/cua/main.py`
**Invoked as:** `cua --url "..." --prompt "..."`

### All CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | *(required)* | URL to navigate to. `http://` is auto-prepended if missing |
| `--prompt` | *(required)* | Task description sent to the agent |
| `--model` | `haiku` | `haiku` or `sonnet`. Maps to Bedrock inference profile IDs |
| `--mode` | `efficient` | `efficient`, `agno`, or `classic` |
| `--max-iterations` | `30` | Passed to coordinator but **ignored** in efficient mode |
| `--max-tool-calls` | `150` | Hard cap on total Playwright + state tracker calls per run |
| `--display-width` | `1280` | Browser viewport width in pixels |
| `--display-height` | `720` | Browser viewport height in pixels |
| `--headless / --no-headless` | headless | Headed mode requires `xvfb-run` on Ubuntu server |
| `--record-video` | off | Enables `--save-video` and `--save-trace` in Playwright MCP |
| `--log-level` | `INFO` | Passed through but **not yet wired** to Python logger in efficient mode |
| `--zoom` | `85` | **Not used** in efficient mode (legacy flag) |
| `--enable-caching` | on | **Not used** in efficient mode (legacy flag) |
| `--context-window-size` | `10` | **Not used** in efficient mode (legacy flag) |
| `--extended-thinking` | off | **Not used** in efficient mode (legacy flag) |
| `--thinking-budget` | `10000` | **Not used** in efficient mode (legacy flag) |
| `--use-accessibility-tree` | on | **Not used** in efficient mode (legacy flag) |

> **Note:** Several flags exist only for legacy mode compatibility. In efficient mode, only `url`, `prompt`, `model`, `max-tool-calls`, `display-width/height`, `headless`, and `record-video` have any effect.

### Model ID Mapping

```python
# What "haiku" and "sonnet" resolve to on Bedrock:
haiku  → "us.anthropic.claude-haiku-4-5-20251001-v1:0"
sonnet → "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
```

These are **cross-region inference profile IDs** (the `us.` prefix). The region defaults to `us-east-1` from `AWS_REGION` env var.

---

## 3. Full Sequence of Events

### Phase 0: Startup (synchronous, instant)

```
cua --url "..." --prompt "..." --model haiku --record-video
   │
   ├─ Click parses CLI args
   ├─ load_dotenv() reads .env
   ├─ URL gets https:// prepended if needed
   ├─ AWS_BEARER_TOKEN_BEDROCK → AWS_SESSION_TOKEN env mapping (if needed)
   └─ SoloCoordinator.__init__() is called
         ├─ session_id = YYYYMMDD_HHMMSS  (e.g. 20260223_103758)
         ├─ Creates directories:
         │     test_artifacts/{session_id}/
         │     test_artifacts/{session_id}/logs/
         │     test_artifacts/{session_id}/screenshots/
         │     test_artifacts/{session_id}/recordings/
         │     test_artifacts/{session_id}/snapshots/
         ├─ TimelineLogger initialized → writes session_start event
         └─ get_bedrock_model("haiku") creates BedrockMCPModel instance
```

### Phase 1: Agent Creation (synchronous, ~instant)

```
SoloCoordinator.run_task(url, prompt)
   │
   └─ asyncio.run(_run_async(url, prompt))
         │
         └─ create_solo_agent(model, session_dir, record_video, ...)
               │
               ├─ Builds Playwright MCP command string:
               │     "npx @playwright/mcp
               │       --viewport-size=1280x720
               │       --no-sandbox
               │       --snapshot-mode=incremental
               │       --headless
               │       [--output-dir=.../recordings]      ← only if record_video
               │       [--save-video=1280x720]             ← only if record_video
               │       [--save-trace]"                     ← only if record_video
               │
               ├─ MCPTools(command=..., refresh_connection=False, timeout_seconds=120)
               │     NOTE: The Playwright Node.js server is NOT started yet here.
               │     It starts on first tool call inside agent.arun().
               │
               ├─ BrowserStateTracker() — Python-only, no external process
               │
               └─ Agent(model, tools=[playwright_mcp, state_tracker],
                         tool_call_limit=150, ...)
                     The agent is configured but NOT yet running.
```

### Phase 2: Prompt Construction

```
_build_prompt(url, task) returns a string containing:
  - "Navigate to: {url}"
  - "Task: {task}"
  - "SCREENSHOT DIRECTORY: /absolute/path/to/screenshots/"
  - Screenshot instructions with exact filenames to use
  - 7-step task instructions
  - "TASK COMPLETE: [summary]" termination signal
```

### Phase 3: Agent Run Loop (the main loop — async)

This is everything inside `agent.arun(task_prompt)`. Agno manages this loop internally.

```
agent.arun(task_prompt)
   │
   ├─ [LLM Call 0] Bedrock Converse API called with:
   │     - System message: SOLO_AGENT_INSTRUCTIONS (~5000 tokens)
   │     - User message: task_prompt (~300 tokens)
   │     Claude decides what to do first (e.g. browser_navigate)
   │
   ├─ [Tool Call 1] e.g. browser_navigate(url="https://...")
   │     ├─ Agno routes to MCPTools
   │     ├─ MCPTools starts the Playwright Node.js server (first call only)
   │     ├─ Sends MCP request over stdio to Playwright server
   │     ├─ Playwright opens Chromium, navigates to URL
   │     ├─ Returns result string to MCPTools
   │     ├─ MCPTools returns to Agno
   │     └─ Agno appends tool result to conversation history
   │
   ├─ [LLM Call 1] Bedrock called again with:
   │     - Full conversation so far (system + user prompt + tool result)
   │     - BedrockMCPModel._format_messages() runs:
   │         * Groups consecutive tool results into single user message
   │         * Truncates any result > 2000 chars
   │         * Wraps strings in {"text": ...} blocks for Bedrock format
   │     Claude decides next action
   │
   ├─ [Tool Call 2] e.g. browser_snapshot()
   │     ├─ Playwright captures accessibility tree of current page
   │     ├─ Returns YAML-like tree text (can be 100s of lines)
   │     └─ BedrockMCPModel truncates to 2000 chars if needed
   │
   ├─ ... (loop continues until tool_call_limit or Claude outputs TASK COMPLETE)
   │
   └─ Returns RunOutput with:
         - content: Claude's final text response
         - tools: List[ToolExecution] — all tool calls made
         - metrics: Metrics(input_tokens, output_tokens)
```

**Key mechanics of the loop:**
- Each LLM call re-sends the full conversation history (quadratic token growth)
- Claude can request multiple tool calls per LLM response (batched)
- `tool_call_limit=150` is a hard stop; Agno raises after that many calls
- The loop ends when Claude outputs no more tool calls (just text)

### Phase 4: Post-Run Artifact Organization

```
_log_tool_calls(run_output)
   └─ Reads run_output.tools (all ToolExecution objects)
      For each: log_action(name, description, screenshot_path)
      Returns count of browser_take_screenshot calls

_organize_artifacts()
   ├─ recordings/videos/hash.webm  →  recordings/session-{id}.webm
   ├─ recordings/console-*.log     →  logs/browser-console-*.log
   ├─ Stray step-*.png in test_artifacts/ root  →  screenshots/
   │     (only files newer than session start time)
   └─ Returns Path to renamed video

logger.log_task_complete(...)
logger.log_token_usage(...)
logger.write_report()  →  REPORT.md
```

### Phase 5: Display & Exit

```
_display_result()  →  prints to console:
   Status / Duration / Steps done / Screenshots / Tokens / Cost
   Completed steps list
   Discovered facts
   Artifact paths

main.py: sys.exit(0 if result.success else 1)
```

**Success detection:** `"TASK COMPLETE" in result_text.upper()` — a simple string match on Claude's final output. If Claude never outputs those words, the run is marked incomplete even if it did useful work.

---

## 4. Agent Tools Reference

The agent has access to two tool groups simultaneously.

### Group A: Playwright MCP Tools (30+ tools, via Node.js subprocess)

These are provided by `npx @playwright/mcp@0.0.68`. All are called via MCP stdio protocol. The agent gets element refs (e.g. `ref=e123`) from `browser_snapshot` and uses them in click/type calls.

#### Navigation

| Tool | Arguments | What It Does | Notes |
|------|-----------|--------------|-------|
| `browser_navigate` | `url: str` | Navigate to URL, wait for load | Most-used entry point |
| `browser_navigate_back` | — | Go back in history | |
| `browser_wait_for` | `text?: str, time?: int` | Wait for text to appear OR N seconds | `time` in seconds |
| `browser_reload` | — | Reload current page | (available but not in instructions) |

#### Observation

| Tool | Arguments | What It Does | Notes |
|------|-----------|--------------|-------|
| `browser_snapshot` | — | Returns accessibility tree (YAML-like) with element refs | With `--snapshot-mode=incremental`, first call = full tree, subsequent = changes only |
| `browser_take_screenshot` | `filename?: str, fullPage?: bool` | Captures screenshot PNG | READ-ONLY — no refs returned. Agent should save to absolute path |

#### Interaction

| Tool | Arguments | What It Does | Notes |
|------|-----------|--------------|-------|
| `browser_click` | `element?: str, ref?: str` | Click element | Use `ref` from snapshot |
| `browser_type` | `ref: str, text: str` | Type text, fires keyboard events | **Correct for React forms** — updates React state |
| `browser_fill_form` | `fields: dict` | Fill multiple form fields | More efficient than individual type calls |
| `browser_select_option` | `ref: str, values: list` | Select dropdown option | |
| `browser_press_key` | `key: str` | Press keyboard key | e.g. `"Enter"`, `"Tab"`, `"Escape"` |
| `browser_mouse_wheel` | `deltaX: int, deltaY: int` | Scroll the page | `deltaY=500` ≈ half screen down |
| `browser_handle_dialog` | `accept: bool, promptText?: str` | Accept/dismiss JS dialogs | For `alert()`, `confirm()`, `prompt()` |
| `browser_hover` | `ref: str` | Hover (for hover menus) | |
| `browser_drag` | `startRef: str, endRef: str` | Drag and drop | |
| `browser_file_upload` | `ref: str, paths: list` | Upload file(s) | |

#### Advanced / Escape Hatches

| Tool | Arguments | What It Does | Notes |
|------|-----------|--------------|-------|
| `browser_evaluate` | `function: str` | Execute JS expression, returns result | Lightweight. Use for: remove overlay, get hidden text, check URL |
| `browser_run_code` | `code: str` | Run full Playwright code with `page` object | Most powerful. `async (page) => { ... }`. High token cost — use sparingly |
| `browser_console_messages` | — | Get all browser console messages | Useful for JS error debugging |
| `browser_network_requests` | — | List network requests since page load | Useful for API debugging |

#### Verification

| Tool | Arguments | What It Does |
|------|-----------|--------------|
| `browser_verify_text_visible` | `text: str` | Assert text is present on page |
| `browser_verify_element_visible` | `ref: str` | Assert element is visible |
| `browser_verify_value` | `ref: str, value: str` | Assert input has specific value |

#### Utilities

| Tool | Arguments | What It Does |
|------|-----------|--------------|
| `browser_tabs` | `action, ...` | List/create/close/select tabs |
| `browser_resize` | `width, height` | Resize viewport |
| `browser_install` | — | Install Playwright browser if missing |
| `browser_close` | — | Close current page |

### Group B: BrowserStateTracker Tools (Python, in-process)

These are Python functions registered as Agno tools. No external process, instant.

| Tool | Arguments | Returns | Purpose |
|------|-----------|---------|---------|
| `mark_complete` | `step: str` | Confirmation string | Record a milestone. Persists in `state_tracker.completed_steps` |
| `store_fact` | `key: str, value: str` | Confirmation string | Remember a code/value. Persists in `state_tracker.facts` |
| `get_facts` | — | All stored facts as text | Recall stored information |
| `get_progress` | — | Numbered list of completed steps | Check what's been done (anti-loop mechanism) |

**Why these exist:** Replaces the separate Memory MCP Agent from the old multi-agent system. Zero overhead — just Python dicts. The data is also available after the run in `state_tracker.facts` and `state_tracker.completed_steps` for the coordinator to log.

### When Tools Are Triggered

There is no deterministic trigger mapping — **Claude decides** which tools to call based on the system prompt, current page state, and task context. The system prompt establishes preferred patterns:

```
Page load          → browser_navigate → browser_snapshot → browser_take_screenshot
Popup present      → browser_click (dismiss) or browser_evaluate (remove)
Code reveal needed → browser_scroll + browser_snapshot → browser_click (Reveal Code)
Code found         → store_fact(code)
Form entry         → browser_click (focus) → browser_type (text) → browser_click (submit)
After submit       → browser_wait_for(3s) → browser_evaluate(check URL)
Milestone done     → mark_complete(step description) → browser_take_screenshot
Confusion          → get_progress() + get_facts() → browser_snapshot
Task done          → browser_take_screenshot(final) → output "TASK COMPLETE: ..."
```

---

## 5. Bedrock Model Layer

**File:** `src/cua/agno_config/bedrock_mcp_model.py`

`BedrockMCPModel` extends Agno's `AwsBedrock` with two overrides:

### Override 1: `_format_messages()` — Consecutive Tool Result Grouping

**Why it exists:** AWS Bedrock Converse API requires all tool results from a single LLM turn to be in **one message** with `role="user"` containing multiple `toolResult` blocks. Agno's default `AwsBedrock` creates a separate message per tool result, which Bedrock rejects.

```python
# Bedrock requires this (what BedrockMCPModel produces):
{"role": "user", "content": [
    {"toolResult": {"toolUseId": "id1", "content": [...]}},
    {"toolResult": {"toolUseId": "id2", "content": [...]}},
]}

# Agno default produces this (Bedrock rejects it):
{"role": "user", "content": [{"toolResult": ...}]}  # message 1
{"role": "user", "content": [{"toolResult": ...}]}  # message 2  ← ERROR
```

The override collects `pending_tool_results` and flushes them into a single message when a non-tool message is encountered.

### Override 2: `_format_tool_result_content()` — Truncation + Wrapping

**Why it exists:** Two reasons:
1. MCP tools return plain strings; Bedrock expects `{"text": "..."}` format
2. Large tool results (accessibility trees with 100+ elements) cause quadratic context growth

```python
MAX_TOOL_RESULT_CHARS = 2000  # ≈ 500 tokens

def _format_tool_result_content(content):
    if isinstance(content, str):
        content = truncate(content, 2000)   # Hard cap
        return [{"text": content}]
    if isinstance(content, list) and already_formatted:
        return content                       # Pass through
    return [{"json": {"result": content}}]  # Wrap other types
```

**Impact of truncation:** Without this, a single `browser_snapshot` on the challenge page (100+ sections) returned ~15,000 chars. At 100 tool calls, the accumulated history reaches 1.5M+ chars before even counting LLM responses. With truncation at 2000 chars, the same 100 calls accumulate ~200K chars of tool results — a 7.5x reduction in context growth rate.

### Authentication Flow

```python
# Priority order (checked in get_bedrock_model()):
1. AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY  →  standard IAM
2. AWS_BEARER_TOKEN_BEDROCK                   →  mapped to AWS_SESSION_TOKEN
3. IAM role (EC2 instance profile)            →  boto3 credential chain
4. ~/.aws/credentials                         →  boto3 fallback
```

The mapping `AWS_BEARER_TOKEN_BEDROCK → AWS_SESSION_TOKEN` happens at import time in `models.py` and before each model instantiation.

### Message Format Sent to Bedrock

Each LLM call sends this structure:

```json
{
  "modelId": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "system": [{"text": "SOLO_AGENT_INSTRUCTIONS (5000 tokens)"}],
  "messages": [
    {"role": "user",    "content": [{"text": "task_prompt"}]},
    {"role": "assistant","content": [{"toolUse": {"toolUseId": "...", "name": "browser_navigate", "input": {"url": "..."}}}]},
    {"role": "user",    "content": [{"toolResult": {"toolUseId": "...", "content": [{"text": "Navigation result"}]}}]},
    {"role": "assistant","content": [{"toolUse": {"name": "browser_snapshot", ...}}]},
    {"role": "user",    "content": [{"toolResult": {...}}]},
    ... (grows with every tool call)
  ],
  "toolConfig": {"tools": [... all 30+ Playwright tools + 4 state tracker tools ...]}
}
```

The **full conversation history is re-sent every call**. This is the fundamental source of quadratic token growth.

---

## 6. Artifact Organization

Every run creates a timestamped session directory:

```
test_artifacts/
└── {YYYYMMDD_HHMMSS}/            ← session_id, created at coordinator init
    ├── REPORT.md                  ← Markdown timeline, written at end of run
    │
    ├── logs/
    │   ├── timeline.json          ← Machine-readable structured log (updated live)
    │   ├── session.log            ← Human-readable text log (updated live)
    │   └── browser-console-*.log  ← Playwright browser JS console (moved post-run)
    │
    ├── screenshots/               ← Agent-saved screenshots (absolute paths in prompt)
    │   ├── step-01-start.png
    │   ├── step-01-done.png
    │   └── ...
    │
    ├── recordings/                ← Video and trace (Playwright MCP output dir)
    │   ├── session-{id}.webm      ← Video recording (renamed from hash.webm post-run)
    │   └── traces/                ← Playwright trace for trace viewer
    │       └── trace.json
    │
    └── snapshots/                 ← Empty currently (placeholder for future use)
```

### How Files Get There

| File | Created By | When | Notes |
|------|------------|------|-------|
| `logs/timeline.json` | `TimelineLogger` | Updated live throughout run | Overwritten on every event |
| `logs/session.log` | `TimelineLogger` | Appended live throughout run | |
| `screenshots/*.png` | Agent via `browser_take_screenshot` | During run | Agent must use absolute path from prompt |
| `recordings/videos/hash.webm` | Playwright MCP (`--save-video`) | During run | Renamed post-run |
| `recordings/session-{id}.webm` | `_organize_artifacts()` | Post-run | Renamed from hash |
| `recordings/traces/` | Playwright MCP (`--save-trace`) | During run | Trace viewer format |
| `logs/browser-console-*.log` | `_organize_artifacts()` | Post-run | Moved from `recordings/` |
| `REPORT.md` | `TimelineLogger.write_report()` | Post-run | Generated from timeline events |

### Important Quirk: Screenshots

The agent is told via the task prompt:
```
SCREENSHOT DIRECTORY: /absolute/path/to/test_artifacts/{id}/screenshots/
browser_take_screenshot(filename="/absolute/path/.../step-01-start.png")
```

Using absolute paths prevents the agent from shortening to relative paths like `test_artifacts/step-01.png` (which happened in earlier versions). A post-run cleanup in `_organize_artifacts()` also catches any stray files newer than the session start time.

---

## 7. Logging & Timeline

**File:** `src/cua/utils/timeline_logger.py`

### Event Types Written to `timeline.json`

| Event Type | Trigger | Data Fields |
|------------|---------|-------------|
| `session_start` | Coordinator init | `session_id`, `start_time` |
| `task_start` | `run_task()` called | `url`, `prompt` |
| `browser_action` | Post-run, from `run_output.tools` | `action`, `details`, optional `screenshot` |
| `info` | `_organize_artifacts()` | `message` |
| `error` | Exception caught | `message`, `error_type`, `error_detail` |
| `task_complete` | After `agent.arun()` returns | `success`, `summary`, `elapsed_seconds`, `completed_steps`, `facts_discovered`, `total_tokens` |
| `token_usage` | After `agent.arun()` returns | `input_tokens`, `output_tokens`, `total_tokens`, `estimated_cost_usd` |

### Important Timing Note

All `browser_action` events are logged **after the run completes**, not in real time. They're extracted from `run_output.tools` in a single batch. This means `timeline.json` only gets the browser actions at the very end, not during. The `elapsed_s` field shows the run's total duration for every action event, not when each action occurred.

This is a known limitation — real-time action timing requires hooking into Agno's tool execution loop, which was not implemented.

### Cost Estimate Formula

```python
# Bedrock Haiku pricing (approximate):
input_cost  = (input_tokens  / 1000) * $0.00025
output_cost = (output_tokens / 1000) * $0.00125
# Note: Sonnet pricing is roughly 3x higher
```

---

## 8. Token Economics

### Sources of Token Usage

Each LLM call sends:

| Component | Approximate Tokens | Notes |
|-----------|--------------------|-------|
| System prompt (SOLO_AGENT_INSTRUCTIONS) | ~1,300 | Constant every call |
| Tool schema definitions (30+ tools) | ~2,000–3,000 | Constant every call |
| Task prompt | ~300 | Constant every call |
| Accumulated conversation history | Grows per call | Main source of growth |
| Per tool call in history: request | ~200 | Tool name + arguments |
| Per tool call in history: result | up to 500 (2000 chars) | Truncated |
| Per LLM response in history | ~200–500 | Claude's reasoning |

### Growth Formula

With `N` total tool calls made so far, the tokens sent in the Nth LLM call approximately:

```
tokens_at_call_N ≈ 4500 (fixed) + N × 900 (per tool call in history)
```

Total tokens for a complete run of `N` tool calls:

```
total ≈ N × 4500 + N² × 450
```

For N=100: ≈ 4.95M tokens. This matches observed values (~3–4M for 95–99 calls).

### Observed Results

| Model | Tool Calls | Total Tokens | Cost Est. | Steps Done |
|-------|-----------|--------------|-----------|------------|
| Haiku (pre-fix) | 39 | 1.47M | $0.37 | 1 (partial, 404 loop) |
| Haiku (post-fix) | 99 | 3.33M | $0.86 | 1 + reached step 2 |
| Sonnet | 95 | 2.99M | $0.76 | 1 + reached step 2 |

### What Drives Call Count Up

1. **Confusion after form submission** — agent doesn't know if it worked, retries
2. **Popup overload** — challenge page has 6–8 simultaneous overlays requiring multiple dismissals
3. **Overuse of `browser_run_code`** — complex JS calls when simpler tools would work
4. **Re-navigation** — agent navigates back to `/` and restarts (seen in early runs)

---

## 9. Known Issues & Limitations

### Critical

| # | Issue | Impact | Current Mitigation |
|---|-------|--------|--------------------|
| 1 | **Quadratic token growth** | Cost scales with N², not N | 2000-char tool result cap |
| 2 | **No real-time action timestamps** | Timeline shows all actions at run end, not during | Known limitation, cosmetic |
| 3 | **Success detection is fragile** | `"TASK COMPLETE" in response` — Claude can say it prematurely | No fix yet |
| 4 | **No per-step token tracking** | Can't see which step cost the most | All tokens reported as single total |

### Behavioral

| # | Issue | Impact | Current Mitigation |
|---|-------|--------|--------------------|
| 5 | **Haiku overuses `browser_run_code`** | ~36 calls in 99 total (36%) — adds verbose code to history | Instructions say "last resort only" but Haiku ignores this |
| 6 | **Agent can't verify URL change reliably** | After submit, `browser_wait_for` for text sometimes misses the step heading | Added URL check via `browser_evaluate(() => window.location.href)` |
| 7 | **First `browser_snapshot` is always full** | Even with `--snapshot-mode=incremental`, the first call on a new page is the complete tree | Accepted — incremental mode reduces subsequent calls |
| 8 | **4.2KB "blank" screenshots** | When page renders white (React app not loaded), screenshot is ~4KB white PNG | No fix — indicates underlying page issue |

### Infrastructure

| # | Issue | Impact | Current Mitigation |
|---|-------|--------|--------------------|
| 9 | **Headed mode requires Xvfb on this VM** | `--no-headless` fails without display | `xvfb-run --auto-servernum` wraps the command |
| 10 | **MCP timeout at 120s** | Very large pages (100+ DOM sections) can take >120s for first snapshot | Increased from 60s; root fix is JS-targeted extraction |
| 11 | **No retry on MCP timeout** | When `browser_snapshot` times out, Claude gets an error and must recover | Instructions tell Claude to fall back to `browser_evaluate` |
| 12 | **Video filename is a hash** | `videos/abc123.webm` until post-run rename | `_organize_artifacts()` renames to `session-{id}.webm` |

### Architecture Debt

| # | Issue |
|---|-------|
| 13 | `--zoom`, `--enable-caching`, `--context-window-size`, `--extended-thinking` flags accepted but do nothing in efficient mode |
| 14 | `max_iterations` parameter accepted but ignored (legacy compatibility arg) |
| 15 | `HAIKU_MODEL` and `SONNET_MODEL` module-level instances in `models.py` are created at import time, which triggers `AWS_SESSION_TOKEN` mapping as a side effect |
| 16 | `SoloCoordinator` accepts many `AgnoCoordinator` constructor args as no-ops |

---

## 10. Configuration Reference

### Environment Variables

| Variable | Required | Effect |
|----------|----------|--------|
| `AWS_BEARER_TOKEN_BEDROCK` | Yes (or access key pair) | Maps to `AWS_SESSION_TOKEN` for Bedrock auth |
| `AWS_ACCESS_KEY_ID` | Alternative auth | Standard AWS credential |
| `AWS_SECRET_ACCESS_KEY` | Alternative auth | Standard AWS credential |
| `AWS_REGION` | No (defaults to `us-east-1`) | Bedrock region |
| `BEDROCK_MODEL` | No (defaults to `haiku`) | Sets `--model` default |
| `MAX_TOOL_CALLS` | No (defaults to `150`) | Sets `--max-tool-calls` default |
| `DISPLAY_WIDTH` | No (defaults to `1280`) | Browser viewport width |
| `DISPLAY_HEIGHT` | No (defaults to `720`) | Browser viewport height |

### Playwright MCP Flags Used

```bash
npx @playwright/mcp
  --viewport-size=1280x720      # Browser window size
  --no-sandbox                  # Required on Linux/Docker (no root sandbox)
  --snapshot-mode=incremental   # Only changed elements after first snapshot
  --headless                    # Headless Chromium (omit for headed)
  --output-dir=.../recordings   # Where to write video/trace (only with --record-video)
  --save-video=1280x720         # Record browser session video (only with --record-video)
  --save-trace                  # Record Playwright trace (only with --record-video)
```

### Key Code Locations

| What | File | Line/Class |
|------|------|------------|
| CLI entry point | `src/cua/main.py` | `cli()` function |
| Agent instructions (system prompt) | `src/cua/agno_agents/solo_agent.py` | `SOLO_AGENT_INSTRUCTIONS` constant |
| Playwright command builder | `src/cua/agno_agents/solo_agent.py` | `build_playwright_command()` |
| Agent + state tracker creation | `src/cua/agno_agents/solo_agent.py` | `create_solo_agent()` |
| Tool result truncation | `src/cua/agno_config/bedrock_mcp_model.py` | `MAX_TOOL_RESULT_CHARS = 2000` |
| Bedrock message grouping fix | `src/cua/agno_config/bedrock_mcp_model.py` | `_format_messages()` |
| Model IDs | `src/cua/agno_config/models.py` | `HAIKU_MODEL_ID`, `SONNET_MODEL_ID` |
| Session directory layout | `src/cua/utils/session_paths.py` | `get_session_dir()` etc. |
| Artifact post-processing | `src/cua/coordinator/solo_coordinator.py` | `_organize_artifacts()` |
| Task prompt construction | `src/cua/coordinator/solo_coordinator.py` | `_build_prompt()` |
| Success detection | `src/cua/coordinator/solo_coordinator.py` | `"TASK COMPLETE" in result_text.upper()` |
| Timeline events | `src/cua/utils/timeline_logger.py` | `TimelineLogger` class |

---

*Report generated from codebase snapshot on branch `efficient-single-agent`, commit `8b3c069`.*
