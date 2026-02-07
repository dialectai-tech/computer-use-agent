#!/usr/bin/env python3
"""Quick test to verify context reset integration."""

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

        # Check CONTEXT_RESET exists
        assert hasattr(ActionType, 'CONTEXT_RESET'), "CONTEXT_RESET not in ActionType"
        print("✓ CONTEXT_RESET action type exists")

        from cua.tools.context_reset_tool import (
            ContextResetTool,
            CONTEXT_RESET_TOOL_DEFINITION,
            ContextResetRequest
        )
        print("✓ ContextResetTool components imported")

        from cua.providers.bedrock import BedrockProvider
        print("✓ BedrockProvider imported")

        from cua.prompts import CONTEXT_RESET_GUIDE
        print("✓ CONTEXT_RESET_GUIDE imported from prompts")

        print("\n✅ All imports successful!")
        return True

    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tool_definition():
    """Test context reset tool definition structure."""
    print("\nTesting tool definition...")

    try:
        from cua.tools.context_reset_tool import CONTEXT_RESET_TOOL_DEFINITION

        assert "name" in CONTEXT_RESET_TOOL_DEFINITION, "Missing 'name' in tool definition"
        assert CONTEXT_RESET_TOOL_DEFINITION["name"] == "reset_context", \
            f"Wrong tool name: {CONTEXT_RESET_TOOL_DEFINITION['name']}"
        print("✓ Tool name correct: reset_context")

        assert "description" in CONTEXT_RESET_TOOL_DEFINITION, "Missing 'description'"
        print("✓ Tool description present")

        assert "input_schema" in CONTEXT_RESET_TOOL_DEFINITION, "Missing 'input_schema'"
        schema = CONTEXT_RESET_TOOL_DEFINITION["input_schema"]

        assert "properties" in schema, "Missing 'properties' in schema"
        required_props = ["reason", "progress_summary", "next_goal"]
        for prop in required_props:
            assert prop in schema["properties"], f"Missing property: {prop}"
        print(f"✓ All required properties present: {required_props}")

        assert schema["required"] == required_props, "Required fields mismatch"
        print("✓ Required fields correctly specified")

        print("\n✅ Tool definition valid!")
        return True

    except Exception as e:
        print(f"\n❌ Tool definition test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_validation():
    """Test context reset request validation."""
    print("\nTesting validation...")

    try:
        from cua.tools.context_reset_tool import ContextResetRequest, ContextResetTool

        # Test valid request
        valid_request = ContextResetRequest(
            reason="Completed Step 5, starting Step 6",
            progress_summary="Completed steps 1-5 successfully. Now on Step 6 of 30.",
            next_goal="Find code for Step 6, enter it, proceed to Step 7"
        )
        result = ContextResetTool.validate_request(valid_request)
        assert result["success"], f"Valid request rejected: {result.get('error')}"
        print("✓ Valid request accepted")

        # Test invalid reason (too short)
        invalid_request = ContextResetRequest(
            reason="Short",
            progress_summary="Completed steps 1-5 successfully.",
            next_goal="Continue with next step"
        )
        result = ContextResetTool.validate_request(invalid_request)
        assert not result["success"], "Invalid reason not caught"
        print("✓ Invalid reason rejected")

        # Test bad keyword
        bad_request = ContextResetRequest(
            reason="In the middle of form filling",
            progress_summary="Halfway through the registration form.",
            next_goal="Complete the form"
        )
        result = ContextResetTool.validate_request(bad_request)
        assert not result["success"], "Bad timing keyword not caught"
        print("✓ Bad timing keyword rejected")

        print("\n✅ Validation working correctly!")
        return True

    except Exception as e:
        print(f"\n❌ Validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_provider_method():
    """Test that BedrockProvider has reset_context method."""
    print("\nTesting provider method...")

    try:
        from cua.providers.bedrock import BedrockProvider

        # Check that reset_context method exists
        assert hasattr(BedrockProvider, 'reset_context'), \
            "BedrockProvider missing reset_context method"
        print("✓ BedrockProvider has reset_context method")

        # Check method signature
        import inspect
        sig = inspect.signature(BedrockProvider.reset_context)
        params = list(sig.parameters.keys())
        expected_params = ['self', 'progress_summary', 'next_goal', 'current_screenshot', 'current_page_info']
        assert params == expected_params, f"Method signature mismatch: {params}"
        print("✓ reset_context method signature correct")

        print("\n✅ Provider method present!")
        return True

    except Exception as e:
        print(f"\n❌ Provider method test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_prompts():
    """Test that prompts include context reset guidance."""
    print("\nTesting prompts...")

    try:
        from cua.prompts import (
            SYSTEM_PROMPT,
            CONTEXT_RESET_GUIDE,
            build_initial_prompt
        )

        assert "reset context" in SYSTEM_PROMPT.lower() or "context reset" in SYSTEM_PROMPT.lower(), \
            "Context reset not mentioned in SYSTEM_PROMPT"
        print("✓ SYSTEM_PROMPT mentions context reset")

        assert "reset_context" in CONTEXT_RESET_GUIDE.lower(), \
            "CONTEXT_RESET_GUIDE doesn't mention reset_context"
        print("✓ CONTEXT_RESET_GUIDE present")

        # Test build_initial_prompt includes context reset guide
        prompt = build_initial_prompt("Test task", has_search_tool=True, has_page_text=True)
        assert "reset_context" in prompt.lower() or "context reset" in prompt.lower(), \
            "Context reset not in built prompt"
        print("✓ build_initial_prompt includes context reset guide")

        print("\n✅ Prompts include context reset guidance!")
        return True

    except Exception as e:
        print(f"\n❌ Prompt test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Context Reset Integration Test")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Tool Definition", test_tool_definition()))
    results.append(("Validation", test_validation()))
    results.append(("Provider Method", test_provider_method()))
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
        print("🎉 All tests passed! Context reset is integrated.")
    else:
        print("⚠️  Some tests failed. Check output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
