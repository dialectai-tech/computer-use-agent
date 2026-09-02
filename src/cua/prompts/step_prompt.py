"""System prompt and step prompt builder for the step-reset agent.

No imports from cua.agent to avoid circular dependencies.
The build_step_prompt function accepts any object with the right attributes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cua.agent.step_executor import StepState


SYSTEM_PROMPT = """You are a browser automation agent completing a 30-step browser navigation challenge.

## THE EXACT WORKFLOW FOR EVERY STEP PAGE

When you land on a challenge step page (/step1, /step2, etc.):

1. **CALL get_code_from_page() IMMEDIATELY** — it auto-reveals and returns the code
   - Do NOT try browser_click on challenge elements
   - Do NOT try browser_evaluate to click things manually
   - get_code_from_page() handles Hidden DOM, Scroll to Reveal, and Click to Reveal automatically
   - If it returns "HIDDEN" or "not found", call it AGAIN (wait one moment first)

2. **CALL store_fact("code_stepN", code)** — save the discovered code

3. **CALL enter_code_in_input(code)** — enters code with React-compatible events and submits
   - It returns the new URL when done (e.g. "URL: .../step2?version=1")

4. **CALL browser_snapshot()** — see the new step page
   - DO NOT check body.innerHTML — React loads after the navigation
   - If snapshot shows a new step (e.g. /step2), proceed to get_code_from_page()
   - The browser stays on the new step even if snapshot briefly shows loading

5. **CALL mark_complete("Entered code X, advanced to stepY")** — record progress

6. **REPEAT from step 1** on the new step page

## INITIAL NAVIGATION
If current URL is / (home page), click the START button first:
  browser_click(ref of START button)
Then proceed with the workflow above.

## AFTER get_code_from_page() Returns "not found" or "HIDDEN"
This means the challenge needs a trigger. Try:
  browser_press_key("PageDown") × 3 — for scroll challenges
Then call get_code_from_page() again.

## POPUP HANDLING
Before the workflow: remove all popups in one shot:
  browser_evaluate(() => document.querySelectorAll('[role="dialog"],[class*="modal"],[class*="overlay"],[class*="popup"],[class*="cookie"],[class*="consent"],[class*="banner"],[class*="backdrop"]').forEach(e=>e.remove()))

## AFTER CODE SUBMISSION
When enter_code_in_input returns a new URL (e.g. step2):
- DO NOT check body.innerHTML — React loads asynchronously, always blank initially
- DO NOT navigate back to /
- Just call browser_snapshot() and proceed to get_code_from_page()

## COMPLETION
When all 30 steps done: output "TASK COMPLETE: Completed all 30 steps"
"""


def build_step_prompt(state: Any) -> str:
    """Build the user message for a step, injecting current state context.

    Adds specific action hints when codes are known (guide the model directly).

    Args:
        state: StepState object with url, task, completed_steps, facts, step_number

    Returns:
        Prompt string for the model
    """
    parts = [f"Current URL: {state.url}"]

    if state.completed_steps:
        parts.append("Already completed (do NOT repeat these):")
        for i, s in enumerate(state.completed_steps, 1):
            parts.append(f"  {i}. {s}")

    if state.facts:
        parts.append("Discovered facts (codes already found):")
        for k, v in state.facts.items():
            parts.append(f"  {k}: {v}")

    parts.append(f"\nTask: {state.task}")

    # Add action hint based on current state
    hint = _build_action_hint(state)
    if hint:
        parts.append(f"\nACTION HINT: {hint}")

    parts.append(
        f"\n(Step {state.step_number}) Begin: clear all popups, take browser_snapshot(), "
        "then complete the next logical step."
    )

    return "\n".join(parts)


def _build_action_hint(state: Any) -> str:
    """Generate a specific action hint based on current state."""
    import re

    url = state.url or ""
    step_match = re.search(r"/step(\d+)", url)
    current_step_num = int(step_match.group(1)) if step_match else 0

    # Check for unsubmitted codes
    code_facts = {k: v for k, v in state.facts.items()
                  if any(word in k.lower() for word in ["code", "step", "key", "token"])}
    unsubmitted = {
        k: v for k, v in code_facts.items()
        if not any(v in s for s in state.completed_steps)
    }

    if current_step_num == 0:
        # On home page — need to navigate to challenge
        return "Click the START button to begin the challenge, then call get_code_from_page()."

    if unsubmitted:
        # Have code to submit
        code_val = next(iter(unsubmitted.values()))
        return (
            f"IMMEDIATE ACTION: Call enter_code_in_input(code='{code_val}') to submit. "
            f"Then browser_snapshot() to see next step. "
            f"Then mark_complete('Entered {code_val}, advanced to step {current_step_num + 1}')."
        )

    # On a step page, need to find the code
    return (
        f"IMMEDIATE ACTION: Call get_code_from_page() to find the code for step {current_step_num}. "
        "If it returns 'not found', call browser_press_key('PageDown') × 3 then try again. "
        "Then enter_code_in_input(code), then mark_complete(...)."
    )
