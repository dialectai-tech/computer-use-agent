# Test Prompt for Browser Navigation Challenge

This is a comprehensive, detailed prompt for testing the Computer Use Agent on the browser navigation challenge.

## Usage

```bash
python -m cua --provider bedrock --model sonnet-4.5 --url "YOUR_CHALLENGE_URL" --two-phase-workflow --extended-thinking --thinking-budget 15000 --prompt "$(cat TEST_PROMPT.md | grep -A 1000 '## TASK PROMPT' | tail -n +2)"
```

Or use the prompt directly:

```bash
python -m cua --provider bedrock --model sonnet-4.5 --url "YOUR_CHALLENGE_URL" --two-phase-workflow --extended-thinking --prompt "Navigate to the webpage and complete all tasks listed on it. The webpage contains a browser navigation challenge with multiple steps. You need to find codes, interact with UI elements, handle popups/modals, and follow instructions carefully. Use the search_page_content tool extensively to find all relevant content before taking actions."
```

---

## TASK PROMPT

Navigate to the webpage and complete the browser navigation challenge by following these instructions carefully:

### Your Objective

This webpage contains a multi-step browser navigation challenge designed to test automated agents. Your goal is to complete ALL steps of the challenge by:
1. Finding and collecting codes displayed on the page
2. Interacting with various UI elements (buttons, inputs, modals, dropdowns)
3. Handling popups, dialogs, and dynamic content
4. Following sequential instructions that reveal themselves step by step
5. Entering collected information into appropriate fields
6. Successfully navigating through the entire challenge workflow

### Critical Strategy: Search First, Act Second

**PHASE 1 - SEARCH AND DISCOVERY:**
Before you click ANYTHING or scroll ANYWHERE, you MUST:

1. **Use the search_page_content tool** to find all relevant content on the page:
   - Search for 6-character codes (pattern: `[A-Z0-9]{6}`)
   - Search for button names and labels
   - Search for input field labels
   - Search for instructions and step indicators
   - Search for modal/popup content

2. **Build a complete mental map** of the page:
   - What codes are present and where?
   - What buttons need to be clicked and in what order?
   - What inputs need to be filled?
   - What hidden content exists in modals or collapsible sections?

**PHASE 2 - COORDINATED ACTION:**
After you have the complete picture from search:
1. Look at the screenshot to find visual coordinates [x, y] of elements
2. Execute actions in the correct sequence
3. Verify each action's result before proceeding

### Expected Challenge Structure

Based on typical browser navigation challenges, expect:

1. **Initial Instructions Section**
   - May contain overview of what needs to be done
   - Often includes the first code or clue
   - Search for: "instruction", "step", "task", "challenge"

2. **Multiple Codes to Find**
   - Codes are typically 6 characters: letters and numbers
   - May be hidden in various places:
     - Plain text on page
     - Inside collapsed sections
     - Within modal popups
     - In dynamically loaded content
   - Search pattern: `\b[A-Z0-9]{6}\b`

3. **Interactive Elements**
   - Buttons to click (may trigger modals or reveal new content)
   - Input fields for entering codes or information
   - Dropdowns for selections
   - Checkboxes or radio buttons
   - Search for: "button", "textbox", "combobox", "checkbox"

4. **Modal Dialogs/Popups**
   - May contain additional codes or instructions
   - Require interaction before closing
   - May need scrolling within the modal
   - Look for close buttons (often "×" or "Close")

5. **Sequential Steps**
   - Challenge likely progresses through numbered steps
   - Each step may unlock the next
   - Pay attention to step counters or progress indicators

6. **Final Submission**
   - Usually a final input field or button
   - May require entering all collected codes
   - Look for "Submit", "Finish", "Complete" buttons

### Detailed Action Plan

**STEP 1: Initial Page Analysis**
```
1. Take initial screenshot to see the page layout
2. Use search_page_content(query="\b[A-Z0-9]{6}\b", search_type="both") to find all codes
3. Use search_page_content(query="button", search_type="tree") to find all buttons
4. Use search_page_content(query="textbox", search_type="tree") to find all input fields
5. Use search_page_content(query="instruction|step|task", search_type="text") to find instructions
6. Document all findings before taking any action
```

**STEP 2: Read Instructions Carefully**
```
1. Locate and read the main instruction text
2. Identify what the challenge is asking you to do
3. Note any specific order or sequence required
4. Identify the starting point of the challenge
```

**STEP 3: Collect All Codes**
```
For each code found in search results:
1. Note its exact value (6 characters)
2. Note where it's located (line number, element)
3. Determine if it's visible or hidden
4. If hidden, plan how to reveal it (button click, modal open, scroll)
```

**STEP 4: Execute Actions Methodically**
```
For each required action:
1. Find element in accessibility tree (you have this from search)
2. Locate element visually in screenshot
3. Get precise [x, y] coordinates from screenshot
4. Execute action (click, type, etc.)
5. Take new screenshot immediately after
6. Verify the action had the expected effect
7. If modal/popup opened, search its content before interacting
```

**STEP 5: Handle Modals and Popups**
```
When a modal appears:
1. Mark the popup with [transient] tags in your thinking if it's just a temporary acknowledgment
2. Use search_page_content to scan the modal's text content
3. Extract any codes or important information
4. If the modal has scrollable content:
   - Click inside the modal area first
   - Use scroll action with coordinates inside the modal
   - Search the new content after scrolling
5. Complete required actions within modal
6. Close modal using the close button or as instructed
```

**STEP 6: Fill Input Fields**
```
For each input field:
1. Identify what it expects (code, text, number)
2. Click on the input to focus it
3. Type the correct value
4. Verify the text appeared correctly
5. Move to next input or submit
```

**STEP 7: Final Submission**
```
1. Verify all required information is entered
2. Look for final submit/complete button
3. Click to submit
4. Verify success message or completion indicator
```

### Common Pitfalls to Avoid

❌ **DON'T DO THIS:**
- Scrolling blindly hoping to find content
- Clicking random elements without a plan
- Ignoring the search tool results
- Acting before having a complete picture
- Missing codes hidden in modals
- Forgetting to verify actions before proceeding
- Entering codes in wrong order or wrong fields

✅ **ALWAYS DO THIS:**
- Search FIRST using search_page_content
- Read ALL search results before acting
- Build a complete action plan
- Execute methodically, one step at a time
- Verify each action's result
- Mark transient content with [transient] tags
- Mark important findings with [remember] tags
- Use coordinates from screenshot for clicks

### Tool Usage Examples

**Finding Codes:**
```
search_page_content(query="\\b[A-Z0-9]{6}\\b", search_type="both")
```

**Finding Buttons:**
```
search_page_content(query="button.*submit|button.*next|button.*complete", search_type="tree")
```

**Finding Instructions:**
```
search_page_content(query="step \\d|instruction|task \\d", search_type="text")
```

**Finding Input Fields:**
```
search_page_content(query="textbox|input", search_type="tree")
```

### Memory Management

Use the memory tags to optimize context:

**Mark transient content:**
```
[transient]
I clicked the "OK" button to dismiss the acknowledgment popup.
The popup just said "Understood" and required no action beyond closing.
[/transient]
```

**Mark important findings:**
```
[remember]
Found code in modal: AJAF5H
This code needs to be entered in the "Code 2" input field.
[/remember]
```

### Success Criteria

You have successfully completed the challenge when:
1. ✅ All codes have been found and collected
2. ✅ All required UI interactions have been performed
3. ✅ All input fields are correctly filled
4. ✅ Final submission has been completed
5. ✅ Success/completion message is displayed
6. ✅ No error messages or missing information warnings

### Efficiency Targets

- **Total iterations:** Aim for < 20 iterations
- **Search usage:** Use search tool at least 5-10 times
- **Wasted actions:** Minimize aimless scrolling (should be 0)
- **Accuracy:** Enter correct codes on first try
- **Verification:** Always verify action results before proceeding

### Reporting

As you work through the challenge, clearly report:
1. What you found in search results
2. What action you're about to take and why
3. What you observe after each action
4. Any codes or important information discovered
5. Progress through the challenge steps
6. Final completion status

Remember: This is a test of systematic, methodical problem-solving. Speed matters, but accuracy and completeness matter more. Search first, understand completely, then act decisively.
