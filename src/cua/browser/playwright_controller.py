"""Playwright-based browser controller."""

import base64
import time
from typing import Optional
from playwright.sync_api import sync_playwright, Page, Browser

from cua.providers.base import Action, ActionType


class PlaywrightController:
    """Controller for browser automation using Playwright."""

    def __init__(self, display_width: int = 1280, display_height: int = 720, headless: bool = True):
        """Initialize Playwright controller.

        Args:
            display_width: Browser viewport width
            display_height: Browser viewport height
            headless: Whether to run browser in headless mode
        """
        self.display_width = display_width
        self.display_height = display_height
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    def start(self):
        """Start the browser."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
        )
        self.page = self.browser.new_page()
        self.page.set_viewport_size({
            "width": self.display_width,
            "height": self.display_height
        })

    def stop(self):
        """Stop the browser."""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def navigate(self, url: str):
        """Navigate to URL.

        Args:
            url: URL to navigate to
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Wait a bit for page to stabilize
        time.sleep(1)

    def take_screenshot(self) -> str:
        """Take screenshot of current page.

        Returns:
            Base64-encoded screenshot
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        screenshot_bytes = self.page.screenshot(full_page=False)
        return base64.b64encode(screenshot_bytes).decode('utf-8')

    def execute_action(self, action: Action) -> dict:
        """Execute an action on the page.

        Args:
            action: Action to execute

        Returns:
            Dictionary with action result
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            if action.type == ActionType.SCREENSHOT:
                screenshot = self.take_screenshot()
                return {"success": True, "screenshot": screenshot}

            elif action.type == ActionType.CLICK:
                x, y = self._get_coordinates(action.params)
                self.page.mouse.click(x, y)
                time.sleep(0.5)
                return {"success": True, "action": "click", "x": x, "y": y}

            elif action.type == ActionType.DOUBLE_CLICK:
                x, y = self._get_coordinates(action.params)
                self.page.mouse.dblclick(x, y)
                time.sleep(0.5)
                return {"success": True, "action": "double_click", "x": x, "y": y}

            elif action.type == ActionType.RIGHT_CLICK:
                x, y = self._get_coordinates(action.params)
                self.page.mouse.click(x, y, button="right")
                time.sleep(0.5)
                return {"success": True, "action": "right_click", "x": x, "y": y}

            elif action.type == ActionType.TYPE:
                text = action.params.get("text", "")
                self.page.keyboard.type(text)
                time.sleep(0.3)
                return {"success": True, "action": "type", "text": text}

            elif action.type in [ActionType.KEY, ActionType.KEYPRESS]:
                # Handle both Claude's "key" and OpenAI's "keypress"
                if "text" in action.params:
                    # Claude format: key with text
                    key = action.params["text"]
                    self.page.keyboard.press(self._map_key(key))
                elif "keys" in action.params:
                    # OpenAI format: keypress with keys array
                    for key in action.params["keys"]:
                        self.page.keyboard.press(self._map_key(key))
                time.sleep(0.3)
                return {"success": True, "action": "keypress"}

            elif action.type == ActionType.SCROLL:
                x, y = self._get_coordinates(action.params)

                # Handle both Claude and OpenAI scroll formats
                if "scroll_direction" in action.params:
                    # Claude format
                    direction = action.params.get("scroll_direction", "down")
                    amount = action.params.get("scroll_amount", 3)
                    scroll_y = amount * 100 if direction == "down" else -amount * 100
                    scroll_x = 0
                elif "scroll_x" in action.params or "scroll_y" in action.params:
                    # OpenAI format
                    scroll_x = action.params.get("scroll_x", 0)
                    scroll_y = action.params.get("scroll_y", 0)
                else:
                    scroll_x = 0
                    scroll_y = 300  # Default scroll down

                # Move mouse to position and scroll
                self.page.mouse.move(x, y)
                self.page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")
                time.sleep(0.5)
                return {"success": True, "action": "scroll", "x": x, "y": y}

            elif action.type == ActionType.WAIT:
                time.sleep(2)
                return {"success": True, "action": "wait"}

            elif action.type == ActionType.MOUSE_MOVE:
                x, y = self._get_coordinates(action.params)
                self.page.mouse.move(x, y)
                time.sleep(0.2)
                return {"success": True, "action": "mouse_move", "x": x, "y": y}

            else:
                return {"success": False, "error": f"Unknown action type: {action.type}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_page_info(self) -> dict:
        """Get information about current page.

        Returns:
            Dictionary with page information
        """
        if not self.page:
            return {}

        return {
            "url": self.page.url,
            "title": self.page.title(),
        }

    def _get_coordinates(self, params: dict) -> tuple[int, int]:
        """Extract coordinates from action parameters.

        Args:
            params: Action parameters

        Returns:
            Tuple of (x, y) coordinates
        """
        # Try different parameter formats
        if "coordinate" in params:
            # Claude format
            return params["coordinate"][0], params["coordinate"][1]
        elif "x" in params and "y" in params:
            # OpenAI format
            return params["x"], params["y"]
        else:
            # Default to center of screen
            return self.display_width // 2, self.display_height // 2

    def _map_key(self, key: str) -> str:
        """Map key names to Playwright key names.

        Args:
            key: Key name from API

        Returns:
            Playwright key name
        """
        # Common key mappings
        key_map = {
            "Return": "Enter",
            "ENTER": "Enter",
            "Enter": "Enter",
            "Space": " ",
            "SPACE": " ",
            "Tab": "Tab",
            "TAB": "Tab",
            "Backspace": "Backspace",
            "Delete": "Delete",
            "Escape": "Escape",
            "ESC": "Escape",
            "ArrowUp": "ArrowUp",
            "ArrowDown": "ArrowDown",
            "ArrowLeft": "ArrowLeft",
            "ArrowRight": "ArrowRight",
            "PageDown": "PageDown",
            "Page_Down": "PageDown",
            "PageUp": "PageUp",
            "Page_Up": "PageUp",
            "Home": "Home",
            "End": "End",
        }

        return key_map.get(key, key)
