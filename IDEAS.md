I'll analyze the document to understand your Computer Use agent problem and provide strategic solutions.Based on your thorough analysis, here's my strategic assessment and concrete solutions:

## Core Problem Diagnosis

You've correctly identified this as a **behavioral problem, not technical**. The data is perfect, but Haiku has "learned helplessness" - it's been trained on vision-first tasks and is reverting to comfortable patterns despite clear instructions.

## Strategic Solutions (Ordered by Impact/Effort)

### 🔥 TIER 1: Architectural Kills (High Impact, Medium Effort)

**1. Two-Phase Forced Workflow**
- **Phase 1**: Send ONLY text + tree (no screenshot). Prompt: "Search this text for [target]. Report line number and exact match."
- **Phase 2**: Only AFTER AI reports findings, send screenshot with: "Now click coordinates for what you found at line X"
- **Why**: Forces sequential processing, removes visual crutch
- **Implementation**: Modify your message construction to conditionally include screenshot

**2. Separate Search Tool**
```python
# Add a new tool alongside 'computer'
tools = [
    {
        "type": "custom",
        "name": "search_page_content",
        "description": "Search page text and tree. ALWAYS use this BEFORE taking any action.",
        "input_schema": {
            "query": "What to search for",
            "return_location": "Return line numbers/tree path"
        }
    },
    # existing computer tool
]
```
- **Why**: Explicit tool = AI must use it, gives you control/validation
- **Benefit**: You can verify AI actually searched before allowing computer tool

**3. Screenshot Degradation**
- Send screenshot at **heavily reduced quality/resolution** (like 400x300, grayscale)
- Make it deliberately harder to read visually
- **Why**: Increases "cost" of visual processing, makes text more attractive
- **Quick test**: Add `--screenshot-quality 20` flag

### 🎯 TIER 2: Model & Provider Changes (High Impact, Low Effort)

**1. Try Sonnet 4.5 FIRST** (Your best quick win)
```bash
cua --provider bedrock --model sonnet-4.5 ...
```
- Sonnet has 3-5x better instruction following
- Worth the cost increase for this problem
- **Expected**: Should respect your prompts better

**2. Try OpenAI GPT-4o**
- Different training paradigm
- Their computer use might handle this better
- API: `gpt-4o` with vision capability

**3. Try Google Gemini 2.0 Flash**
- Recently released, strong multi-modal
- Different architecture might avoid visual bias
- Has native tool use

**4. Specialized Models to Test:**
- **CogAgent**: Specifically trained for UI understanding (open source, runs locally)
- **Fuyu-8B**: Designed for visual UI tasks with text grounding
- **GPT-4V + LangChain ReAct**: Forces structured reasoning

### ⚡ TIER 3: Prompt Engineering Kills (Low Effort, Worth Testing)

**1. Extreme Simplification** (Cut to 300 tokens)
```
RULE: Before ANY action, search page_text for [target].
Report: "Found [X] at position [Y]"
Then: Click coordinates in screenshot.

Page Text:
[text]

Tree:
[tree]

Screenshot:
[image]
```
- **Why**: Current 7k tokens = prompt fatigue. AI skims and looks at image.
- **Test**: Remove ALL examples, keep only rule

**2. Adversarial Prompt**
```
WARNING: Screenshot is LOW QUALITY and may be blurry.
ALWAYS search page_text first for accurate information.
Screenshot is ONLY for clicking coordinates.
```
- **Why**: Primes AI to distrust visual

**3. Response Format Enforcement**
```
You MUST respond in this format:
1. Search: "Searched text, found X at line Y"
2. Action: [tool use]

Any response without step 1 will be rejected.
```
- **Why**: Forces evidence of text reading

**4. Reverse Order**
```
Screenshot: [image]
IGNORE above image until you:
1. Read this text: [text]
2. Read this tree: [tree]
```
- **Why**: Visual bias might make AI skip to image, then instructions tell it to go back

### 🔧 TIER 4: Puppeteer/MCP Enhancements (Medium Effort)

**1. Add DOM Query Tool** (Better than accessibility tree)
```javascript
// Instead of accessibility tree, use Puppeteer's better APIs
await page.evaluate(() => {
  // Find all interactive elements with text content
  const elements = [...document.querySelectorAll('button, input, a, [role="button"]')]
  return elements.map(el => ({
    text: el.innerText || el.value || el.placeholder,
    selector: getCSSSelector(el), // Get unique selector
    boundingBox: el.getBoundingClientRect()
  }))
})
```
- **Why**: More precise than accessibility tree, includes selectors AI can reference

**2. MCP Server Approach**
Create an MCP server with these tools:
```
- read_page_text(query) -> Returns matching text + line numbers
- get_element_info(text_content) -> Returns element details from DOM
- click_element(selector) -> Clicks by selector, not coordinates
- scroll_to_element(selector) -> Scrolls element into view
```
- **Why**: Removes visual dependency entirely, enforces text-first workflow
- **Benefit**: Can unit test each tool independently

**3. Hybrid Selector Approach**
```javascript
// Enhance browser to return selectors with tree
{
  "element": "Submit button",
  "selector": "#submit-btn",
  "xpath": "//button[@id='submit-btn']",
  "coordinates": [640, 480]
}
```
- AI uses selector from text, your system translates to click
- **Why**: Removes coordinate guessing, more reliable

### 💡 TIER 5: Enforcement & Validation (High Impact, High Effort)

**1. Validation Layer**
```python
def validate_response(ai_response, page_text):
    # Check if AI's response references content from page_text
    ai_text = ai_response['content'][0]['text']
    
    if not any(phrase in page_text for phrase in extract_phrases(ai_text)):
        return {
            "error": "You didn't search page text. Try again.",
            "hint": f"Search for: {get_hint(page_text)}"
        }
    return {"success": True}
```
- **Why**: Catches and blocks screenshot-only responses
- **Benefit**: Forces correct behavior through rejection

**2. Multi-Turn Forced Split**
```python
# Turn 1: Analysis only
response1 = call_ai(text + tree, tools=["text_search_only"])

# Turn 2: Only if analysis was good
if validated(response1):
    response2 = call_ai(response1 + screenshot, tools=["computer"])
```
- **Why**: Physically impossible to skip text analysis
- **Benefit**: Complete control over workflow

### 🚀 TIER 6: Alternative Approaches

**1. Traditional Automation Hybrid**
```python
# Use AI for high-level planning only
plan = ai.generate_plan(page_text, tree)
# "Steps: 1) Find code in Section 3, 2) Copy code, 3) Paste in input"

# Execute with traditional Puppeteer
for step in plan:
    execute_with_selectors(step)
```
- **Why**: AI does planning (its strength), Puppeteer does execution (its strength)

**2. Fine-tuned Model**
- Fine-tune Llama 3.1 8B on examples of correct text-first behavior
- **Benefit**: Cheap to run, perfect for your specific task
- **Cost**: ~$100-500 for training, needs labeled examples

**3. Agentic Framework**
- Use LangChain/AutoGPT with forced ReAct reasoning
- Each step must cite source (text/tree/screenshot)
- **Why**: Built-in validation and reasoning transparency

## My Top 3 Recommendations (Start Here)

**1. Try Sonnet 4.5 IMMEDIATELY** (5 minutes)
- Your problem might just be Haiku's limitations
- Sonnet costs more but follows instructions WAY better
- Test with existing setup, see if it respects text-first

**2. Two-Phase Workflow** (30 minutes)
- Implement the forced split: text-only turn, then screenshot turn
- This physically prevents screenshot-first behavior
- High success probability

**3. Add Search Tool + Validation** (1 hour)
- Create explicit `search_page_content` tool
- Validate AI used it before allowing `computer` tool
- Gives you complete control

## Quick Wins to Test Today

```bash
# Test 1: Better model
cua --provider bedrock --model sonnet-4.5 ...

# Test 2: Degraded screenshot (modify code to reduce quality)
screenshot = screenshot.resize((400, 300)).convert('L')  # Grayscale, small

# Test 3: Minimal prompt
--prompt "Search page_text for code. Report location. Then click."
```

## Why NOT MCP Server (Yet)

MCP is great but might be overkill. The problem is **AI behavior**, not **tool availability**. Even with MCP, if AI still prefers visual, it'll use screenshot tool first. Try simpler fixes first.

However, if simpler fixes fail, MCP with **tool dependencies** (must call `search` before `click`) could be your nuclear option.

## Which Would I Try?

**Week 1**: Sonnet 4.5 + Two-phase workflow + Response validation
**Week 2** (if needed): Custom search tool + Screenshot degradation
**Week 3** (if desperate): MCP server with enforced workflow

The scrolling loop is the AI's way of saying "I don't understand what you want from this text blob, so I'll do what I'm trained for: look at pictures and navigate." You need to either force better behavior (two-phase) or use a model that respects instructions (Sonnet).
