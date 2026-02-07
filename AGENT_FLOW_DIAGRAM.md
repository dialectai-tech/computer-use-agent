# Agent Process Flow Diagram

## Overview
This document explains how the CUA agent works, what prompts it uses, and how it decides what to do next.

---

## 1. Initial Setup Phase

```
┌─────────────────────────────────────────────────────────────┐
│                    USER STARTS AGENT                         │
│  Command: cua --url <url> --prompt "Complete the task"      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              SYSTEM PROMPT (Sent ONCE via API)               │
│ ------------------------------------------------------------ │
│  Content: SYSTEM_PROMPT from prompts/__init__.py            │
│  Size: ~500 tokens (optimized)                              │
│  Purpose: Core instructions and capabilities                │
│                                                              │
│  Key sections:                                               │
│  • "You are an autonomous computer use agent..."            │
│  • Core Workflow (search → DOM → coordinates)               │
│  • Tool Priority ranking                                     │
│  • CRITICAL Rules (remember tags, transient marking)        │
│  • When Stuck guidance                                       │
│                                                              │
│  Sent via: Bedrock 'system' parameter (cached by API)       │
│  Frequency: ONCE per session                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│            INITIAL USER MESSAGE COMPOSITION                  │
│ ------------------------------------------------------------ │
│  Components (in order):                                      │
│                                                              │
│  1. USER TASK PROMPT                                        │
│     • What the user wants to accomplish                      │
│     • Example: "Complete the browser navigation challenge"  │
│                                                              │
│  2. AUTONOMOUS_MODE                                         │
│     • "Act autonomously. Observe results and continue..."   │
│                                                              │
│  3. SEARCH_TOOL_GUIDE                                       │
│     • "Use search_page_content(query) BEFORE actions"       │
│                                                              │
│  4. BROWSER_FIND_GUIDE                                      │
│     • "After search, use browser_find to navigate"          │
│                                                              │
│  5. DOM_TOOL_GUIDE                                          │
│     • "DOM Tool (10-100x faster!)"                          │
│     • Shows exact syntax: find_selectors, click_selector    │
│     • CRITICAL: Shows required parameter names              │
│                                                              │
│  6. CONTEXT_RESET_GUIDE                                     │
│     • "Context Reset (60-80% token savings!)"               │
│     • Shows exact example with all 3 required params        │
│     • When to use / when NOT to use                         │
│                                                              │
│  7. TOOL_USAGE_ESSENTIALS                                   │
│     • Priority: search → DOM → coordinates                  │
│     • Keyboard shortcuts                                     │
│                                                              │
│  8. SCREENSHOT (if not two-phase mode)                      │
│     • Base64 PNG image                                      │
│     • ~1,400 tokens                                         │
│                                                              │
│  9. PAGE TEXT (initial page only)                           │
│     • Visible text from webpage                             │
│     • Up to 10,000 chars                                    │
│     • ~2,500 tokens                                         │
│                                                              │
│  10. ACCESSIBILITY TREE (if enabled)                        │
│      • JSON structure of page                               │
│      • ~1,000-4,000 tokens                                  │
│                                                              │
│  Total Initial Message: ~4,500-5,000 tokens                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  TOOLS AVAILABLE TO AI                       │
│ ------------------------------------------------------------ │
│                                                              │
│  Tool 1: search_page_content                                │
│    Parameters: query (required), search_type (optional)     │
│    Purpose: Find text/elements on page before acting        │
│    Returns: Line numbers, matches (limited to 15)           │
│                                                              │
│  Tool 2: browser_find                                       │
│    Parameters: search_term (required), close_after          │
│    Purpose: Ctrl+F to scroll to content instantly           │
│    Returns: Success/failure, screenshot with highlight      │
│                                                              │
│  Tool 3: dom_manipulation                                   │
│    Parameters: action_type, selector, text, search_text     │
│    Action types:                                             │
│      • find_selectors - Find CSS selector by text           │
│      • click_selector - Click element (accepts "click")     │
│      • fill_selector - Fill input (accepts "fill")          │
│      • get_info - Get element details                       │
│      • evaluate_js - Run JavaScript                         │
│    Purpose: Direct DOM actions, 10-100x faster              │
│    Returns: Success/error, compact result                   │
│                                                              │
│  Tool 4: reset_context                                      │
│    Parameters: reason, progress_summary, next_goal (ALL 3!) │
│    Purpose: Clear conversation, save tokens, escape loops   │
│    Returns: Confirmation, context is reset                  │
│                                                              │
│  Tool 5: computer                                           │
│    Parameters: action, coordinate, text                     │
│    Actions: screenshot, left_click, type, key, scroll, etc  │
│    Purpose: Coordinate-based actions (fallback)             │
│    Returns: Screenshot after action                         │
│                                                              │
│  Tool 6: bash                                               │
│    Parameters: command                                       │
│    Purpose: Execute shell commands (rarely used)            │
│    Returns: Command output                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    [API CALL TO BEDROCK]
                            ↓
                  [AI GENERATES RESPONSE]
```

---

## 2. Main Iteration Loop

```
┌─────────────────────────────────────────────────────────────┐
│                    ITERATION N STARTS                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              AI RECEIVES PREVIOUS CONTEXT                    │
│ ------------------------------------------------------------ │
│  Context includes (from message history):                    │
│                                                              │
│  • First user message (kept always)                         │
│    - User task + all guides                                 │
│    - ~2,000-2,500 tokens                                    │
│                                                              │
│  • Last N conversation turns (N = context_window_size)      │
│    - Default: 5 turns kept                                  │
│    - Each turn = user message + assistant response          │
│    - Includes tool results + AI's reasoning                 │
│                                                              │
│  • Previous screenshots (up to N)                           │
│    - Each screenshot: ~1,400 tokens                         │
│    - Marked as "important" or "transient"                   │
│                                                              │
│  • Tool results from previous actions                       │
│    - Search results (compact, 15 max)                       │
│    - DOM results (compact format)                           │
│    - Error messages                                         │
│                                                              │
│  System prompt: CACHED by API (not re-sent)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           ADDITIONAL CONTEXT INJECTIONS                      │
│         (Added to user message based on state)               │
│ ------------------------------------------------------------ │
│                                                              │
│  IF stuck_detected (same action 3x):                        │
│    ⚠️ STUCK DETECTED: You've used 'X' 3 times...           │
│    Try a DIFFERENT approach:                                │
│    - If searching fails → Use browser_find or scroll        │
│    - If clicking fails → Verify element visible first       │
│    - Consider MULTIPLE actions in one response              │
│                                                              │
│  IF progress_check (every 10 iterations):                   │
│    📊 PROGRESS CHECK (Iteration X):                         │
│    Currently on Step Y of 30.                               │
│    Z more steps to complete.                                │
│    Remember: Keep working through ALL steps...              │
│                                                              │
│  IF two_phase_workflow && phase == 1:                       │
│    **PHASE 1: SEARCH ONLY (REQUIRED)**                      │
│    You do NOT have a screenshot yet.                        │
│    You MUST use search_page_content to find what you need.  │
│                                                              │
│  IF two_phase_workflow && phase == 2:                       │
│    📸 PHASE 2: NOW TAKE ACTION (REQUIRED)                   │
│    Search results from Phase 1: [results]                   │
│    You MUST use computer tool to take action.               │
│    Example: {"action": "left_click", "coordinate": [x,y]}   │
│    DO NOT just search again.                                │
│                                                              │
│  IF no_action_count > 0:                                    │
│    ⚠ No actions provided (attempt X/3)                      │
│    (With screenshot to show current state)                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    [API CALL TO BEDROCK]
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              AI GENERATES RESPONSE                           │
│ ------------------------------------------------------------ │
│  Response format:                                            │
│                                                              │
│  1. THINKING (visible to user)                              │
│     • AI explains what it sees                              │
│     • What it plans to do                                   │
│     • Example: "I can see the START button at [640, 227]"  │
│                                                              │
│  2. TOOL CALLS (0 or more)                                  │
│     • AI calls tools based on its plan                      │
│     • Can call MULTIPLE tools in one response               │
│     • Examples:                                             │
│       - search_page_content(query="Reveal Code")            │
│       - dom_manipulation(action_type="click_selector", ...) │
│       - computer(action="screenshot")                       │
│                                                              │
│  3. TRANSIENT MARKING (optional)                            │
│     • If action was transient: "TRANSIENT: Closed popup"   │
│     • Marks this iteration for removal later                │
│                                                              │
│  4. REMEMBER TAGS (optional)                                │
│     • [remember]CODE123[/remember]                          │
│     • Preserves important info during context pruning       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              AGENT PROCESSES AI RESPONSE                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
                 ┌──────────────────┐
                 │  Extract Actions  │
                 └──────────────────┘
                            ↓
              ┌─────────────────────────┐
              │  Are there any actions?  │
              └─────────────────────────┘
                     ↓           ↓
                   YES          NO
                     ↓           ↓
                     │      ┌─────────────────────────┐
                     │      │ Increment no_action_count│
                     │      │ If count >= 3: FAIL      │
                     │      │ Else: Send reminder +    │
                     │      │       screenshot         │
                     │      └─────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              FOR EACH ACTION: EXECUTE                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              ACTION EXECUTION ROUTING                        │
│ ------------------------------------------------------------ │
│                                                              │
│  IF action.type == SEARCH:                                  │
│    1. Get page_text from browser                            │
│    2. Get accessibility_tree (if enabled)                   │
│    3. Create SearchTool(page_text, tree)                    │
│    4. Call search_tool.search(query, max_results=15)        │
│    5. Return compact summary (not full JSON)                │
│                                                              │
│  IF action.type == DOM_MANIPULATION:                        │
│    1. Create DOMTool(browser)                               │
│    2. Normalize action_type ("click" → "click_selector")    │
│    3. Call dom_tool.execute(action)                         │
│    4. Return compact result:                                │
│       - Success: "✓ DOM action successful"                  │
│       - Fail: "✗ DOM action failed: error"                  │
│    5. NO page text or tree sent back                        │
│                                                              │
│  IF action.type == CONTEXT_RESET:                           │
│    1. Validate request (all 3 params present?)              │
│    2. If invalid: Return error to AI                        │
│    3. If valid:                                             │
│       a. Get current screenshot                             │
│       b. Get current page_info                              │
│       c. Call provider.reset_context()                      │
│       d. Keep ONLY first user message                       │
│       e. Add checkpoint message with:                       │
│          - Progress summary                                 │
│          - Next goal                                        │
│          - Current screenshot                               │
│       f. Clear message history except first + checkpoint    │
│    4. Return: "Context has been reset. Continue..."         │
│                                                              │
│  IF action.type == COMPUTER (screenshot/click/type/etc):    │
│    1. Call browser.execute_action(action)                   │
│    2. Take screenshot after action                          │
│    3. Return ONLY screenshot (no page text)                 │
│    4. Increment screenshot counter                          │
│                                                              │
│  IF action.type == BROWSER_FIND:                            │
│    1. Call browser.find_on_page(search_term)                │
│    2. Browser auto-scrolls to match, highlights it          │
│    3. Take screenshot showing highlighted text              │
│    4. Return screenshot with "Found X matches" message      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              TRACK ACTION PATTERNS                           │
│ ------------------------------------------------------------ │
│  • Count consecutive same actions                           │
│  • If same action 3x → stuck_detected = True                │
│  • Track which tools used recently                          │
│  • Track no_action_count                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         BUILD NEXT USER MESSAGE (Tool Results)               │
│ ------------------------------------------------------------ │
│  For each tool call in AI's response:                       │
│                                                              │
│  1. Create toolResult block                                 │
│     • toolUseId: matches tool call ID                       │
│     • content: [result text/image]                          │
│                                                              │
│  2. Format result based on tool:                            │
│     • search_page_content: Compact summary only             │
│     • dom_manipulation: "✓ Found: selector1, selector2"     │
│     • computer: Screenshot image only                       │
│     • reset_context: Confirmation message                   │
│                                                              │
│  3. Add screenshots if present                              │
│     • Screenshots are images in toolResult                  │
│     • Each ~1,400 tokens                                    │
│                                                              │
│  4. Inject any additional messages:                         │
│     • Stuck detection warning                               │
│     • Progress check                                        │
│     • Phase transition instructions                         │
│                                                              │
│  5. NO page text (unless search action)                     │
│  6. NO accessibility tree (unless search action)            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│            PRUNE MESSAGE HISTORY (If needed)                 │
│ ------------------------------------------------------------ │
│  Goal: Keep only recent N turns + first message             │
│                                                              │
│  Algorithm:                                                  │
│  1. Always keep: First user message (has all guides)        │
│  2. Keep: Last N complete turns (user + assistant pairs)    │
│     • N = context_window_size (default 5)                   │
│  3. Remove: Everything else (old turns, old screenshots)    │
│                                                              │
│  Transient content removal:                                  │
│  • If assistant response contains "TRANSIENT:", mark it     │
│  • These turns are eligible for early removal               │
│  • Preserves [remember] tagged content                      │
│                                                              │
│  Result: Message history stays manageable                    │
│          Tokens stay under control                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              CHECK COMPLETION CONDITIONS                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
              ┌──────────────────────────┐
              │  Is task complete?       │
              │  (No more tool calls)    │
              └──────────────────────────┘
                     ↓           ↓
                   YES          NO
                     ↓           ↓
           ┌──────────────┐     │
           │ Check if     │     │
           │ TRULY done   │     │
           └──────────────┘     │
                     ↓           │
           ┌──────────────┐     │
           │ Look for:    │     │
           │ "Task X/Y"   │     │
           │ "Step X/Y"   │     │
           └──────────────┘     │
                     ↓           │
           If X < Y: NOT DONE   │
           Continue with        │
           reminder             │
                     ↓           │
           If truly done:       │
           SUCCESS! Exit        │
                                │
                                │
               ┌────────────────┘
               │
               ↓
      [BACK TO TOP OF LOOP]

      Iteration N+1 begins...
```

---

## 3. How AI Decides Next Steps

```
┌─────────────────────────────────────────────────────────────┐
│              AI DECISION-MAKING PROCESS                      │
│         (How AI chooses what to do next)                     │
└─────────────────────────────────────────────────────────────┘

The AI uses these prompts/guides to decide:

1. SYSTEM_PROMPT (always active via system parameter)
   ├─ "Core Workflow: search → DOM → coordinates"
   ├─ Teaches: Always search BEFORE acting
   └─ Teaches: Prefer DOM over coordinates

2. Tool Guides in initial message (always in context)
   ├─ SEARCH_TOOL_GUIDE: "Use search_page_content BEFORE actions"
   ├─ DOM_TOOL_GUIDE: Shows exact syntax, tells AI it's 10-100x faster
   ├─ CONTEXT_RESET_GUIDE: When to reset (20+ iterations, after milestones)
   └─ TOOL_USAGE_ESSENTIALS: "Priority: search → DOM → coordinates"

3. Current context (what AI can see)
   ├─ Last screenshot: Shows visual state
   ├─ Previous actions: What was tried
   ├─ Tool results: What worked/failed
   └─ Conversation history: Last 5 turns

4. Injected warnings/reminders
   ├─ Stuck detection: "Try a DIFFERENT approach"
   ├─ Progress check: "29 more steps to complete"
   ├─ Phase 2 reminder: "You MUST use computer tool now"
   └─ No action reminder: "Make at least ONE tool call"

┌─────────────────────────────────────────────────────────────┐
│              DECISION FLOW EXAMPLE                           │
└─────────────────────────────────────────────────────────────┘

Scenario: AI sees "Reveal Code" button in screenshot

Step 1: AI reads SYSTEM_PROMPT
        → "Search first before acting"

Step 2: AI reads DOM_TOOL_GUIDE
        → "Use find_selectors to search by text"
        → "10-100x faster than coordinates"

Step 3: AI decides action priority:
        1st choice: dom_manipulation(action_type="find_selectors",
                                     search_text="Reveal Code")
        2nd choice: search_page_content(query="Reveal Code")
        3rd choice: computer(action="screenshot") to get coordinates

Step 4: AI calls dom_manipulation (fastest option)

Step 5: Result comes back:
        "✓ Found: button#reveal-code"

Step 6: AI reads result, decides next:
        → "I have the selector, now click it"
        → dom_manipulation(action_type="click_selector",
                          selector="button#reveal-code")

This is guided by:
- SYSTEM_PROMPT: "Prefer DOM over coordinates"
- DOM_TOOL_GUIDE: Shows exact syntax
- Recent context: Previous action succeeded
- No warnings: AI is making progress

┌─────────────────────────────────────────────────────────────┐
│           WHEN AI GETS STUCK - RECOVERY PROCESS              │
└─────────────────────────────────────────────────────────────┘

Iteration N: AI clicks button X
Iteration N+1: AI clicks button X again (no change)
Iteration N+2: AI clicks button X third time

→ Stuck detection triggers!

Injected message:
  ⚠️ STUCK DETECTED: You've used 'click' 3 times without progress.
  Try a DIFFERENT approach:
  - If clicking fails → Verify element visible in screenshot
  - Use search_page_content to understand what changed
  - Consider MULTIPLE actions in one response

AI reads this + context:
  - Sees same screenshot 3 times
  - Sees "STUCK DETECTED" warning
  - Remembers SYSTEM_PROMPT: "Try DIFFERENT approach"

AI decides:
  1. Take screenshot to see current state (verify)
  2. Use search_page_content to find alternatives
  3. Try DOM manipulation with different selector
  4. Or use coordinates as fallback

The warning + guides → AI changes strategy
```

---

## 4. Token Flow & Optimization

```
┌─────────────────────────────────────────────────────────────┐
│           WHAT GETS SENT WITH EACH ITERATION                 │
└─────────────────────────────────────────────────────────────┘

ITERATION 1 (Initial):
├─ System prompt: 500 tokens (via 'system' parameter, cached)
├─ First user message: 2,000 tokens
│  ├─ User task: 200 tokens
│  ├─ All guides: 1,500 tokens
│  ├─ Screenshot: 1,400 tokens
│  └─ Page text: 2,500 tokens (initial only)
├─ Tools definition: Sent via API metadata (not counted)
└─ TOTAL: ~5,000 tokens input

ITERATION 2-N (Continuation):
├─ System prompt: 0 tokens (CACHED by API, not re-sent!)
├─ Message history: Variable
│  ├─ First message: 2,000 tokens (always kept)
│  ├─ Last 5 turns: ~3,000-5,000 tokens
│  │  ├─ Tool results (compact): ~100-500 tokens each
│  │  ├─ AI responses: ~500-1,000 tokens each
│  │  └─ Screenshots: 1,400 tokens each (3-5 kept)
│  └─ Injected warnings: 0-300 tokens
├─ NO page text (unless search action)
├─ NO accessibility tree (unless search action)
└─ TOTAL: ~7,000-12,000 tokens input per iteration

OPTIMIZATIONS APPLIED:
✓ System prompt: Sent once via 'system' param (was 500 per iter)
✓ Search results: Limited to 15 matches (was unlimited)
✓ Tool results: Compact format (was verbose JSON)
✓ Page text: Only with search (was every action)
✓ Message pruning: Keep only 5 recent turns (was growing)

RESULT: ~75-80% token reduction!
```

---

## 5. Prompt Priority & Influence

```
┌─────────────────────────────────────────────────────────────┐
│     WHICH PROMPTS HAVE THE MOST INFLUENCE?                  │
│              (Ranked by impact on AI decisions)              │
└─────────────────────────────────────────────────────────────┘

🥇 HIGHEST PRIORITY - SYSTEM_PROMPT
   • Always active (sent via 'system' parameter)
   • Defines core behavior: "search first, use DOM, act autonomously"
   • AI treats this as fundamental rules
   • Cannot be overridden by other prompts

🥈 HIGH PRIORITY - Recent Context (Last 3-5 turns)
   • What happened in last few iterations
   • What AI tried, what worked/failed
   • Current screenshot showing visual state
   • Recent tool results
   • AI weighs this heavily when deciding next step

🥉 MEDIUM PRIORITY - Tool Guides (DOM, Search, Context Reset)
   • Teaches exact syntax and parameters
   • Shows examples of correct usage
   • AI refers to these when using tools
   • Important for preventing errors

🏅 MEDIUM PRIORITY - Injected Warnings
   • Stuck detection: "Try DIFFERENT approach"
   • Progress check: "29 more steps to complete"
   • Phase transitions: "You MUST take action now"
   • These interrupt AI's current strategy

🎖️ LOW PRIORITY - User Task (Original prompt)
   • What user originally asked for
   • Always in context (first message)
   • But AI may lose track after many iterations
   • Progress checks help remind AI of goal

┌─────────────────────────────────────────────────────────────┐
│              HOW PROMPTS INTERACT                            │
└─────────────────────────────────────────────────────────────┘

Example: AI needs to click a button

SYSTEM_PROMPT says:
  "Prefer DOM manipulation over coordinates"
  ↓
DOM_TOOL_GUIDE says:
  "Use find_selectors first, then click_selector"
  ↓
Recent context shows:
  Last action: Found selector "button#start"
  ↓
AI decides:
  "I should use click_selector with the selector I just found"
  ↓
AI calls:
  dom_manipulation(action_type="click_selector", selector="button#start")

If that fails:

Result says:
  "✗ Error: Element not found"
  ↓
SYSTEM_PROMPT says:
  "When stuck, try DIFFERENT approach"
  ↓
Stuck detection injects:
  "⚠️ Clicking failed. Verify element visible in screenshot"
  ↓
AI decides:
  "I should take a screenshot first, then use coordinates"
  ↓
AI calls:
  computer(action="screenshot")

The prompts work together:
• System prompt: High-level strategy
• Tool guides: Tactical details
• Warnings: Course correction
• Context: Situational awareness
```

---

## 6. Special Modes & Features

```
┌─────────────────────────────────────────────────────────────┐
│              TWO-PHASE WORKFLOW MODE                         │
│         (When --two-phase-workflow flag used)                │
└─────────────────────────────────────────────────────────────┘

PHASE 1: Search Only
├─ No screenshot sent initially (save tokens)
├─ AI MUST use search_page_content
├─ Extra prompt injected:
│  "**PHASE 1: SEARCH ONLY (REQUIRED)**
│   You do NOT have a screenshot yet.
│   You MUST use search_page_content to find what you need."
└─ AI cannot take actions, only search

↓ (Search results stored)

PHASE 2: Action with Screenshot
├─ Search results from Phase 1 shown
├─ Screenshot now provided
├─ Extra prompt injected:
│  "📸 PHASE 2: NOW TAKE ACTION (REQUIRED)
│   Search results: [results from phase 1]
│   You MUST use computer tool to take action.
│   DO NOT just search again."
└─ AI must take at least one action

Purpose: Enforce search-first workflow, save tokens

┌─────────────────────────────────────────────────────────────┐
│              CONTEXT RESET FEATURE                           │
│           (AI can reset its own context)                     │
└─────────────────────────────────────────────────────────────┘

When AI calls: reset_context(
  reason="Completed Step 5, starting Step 6",
  progress_summary="Finished steps 1-5. Currently on Step 6.",
  next_goal="Find Step 6 code, enter it, submit"
)

What happens:
1. Validate: All 3 parameters present and long enough?
2. If invalid: Return error to AI
3. If valid:
   ├─ Keep: First user message (with all guides)
   ├─ Keep: Current screenshot
   ├─ Clear: All message history (old turns, screenshots)
   ├─ Add: Checkpoint message
   │  "**CONTEXT RESET - CHECKPOINT**
   │   Previous conversation cleared to save tokens.
   │
   │   **Current Progress:** [progress_summary]
   │   **Next Goal:** [next_goal]
   │
   │   Continue from this checkpoint."
   └─ Result: Fresh start, ~60-80% token savings

When to use:
• After completing major milestones (Step 5 → 6)
• When conversation is very long (20+ iterations)
• When stuck in a loop

When NOT to use:
• In middle of filling a form
• While troubleshooting an error
• Before iteration 15
```

---

## 7. Complete Example: Clicking START Button

```
┌─────────────────────────────────────────────────────────────┐
│        COMPLETE FLOW: "Click START button"                  │
└─────────────────────────────────────────────────────────────┘

USER COMMAND:
cua --url example.com --prompt "Click START button"

═══════════════════════════════════════════════════════════════
ITERATION 1
═══════════════════════════════════════════════════════════════

→ PROMPTS ACTIVE:
  ✓ SYSTEM_PROMPT (via 'system' param)
  ✓ User task: "Click START button"
  ✓ AUTONOMOUS_MODE
  ✓ SEARCH_TOOL_GUIDE
  ✓ DOM_TOOL_GUIDE
  ✓ CONTEXT_RESET_GUIDE
  ✓ TOOL_USAGE_ESSENTIALS
  ✓ Screenshot of initial page
  ✓ Page text (initial)

→ AI READS:
  • System prompt: "Search first, use DOM"
  • DOM guide: "Use find_selectors to search by text"
  • Screenshot: Shows page with START button
  • User task: "Click START button"

→ AI REASONING:
  "I see a START button in the screenshot.
   System prompt says to use DOM manipulation.
   DOM guide says to use find_selectors first.
   I should find the selector for START button."

→ AI CALLS TOOL:
  dom_manipulation(
    action_type="find_selectors",
    search_text="START"
  )

→ TOOL EXECUTES:
  • Browser runs JavaScript to find elements with "START" text
  • Finds: button.start-btn, button#begin, etc.
  • Returns: "✓ Found: button.start-btn, button#begin"

═══════════════════════════════════════════════════════════════
ITERATION 2
═══════════════════════════════════════════════════════════════

→ PROMPTS ACTIVE:
  ✓ SYSTEM_PROMPT (cached, not re-sent)
  ✓ First message (all guides) - kept
  ✓ Previous turn (iteration 1) - kept
  ✓ Tool result: "✓ Found: button.start-btn, button#begin"
  ✓ Screenshot (same as before, no new action yet)

→ AI READS:
  • Previous result: Found selectors for START
  • DOM guide: "Then use click_selector"
  • System prompt: "Be efficient, chain actions"

→ AI REASONING:
  "I found the selector button.start-btn.
   Now I should click it using click_selector.
   The result said it found the button, so it exists."

→ AI CALLS TOOL:
  dom_manipulation(
    action_type="click_selector",
    selector="button.start-btn"
  )

→ TOOL EXECUTES:
  • Browser executes: page.click("button.start-btn")
  • Button is clicked successfully
  • Page navigates to /step1
  • Returns: "✓ DOM action successful"
  • Screenshot taken showing new page

═══════════════════════════════════════════════════════════════
ITERATION 3
═══════════════════════════════════════════════════════════════

→ PROMPTS ACTIVE:
  ✓ SYSTEM_PROMPT (cached)
  ✓ First message (guides) - kept
  ✓ Last 2 turns - kept
  ✓ Tool result: "✓ DOM action successful"
  ✓ NEW screenshot showing Step 1 page

→ AI READS:
  • Previous action: Click succeeded
  • New screenshot: Shows Step 1 of challenge
  • User task: "Click START button" (DONE!)

→ AI REASONING:
  "The START button was clicked successfully.
   The page changed to Step 1.
   The task was to click START button.
   Task is complete!"

→ AI RESPONSE:
  "I successfully clicked the START button.
   The page has navigated to Step 1 of the challenge.
   Task completed."

  (No more tool calls)

→ AGENT DETECTS:
  • No tool calls in response
  • AI says "Task completed"
  • Task is marked as COMPLETE
  • Agent exits successfully

═══════════════════════════════════════════════════════════════
SUMMARY: Which prompts influenced each decision?
═══════════════════════════════════════════════════════════════

Iteration 1: Use find_selectors
  Influenced by:
  🥇 SYSTEM_PROMPT: "Search first, use DOM"
  🥉 DOM_TOOL_GUIDE: Shows find_selectors syntax
  🥈 Screenshot: Shows START button exists

Iteration 2: Use click_selector
  Influenced by:
  🥈 Previous result: "Found button.start-btn"
  🥉 DOM_TOOL_GUIDE: "Then use click_selector"
  🥇 SYSTEM_PROMPT: "Be efficient"

Iteration 3: Declare complete
  Influenced by:
  🥈 New screenshot: Shows different page
  🥈 Previous result: "✓ DOM action successful"
  🎖️ User task: "Click START button" (goal achieved)
```

---

## 8. Key Takeaways

### For Understanding Agent Behavior

1. **System Prompt is King**
   - Sent once via 'system' parameter (cached by API)
   - Defines core strategy: search → DOM → coordinates
   - AI always refers to this as foundation

2. **Guides Teach Tactics**
   - DOM_TOOL_GUIDE: Exact syntax, parameter names
   - SEARCH_TOOL_GUIDE: When and how to search
   - CONTEXT_RESET_GUIDE: With complete examples
   - These prevent errors and guide correct usage

3. **Context Drives Decisions**
   - Recent actions (last 5 turns) heavily influence AI
   - Screenshots show visual state
   - Tool results show what worked/failed
   - AI adapts based on what it sees

4. **Warnings Correct Course**
   - Stuck detection: Forces strategy change
   - Progress checks: Reminds of overall goal
   - Phase transitions: Enforces workflow
   - No-action reminders: Prevents stalling

5. **Token Efficiency Matters**
   - System prompt: Sent once, not repeated
   - Search results: Limited to 15 matches
   - Tool results: Compact format
   - Message history: Pruned to 5 turns
   - Page text: Only when needed

### For Debugging Issues

1. **AI not using tools correctly?**
   → Check tool guides have clear examples

2. **AI getting stuck in loops?**
   → Check stuck detection is triggering
   → Check SYSTEM_PROMPT has "try DIFFERENT approach"

3. **AI losing track of goal?**
   → Check progress checks are injected
   → Check user task is in first message (always kept)

4. **Tokens growing too fast?**
   → Check system prompt not in message history
   → Check page text only sent with search
   → Check message pruning is working

5. **Context reset not working?**
   → Check AI providing all 3 required parameters
   → Check validation error messages reaching AI
   → Check CONTEXT_RESET_GUIDE has complete example

---

## File Locations Reference

- System prompt: `src/cua/prompts/__init__.py` → `SYSTEM_PROMPT`
- Tool guides: `src/cua/prompts/__init__.py` → `DOM_TOOL_GUIDE`, etc.
- Tool definitions: `src/cua/tools/dom_tool.py`, `search_tool.py`, etc.
- Message building: `src/cua/providers/bedrock.py` → `create_initial_request()`, `create_continuation_request()`
- Action execution: `src/cua/agent/loop.py` → `run()` method main loop
- Message pruning: `src/cua/providers/bedrock.py` → `_prune_message_history()`
- Context reset: `src/cua/providers/bedrock.py` → `reset_context()`

---

**End of Flow Diagram**
