# Atomic Flag-to-Prompt Mapping

## Overview

This document defines the **atomic relationships** between CLI flags and prompt components. Each flag controls specific functionality AND the prompts that reference that functionality.

**Core Principle**: If a flag disables a feature, prompts referencing that feature should NOT be included.

---

## Flag-to-Prompt Mappings

### 1. Search Data Sources

**Flags:**
- `--use-page-text` / `--no-page-text` (default: enabled)
- `--use-accessibility-tree` / `--no-accessibility-tree` (default: disabled)

**Combined Logic:**
```python
has_search_tool = use_page_text OR use_accessibility_tree
```

**Prompt Control:**
- `SEARCH_TOOL_GUIDE` - **Conditional**
  - Included: Only if `has_search_tool=True`
  - Contains: Instructions for using `search_page_content(query)`
  - Reason: Search tool requires data to search (page text OR accessibility tree)

- `TOOL_USAGE_ESSENTIALS` vs `TOOL_USAGE_ESSENTIALS_NO_SEARCH` - **Conditional**
  - `TOOL_USAGE_ESSENTIALS`: Included when `has_search_tool=True`
    - Priority: "search → DOM → coordinates"
  - `TOOL_USAGE_ESSENTIALS_NO_SEARCH`: Included when `has_search_tool=False`
    - Priority: "DOM → coordinates → screenshot"

**Validation:**
```python
if not use_page_text and not use_accessibility_tree:
    # Warning: search_page_content tool will have no data
    # Agent will rely on DOM manipulation and coordinates only
```

---

### 2. Two-Phase Workflow

**Flag:**
- `--two-phase-workflow` / `--no-two-phase-workflow` (default: disabled)

**Prompt Control:**
- `TWO_PHASE_PROMPT_P1` - **Conditional**
  - Included: Only if `two_phase=True`
  - Contains: "PHASE 1: SEARCH ONLY" instructions
  - Replaces: TOOL_USAGE_ESSENTIALS (mutually exclusive)

- `TWO_PHASE_PROMPT_P2` - **Runtime**
  - Sent during execution when transitioning from Phase 1 to Phase 2
  - Contains: Phase 2 instructions with search results from Phase 1

**Validation:**
```python
if two_phase_workflow and not use_page_text and not use_accessibility_tree:
    # ERROR: Two-phase requires data source for Phase 1 search
    sys.exit(1)
```

---

### 3. Always-Available Tools

**Flags:** None (these tools are always available)

**Prompt Control:**
- `BROWSER_FIND_GUIDE` - **Always included**
  - Tool: `browser_find("text")`
  - Reason: Uses browser's native Ctrl+F, doesn't require any flags

- `DOM_TOOL_GUIDE` - **Always included**
  - Tool: `dom_manipulation(action_type="...", ...)`
  - Reason: DOM access is always available, doesn't require any flags
  - **Critical**: Contains action_type examples that AI needs to use tool correctly

- `CONTEXT_RESET_GUIDE` - **Always included**
  - Tool: `reset_context(reason, progress_summary, next_goal)`
  - Reason: Context management is always available

---

## Implementation

### Prompt Building Logic

**File:** `src/cua/prompts/__init__.py`

```python
def build_initial_prompt(
    user_prompt: str,
    has_search_tool: bool = True,
    has_page_text: bool = True,
    two_phase: bool = False
) -> str:
    parts = [user_prompt, AUTONOMOUS_MODE]

    # ATOMIC RULE: Only include guides for tools that will actually work

    # SEARCH_TOOL_GUIDE: Only if search tool has data to search
    if has_search_tool:
        parts.append(SEARCH_TOOL_GUIDE)

    # BROWSER_FIND_GUIDE: Always available
    parts.append(BROWSER_FIND_GUIDE)

    # DOM_TOOL_GUIDE: Always available (CRITICAL: Contains action_type examples)
    parts.append(DOM_TOOL_GUIDE)

    # CONTEXT_RESET_GUIDE: Always available
    parts.append(CONTEXT_RESET_GUIDE)

    if two_phase:
        parts.append(TWO_PHASE_PROMPT_P1)
    else:
        # Use appropriate essentials based on search tool availability
        if has_search_tool:
            parts.append(TOOL_USAGE_ESSENTIALS)
        else:
            parts.append(TOOL_USAGE_ESSENTIALS_NO_SEARCH)

    return "\n\n".join(parts)
```

### Provider Logic

**Files:** `src/cua/providers/bedrock.py`, `openai.py`, `claude.py`

All providers calculate `has_search_tool` based on actual data availability:

```python
has_search_tool = page_text is not None or (accessibility_tree and not accessibility_tree.get("error"))

full_prompt = build_initial_prompt(
    user_prompt=prompt,
    has_search_tool=has_search_tool,
    has_page_text=bool(page_text),
    two_phase=False
)
```

### CLI Validation

**File:** `src/cua/main.py`

```python
# Validate flag combinations (atomic flag-to-feature relationships)
if not use_page_text and not use_accessibility_tree:
    console.print("⚠️  Warning: search_page_content tool will have no data to search.")
    console.print("   Agent will rely on DOM manipulation and coordinate-based actions only.")

if two_phase_workflow and not use_page_text and not use_accessibility_tree:
    console.print("Error: --two-phase-workflow requires either --use-page-text or --use-accessibility-tree")
    console.print("Enable at least one: --use-page-text (recommended) or --use-accessibility-tree")
    sys.exit(1)
```

---

## Test Coverage

**File:** `/tmp/test_atomic_flags.py`

All scenarios tested and passing:

1. ✅ **Default** (page_text=True) → SEARCH_TOOL_GUIDE included
2. ✅ **No data sources** (both=False) → SEARCH_TOOL_GUIDE excluded, NO_SEARCH variant used
3. ✅ **Only accessibility tree** → SEARCH_TOOL_GUIDE included
4. ✅ **Both sources** → SEARCH_TOOL_GUIDE included
5. ✅ **Two-phase with search** → TWO_PHASE_PROMPT_P1 included, essentials excluded
6. ✅ **Two-phase without search** → CLI blocks this combination (validation test)

Run tests:
```bash
python /tmp/test_atomic_flags.py
```

---

## Flag Combination Matrix

| page_text | accessibility_tree | has_search_tool | SEARCH_TOOL_GUIDE | TOOL_USAGE_ESSENTIALS |
|-----------|-------------------|-----------------|-------------------|----------------------|
| ✓         | ✓                 | ✓               | ✓ Included        | Regular (with search) |
| ✓         | ✗                 | ✓               | ✓ Included        | Regular (with search) |
| ✗         | ✓                 | ✓               | ✓ Included        | Regular (with search) |
| ✗         | ✗                 | ✗               | ✗ Excluded        | NO_SEARCH variant    |

| two_phase | has_search_tool | TWO_PHASE_PROMPT_P1 | TOOL_USAGE_ESSENTIALS | CLI Validation |
|-----------|-----------------|---------------------|----------------------|----------------|
| ✓         | ✓               | ✓ Included          | ✗ Excluded           | ✅ Allowed     |
| ✓         | ✗               | ✓ Included          | ✗ Excluded           | ❌ Blocked     |
| ✗         | ✓               | ✗ Excluded          | ✓ Included           | ✅ Allowed     |
| ✗         | ✗               | ✗ Excluded          | ✓ Included (NO_SEARCH)| ✅ Allowed (with warning) |

---

## Prompt Component Sizes

| Component                        | Size (chars) | Conditional? | Depends On           |
|----------------------------------|--------------|--------------|----------------------|
| User prompt                      | ~50-200      | No           | -                    |
| AUTONOMOUS_MODE                  | ~57          | No           | -                    |
| SEARCH_TOOL_GUIDE                | ~78          | **Yes**      | has_search_tool      |
| BROWSER_FIND_GUIDE               | ~83          | No           | -                    |
| DOM_TOOL_GUIDE                   | ~388         | No           | -                    |
| CONTEXT_RESET_GUIDE              | ~437         | No           | -                    |
| TWO_PHASE_PROMPT_P1              | ~201         | **Yes**      | two_phase            |
| TOOL_USAGE_ESSENTIALS            | ~121         | **Yes**      | has_search_tool (normal mode) |
| TOOL_USAGE_ESSENTIALS_NO_SEARCH  | ~108         | **Yes**      | !has_search_tool (normal mode) |

**Total prompt size:**
- Default (search available): ~1,440 chars
- No search: ~1,383 chars
- Two-phase (search available): ~1,641 chars

---

## Why This Matters

### Before Atomic Mapping:
```
User runs: cua --no-page-text --url ... --prompt "Click START"

Prompt sent to AI:
  ✓ "Use search_page_content(query) BEFORE other actions"  ← AI tries to use this
  ✓ "dom_manipulation(action_type='find_selectors')"

AI attempts: search_page_content(query="START")
Result: Tool returns empty (no data to search!)
AI state: Confused, wastes iterations retrying search
```

### After Atomic Mapping:
```
User runs: cua --no-page-text --url ... --prompt "Click START"

Prompt sent to AI:
  ✗ SEARCH_TOOL_GUIDE (not included - search unavailable)
  ✓ BROWSER_FIND_GUIDE (always available)
  ✓ DOM_TOOL_GUIDE (always available)
  ✓ TOOL_USAGE_ESSENTIALS_NO_SEARCH: "Priority: DOM → coordinates"

AI uses: dom_manipulation(action_type="find_selectors", search_text="START")
Result: ✓ Works correctly, no wasted iterations
```

---

## Key Principles

1. **Atomic Control**: Each flag controls both functionality AND prompts
2. **No False Promises**: Never tell AI about tools that won't work
3. **Always Available**: Tools without flag dependencies always get guides
4. **Fail Fast**: CLI validation catches invalid combinations early
5. **Clear Alternatives**: When a tool is unavailable, prompt shows alternatives

---

## Related Files

- `src/cua/main.py` - CLI flags and validation
- `src/cua/prompts/__init__.py` - Prompt building logic
- `src/cua/providers/bedrock.py` - Bedrock provider implementation
- `src/cua/providers/openai.py` - OpenAI provider implementation
- `src/cua/providers/claude.py` - Claude provider implementation
- `/tmp/test_atomic_flags.py` - Comprehensive test suite

---

## Historical Context

This implementation was added in response to a critical bug where:
1. CLI default was changed to `--no-page-text`
2. Tool guides were always included regardless of flag state
3. AI received instructions to use `search_page_content` but search had no data
4. AI used wrong parameter names because guides were missing

The fix ensures flags atomically control both functionality and prompts, preventing such mismatches.

**Related Documentation:**
- `PROMPT_FLOW_INVESTIGATION.md` - Investigation that revealed the bug
- `AGENT_FLOW_DIAGRAM.md` - Overall agent flow and decision-making
