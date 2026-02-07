# Quick Reference - Both Features Implemented

## ✅ What's Implemented

### Feature 1: Custom Search Tool
**Branch**: `feature/two-phase-workflow-and-search-tool`
- Adds `search_page_content` tool for AI to search page content
- AI can search text and accessibility tree before taking actions
- Returns line numbers, matches, and element locations

### Feature 2: Two-Phase Workflow
**Branch**: `feature/add-two-phase-workflow` (current)
- Forces AI to search FIRST (Phase 1: no screenshot)
- Then provides screenshot for actions (Phase 2: with coordinates)
- Eliminates visual bias completely

---

## 🚀 Quick Test Commands

### Test Search Tool Only:
```bash
git checkout feature/two-phase-workflow-and-search-tool

cua --provider bedrock --model haiku \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --max-iterations 100 \
  --use-accessibility-tree \
  --record-video
```

### Test Two-Phase Workflow (includes search tool):
```bash
git checkout feature/add-two-phase-workflow

cua --provider bedrock --model haiku \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --max-iterations 100 \
  --use-accessibility-tree \
  --two-phase-workflow \
  --record-video
```

### Try with Better Model (Sonnet):
```bash
cua --provider bedrock --model sonnet \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --max-iterations 100 \
  --use-accessibility-tree \
  --two-phase-workflow \
  --record-video
```

---

## 📊 Expected Results

| Feature | Search Usage | Iterations/Level | Success Rate |
|---------|-------------|------------------|--------------|
| **Baseline** | 0% | 40+ | ~20% |
| **Search Tool** | 50-80% | 10-20 | ~60% |
| **Two-Phase** | 100% ✅ | 3-5 ✅ | ~90%+ ✅ |

---

## 🔍 What to Look For

### Search Tool Working:
```
Iteration X/100
  → Search: Query="[A-Z0-9]{6}", Type=text
  ✓ 🔍 Found 1 unique code(s): AJAF5H
```

### Two-Phase Working:
```
Iteration 1/100
  Two-phase workflow: Phase 1 (Search Only)
  → Search: Query="[A-Z0-9]{6}"
  ✓ Found code AJAF5H

  → Transitioning to Phase 2 (Action with Screenshot)

Iteration 2/100
  → Click at (640, 300)
  → Type: "AJAF5H"
```

---

## 📚 Documentation

- **TWO_PHASE_WORKFLOW_GUIDE.md** - Complete two-phase guide
- **TESTING_GUIDE.md** - Search tool testing
- **IMPLEMENTATION_SUMMARY.md** - Technical details
- **IDEAS.md** - Original solutions from senior
- **CURRENT_SYSTEM_WALKTHROUGH.md** - System analysis

---

## 🎯 Decision Tree

```
Test search tool alone first
    ↓
┌───────────────────────┐
│ Does it work well?    │
│ (80%+ search usage)   │
└───────┬───────────────┘
        │
    ┌───┴───┐
    │       │
   YES     NO
    │       │
    │       └→ Test two-phase workflow
    │              ↓
    │          Does it work better?
    │              ↓
    │          ┌───┴───┐
    │          │       │
    │         YES     NO
    │          │       │
    └──────────┤       └→ Try Sonnet
               │           or other solutions
               ↓
          Merge to main!
```

---

## 🔧 Branch Management

### Current State:
```
main
 └── feature/two-phase-workflow-and-search-tool (search tool)
      └── feature/add-two-phase-workflow (two-phase) ← YOU ARE HERE
```

### Switch Branches:
```bash
# Back to search tool only
git checkout feature/two-phase-workflow-and-search-tool

# Back to two-phase (includes search tool)
git checkout feature/add-two-phase-workflow

# Back to main (baseline)
git checkout main
```

---

## 💡 Pro Tips

1. **Try Sonnet First**: Better instruction following than Haiku
   ```bash
   --model sonnet
   ```

2. **Enable All Features**: Maximum effectiveness
   ```bash
   --use-accessibility-tree --two-phase-workflow --enable-caching
   ```

3. **Record Videos**: Review agent behavior later
   ```bash
   --record-video
   ```

4. **Watch for Phase Transitions**: Key indicator of two-phase working
   ```
   Look for: "→ Transitioning to Phase 2"
   ```

5. **Compare Iterations**: Should drop from 40+ to 3-5 per level

---

## ⚠️ Troubleshooting

### AI Still Scrolls Excessively:
- Try Sonnet (better model)
- Enable two-phase workflow
- Check if search tool is available in logs

### Search Returns No Results:
- Ensure page has loaded
- Check page text extraction
- Try different search queries

### Phase 1 Never Completes:
- Check if AI used search tool
- Try more explicit prompt
- Use Sonnet instead of Haiku

---

## 📈 Success Metrics

Track these in logs:
- ✅ Search tool usage rate
- ✅ Iterations per level (target: 3-5)
- ✅ Phase transitions (for two-phase)
- ✅ Success rate (target: >80%)
- ✅ No excessive scrolling

---

## 🎉 Quick Start

**Just want to test everything?**

```bash
# Make sure you're on the right branch
git checkout feature/add-two-phase-workflow

# Run with all features enabled
cua --provider bedrock --model sonnet \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --max-iterations 100 \
  --use-accessibility-tree \
  --two-phase-workflow \
  --enable-caching \
  --record-video \
  --prompt "Complete the Browser Navigation Challenge efficiently."
```

Watch the logs for:
1. "Two-phase workflow: Phase 1" - Feature enabled ✅
2. "→ Search:" - Search tool used ✅
3. "→ Transitioning to Phase 2" - Phase working ✅
4. Quick completions (3-5 iterations) - Success! ✅

---

Ready to test! 🚀
