#!/usr/bin/env python3
"""Test script to verify keyboard shortcuts work correctly."""

from cua.browser.playwright_controller import PlaywrightController
import time

def test_keyboard_shortcuts():
    """Test various keyboard shortcuts."""
    print("Testing keyboard shortcuts...")

    controller = PlaywrightController(headless=False)
    controller.start()

    # Navigate to a test page
    controller.navigate("https://example.com")
    time.sleep(2)

    tests = [
        ("Space", "Scroll down one page"),
        ("Home", "Jump to top"),
        ("End", "Jump to bottom"),
        ("Ctrl+Home", "Jump to absolute beginning"),
        ("Ctrl+End", "Jump to absolute end"),
        ("PageDown", "Page down"),
        ("PageUp", "Page up"),
    ]

    for key, description in tests:
        print(f"\nTesting {key}: {description}")
        try:
            from cua.providers.base import Action, ActionType
            action = Action(
                type=ActionType.KEY,
                params={"text": key},
                id="test"
            )
            result = controller.execute_action(action)
            if result["success"]:
                print(f"  ✓ {key} worked")
            else:
                print(f"  ✗ {key} failed: {result.get('error')}")
            time.sleep(1)
        except Exception as e:
            print(f"  ✗ {key} failed with exception: {e}")

    print("\nAll tests completed!")
    time.sleep(3)
    controller.stop()

if __name__ == "__main__":
    test_keyboard_shortcuts()
