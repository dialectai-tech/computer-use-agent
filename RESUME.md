# CUA Project - Development Resume & Findings

**Date**: February 22, 2026
**Branch**: `agno-phase-2`
**Status**: ⚠️ Working but SLOW - Needs redesign

---

## 📋 Executive Summary

Implemented Agno multi-agent architecture with AWS Bedrock (Haiku) to solve token bloat in browser automation. **The system works** but has critical performance issues that make it impractical for production use.

### Results
- ✅ **Technical Success**: Zero API errors, proper tool result formatting
- ❌ **Performance Failure**: 30 minutes to complete 1 step (expected: 2-3 minutes)
- ❌ **Cost Problem**: $0.33 per step (395 API calls vs expected 5-10)
- ⚠️ **Logging Mess**: Scattered logs, no action timeline, poor observability

---

## 🔥 Critical Problems Discovered

### 1. Multi-Agent Overhead is EXCESSIVE

**Problem**: 395 API calls for 1 step
- Orchestrator → delegates to Browser Agent
- Browser Agent → executes action
- Memory Agent → stores facts
- Analysis Agent → processes results
- Orchestrator → synthesizes response
- **Repeat for every small action**

**Result**: 80x more API calls than necessary

### 2. Agent Getting Stuck in Loops

**Observed Behavior**:
- Completed Step 1 successfully (09:30-09:43)
- Started Step 2 (09:44)
- Got confused, reverted to Step 1 (09:49-09:58)
- Repeated Step 1 screenshots multiple times
- Never progressed past Step 2

**Root Cause**: No clear step completion detection, no memory of progress

### 3. Logging is Broken

**Current State**:
```
/tmp/cua_final_challenge.log        2.3MB, 24K lines, debug noise
/tmp/claude-1000/*                  1.6MB, my internal task tracking
test_artifacts/{id}/logs/session.log  3 lines (useless!)
test_artifacts/{id}/screenshots/      31 files, no manifest
```

**Problems**:
- No action timeline
- No screenshot references
- No token tracking per action
- Can't correlate logs with screenshots
- Scattered across multiple locations

### 4. Token Tracking Not Implemented

**Issue**: `TokenTracker` class exists but never gets data
- Agno's `Team.arun()` doesn't expose Bedrock metadata
- All token counts show as 0
- Cost tracking based on estimates only
- Can't optimize without real data

### 5. Video Recording Failed

**Issue**: `recordings/` directory empty
- Playwright MCP not saving video
- Browser closes before finalization
- No error messages
- Unknown root cause

---

## ✅ What We Fixed Successfully

### Critical Fix: Tool Result Grouping

**Problem**: Bedrock API validation error
```
ValidationException: Expected toolResult blocks at messages.X.content
```

**Root Cause**: Multiple consecutive tool results sent as separate messages:
```python
# ❌ WRONG (what we had)
Message N:   {"role": "user", "content": [{"toolResult": {...}}]}
Message N+1: {"role": "user", "content": [{"toolResult": {...}}]}

# ✅ CORRECT (what we fixed)
Message N: {"role": "user", "content": [
    {"toolResult": {...}},
    {"toolResult": {...}}
]}
```

**Solution**: Modified `BedrockMCPModel._format_messages()` to:
1. Collect consecutive tool results in `pending_tool_results` list
2. Flush grouped results as single message when non-tool message encountered
3. Flush remaining results at end of message list

**Result**: Zero errors in 395 API calls ✅

**Commit**: `6a981a7` - "fix: Group consecutive tool results into single message for Bedrock"

---

## 📊 Test Results - Session 20260222_092849

### Performance Metrics

| Metric | Value | Expected | Status |
|--------|-------|----------|--------|
| Duration | 31.75 min | 2-3 min | ❌ 10x slower |
| API Calls | 395 | 5-10 | ❌ 40-80x more |
| Steps Completed | 1 / 30 | 5-10 | ❌ Failed |
| Estimated Cost | $0.33 | $0.03 | ❌ 11x expensive |
| Errors | 0 | 0 | ✅ Perfect |
| Screenshots | 31 | 5-10 | ⚠️ Too many |

### Token Usage (Estimated)

- **Input Tokens**: ~592,500
- **Output Tokens**: ~142,200
- **Total**: ~734,700 tokens
- **Cost**: ~$0.33 (Bedrock Haiku)

*Note: Real tracking not implemented - this is estimation based on 395 calls × 1,860 avg tokens/call*

### Step Progress

**Step 1** ✅ COMPLETED (13 minutes)
- 09:30 - Navigate to challenge
- 09:33 - Click START, close popups
- 09:37 - Multiple clicks attempting to progress
- 09:40 - Scroll to reveal code
- 09:42 - Code revealed
- 09:43 - Code entered and submitted

**Step 2** ⚠️ ATTEMPTED (7 minutes)
- 09:44 - Step 2 loaded
- 09:48 - Agent captured screenshots
- 09:49 - Reverted back to Step 1
- 09:52-09:58 - Repeated Step 1 screenshots
- Never completed Step 2

**Steps 3-30** ❌ NOT REACHED

---

## 🏗️ Architecture Analysis

### Current Architecture (Agno Multi-Agent)

```
User Request
    ↓
Orchestrator Agent (Haiku)
    ├─→ Browser Agent (Haiku + Playwright MCP)
    ├─→ Memory Agent (Haiku + Memory MCP)
    └─→ Analysis Agent (Haiku + Python functions)
        ↓
Synthesize Result
    ↓
Repeat for every action
```

**Problems**:
- 4 agents = 4x coordination overhead
- Each delegation = 2-3 API calls minimum
- Context passed between agents
- Agno Team coordination adds latency
- Hard to debug (which agent failed?)

### What We Should Have Built

```
User Request
    ↓
Single Agent (Sonnet)
    ├─→ Direct Playwright tools
    ├─→ Direct memory store
    └─→ Built-in analysis
        ↓
Execute action
    ↓
Return result
```

**Benefits**:
- 1 agent = minimal overhead
- 1 API call per action
- All context in one place
- Easy to debug
- 10x faster

---

## 🗂️ File Structure

### What Works

```
test_artifacts/{session_id}/
├── screenshots/           ✅ 31 PNG files properly saved
├── recordings/           ❌ Empty (MCP issue)
├── snapshots/            ❌ Empty (not used)
├── logs/
│   └── session.log       ⚠️ Only 3 lines (useless)
└── TEST_REPORT.md        ✅ Comprehensive report
```

### External Logs (Problems)

```
/tmp/cua_final_challenge.log           2.3MB debug noise
/tmp/claude-1000/tasks/*.output        My internal background processes
```

**Issue**: Logs not consolidated, no action timeline, no correlation with screenshots

### Key Implementation Files

**Agno Configuration**:
- `src/cua/agno_config/models.py` - Bedrock model setup
- `src/cua/agno_config/bedrock_mcp_model.py` - **Critical fix here** (tool grouping)

**Agents**:
- `src/cua/agno_agents/orchestrator.py` - Task coordinator
- `src/cua/agno_agents/browser_agent.py` - Playwright MCP wrapper
- `src/cua/agno_agents/memory_agent.py` - Memory MCP wrapper
- `src/cua/agno_agents/analysis_agent.py` - Fact extraction (not actually used)

**Coordination**:
- `src/cua/agno_teams/cua_team.py` - Agno Team setup
- `src/cua/coordinator/agno_coordinator.py` - Coordinator wrapper

**Utilities**:
- `src/cua/utils/token_tracker.py` - ⚠️ Exists but never gets data
- `src/cua/utils/structured_logger.py` - ⚠️ Barely used (3 log lines)
- `src/cua/utils/session_paths.py` - ✅ Works well

---

## 💡 Root Cause Analysis

### Why So Slow?

1. **Multi-Agent Tax**: Every action requires Orchestrator → Agent → Orchestrator round-trip
2. **Over-Delegation**: Even simple actions get delegated to specialists
3. **Context Duplication**: Same context passed to 4 different agents
4. **No Step Memory**: Agent doesn't remember it completed Step 1
5. **Poor Prompts**: Agents get confused about what to do next

### Why 395 API Calls for 1 Step?

Typical flow for clicking a button:
1. Orchestrator: "Delegate to Browser Agent to click button"
2. Browser Agent: "Call Playwright MCP to click"
3. Browser Agent: "Return result to Orchestrator"
4. Orchestrator: "Delegate to Analysis Agent to check result"
5. Analysis Agent: "Analyze page state"
6. Analysis Agent: "Return analysis to Orchestrator"
7. Orchestrator: "Synthesize and decide next action"

**That's 7 API calls to click ONE button!**

With retries, confusion, and getting stuck = 395 calls for 1 step.

---

## 🎯 Lessons Learned

### What Works

✅ **Bedrock Integration** - Haiku/Sonnet work great with proper formatting
✅ **MCP Playwright** - Browser automation works reliably
✅ **Tool Result Formatting** - Our fix handles all edge cases
✅ **Session Organization** - Directory structure is clean
✅ **Error Recovery** - Zero crashes, graceful handling

### What Doesn't Work

❌ **Multi-Agent Architecture** - 80x overhead, not worth it
❌ **Agno Team Coordination** - Too much abstraction
❌ **Token Tracking** - Not integrated with Agno
❌ **Logging** - Scattered, incomplete, hard to debug
❌ **Step Tracking** - Agent forgets progress
❌ **Video Recording** - MCP doesn't save

### Critical Insights

1. **Simpler is Better**: Single agent would be 10x faster
2. **Haiku is Too Dumb**: Needs Sonnet for complex tasks
3. **Direct Tools > MCP**: Less abstraction = more control
4. **Observability Matters**: Can't optimize what you can't measure
5. **Step Memory Required**: Must track progress explicitly

---

## 📈 Comparison: Expected vs Actual

### Expected (Initial Design)

- **Time**: 2-3 min per step → 60-90 min for 30 steps
- **Cost**: $0.03 per step → $0.90 total
- **API Calls**: 5-10 per step → 150-300 total
- **Token Usage**: 50-100K per step → 1.5-3M total

### Actual (Current Implementation)

- **Time**: 30 min for 1 step → 900 min for 30 steps (15 hours!)
- **Cost**: $0.33 per step → $10 total
- **API Calls**: 395 for 1 step → 12,000 total
- **Token Usage**: 735K for 1 step → 22M total

### Comparison

| Metric | Expected | Actual | Ratio |
|--------|----------|--------|-------|
| Time per step | 2-3 min | 30 min | **10x slower** |
| Cost per step | $0.03 | $0.33 | **11x more** |
| API calls/step | 5-10 | 395 | **40-80x more** |
| Total challenge | 90 min | 15 hours | **10x slower** |

**Conclusion**: Current architecture is **completely impractical** for production use.

---

## 📝 Technical Debt

### Immediate (Must Fix)

1. **Token Tracking** - Hook into Bedrock response metadata
2. **Logging** - Single timeline file with action correlation
3. **Step Memory** - Track completed steps in Memory Agent
4. **Video Recording** - Debug MCP video API

### Short-term (Should Fix)

1. **Performance** - Reduce API calls per step (use Option 1, 2, or 3)
2. **Cost Tracking** - Real-time cost monitoring
3. **Step Validation** - Detect when step is complete
4. **Error Recovery** - Don't revert to Step 1 when stuck

### Long-term (Nice to Have)

1. **Prompt Caching** - Reduce input token costs
2. **Parallel Actions** - Execute independent actions concurrently
3. **Smart Screenshots** - Only capture when needed
4. **Resume from Checkpoint** - Continue interrupted runs

---

## 🎬 Conclusion

### What We Achieved

✅ Built working multi-agent browser automation system
✅ Integrated AWS Bedrock with MCP servers
✅ Fixed critical tool result formatting bug
✅ Zero runtime errors across 395 API calls
✅ Proper session organization and artifact storage

### What We Learned

❌ Multi-agent architecture is **10x slower** than necessary
❌ Agno coordination adds **massive overhead**
❌ Current approach is **impractical for production**
⚠️ Need to **simplify drastically** or **optimize heavily**
⚠️ **Observability is critical** - can't improve what we can't measure

### Next Steps

**Priority**: Performance over architecture elegance
**Goal**: 2-3 min per step, $0.03-0.05 cost
**Timeline**: Architecture decision needed

---

## 📚 References

### Key Commits

- `6a981a7` - Tool result grouping fix (CRITICAL)
- `df6ea6e` - Direct MCP tool outputs to session directories
- `e7922e9` - Add gitignore rules for MCP snapshot files
- `4adce75` - Phase 3 final status commit

### Documentation

- `test_artifacts/20260222_092849/TEST_REPORT.md` - Detailed test results
- `docs/agno/FINAL_STATUS.md` - Phase 3 completion report
- `docs/agno/TEST_STATUS_PHASE3.md` - Test execution details

### Key Files

- `src/cua/agno_config/bedrock_mcp_model.py` - Tool grouping fix
- `src/cua/agno_teams/cua_team.py` - Team setup
- `src/cua/coordinator/agno_coordinator.py` - Main coordinator

---

**Last Updated**: February 22, 2026
**Status**: Working but needs redesign
