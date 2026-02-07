#!/usr/bin/env python3
"""Quick test to verify DOM manipulation integration."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that all components can be imported."""
    print("Testing imports...")

    try:
        from cua.providers.base import ActionType
        print("✓ ActionType imported")

        # Check DOM_MANIPULATION exists
        assert hasattr(ActionType, 'DOM_MANIPULATION'), "DOM_MANIPULATION not in ActionType"
        print("✓ DOM_MANIPULATION action type exists")

        from cua.tools.dom_tool import DOMTool, DOM_TOOL_DEFINITION, DOMAction
        print("✓ DOMTool components imported")

        from cua.providers.bedrock import BedrockProvider
        print("✓ BedrockProvider imported")

        from cua.prompts import DOM_TOOL_GUIDE
        print("✓ DOM_TOOL_GUIDE imported from prompts")

        print("\n✅ All imports successful!")
        return True

    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tool_definition():
    """Test DOM tool definition structure."""
    print("\nTesting tool definition...")

    try:
        from cua.tools.dom_tool import DOM_TOOL_DEFINITION

        assert "name" in DOM_TOOL_DEFINITION, "Missing 'name' in tool definition"
        assert DOM_TOOL_DEFINITION["name"] == "dom_manipulation", f"Wrong tool name: {DOM_TOOL_DEFINITION['name']}"
        print("✓ Tool name correct: dom_manipulation")

        assert "description" in DOM_TOOL_DEFINITION, "Missing 'description'"
        print("✓ Tool description present")

        assert "input_schema" in DOM_TOOL_DEFINITION, "Missing 'input_schema'"
        schema = DOM_TOOL_DEFINITION["input_schema"]

        assert "properties" in schema, "Missing 'properties' in schema"
        assert "action_type" in schema["properties"], "Missing 'action_type' property"

        action_types = schema["properties"]["action_type"]["enum"]
        expected_actions = ["find_selectors", "click_selector", "fill_selector", "get_info", "evaluate_js"]
        for action in expected_actions:
            assert action in action_types, f"Missing action type: {action}"
        print(f"✓ All action types present: {action_types}")

        print("\n✅ Tool definition valid!")
        return True

    except Exception as e:
        print(f"\n❌ Tool definition test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_prompts():
    """Test that prompts include DOM guidance."""
    print("\nTesting prompts...")

    try:
        from cua.prompts import (
            SYSTEM_PROMPT,
            DOM_TOOL_GUIDE,
            TOOL_USAGE_ESSENTIALS,
            build_initial_prompt
        )

        assert "DOM manipulation" in SYSTEM_PROMPT or "dom_manipulation" in SYSTEM_PROMPT, \
            "DOM not mentioned in SYSTEM_PROMPT"
        print("✓ SYSTEM_PROMPT mentions DOM")

        assert "dom_manipulation" in DOM_TOOL_GUIDE.lower(), "DOM_TOOL_GUIDE doesn't mention dom_manipulation"
        print("✓ DOM_TOOL_GUIDE present")

        assert "dom" in TOOL_USAGE_ESSENTIALS.lower(), "DOM not in TOOL_USAGE_ESSENTIALS"
        print("✓ TOOL_USAGE_ESSENTIALS mentions DOM")

        # Test build_initial_prompt includes DOM guide
        prompt = build_initial_prompt("Test task", has_search_tool=True, has_page_text=True)
        assert "dom_manipulation" in prompt.lower(), "DOM not in built prompt"
        print("✓ build_initial_prompt includes DOM guide")

        print("\n✅ Prompts include DOM guidance!")
        return True

    except Exception as e:
        print(f"\n❌ Prompt test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("DOM Manipulation Integration Test")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Tool Definition", test_tool_definition()))
    results.append(("Prompts", test_prompts()))

    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:20s}: {status}")

    all_passed = all(passed for _, passed in results)

    print("=" * 60)
    if all_passed:
        print("🎉 All tests passed! DOM manipulation is integrated.")
    else:
        print("⚠️  Some tests failed. Check output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
