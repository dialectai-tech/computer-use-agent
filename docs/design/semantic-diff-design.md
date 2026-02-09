# Semantic Diff for Accessibility Tree - Design Document

## Overview

Instead of sending the full accessibility tree after every action (which can be 5000-10000 tokens), we send:
1. **Full tree** on page load or first action
2. **Semantic diff** for subsequent actions on the same page

This reduces token usage by 80-95% while providing more meaningful information than image diffs.

## Problem Statement

### Current Approach
```
Every action → Full a11y tree (~8000 tokens)
3 actions = 24,000 tokens just for a11y trees
```

### Proposed Approach
```
Action 1 (page load) → Full a11y tree (8000 tokens)
Action 2 (click) → Semantic diff (500 tokens)
Action 3 (type) → Semantic diff (300 tokens)
Total: 8,800 tokens (63% savings)
```

## Design Decisions

### 1. When to Send Full Tree

✅ **Full Tree Scenarios:**
- First action in session (no baseline)
- Page navigation (URL changed)
- After context reset (baseline lost)
- Large diff (>60% of tree changed)

Example:
```
Iteration 1: Click → Navigate to new page → Send full tree
Iteration 2: Type in field → Same page → Send diff
Iteration 3: Click button → Same page → Send diff
```

### 2. When to Send Semantic Diff

✅ **Diff Scenarios:**
- Same page, element interaction
- DOM manipulation actions
- Small to medium structural changes

### 3. What Constitutes a Semantic Change?

**Track These Changes:**
- ✅ Elements added (new buttons, notifications, modals)
- ✅ Elements removed (spinners, error messages)
- ✅ State changes (disabled → enabled, unchecked → checked)
- ✅ Text content changes (button label, heading text)
- ✅ Value changes (input field value)
- ✅ Attribute changes (aria-label, aria-expanded)

**Ignore These:**
- ❌ Rendering-specific attributes (x, y, width, height)
- ❌ Focus state (transient)
- ❌ Style attributes (color, font-size)
- ❌ Internal IDs that don't convey meaning

### 4. Element Identity

**How to track "same element across trees?"**

Use composite key:
```python
element_key = f"{role}:{name}:{path_to_root}"
```

Examples:
- `button:Submit:div[0]/form[0]/button[0]`
- `textbox:Email:div[0]/input[0]`

**Why not element ID?**
- IDs may not exist or be auto-generated
- Path-based identity more stable
- Role + name gives semantic meaning

## Data Structures

### AccessibilityTreeDiff

```python
@dataclass
class AccessibilityTreeDiff:
    """Semantic diff of accessibility tree changes."""

    # Elements that appeared
    added_elements: List[Dict[str, Any]]

    # Elements that disappeared
    removed_elements: List[Dict[str, Any]]

    # Elements that changed state/content
    modified_elements: List[Dict[str, Any]]

    # Human-readable summary for LLM
    summary: str

    # Statistics
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0

    # Flag indicating if diff is too large
    is_large_diff: bool = False  # If >60% changed, send full tree instead
```

### Diff Output Format

**Compact Format for LLM:**
```
🌲 Accessibility Tree Changes:

Added (3):
+ button "Submit" (enabled)
+ text "Success!" in div.notification
+ link "View Details"

Removed (2):
- button "Loading..." (disabled)
- img[spinner]

Modified (2):
~ button[#submit]: disabled → enabled
~ textbox[#email]: value "" → "user@example.com"
```

**Full JSON (for logging/debugging):**
```json
{
  "added_elements": [
    {
      "role": "button",
      "name": "Submit",
      "path": "div[0]/form[0]/button[1]",
      "attributes": {"enabled": true}
    }
  ],
  "removed_elements": [...],
  "modified_elements": [...],
  "summary": "Added 3, Removed 2, Modified 2",
  "is_large_diff": false
}
```

## Algorithm

### compute_a11y_tree_diff(old_tree, new_tree)

```python
def compute_a11y_tree_diff(old_tree: dict, new_tree: dict) -> AccessibilityTreeDiff:
    """
    Compute semantic diff between two accessibility trees.

    Args:
        old_tree: Previous accessibility tree
        new_tree: Current accessibility tree

    Returns:
        AccessibilityTreeDiff with added/removed/modified elements
    """

    # Step 1: Build element maps (key → element)
    old_elements = build_element_map(old_tree)
    new_elements = build_element_map(new_tree)

    # Step 2: Find added/removed elements
    old_keys = set(old_elements.keys())
    new_keys = set(new_elements.keys())

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys
    common_keys = old_keys & new_keys

    added_elements = [new_elements[k] for k in added_keys]
    removed_elements = [old_elements[k] for k in removed_keys]

    # Step 3: Find modified elements
    modified_elements = []
    for key in common_keys:
        old_elem = old_elements[key]
        new_elem = new_elements[key]

        changes = compare_elements(old_elem, new_elem)
        if changes:
            modified_elements.append({
                "key": key,
                "changes": changes,
                "old": old_elem,
                "new": new_elem
            })

    # Step 4: Check if diff is too large (>60% changed)
    total_elements = len(old_keys | new_keys)
    changed_elements = len(added_keys) + len(removed_keys) + len(modified_elements)
    is_large_diff = (changed_elements / total_elements) > 0.6 if total_elements > 0 else False

    # Step 5: Generate human-readable summary
    summary = generate_summary(added_elements, removed_elements, modified_elements)

    return AccessibilityTreeDiff(
        added_elements=added_elements,
        removed_elements=removed_elements,
        modified_elements=modified_elements,
        summary=summary,
        total_added=len(added_elements),
        total_removed=len(removed_elements),
        total_modified=len(modified_elements),
        is_large_diff=is_large_diff
    )
```

### build_element_map(tree, path="")

```python
def build_element_map(tree: dict, path: str = "") -> Dict[str, dict]:
    """
    Recursively build a flat map of elements with stable keys.

    Args:
        tree: Accessibility tree node
        path: Current path from root

    Returns:
        Dict mapping element_key → element_data
    """
    elements = {}

    if not tree or isinstance(tree, str):
        return elements

    # Generate stable key for this element
    role = tree.get("role", "unknown")
    name = tree.get("name", "")
    element_key = f"{role}:{name}:{path}"

    # Store element with key semantic attributes
    elements[element_key] = {
        "role": role,
        "name": name,
        "value": tree.get("value"),
        "description": tree.get("description"),
        "checked": tree.get("checked"),
        "disabled": tree.get("disabled"),
        "expanded": tree.get("expanded"),
        "path": path
    }

    # Recurse into children
    if "children" in tree and isinstance(tree["children"], list):
        for i, child in enumerate(tree["children"]):
            child_path = f"{path}/{role}[{i}]" if path else f"{role}[{i}]"
            child_elements = build_element_map(child, child_path)
            elements.update(child_elements)

    return elements
```

### compare_elements(old, new)

```python
def compare_elements(old: dict, new: dict) -> Optional[Dict[str, tuple]]:
    """
    Compare two elements and return what changed.

    Args:
        old: Old element data
        new: New element data

    Returns:
        Dict of changed attributes with (old_value, new_value) tuples,
        or None if no meaningful changes
    """
    changes = {}

    # Compare meaningful attributes
    attributes_to_check = [
        "value", "checked", "disabled", "expanded",
        "name", "description"
    ]

    for attr in attributes_to_check:
        old_val = old.get(attr)
        new_val = new.get(attr)

        if old_val != new_val:
            changes[attr] = (old_val, new_val)

    return changes if changes else None
```

### generate_summary(added, removed, modified)

```python
def generate_summary(
    added: List[dict],
    removed: List[dict],
    modified: List[dict],
    max_items: int = 10
) -> str:
    """
    Generate human-readable summary for LLM consumption.

    Args:
        added: Added elements
        removed: Removed elements
        modified: Modified elements
        max_items: Max items to show per category

    Returns:
        Formatted summary string
    """
    lines = ["🌲 Accessibility Tree Changes:\n"]

    # Added elements
    if added:
        lines.append(f"Added ({len(added)}):")
        for elem in added[:max_items]:
            role = elem.get("role", "unknown")
            name = elem.get("name", "")
            disabled = " (disabled)" if elem.get("disabled") else ""
            lines.append(f"+ {role} \"{name}\"{disabled}")
        if len(added) > max_items:
            lines.append(f"  ... and {len(added) - max_items} more")
        lines.append("")

    # Removed elements
    if removed:
        lines.append(f"Removed ({len(removed)}):")
        for elem in removed[:max_items]:
            role = elem.get("role", "unknown")
            name = elem.get("name", "")
            lines.append(f"- {role} \"{name}\"")
        if len(removed) > max_items:
            lines.append(f"  ... and {len(removed) - max_items} more")
        lines.append("")

    # Modified elements
    if modified:
        lines.append(f"Modified ({len(modified)}):")
        for item in modified[:max_items]:
            key = item["key"]
            changes = item["changes"]

            # Parse key for display
            role = key.split(":")[0]
            name = key.split(":")[1]

            # Format changes
            change_strs = []
            for attr, (old_val, new_val) in changes.items():
                change_strs.append(f"{attr}: {old_val} → {new_val}")

            changes_text = ", ".join(change_strs)
            lines.append(f"~ {role} \"{name}\": {changes_text}")

        if len(modified) > max_items:
            lines.append(f"  ... and {len(modified) - max_items} more")

    # If no changes
    if not added and not removed and not modified:
        lines.append("(No semantic changes detected)")

    return "\n".join(lines)
```

## Integration with Agent Loop

### Modified Workflow

```python
# In agent loop (loop.py)

# Initialize tracking
last_a11y_tree = None
last_a11y_url = None

for action in actions:
    # Execute action
    result = execute_action(action)

    # Get current state
    current_url = browser.get_page_info().get('url', '')
    current_a11y_tree = browser.get_accessibility_tree()

    # Determine if we should send full tree or diff
    should_send_full_tree = (
        last_a11y_tree is None or  # First action
        current_url != last_a11y_url or  # Page navigation
        action.type == ActionType.CONTEXT_RESET  # After reset
    )

    a11y_diff = None
    a11y_tree_to_send = None

    if should_send_full_tree:
        # Send full tree
        a11y_tree_to_send = current_a11y_tree
        console.print("  [dim]📊 Sending full a11y tree (baseline)[/dim]")
    else:
        # Compute diff
        a11y_diff = compute_a11y_tree_diff(last_a11y_tree, current_a11y_tree)

        # If diff is too large, send full tree instead
        if a11y_diff.is_large_diff:
            a11y_tree_to_send = current_a11y_tree
            console.print("  [dim]📊 Large diff detected, sending full tree[/dim]")
        else:
            # Send diff only
            console.print(f"  [dim]🔄 A11y changes: +{a11y_diff.total_added} -{a11y_diff.total_removed} ~{a11y_diff.total_modified}[/dim]")

    # Store in evidence
    evidence = ActionEvidence(
        action_id=action.id,
        action_type=action.type,
        result=result,
        screenshot=screenshot,
        accessibility_tree=a11y_tree_to_send,  # Full tree if baseline needed
        accessibility_tree_diff=a11y_diff,  # Diff if incremental
        ...
    )

    # Update tracking
    last_a11y_tree = current_a11y_tree
    last_a11y_url = current_url
```

## Integration with Provider

### Bedrock Provider Changes

```python
# In bedrock.py - create_continuation_request()

for tool_use in self.last_tool_uses:
    tool_id = tool_use.get('toolUseId')
    action_evidence = action_evidence_map.get(tool_id)

    # ... existing tool result building ...

    # Add accessibility tree or diff
    if action_evidence:
        # Check if full tree or diff
        if action_evidence.accessibility_tree:
            # Full tree (baseline)
            tree_text = format_a11y_tree_compact(action_evidence.accessibility_tree)
            result_content.append({"text": f"\n\n**Accessibility Tree (Baseline):**\n```\n{tree_text}\n```"})

        elif action_evidence.accessibility_tree_diff:
            # Semantic diff (incremental)
            diff_text = action_evidence.accessibility_tree_diff.summary
            result_content.append({"text": f"\n{diff_text}"})
```

## Configuration

### CLI Flags

```python
@click.option(
    "--use-accessibility-tree/--no-use-accessibility-tree",
    default=True,
    help="Use accessibility tree (default: enabled)"
)
@click.option(
    "--use-semantic-diff/--no-use-semantic-diff",
    default=True,
    help="Use semantic diff for a11y tree instead of full tree after baseline (default: enabled)"
)
```

### Behavior Matrix

| Flag Combination | Behavior |
|------------------|----------|
| `--use-accessibility-tree --use-semantic-diff` | Full tree on baseline, diff thereafter (RECOMMENDED) |
| `--use-accessibility-tree --no-use-semantic-diff` | Always send full tree (legacy mode) |
| `--no-use-accessibility-tree` | No a11y tree at all (semantic diff flag ignored) |

## Token Impact Analysis

### Typical Web Application

**Without Semantic Diff (Current):**
```
Iteration 1: Full tree = 8,000 tokens
Iteration 2: Full tree = 8,000 tokens
Iteration 3: Full tree = 8,000 tokens
Total: 24,000 tokens
```

**With Semantic Diff (Proposed):**
```
Iteration 1: Full tree = 8,000 tokens
Iteration 2: Diff = 500 tokens (+3 -2 ~2)
Iteration 3: Diff = 300 tokens (+1 -1 ~1)
Total: 8,800 tokens (63% savings!)
```

### Worst Case (Every Action Changes Everything)

**Without Semantic Diff:**
```
3 actions × 8,000 = 24,000 tokens
```

**With Semantic Diff:**
```
Action 1: Full tree = 8,000 tokens
Action 2: Large diff → Full tree = 8,000 tokens
Action 3: Large diff → Full tree = 8,000 tokens
Total: 24,000 tokens (no savings, but no harm)
```

### Best Case (Minimal Changes)

**Without Semantic Diff:**
```
3 actions × 8,000 = 24,000 tokens
```

**With Semantic Diff:**
```
Action 1: Full tree = 8,000 tokens
Action 2: Tiny diff = 150 tokens
Action 3: Tiny diff = 150 tokens
Total: 8,300 tokens (65% savings!)
```

## Implementation Phases

### Phase 1: Core Infrastructure (This Commit)
- ✅ AccessibilityTreeDiff dataclass
- ✅ compute_a11y_tree_diff() function
- ✅ build_element_map() helper
- ✅ compare_elements() helper
- ✅ generate_summary() helper

### Phase 2: Agent Integration (This Commit)
- ✅ Track last_a11y_tree in loop
- ✅ Determine when to send full vs diff
- ✅ Store diff in ActionEvidence
- ✅ Update last_a11y_tree after each action

### Phase 3: Provider Integration (This Commit)
- ✅ Modify create_continuation_request
- ✅ Send full tree or diff based on evidence
- ✅ Format diff for LLM consumption

### Phase 4: CLI Configuration (This Commit)
- ✅ Add --use-semantic-diff flag
- ✅ Pass through to agent
- ✅ Documentation

## Testing Strategy

### Test Cases

1. **Baseline Test**: First action sends full tree
2. **Incremental Test**: Subsequent actions send diff
3. **Navigation Test**: Page change → full tree
4. **Large Diff Test**: Major change → full tree fallback
5. **No Change Test**: Same tree → empty diff
6. **Modification Test**: Button state change → shows in diff
7. **Mixed Test**: Add + remove + modify → all in diff summary

### Example Test Scenario

```python
# Start at page A
action_1 = click_button()  # Navigate to page B
# → Expect: Full tree (URL changed)

action_2 = fill_input("test")  # Same page
# → Expect: Diff showing textbox value change

action_3 = click_submit()  # Same page
# → Expect: Diff showing button state + new elements
```

## Success Metrics

- ✅ 60-80% token reduction for typical workflows
- ✅ No information loss (diff captures all semantic changes)
- ✅ Backward compatible (flag to disable)
- ✅ Fast computation (<100ms for typical trees)

## References

- Text diff implementation (previous commit)
- Multi-action evidence collection
- Accessibility tree format (Playwright)
- Difflib unified_diff algorithm

---

**Status**: Ready for Implementation
**Estimated Savings**: 60-80% of a11y tree tokens
**Complexity**: Medium (tree traversal + diff logic)
**Risk**: Low (fallback to full tree if diff too large)
