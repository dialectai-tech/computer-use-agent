"""Per-step isolated conversation loop.

Each call to execute_step() runs ONE logical step in a fresh mini-conversation.
The messages list is local to the function and garbage collected when it returns.
Only StepResult (a few hundred bytes of structured data) persists.

This is the core of the per-step context reset architecture that prevents
quadratic token growth across a long task.

Token economics:
- Before: N steps × N previous tool calls × ~4500 tokens/call = O(N²) growth
- After:  N steps × ~10 tool calls per step × ~700 tokens/call = O(N) growth
"""

from __future__ import annotations

import asyncio
import re as _re_module

from dataclasses import dataclass, field
from typing import Optional

from cua.llm.bedrock_engine import BedrockEngine, ToolResult
from cua.mcp.session import PlaywrightMCPSession
from cua.prompts.step_prompt import SYSTEM_PROMPT, build_step_prompt


@dataclass
class StepState:
    """State carried forward between steps (everything else is discarded).

    This is intentionally minimal — only what the model needs to know
    at the start of each new step to make progress.
    """

    url: str
    task: str
    completed_steps: list[str] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)
    step_number: int = 1


@dataclass
class StepResult:
    """Result of a single step execution returned to the coordinator."""

    success: bool
    step_summary: str
    new_facts: dict[str, str]
    new_completed: list[str]
    tokens_used: int
    tool_calls_made: int
    task_complete: bool  # Model output "TASK COMPLETE" — full task is done


# State management tools exposed to the model (Python-side, not MCP)
_STATE_TOOL_SPECS: list[dict] = [
    {
        "toolSpec": {
            "name": "enter_code_in_input",
            "description": (
                "Enter a code into the challenge form input and submit it. "
                "Use this when you have a code to submit — it handles React forms correctly. "
                "Returns 'submitted: URL' if successful, or an error message."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The 6-character code to enter and submit",
                        },
                    },
                    "required": ["code"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_code_from_page",
            "description": (
                "Extract the revealed challenge code from the current page. "
                "Searches all text nodes and DOM attributes for 6-character alphanumeric codes. "
                "Returns the code string, or 'not found' if no code is visible yet."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "store_fact",
            "description": "Store an important fact for later use (codes, URLs, values, selectors)",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Name for this fact (e.g. 'challenge_code', 'email')",
                        },
                        "value": {
                            "type": "string",
                            "description": "The value to store (e.g. 'ABC123')",
                        },
                    },
                    "required": ["key", "value"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "mark_complete",
            "description": "Mark a sub-task or milestone as completed",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "step": {
                            "type": "string",
                            "description": "Description of the completed step",
                        },
                    },
                    "required": ["step"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_facts",
            "description": "Retrieve all stored facts (codes, values discovered so far)",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_progress",
            "description": "Get current task progress — list of completed steps",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                }
            },
        }
    },
]


def _build_tool_config(mcp: PlaywrightMCPSession) -> dict:
    """Build combined tool config: Playwright MCP tools + state management tools."""
    return {"tools": mcp.get_tool_specs() + _STATE_TOOL_SPECS}


_ENTER_CODE_JS = """(code) => {
    // Find the code entry input
    const input = document.querySelector('input[placeholder*="code"], input[placeholder*="Code"]');
    if (!input) return JSON.stringify({ok: false, error: 'input not found'});

    // Scroll to it
    input.scrollIntoView({block: 'center'});

    // React-compatible value setting (fires synthetic events)
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
    ).set;
    nativeInputValueSetter.call(input, code);
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
    input.focus();

    return JSON.stringify({ok: true, value: input.value, url: location.href});
}"""

_SUBMIT_FORM_JS = """() => {
    // Primary: dispatch Enter key on the input — works with React's onKeyDown handler
    const input = document.querySelector('input[placeholder*="code"], input[placeholder*="Code"]');
    if (input) {
        input.focus();
        input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', keyCode: 13, bubbles: true}));
        input.dispatchEvent(new KeyboardEvent('keypress', {key: 'Enter', keyCode: 13, bubbles: true}));
        input.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', keyCode: 13, bubbles: true}));
        // Also dispatch form submit event as fallback
        if (input.form) {
            input.form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
        }
        return JSON.stringify({ok: true, method: 'enter_key', value: input.value});
    }
    // Fallback: click the submit button
    const btns = [...document.querySelectorAll('button')];
    const submit = btns.find(b =>
        b.textContent.trim().toLowerCase().includes('submit') ||
        b.type === 'submit'
    );
    if (submit) {
        submit.click();
        return JSON.stringify({ok: true, method: 'button_click', text: submit.textContent.trim()});
    }
    return JSON.stringify({ok: false, error: 'no input or submit button found'});
}"""

_GET_CODE_JS = """() => {
    // Words that look like codes but are common English words (false positives)
    const FALSE_POSITIVES = new Set(['HIDDEN', 'SCROLL', 'BUTTON', 'REVEAL', 'SUBMIT', 'CUSTOM',
                                      'COOKIE', 'ACCEPT', 'DIALOG', 'POPUPS', 'BANNER', 'BOTTOM',
                                      'FOOTER', 'HEADER', 'ACTIVE', 'TOGGLE', 'EXPAND']);

    function searchCode() {
        // Walk text nodes for standalone 6-char uppercase alphanumeric codes
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        const found = [];
        let node;
        while ((node = walker.nextNode())) {
            const text = node.textContent.trim();
            if (/^[A-Z0-9]{6}$/.test(text) && !FALSE_POSITIVES.has(text)) found.push(text);
            // Also within longer text
            const m = text.match(/\\bCode[:\\s]+([A-Z0-9]{6})\\b/i) ||
                      text.match(/code\\s+is\\s+([A-Z0-9]{6})/i);
            if (m) found.push(m[1].toUpperCase());
        }
        if (found.length > 0) return found[0];

        // Check data attributes
        const withData = document.querySelector('[data-code],[data-challenge-code],[data-answer]');
        if (withData) {
            const c = withData.dataset.code || withData.dataset.challengeCode || withData.dataset.answer;
            if (c && /^[A-Z0-9]{4,10}$/i.test(c.trim())) return c.trim().toUpperCase();
        }
        return null;
    }

    // First try: code already visible?
    let code = searchCode();
    if (code) return code;

    // If not found, try to reveal it based on challenge type

    // Hidden DOM Challenge: click the challenge div that says "click here to reveal"
    // Use broad selector to catch both class-based and inline-style cursor:pointer
    const hiddenDomEl = [...document.querySelectorAll('div, section, article')].find(d => {
        const isClickable = d.className.includes('cursor-pointer') ||
                           d.style.cursor === 'pointer' ||
                           getComputedStyle(d).cursor === 'pointer';
        return isClickable && (d.textContent.includes('click here') ||
                               d.textContent.includes('Click here') ||
                               d.textContent.includes('Hidden DOM'));
    });
    if (hiddenDomEl) {
        for (let i = 0; i < 4; i++) {
            hiddenDomEl.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
            hiddenDomEl.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true}));
            hiddenDomEl.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
        }
        code = searchCode();
        if (code && code !== 'HIDDEN') return code;
    }

    // Click to Reveal: click the Reveal Code button
    const revealBtn = [...document.querySelectorAll('button')].find(b => b.textContent.includes('Reveal Code'));
    if (revealBtn) {
        revealBtn.click();
        code = searchCode();
        if (code) return code;
    }

    // Scroll to Reveal: dispatch wheel events to trigger scroll listener
    for (let i = 0; i < 6; i++) {
        window.dispatchEvent(new WheelEvent('wheel', {deltaY: 300, bubbles: true}));
        window.scrollBy(0, 300);
    }
    code = searchCode();
    if (code) return code;

    return 'not found';
}"""


def _handle_state_tool(name: str, args: dict, state: StepState) -> str:
    """Handle state management tool calls (Python-side, no MCP involved).

    Also mutates state immediately so subsequent tool calls in the same step
    can access newly stored facts/completions.

    Note: enter_code_in_input and get_code_from_page are handled separately
    in execute_step() because they need async MCP access.
    """
    if name == "store_fact":
        key = str(args.get("key", "")).strip()
        value = str(args.get("value", "")).strip()
        if key:
            state.facts[key] = value
        return f"Stored: {key} = {value}"

    elif name == "mark_complete":
        step_desc = str(args.get("step", "")).strip()
        if step_desc:
            state.completed_steps.append(step_desc)
        return f"Step completed: {step_desc} (total: {len(state.completed_steps)})"

    elif name == "get_facts":
        if not state.facts:
            return "No facts stored yet."
        lines = ["Stored facts:"]
        lines.extend(f"  {k}: {v}" for k, v in state.facts.items())
        return "\n".join(lines)

    elif name == "get_progress":
        if not state.completed_steps:
            return "No steps completed yet."
        lines = ["Completed steps:"]
        lines.extend(f"  {i + 1}. {s}" for i, s in enumerate(state.completed_steps))
        return "\n".join(lines)

    else:
        return f"Unknown state tool: {name}"


async def _enter_code_tool(mcp: PlaywrightMCPSession, code: str) -> str:
    """Enter a code into the challenge form using React-compatible events.

    Bypasses the need for a snapshot ref — finds the input via CSS selector,
    uses nativeInputValueSetter to trigger React synthetic events, then submits.
    """
    import json as _json

    if not code:
        return "Error: no code provided"

    # Sanitize code for JS string embedding (only alphanumeric expected)
    safe_code = code.strip()[:20]

    # Build fill JS: find input, set value via React-compatible method, fire events
    fill_js = f"""() => {{
        const input = document.querySelector('input[placeholder*="code"], input[placeholder*="Code"]');
        if (!input) return JSON.stringify({{ok: false, error: 'input not found'}});
        input.scrollIntoView({{block: 'center'}});
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, '{safe_code}');
        input.dispatchEvent(new Event('input', {{bubbles: true}}));
        input.dispatchEvent(new Event('change', {{bubbles: true}}));
        input.focus();
        return JSON.stringify({{ok: true, value: input.value}});
    }}"""

    fill_result = await mcp.call_tool("browser_evaluate", {"function": fill_js})
    await asyncio.sleep(0.8)  # Let React process the state change

    # Submit the form
    submit_result = await mcp.call_tool("browser_evaluate", {"function": _SUBMIT_FORM_JS})

    # Poll for page to fully render (React needs time to hydrate after full-page reload)
    for _wait_attempt in range(6):  # up to 18 seconds total
        await asyncio.sleep(3)
        body_check = await mcp.call_tool(
            "browser_evaluate",
            {"function": "() => document.querySelector('#root')?.children?.length || 0"},
        )
        # If React rendered at least one child, we're good
        if "0" not in body_check[:20] and "Error" not in body_check:
            break

    # Check resulting URL
    url_result = await mcp.call_tool(
        "browser_evaluate", {"function": "() => location.href"}
    )

    # Extract URL from result
    import re as _re
    url_match = _re.search(r'https?://\S+step\d+\S*', url_result)
    new_url = url_match.group(0).rstrip('"') if url_match else "unknown"
    new_step_match = _re.search(r'/step(\d+)', new_url)
    new_step_num = new_step_match.group(1) if new_step_match else "?"

    # Determine if URL changed (success)
    url_changed = new_step_num != "?" and new_url != "unknown"

    if url_changed:
        return (
            f"SUCCESS: Entered code '{safe_code}'. Now on step{new_step_num}. "
            f"URL: {new_url} | "
            f"Call mark_complete('Entered {safe_code}, advanced to step{new_step_num}') then "
            f"call get_code_from_page() to find step{new_step_num}'s code."
        )
    else:
        return (
            f"SUBMITTED code '{safe_code}' but URL unchanged. "
            f"Fill: {fill_result[:40].replace(chr(10), ' ')} | "
            f"URL: {url_result[:60].replace(chr(10), ' ')} | "
            f"The code may be wrong or scroll challenge not satisfied. "
            f"Try browser_press_key('PageDown') × 3 then retry enter_code_in_input."
        )


async def execute_step(
    engine: BedrockEngine,
    mcp: PlaywrightMCPSession,
    state: StepState,
    system_prompt: str = SYSTEM_PROMPT,
    max_calls: int = 20,
) -> StepResult:
    """Execute a single logical step in an isolated mini-conversation.

    CRITICAL PROPERTY: The `messages` list is local to this function.
    When it returns, the conversation is garbage collected.
    Only `StepResult` (structured data, ~bytes) persists to the coordinator.

    This is what prevents quadratic token growth:
    - Each step starts with a fresh context (~1800 tokens overhead)
    - State is injected as a compact text block (<200 tokens)
    - Previous step conversations are completely discarded

    Args:
        engine: Bedrock API wrapper (tracks cumulative tokens across all steps)
        mcp: Playwright MCP session (persistent — same browser for all steps)
        state: Current state (URL, facts, completed_steps) — mutated in-place
        system_prompt: System prompt for the agent
        max_calls: Maximum LLM API calls per step (circuit breaker)

    Returns:
        StepResult with discoveries, token count, and completion flag
    """
    # Track what this step discovers (also updated into state immediately)
    step_new_facts: dict[str, str] = {}
    step_new_completed: list[str] = []

    # Track initial completed/facts length to detect new additions
    initial_completed_count = len(state.completed_steps)
    initial_facts = set(state.facts.keys())

    # Build fresh messages — NO history from previous steps
    initial_prompt = build_step_prompt(state)
    messages: list[dict] = [
        {"role": "user", "content": [{"text": initial_prompt}]}
    ]

    tool_config = _build_tool_config(mcp)
    tokens_before = engine.total_tokens
    tool_calls_made = 0
    last_text = ""
    last_turn = None

    for _i in range(max_calls):
        turn = engine.call(system_prompt, messages, tool_config)
        last_turn = turn
        messages.append(turn.assistant_message)

        if turn.text:
            last_text = turn.text

        # No tool calls means the model is done with this step
        if not turn.tool_calls:
            break

        # Execute each tool call and collect results
        results: list[ToolResult] = []
        for tc in turn.tool_calls:
            tool_calls_made += 1
            try:
                if tc.name.startswith("browser_"):
                    result_text = await mcp.call_tool(tc.name, tc.args)
                elif tc.name == "enter_code_in_input":
                    result_text = await _enter_code_tool(mcp, tc.args.get("code", ""))
                    # Auto-track successful submissions so the action hint knows this code was submitted
                    if result_text.startswith("SUCCESS:"):
                        _code = tc.args.get("code", "")
                        _step_m = _re_module.search(r"step(\d+)", result_text)
                        _step_n = _step_m.group(1) if _step_m else "next"
                        _auto_complete = f"Entered {_code}, advanced to step{_step_n}"
                        # Only add if not already present (avoid duplicates with explicit mark_complete)
                        if not any(_code in s for s in state.completed_steps):
                            state.completed_steps.append(_auto_complete)
                            step_new_completed.append(_auto_complete)
                elif tc.name == "get_code_from_page":
                    result_text = await mcp.call_tool(
                        "browser_evaluate", {"function": _GET_CODE_JS}
                    )
                    # If not found, retry up to 3 times with 2s between each.
                    # Handles: (a) async React re-render after JS click, (b) Delayed Reveal challenges
                    # (some challenges show code after 4+ seconds without any action).
                    for _retry in range(3):
                        _needs_retry = (
                            "not found" in result_text
                            or result_text.strip().strip('"') in ("HIDDEN", "not found")
                        )
                        if not _needs_retry:
                            break
                        await asyncio.sleep(2)
                        result_text = await mcp.call_tool(
                            "browser_evaluate", {"function": _GET_CODE_JS}
                        )
                else:
                    result_text = _handle_state_tool(tc.name, tc.args, state)
            except Exception as exc:
                result_text = f"Error executing {tc.name}: {exc}"

            # Debug: log tool call to stderr (remove in production)
            import sys
            print(
                f"    [tool] {tc.name}({str(tc.args)[:55]}) → "
                f"{result_text[:75].replace(chr(10), ' ')}",
                file=sys.stderr,
                flush=True,
            )

            results.append(ToolResult(id=tc.id, content=result_text))

        messages.append(engine.make_tool_result_message(results))
    # END conversation loop — messages goes out of scope, will be GC'd

    tokens_used = engine.total_tokens - tokens_before

    # Detect what was discovered during this step
    for k, v in state.facts.items():
        if k not in initial_facts:
            step_new_facts[k] = v

    for s in state.completed_steps[initial_completed_count:]:
        step_new_completed.append(s)

    # Check if model signaled full task completion
    task_complete = "TASK COMPLETE" in last_text.upper()

    # Determine step success
    made_progress = bool(step_new_completed) or bool(step_new_facts) or task_complete

    # Build step summary
    if task_complete:
        step_summary = last_text[:500]
    elif step_new_completed:
        step_summary = f"Completed: {', '.join(step_new_completed)}"
    elif last_text:
        step_summary = last_text[:200]
    else:
        step_summary = f"Step {state.step_number}: {tool_calls_made} tool calls, no explicit completion"

    return StepResult(
        success=made_progress,
        step_summary=step_summary,
        new_facts=step_new_facts,
        new_completed=step_new_completed,
        tokens_used=tokens_used,
        tool_calls_made=tool_calls_made,
        task_complete=task_complete,
    )
