# Simplified MCP Multi-Agent Architecture Plan

## Date: 2026-02-09
## Branch: simplified-mcp-multi-agent
## Parent: main (commit 3c828f6)

---

## Why Simplify?

### Lessons from Phase 1-3:
1. **Too complex upfront** - Created 5 workers before knowing which were needed
2. **Unused components** - Workers created but never delegated to
3. **Test page too hard** - 30-step maze with popups overwhelming for Haiku
4. **Token explosion** - 2.1M tokens for Step 1 alone
5. **Debug overhead** - Logging affected performance
6. **Model limitations** - Haiku struggles with recovery

### What Worked:
- ✅ CoordinatorAgent pattern (good separation)
- ✅ Critical facts tracking (helps maintain state)
- ✅ Context-aware recovery (better than generic)
- ✅ Tool registry (flexible)

### What Didn't Work:
- ❌ Creating all workers upfront (YAGNI violation)
- ❌ Complex browser abstraction layers (MCP not tested)
- ❌ Too many specialized workers (memory, analysis, diff)
- ❌ Generic prompts (AI ignores them)

---

## New Simplified Architecture

### Core Principle: **Start Minimal, Expand When Needed**

### Components

#### 1. Coordinator Agent (Simple)
- Main orchestrator
- Maintains conversation state
- Tracks critical facts (codes, selectors)
- Delegates to MCP servers directly (no worker wrapper)

```python
class CoordinatorAgent:
    def __init__(self, mcp_servers: List[MCPServer]):
        self.mcp_servers = mcp_servers
        self.critical_facts = {}  # Simple dict
        self.conversation = []

    async def run_task(self, goal: str):
        while not done:
            # Get AI response
            response = await self.llm.generate(self.conversation)

            # Execute tool calls via MCP
            for tool_call in response.tool_calls:
                result = await self.execute_mcp_tool(tool_call)

            # Track critical facts
            self.extract_facts(result)
```

#### 2. MCP Servers (2-3 Maximum)

**Option A: Playwright MCP**
- Browser automation
- DOM manipulation
- Screenshot capture
- Navigation

**Option B: Filesystem MCP** (if needed)
- Read/write files
- Store session state
- Log results

**Option C: Memory MCP** (optional)
- Persistent memory across sessions
- Simple key-value store

#### 3. No Workers (Initially)
- Don't create BrowserWorker, MemoryWorker, etc.
- Call MCP servers directly from coordinator
- Add workers only if delegation needed

#### 4. Simple Critical Facts
```python
critical_facts = {
    "codes": [],          # Codes discovered
    "selectors": {},      # {type: [selectors]}
    "completed": []       # Completed steps
}
```

No complex extraction logic - just pattern matching.

---

## Simplified Flow

```
User Request → Coordinator Agent → LLM (Sonnet)
                                    ↓
                                Tool Calls
                                    ↓
                           MCP Server (Playwright)
                                    ↓
                           Browser Actions
                                    ↓
                           Results → Track Facts
                                    ↓
                           Continue Loop
```

No worker delegation, no inter-agent communication, no complex state management.

---

## Implementation Plan

### Phase 1: Minimal Viable (Day 1)
1. CoordinatorAgent with basic loop
2. Direct MCP client (Playwright)
3. Simple critical facts tracking
4. Basic recovery prompt

**Goal**: Get ONE simple task working (e.g., fill a form)

### Phase 2: Enhanced (Day 2-3)
1. Add context-aware recovery
2. Improve fact extraction
3. Add screenshot comparison
4. Test with multiple tasks

### Phase 3: Scale (Day 4-5)
1. Add more MCP servers if needed
2. Consider worker delegation if delegation needed
3. Optimize token usage
4. Production-ready

---

## Tech Stack

### Model: **Claude Sonnet** (not Haiku)
- Better reasoning
- Stronger recovery
- Worth the extra cost

### MCP Servers:
1. **@playwright/mcp** - Browser automation
2. (Optional) **@modelcontextprotocol/server-filesystem** - File operations
3. (Optional) Custom memory MCP

### No External Tools:
- No DOMTool wrapper (use MCP directly)
- No SearchTool (use MCP)
- No custom browser abstraction

---

## Code Structure

```
src/cua/
├── coordinator/
│   ├── __init__.py
│   ├── agent.py              # CoordinatorAgent
│   └── facts_tracker.py      # Simple facts tracking
├── mcp/
│   ├── __init__.py
│   ├── client.py             # Generic MCP client
│   └── playwright_client.py  # Playwright-specific
├── prompts/
│   ├── system.py             # System prompts
│   └── recovery.py           # Recovery prompts
├── utils/
│   ├── logger.py
│   └── token_counter.py
└── main.py                   # Entry point
```

**Total new files**: ~8 files (vs 20+ in Phase 1-3)

---

## Key Differences from Phase 1-3

| Aspect | Phase 1-3 | Simplified |
|--------|-----------|------------|
| **Workers** | 5 workers created | 0 workers (direct MCP) |
| **Abstraction Layers** | Multiple (BrowserInterface, etc.) | None (direct calls) |
| **Tools** | Custom wrappers (DOMTool, SearchTool) | MCP native |
| **Model** | Haiku | Sonnet |
| **Initial Complexity** | High (all features) | Low (MVP first) |
| **Files** | 20+ new files | 8 new files |
| **Lines of Code** | 2000+ | ~500 |

---

## Success Criteria

### Week 1:
- ✅ CoordinatorAgent working
- ✅ Playwright MCP integrated
- ✅ ONE simple task completes (form fill)

### Week 2:
- ✅ Critical facts tracking working
- ✅ Context-aware recovery working
- ✅ 3+ different tasks complete

### Week 3:
- ✅ Token usage optimized
- ✅ Production-ready
- ✅ Documentation complete

---

## Testing Strategy

### Start Simple:
1. **Test Task**: Fill a simple form (name, email, submit)
   - Not a 30-step maze
   - No trick popups
   - Clear success criteria

2. **Test Task**: Login flow
   - Find username field
   - Fill username
   - Find password field
   - Fill password
   - Click login

3. **Test Task**: Search + extract
   - Go to website
   - Search for item
   - Extract result

### Then Scale Up:
4. Multi-step workflows
5. Complex pages
6. Error recovery

---

## Migration Path from Phase 1-3

### Keep:
- CoordinatorAgent concept
- Critical facts tracking pattern
- Context-aware recovery prompts
- Token tracking utilities

### Remove:
- All worker classes (BrowserWorker, MemoryWorker, etc.)
- BrowserInterface abstraction
- PlaywrightMCPClient wrapper
- DOMTool, SearchTool custom wrappers
- Tool registry (use MCP native tools)

### Simplify:
- main.py (less CLI flags)
- loop.py (simpler iteration logic)
- Recovery prompts (more focused)

---

## Risk Mitigation

### Risk 1: MCP Integration Complex
**Mitigation**: Use official @playwright/mcp, well-tested

### Risk 2: Sonnet Too Expensive
**Mitigation**: Optimize prompts, use prompt caching aggressively

### Risk 3: Still Too Complex
**Mitigation**: Start with ONE task, validate before expanding

### Risk 4: Token Usage Still High
**Mitigation**: Aggressive pruning from day 1, semantic diff

---

## Timeline

### Sprint 1 (Day 1-2): MVP
- Day 1 AM: Teardown Phase 1-3 components
- Day 1 PM: Build CoordinatorAgent + MCP client
- Day 2: Test with simple form task

### Sprint 2 (Day 3-4): Enhanced
- Day 3: Add critical facts tracking
- Day 4: Add recovery prompts

### Sprint 3 (Day 5): Polish
- Day 5: Optimize, document, test multiple tasks

---

## Next Steps

1. **Commit this plan** ✅
2. **Remove Phase 1-3 code** (next commit)
3. **Create new CoordinatorAgent** (minimal)
4. **Integrate Playwright MCP**
5. **Test with ONE simple task**

---

## References

- Phase 1-3 branch: `phase-1-multi-agent-foundation` (preserved)
- Phase 1-3 final state: `PHASE1_FINAL_STATE.md`
- Lessons learned: All test analysis docs (TEST3_ANALYSIS.md, etc.)

---

## Philosophy

**"Make it work, make it right, make it fast"** - Kent Beck

Phase 1-3 tried to "make it right" first (perfect architecture).
This approach: **Make it work first** (simple, minimal, functional).

Then iterate based on real needs, not imagined requirements.
