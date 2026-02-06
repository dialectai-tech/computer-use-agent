"""Playwright-based browser controller."""

import base64
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from playwright.sync_api import sync_playwright, Page, Browser

from cua.providers.base import Action, ActionType


class PlaywrightController:
    """Controller for browser automation using Playwright."""

    def __init__(
        self,
        display_width: int = 1024,
        display_height: int = 768,
        zoom: int = 85,
        headless: bool = True,
        record_video: bool = False,
        video_dir: Optional[str] = None
    ):
        """Initialize Playwright controller.

        Args:
            display_width: Browser viewport width
            display_height: Browser viewport height
            zoom: Browser zoom level as percentage (default: 85)
            headless: Whether to run browser in headless mode
            record_video: Whether to record video of the session
            video_dir: Directory to save videos (default: ./recordings)
        """
        self.display_width = display_width
        self.display_height = display_height
        self.zoom = zoom
        self.headless = headless
        self.record_video = record_video
        self.video_dir = video_dir or "./recordings"
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.video_path: Optional[str] = None

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

        # Setup video recording if enabled
        context_options = {
            "viewport": {
                "width": self.display_width,
                "height": self.display_height
            }
        }

        if self.record_video:
            # Create recordings directory if it doesn't exist
            Path(self.video_dir).mkdir(parents=True, exist_ok=True)

            # Generate video filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"cua_session_{timestamp}.webm"
            self.video_path = os.path.join(self.video_dir, video_filename)

            context_options["record_video_dir"] = self.video_dir
            context_options["record_video_size"] = {
                "width": self.display_width,
                "height": self.display_height
            }

        # Create browser context
        context = self.browser.new_context(**context_options)
        self.page = context.new_page()

    def stop(self):
        """Stop the browser and save video if recording."""
        if self.page:
            # Close page and context to finalize video
            context = self.page.context
            self.page.close()
            if self.record_video:
                context.close()  # This finalizes the video
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def get_video_path(self) -> Optional[str]:
        """Get the path to the recorded video.

        Returns:
            Path to video file, or None if not recording
        """
        if self.record_video and self.page:
            try:
                # Get the actual video path from the page
                video = self.page.video
                if video:
                    return video.path()
            except Exception:
                pass
        return None

    def navigate(self, url: str):
        """Navigate to URL.

        Args:
            url: URL to navigate to
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Set zoom level if not 100%
        if self.zoom != 100:
            self._set_zoom()

        # Wait a bit for page to stabilize
        time.sleep(1)

    def _set_zoom(self):
        """Set the browser zoom level."""
        if not self.page:
            return

        # Use CSS zoom to adjust page scale
        zoom_factor = self.zoom / 100.0
        self.page.evaluate(f"""
            document.body.style.zoom = '{zoom_factor}';
        """)

    def take_screenshot(self) -> str:
        """Take screenshot of current page.

        Returns:
            Base64-encoded screenshot
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        screenshot_bytes = self.page.screenshot(full_page=False)
        return base64.b64encode(screenshot_bytes).decode('utf-8')

    def get_accessibility_tree(self, max_depth: int = 10) -> dict:
        """Get accessibility tree of current page.

        Args:
            max_depth: Maximum depth to traverse (default: 10)

        Returns:
            Dictionary containing accessibility tree
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            # Get accessibility snapshot
            tree = self.page.accessibility.snapshot(
                interesting_only=True,  # Filter out non-interactive elements
                root=None  # Start from page root
            )

            # Simplify tree structure for token efficiency
            simplified = self._simplify_accessibility_tree(tree, max_depth=max_depth)
            return simplified
        except Exception as e:
            # Return empty tree if accessibility snapshot fails
            return {"error": str(e), "tree": None}

    def _simplify_accessibility_tree(self, node: dict, depth: int = 0, max_depth: int = 10) -> dict:
        """Simplify accessibility tree to reduce token usage.

        Args:
            node: Accessibility tree node
            depth: Current depth in tree
            max_depth: Maximum depth to traverse

        Returns:
            Simplified node dictionary
        """
        if not node or depth >= max_depth:
            return None

        # Extract essential properties
        simplified = {}

        # Core properties
        if node.get('role'):
            simplified['role'] = node['role']
        if node.get('name'):
            simplified['name'] = node['name'][:100]  # Truncate long names

        # Important attributes
        if node.get('value'):
            simplified['value'] = str(node['value'])[:50]
        if node.get('description'):
            simplified['description'] = node['description'][:100]
        if node.get('disabled'):
            simplified['disabled'] = True
        if node.get('checked') is not None:
            simplified['checked'] = node['checked']
        if node.get('pressed') is not None:
            simplified['pressed'] = node['pressed']
        if node.get('expanded') is not None:
            simplified['expanded'] = node['expanded']
        if node.get('modal'):
            simplified['modal'] = True
        if node.get('level'):
            simplified['level'] = node['level']

        # Recursively process children (limit to avoid token explosion)
        children = node.get('children', [])
        if children and depth < max_depth:
            simplified_children = []
            for child in children[:50]:  # Limit children per node
                simplified_child = self._simplify_accessibility_tree(child, depth + 1, max_depth)
                if simplified_child:
                    simplified_children.append(simplified_child)

            if simplified_children:
                simplified['children'] = simplified_children

        return simplified if simplified else None

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
            x, y = params["coordinate"][0], params["coordinate"][1]

            # Warn if coordinates are suspiciously at origin (common AI error)
            if x == 0 and y == 0:
                print(f"⚠️  WARNING: Coordinates are (0, 0) - AI may not be using screenshot for positioning")
                print(f"   Action params: {params}")

            return x, y
        elif "x" in params and "y" in params:
            # OpenAI format
            x, y = params["x"], params["y"]

            # Warn if coordinates are at origin
            if x == 0 and y == 0:
                print(f"⚠️  WARNING: Coordinates are (0, 0) - AI may not be using screenshot for positioning")
                print(f"   Action params: {params}")

            return x, y
        else:
            # Default to center of screen
            print(f"⚠️  WARNING: No coordinates found in params, using center of screen")
            print(f"   Action params: {params}")
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
