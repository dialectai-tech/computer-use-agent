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
            try:
                self.page.close()
            except Exception as e:
                print(f"Warning: Error closing page: {e}")

            if self.record_video:
                try:
                    context.close()  # This finalizes the video
                except Exception as e:
                    print(f"Warning: Error closing context: {e}")
        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                print(f"Warning: Error closing browser: {e}")
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                print(f"Warning: Error stopping playwright: {e}")

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

        Note: Playwright Python doesn't have page.accessibility API.
        We use JavaScript evaluation to extract accessibility information from DOM.

        Args:
            max_depth: Maximum depth to traverse (default: 10)

        Returns:
            Dictionary containing accessibility tree
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            # Use JavaScript to build accessibility tree from DOM
            # Extracts ARIA roles, labels, values, and states
            tree = self.page.evaluate("""
                (maxDepth) => {
                    function getAccessibilityInfo(element, depth) {
                        if (!element || depth > maxDepth) return null;

                        const role = element.getAttribute('role') || getImplicitRole(element);
                        const name = getAccessibleName(element);
                        const value = getAccessibleValue(element);
                        const state = getAccessibleState(element);

                        // STRICT FILTER: Only include elements with semantic roles
                        // This prevents text-only divs from bloating the tree
                        // We want interactive/structural elements, not generic containers
                        if (!role) {
                            // No role - recurse to children but don't create node
                            const children = [];
                            if (depth < maxDepth && element.children) {
                                for (let child of element.children) {
                                    const childNode = getAccessibilityInfo(child, depth);
                                    if (childNode) children.push(childNode);
                                }
                            }
                            // Return first child if only one, otherwise return all
                            if (children.length === 1) return children[0];
                            if (children.length > 1) return { role: 'generic', name: '', children };
                            return null;
                        }

                        // Has role - create node
                        const node = { role, name, value, ...state, children: [] };

                        // Process children
                        if (depth < maxDepth && element.children) {
                            for (let child of element.children) {
                                const childNode = getAccessibilityInfo(child, depth + 1);
                                if (childNode) node.children.push(childNode);
                            }
                        }

                        return node;
                    }

                    function getImplicitRole(el) {
                        const tag = el.tagName.toLowerCase();
                        const type = el.getAttribute('type');
                        const roles = {
                            'button': 'button',
                            'a': el.hasAttribute('href') ? 'link' : null,
                            'input': type === 'checkbox' ? 'checkbox' : type === 'radio' ? 'radio' : type === 'button' ? 'button' : 'textbox',
                            'textarea': 'textbox', 'select': 'combobox', 'img': 'img',
                            'h1': 'heading', 'h2': 'heading', 'h3': 'heading',
                            'h4': 'heading', 'h5': 'heading', 'h6': 'heading',
                            'nav': 'navigation', 'main': 'main', 'form': 'form',
                            'ul': 'list', 'ol': 'list', 'li': 'listitem'
                        };
                        return roles[tag] || null;
                    }

                    function getAccessibleName(el) {
                        // Priority: explicit labels over content
                        const explicitLabel = el.getAttribute('aria-label') ||
                                            el.getAttribute('title') ||
                                            el.getAttribute('alt') ||
                                            el.getAttribute('placeholder') ||
                                            (el.labels?.[0]?.textContent?.trim());

                        if (explicitLabel) return explicitLabel.substring(0, 100);

                        // For buttons/links, use direct text only (not nested content)
                        const tag = el.tagName.toLowerCase();
                        if (tag === 'button' || (tag === 'a' && el.hasAttribute('href'))) {
                            // Get only direct text nodes, not deeply nested content
                            let text = '';
                            for (let node of el.childNodes) {
                                if (node.nodeType === Node.TEXT_NODE) {
                                    text += node.textContent;
                                }
                            }
                            return text.trim().substring(0, 100);
                        }

                        // For headings, get text content
                        if (['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) {
                            return el.textContent?.trim().substring(0, 100) || '';
                        }

                        return '';
                    }

                    function getAccessibleValue(el) {
                        const tag = el.tagName.toLowerCase();
                        if (tag === 'input' || tag === 'textarea') return el.value || '';
                        if (tag === 'select') return el.options[el.selectedIndex]?.text || '';
                        return '';
                    }

                    function getAccessibleState(el) {
                        const state = {};
                        if (el.disabled || el.getAttribute('aria-disabled') === 'true') state.disabled = true;
                        if (el.type === 'checkbox' || el.type === 'radio') state.checked = el.checked;
                        if (el.hasAttribute('aria-expanded')) state.expanded = el.getAttribute('aria-expanded') === 'true';
                        return state;
                    }

                    return getAccessibilityInfo(document.body, 0);
                }
            """, max_depth)

            # Simplify tree structure for token efficiency
            if tree:
                simplified = self._simplify_accessibility_tree(tree, max_depth=max_depth)
                return simplified
            else:
                return {"role": "WebArea", "name": "Page", "children": []}
        except Exception as e:
            # Return empty tree if accessibility snapshot fails
            import traceback
            print(f"[ERROR] get_accessibility_tree failed: {e}")
            print(traceback.format_exc())
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
                    key_text = action.params["text"]

                    # Helper function to press a single key or key combo
                    def press_single_key_or_combo(key_str: str):
                        """Press a single key or key combination like 'Ctrl+Home'."""
                        key_str = key_str.strip()
                        if not key_str:
                            return

                        if "+" in key_str:
                            # Key combination (e.g., "Ctrl+Home", "Shift+Tab")
                            parts = [p.strip().lower() for p in key_str.split("+")]
                            modifiers = []
                            main_key = parts[-1]

                            for part in parts[:-1]:
                                if part in ["ctrl", "control"]:
                                    modifiers.append("Control")
                                elif part in ["shift"]:
                                    modifiers.append("Shift")
                                elif part in ["alt"]:
                                    modifiers.append("Alt")
                                elif part in ["meta", "cmd", "command"]:
                                    modifiers.append("Meta")

                            # Map the main key
                            main_key = self._map_key(main_key)

                            # Press modifiers down
                            for mod in modifiers:
                                self.page.keyboard.down(mod)

                            # Press main key
                            self.page.keyboard.press(main_key)

                            # Release modifiers
                            for mod in reversed(modifiers):
                                self.page.keyboard.up(mod)
                        else:
                            # Single key press
                            self.page.keyboard.press(self._map_key(key_str))

                    # Handle space-separated keys (could be single keys, combos, or mix)
                    if " " in key_text:
                        # Multiple keys/combos (e.g., "down down down", "Tab Return", "Ctrl+Home Ctrl+End")
                        keys = key_text.split()
                        for key in keys:
                            press_single_key_or_combo(key)
                            time.sleep(0.1)  # Small delay between key presses
                    else:
                        # Single key or combo
                        press_single_key_or_combo(key_text)

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

                # Move mouse to position first
                self.page.mouse.move(x, y)

                # Try to scroll the element at these coordinates, not just the window
                # This JavaScript finds the scrollable element at the coordinates and scrolls it
                scroll_result = self.page.evaluate(f"""
                    (function() {{
                        // Get the element at the coordinates
                        const element = document.elementFromPoint({x}, {y});
                        if (!element) {{
                            window.scrollBy({scroll_x}, {scroll_y});
                            return {{"scrolled": "window", "element": null}};
                        }}

                        // Find the nearest scrollable ancestor (including the element itself)
                        let scrollableElement = element;
                        while (scrollableElement && scrollableElement !== document.documentElement) {{
                            const style = window.getComputedStyle(scrollableElement);
                            const overflowY = style.overflowY;
                            const overflowX = style.overflowX;

                            // Check if element is scrollable
                            const isScrollableY = (overflowY === 'scroll' || overflowY === 'auto') &&
                                                scrollableElement.scrollHeight > scrollableElement.clientHeight;
                            const isScrollableX = (overflowX === 'scroll' || overflowX === 'auto') &&
                                                scrollableElement.scrollWidth > scrollableElement.clientWidth;

                            if (isScrollableY || isScrollableX) {{
                                // Found scrollable element - scroll it
                                scrollableElement.scrollBy({scroll_x}, {scroll_y});
                                return {{
                                    "scrolled": "element",
                                    "element": scrollableElement.tagName,
                                    "class": scrollableElement.className,
                                    "id": scrollableElement.id
                                }};
                            }}

                            scrollableElement = scrollableElement.parentElement;
                        }}

                        // If no scrollable ancestor found, scroll the window
                        window.scrollBy({scroll_x}, {scroll_y});
                        return {{"scrolled": "window", "element": null}};
                    }})()
                """)

                time.sleep(0.5)
                return {
                    "success": True,
                    "action": "scroll",
                    "x": x,
                    "y": y,
                    "scroll_result": scroll_result
                }

            elif action.type == ActionType.WAIT:
                time.sleep(2)
                return {"success": True, "action": "wait"}

            elif action.type == ActionType.MOUSE_MOVE:
                x, y = self._get_coordinates(action.params)
                self.page.mouse.move(x, y)
                time.sleep(0.2)
                return {"success": True, "action": "mouse_move", "x": x, "y": y}

            elif action.type == ActionType.BROWSER_FIND:
                # Use browser's native find (Ctrl+F) to navigate to content
                # Accept both "search_term" (correct) and "text" (model often uses this by mistake)
                search_term = action.params.get("search_term") or action.params.get("text", "")
                close_after = action.params.get("close_after", True)

                if not search_term:
                    return {"success": False, "error": "search_term (or text) is required for browser_find. Provide the exact text to find on page."}

                # Open browser find dialog with Ctrl+F
                self.page.keyboard.press("Control+f")
                time.sleep(0.5)  # Wait for find dialog to appear

                # Type the search term
                self.page.keyboard.type(search_term)
                time.sleep(0.5)  # Wait for browser to find and highlight

                # Check if any matches were found by looking at the page
                # Most browsers will highlight matches and scroll to the first one

                # Optionally close the find dialog
                if close_after:
                    self.page.keyboard.press("Escape")
                    time.sleep(0.3)

                return {
                    "success": True,
                    "action": "browser_find",
                    "search_term": search_term,
                    "message": f"Used browser find for '{search_term}'. Browser scrolled to and highlighted matches."
                }

            else:
                return {"success": False, "error": f"Unknown action type: {action.type}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_page_text(self) -> str:
        """Extract all visible text from the page.

        Returns:
            String containing all visible text content
        """
        if not self.page:
            return ""

        try:
            # Extract all visible text content from the page body
            text = self.page.evaluate("""
                () => {
                    // Get all text content, removing script/style tags
                    const body = document.body;
                    const elements = body.querySelectorAll('*');
                    const textParts = [];

                    for (const el of elements) {
                        // Skip script, style, and hidden elements
                        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'NOSCRIPT') {
                            continue;
                        }

                        // Get direct text nodes only (not from children)
                        for (const node of el.childNodes) {
                            if (node.nodeType === Node.TEXT_NODE) {
                                const text = node.textContent.trim();
                                if (text) {
                                    textParts.push(text);
                                }
                            }
                        }
                    }

                    return textParts.join('\\n');
                }
            """)
            return text
        except Exception as e:
            import traceback
            print(f"[ERROR] get_page_text failed: {e}")
            print(traceback.format_exc())
            return f"Error extracting page text: {str(e)}"

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
            # Claude format (singular)
            x, y = params["coordinate"][0], params["coordinate"][1]

            # Warn if coordinates are suspiciously at origin (common AI error)
            if x == 0 and y == 0:
                print(f"⚠️  WARNING: Coordinates are (0, 0) - AI may not be using screenshot for positioning")
                print(f"   Action params: {params}")

            return x, y
        elif "coordinates" in params:
            # Some models use plural "coordinates"
            x, y = params["coordinates"][0], params["coordinates"][1]

            # Warn if coordinates are at origin
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
        # Normalize key to lowercase for case-insensitive matching
        key_lower = key.lower()

        # Common key mappings (case-insensitive)
        key_map = {
            "return": "Enter",
            "enter": "Enter",
            "space": " ",
            " ": " ",
            "tab": "Tab",
            "backspace": "Backspace",
            "delete": "Delete",
            "escape": "Escape",
            "esc": "Escape",
            "arrowup": "ArrowUp",
            "arrowdown": "ArrowDown",
            "arrowleft": "ArrowLeft",
            "arrowright": "ArrowRight",
            "pagedown": "PageDown",
            "page_down": "PageDown",
            "pageup": "PageUp",
            "page_up": "PageUp",
            "home": "Home",
            "end": "End",
            "insert": "Insert",
            "f1": "F1",
            "f2": "F2",
            "f3": "F3",
            "f4": "F4",
            "f5": "F5",
            "f6": "F6",
            "f7": "F7",
            "f8": "F8",
            "f9": "F9",
            "f10": "F10",
            "f11": "F11",
            "f12": "F12",
        }

        # Try exact match first (preserves case for letters)
        if key in key_map.values():
            return key

        # Try case-insensitive match
        mapped = key_map.get(key_lower)
        if mapped:
            return mapped

        # Return original key if no mapping found (for letters, numbers, etc.)
        return key

    # ============================================================================
    # DOM Manipulation Methods (Selector-based Actions)
    # ============================================================================

    def click_selector(self, selector: str) -> dict:
        """Click element by CSS selector.

        Args:
            selector: CSS selector string

        Returns:
            Dictionary with action result
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            # First check if element exists at all
            element_count = self.page.evaluate(f"""
                document.querySelectorAll('{selector}').length
            """)

            if element_count == 0:
                return {
                    "success": False,
                    "action": "click_selector",
                    "selector": selector,
                    "error": f"Selector '{selector}' not found on page. Use find_selectors to get valid selector."
                }

            if element_count > 1:
                print(f"[WARNING] Selector '{selector}' matches {element_count} elements. Clicking first match.")

            # Try normal click first (with actionability checks)
            try:
                self.page.click(selector, timeout=10000)
                time.sleep(0.5)
                return {
                    "success": True,
                    "action": "click_selector",
                    "selector": selector
                }
            except Exception as click_error:
                # If normal click fails due to element interception, try force click
                if "intercepts pointer events" in str(click_error) or "Timeout" in str(click_error):
                    print(f"[INFO] Normal click failed (element obstructed), retrying with force=True")
                    try:
                        self.page.click(selector, timeout=5000, force=True)
                        time.sleep(0.5)
                        return {
                            "success": True,
                            "action": "click_selector",
                            "selector": selector,
                            "note": "Clicked with force=True to bypass obstructing elements"
                        }
                    except Exception as force_error:
                        # Force click also failed, raise original error
                        print(f"[ERROR] Force click also failed: {force_error}")
                        raise click_error
                else:
                    # Other error, re-raise
                    raise click_error

        except Exception as e:
            import traceback
            print(f"[ERROR] click_selector failed for '{selector}': {e}")
            print(traceback.format_exc())

            # Provide helpful error message
            error_msg = str(e)
            if "Timeout" in error_msg or "intercepts pointer events" in error_msg:
                error_msg = f"Element '{selector}' exists but not clickable (may be obstructed by popups/modals). Try closing overlays first or use coordinates."
            elif "querySelectorAll" in error_msg:
                error_msg = f"Invalid CSS selector '{selector}'. Use find_selectors to get valid selector."

            return {
                "success": False,
                "action": "click_selector",
                "selector": selector,
                "error": error_msg
            }

    def fill_selector(self, selector: str, text: str) -> dict:
        """Fill input element by CSS selector.

        Args:
            selector: CSS selector string
            text: Text to fill

        Returns:
            Dictionary with action result
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            # Check if element exists
            element_count = self.page.evaluate(f"""
                document.querySelectorAll('{selector}').length
            """)

            if element_count == 0:
                return {
                    "success": False,
                    "action": "fill_selector",
                    "selector": selector,
                    "error": f"Selector '{selector}' not found on page. Use find_selectors to get valid selector."
                }

            if element_count > 1:
                print(f"[WARNING] Selector '{selector}' matches {element_count} elements. Filling first match.")

            # Increase timeout to 10 seconds
            self.page.fill(selector, text, timeout=10000)
            time.sleep(0.3)
            return {
                "success": True,
                "action": "fill_selector",
                "selector": selector,
                "text": text
            }
        except Exception as e:
            import traceback
            print(f"[ERROR] fill_selector failed for '{selector}': {e}")
            print(traceback.format_exc())

            # Provide helpful error message
            error_msg = str(e)
            if "Timeout" in error_msg:
                error_msg += f" | Element '{selector}' exists but not fillable within 10s. May be hidden, disabled, or not an input field. Try find_selectors to find better selector."
            elif "querySelectorAll" in error_msg:
                error_msg = f"Invalid CSS selector '{selector}'. Use find_selectors to get valid selector."

            return {
                "success": False,
                "action": "fill_selector",
                "selector": selector,
                "error": error_msg
            }

    def get_element_info(self, selector: str) -> dict:
        """Get element information without taking action.

        Args:
            selector: CSS selector string

        Returns:
            Dictionary with element information
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            result = self.page.evaluate("""
                (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return null;

                    const rect = el.getBoundingClientRect();
                    return {
                        exists: true,
                        visible: el.offsetParent !== null,
                        text: el.textContent || el.innerText || '',
                        value: el.value || '',
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        placeholder: el.placeholder || '',
                        disabled: el.disabled || false,
                        rect: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        }
                    };
                }
            """, selector)

            if result is None:
                return {
                    "success": False,
                    "exists": False,
                    "selector": selector,
                    "error": "Element not found"
                }

            return {
                "success": True,
                "selector": selector,
                **result
            }
        except Exception as e:
            return {
                "success": False,
                "selector": selector,
                "error": str(e)
            }

    def find_selectors_by_text(self, text: str, limit: int = 10) -> dict:
        """Find CSS selectors for elements containing specific text.

        Args:
            text: Text to search for
            limit: Maximum number of results to return

        Returns:
            Dictionary with list of selectors
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            results = self.page.evaluate(r"""
                ([text, limit]) => {
                    // Find all elements containing the text
                    const allElements = Array.from(document.querySelectorAll('*'));
                    const matches = [];

                    // Helper to get direct text content (excluding children)
                    const getDirectText = (el) => {
                        let text = '';
                        for (let node of el.childNodes) {
                            if (node.nodeType === Node.TEXT_NODE) {
                                text += node.textContent || '';
                            }
                        }
                        return text.trim();
                    };

                    // Helper to validate if a class name is CSS-safe
                    const isValidCSSClass = (className) => {
                        // CSS class names cannot contain: : [ ] ( ) & < > ! @ # $ % ^ * + = ~ ` " ' | \\ / ? ,
                        // Also skip Tailwind arbitrary variants like [&_svg] and pseudo-class variants like focus-visible:
                        return !/[:[\]()&<>!@#$%^*+=~`"'|\\/?]/.test(className);
                    };

                    // Helper to generate unique CSS selector
                    const generateSelector = (el) => {
                        let selector = el.tagName.toLowerCase();

                        if (el.id) {
                            // ID is best - short and unique
                            return '#' + CSS.escape(el.id);
                        } else if (el.className && typeof el.className === 'string') {
                            const classes = el.className.split(' ')
                                .map(c => c.trim())
                                .filter(c => c && isValidCSSClass(c));

                            if (classes.length > 0) {
                                // Use 3-5 valid classes for better specificity
                                // Prioritize semantic/meaningful classes over pure utility classes
                                const semanticClasses = classes.filter(c =>
                                    !c.startsWith('h-') &&
                                    !c.startsWith('w-') &&
                                    !c.startsWith('p-') &&
                                    !c.startsWith('m-') &&
                                    !c.startsWith('text-') &&
                                    !c.startsWith('bg-') &&
                                    !c.startsWith('flex') &&
                                    !c.startsWith('grid') &&
                                    !c.startsWith('gap-') &&
                                    !c.startsWith('space-') &&
                                    !c.startsWith('justify-') &&
                                    !c.startsWith('items-')
                                );

                                // Use semantic classes if available (up to 3), otherwise use first 5 classes
                                const selectedClasses = semanticClasses.length > 0 ?
                                    semanticClasses.slice(0, 3) : classes.slice(0, 5);

                                if (selectedClasses.length > 0) {
                                    selector += '.' + selectedClasses.map(c => CSS.escape(c)).join('.');
                                }
                            }
                        }

                        return selector;
                    };

                    for (const el of allElements) {
                        // Skip script, style, and non-visible elements
                        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;
                        if (el.offsetParent === null && el.tagName !== 'BODY') continue;

                        const fullText = (el.textContent || el.innerText || '').trim();
                        const directText = getDirectText(el);
                        const value = el.value || '';
                        const placeholder = el.placeholder || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';

                        // Check if text matches (prefer direct text matches)
                        const hasDirectMatch = directText.includes(text);
                        const hasFullMatch = fullText.includes(text);
                        const hasValueMatch = value.includes(text);
                        const hasPlaceholderMatch = placeholder.includes(text);
                        const hasAriaMatch = ariaLabel.includes(text);

                        if (hasDirectMatch || hasFullMatch || hasValueMatch || hasPlaceholderMatch || hasAriaMatch) {
                            // Calculate match quality score
                            let score = 0;

                            // Strongly prefer exact text matches
                            if (hasDirectMatch) {
                                if (directText === text) {
                                    score += 200; // BEST: exact match in direct text
                                } else {
                                    score += 100; // Good: substring match in direct text
                                }
                            } else if (hasFullMatch) {
                                if (fullText === text) {
                                    score += 150; // Exact match in full text
                                } else {
                                    score += 50; // Substring match in inherited text
                                }
                            }

                            if (hasValueMatch) {
                                score += (value === text) ? 160 : 80;
                            }
                            if (hasPlaceholderMatch) {
                                score += (placeholder === text) ? 140 : 70;
                            }
                            if (hasAriaMatch) {
                                score += (ariaLabel === text) ? 120 : 60;
                            }

                            // Prefer interactive elements
                            const interactiveTags = ['button', 'a', 'input', 'select', 'textarea'];
                            if (interactiveTags.includes(el.tagName.toLowerCase())) {
                                score += 30;
                            }

                            // Penalize generic containers
                            const containerTags = ['div', 'span', 'section', 'main', 'article'];
                            if (containerTags.includes(el.tagName.toLowerCase())) {
                                score -= 20;
                            }

                            // Get position for uniqueness
                            const rect = el.getBoundingClientRect();

                            // Store matched text for verification
                            const matchedText = hasDirectMatch ? directText : (hasFullMatch ? fullText : (hasValueMatch ? value : (hasPlaceholderMatch ? placeholder : ariaLabel)));

                            matches.push({
                                selector: generateSelector(el),
                                tag: el.tagName.toLowerCase(),
                                matchedText: matchedText.substring(0, 100),
                                text: fullText.substring(0, 100),
                                directText: directText.substring(0, 100),
                                value: value.substring(0, 50),
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                score: score,
                                isInteractive: interactiveTags.includes(el.tagName.toLowerCase())
                            });
                        }
                    }

                    // Sort by score (highest first) and return top matches
                    matches.sort((a, b) => b.score - a.score);
                    return matches.slice(0, limit);
                }
            """, [text, limit])

            return {
                "success": True,
                "text": text,
                "count": len(results),
                "matches": results
            }
        except Exception as e:
            return {
                "success": False,
                "text": text,
                "error": str(e)
            }

    def evaluate_js(self, script: str) -> dict:
        """Execute JavaScript in the page context.

        Args:
            script: JavaScript code to execute

        Returns:
            Dictionary with execution result
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            result = self.page.evaluate(script)
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
