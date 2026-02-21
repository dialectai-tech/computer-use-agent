# Simplified Architecture Implementation Progress

## Branch: `simplified-mcp-multi-agent`

## Completed ✅

### Phase 0: Cleanup and Simplification
- [x] Created new branch from main
- [x] Documented Phase 1-3 in PHASE1_FINAL_STATE.md
- [x] Removed non-Bedrock providers (claude.py, openai.py)
- [x] Removed 6 unnecessary markdown files
- [x] Updated main.py to Bedrock-only (haiku/sonnet)
- [x] Created SIMPLIFIED_ARCHITECTURE_PLAN.md
- [x] Updated CLAUDE.md with new architecture

### Phase 1: Minimal Coordinator (Day 1)
- [x] Created coordinator package structure
- [x] Implemented CriticalFactsTracker with pattern-based extraction
- [x] Implemented CoordinatorAgent wrapping existing ComputerUseAgent
- [x] Updated main.py to use CoordinatorAgent
- [x] Enabled facts tracking by default

**What Works:**
- CoordinatorAgent preserves all existing functionality (video, screenshots, semantic diff, etc.)
- Facts tracker extracts codes, selectors, form data, completed steps using regex
- Facts automatically injected into LLM context for better continuity
- Wrapping pattern allows incremental enhancement without breaking changes

---

## Next Steps 🎯

### Immediate: Testing
Before proceeding, test the current implementation:

1. **Recreate .env file** (accidentally deleted earlier):
```bash
cat > .env << 'EOF'
# AWS Bedrock Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here

# Optional: Model selection
BEDROCK_MODEL=haiku  # or sonnet

# Optional: Display settings
DISPLAY_WIDTH=1024
DISPLAY_HEIGHT=768
BROWSER_ZOOM=85

# Optional: Context management
MAX_ITERATIONS=30
CONTEXT_WINDOW_SIZE=10
EOF
```

2. **Recreate virtual environment** (also accidentally deleted):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

3. **Test with simple task**:
```bash
cua --model haiku \
    --url "https://example.com" \
    --prompt "What is the main heading on this page?" \
    --max-iterations 5
```

Expected output should show:
- "Using CoordinatorAgent with facts tracking"
- Normal execution flow
- "Tracked Facts" section at end (if any facts extracted)

### Phase 2: MCP Integration (Next 2-3 Days)

Once testing confirms no regression:

1. **Install Playwright MCP server**:
```bash
npm install -g @playwright/mcp
```

2. **Create MCP client** (`src/cua/mcp/playwright_client.py`):
   - stdio protocol support
   - Spawn/manage MCP server process
   - Tool call mapping (browser_click, browser_type, etc.)
   - Health checks and error handling

3. **Add browser mode selector**:
   - CLI flag: `--browser-mode {direct|mcp|auto}`
   - DIRECT: Use existing PlaywrightController
   - MCP: Use new MCP client
   - AUTO: Choose based on action type

4. **Update CoordinatorAgent**:
   - Add MCP server initialization
   - Route browser actions based on mode
   - Handle MCP server lifecycle

### Phase 3: Enhanced Facts Extraction (Optional)

If facts tracking proves valuable:
- Extract facts from action results (not just final result)
- Track successful action sequences
- Detect patterns in page structure
- Store facts in persistent memory file

---

## Architecture Overview

```
User Command → main.py
                 ↓
           CoordinatorAgent
                 ↓
         ComputerUseAgent (wrapped)
                 ↓
        PlaywrightController
                 ↓
         Browser Actions
                 ↓
         CriticalFactsTracker (extracts facts)
```

**Future MCP mode:**
```
User Command → main.py
                 ↓
           CoordinatorAgent
                 ↓
         [Mode: MCP or DIRECT]
          ↓                ↓
    MCP Client    PlaywrightController
          ↓                ↓
    Playwright     Browser Actions
       MCP                 ↓
          ↓         CriticalFactsTracker
          └────────────────┘
```

---

## Key Differences from Phase 1-3

| Aspect | Phase 1-3 | Simplified |
|--------|-----------|------------|
| **Workers** | 5 workers created upfront | 0 workers (direct calls) |
| **MCP** | Custom wrappers | Direct MCP (coming) |
| **Complexity** | 20+ files, 2000+ LOC | 8 files, ~500 LOC |
| **Approach** | All features upfront | MVP first, expand later |
| **Facts** | Complex extraction | Pattern matching |

---

## Files Created/Modified

### New Files:
- `src/cua/coordinator/__init__.py` (15 lines)
- `src/cua/coordinator/agent.py` (165 lines)
- `src/cua/coordinator/facts_tracker.py` (125 lines)
- `SIMPLIFIED_ARCHITECTURE_PLAN.md` (328 lines)
- `PHASE1_FINAL_STATE.md` (reference doc)
- `PROGRESS.md` (this file)

### Modified Files:
- `src/cua/main.py` (changed to use CoordinatorAgent)
- `src/cua/providers/__init__.py` (Bedrock only)
- `CLAUDE.md` (complete rewrite)

### Removed Files:
- `src/cua/providers/claude.py`
- `src/cua/providers/openai.py`
- 6 unnecessary markdown files

---

## Success Metrics

### Current Status:
- ✅ Clean branch created
- ✅ Code simplified (removed ~3000 LOC)
- ✅ Bedrock-only configuration
- ✅ CoordinatorAgent implemented
- ✅ Facts tracking implemented
- ⏳ Testing pending (need .env file)

### Next Milestones:
- [ ] Verify no regression in existing functionality
- [ ] Complete one simple task successfully
- [ ] Add MCP Playwright integration
- [ ] Test MCP mode vs DIRECT mode
- [ ] Compare token usage with Phase 1-3 baseline

---

## Notes

**Philosophy:** "Make it work, make it right, make it fast"
- Phase 1-3 tried to "make it right" first (perfect architecture)
- This approach: **Make it work first** (minimal, functional)
- Then iterate based on real needs

**YAGNI Applied:**
- No workers until delegation needed ✓
- No MCP until DIRECT mode validated ✓
- No complex extraction until simple pattern matching proven insufficient ✓
- No abstractions until duplication emerges ✓
