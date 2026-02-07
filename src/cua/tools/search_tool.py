"""Search tool for finding content in page text and accessibility tree."""

import re
import json
from typing import Dict, List, Any, Optional


class SearchTool:
    """Tool for searching page content before taking actions."""

    def __init__(self, page_text: str, accessibility_tree: Optional[dict] = None):
        """Initialize search tool with page content.

        Args:
            page_text: Extracted visible text from the page
            accessibility_tree: Accessibility tree structure
        """
        self.page_text = page_text
        self.accessibility_tree = accessibility_tree or {}
        self._lines = page_text.split('\n') if page_text else []

    def search(self, query: str, search_type: str = "text") -> Dict[str, Any]:
        """Search for content in page text and/or accessibility tree.

        Args:
            query: What to search for (can be regex pattern)
            search_type: Type of search - "text", "tree", or "both"

        Returns:
            Dictionary with search results including matches and locations
        """
        results = {
            "query": query,
            "found": False,
            "text_matches": [],
            "tree_matches": [],
            "summary": ""
        }

        # Search in page text
        if search_type in ["text", "both"]:
            text_matches = self._search_text(query)
            if text_matches:
                results["found"] = True
                results["text_matches"] = text_matches

        # Search in accessibility tree
        if search_type in ["tree", "both"]:
            tree_matches = self._search_tree(query)
            if tree_matches:
                results["found"] = True
                results["tree_matches"] = tree_matches

        # Generate summary
        results["summary"] = self._generate_summary(results)

        return results

    def _search_text(self, query: str) -> List[Dict[str, Any]]:
        """Search in page text.

        Args:
            query: Search query (supports regex)

        Returns:
            List of matches with line numbers and context
        """
        matches = []

        try:
            # Try as regex first
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            # If not valid regex, escape and search as literal
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        for line_num, line in enumerate(self._lines, start=1):
            if pattern.search(line):
                matches.append({
                    "line_number": line_num,
                    "content": line.strip(),
                    "match_type": "exact" if query.lower() in line.lower() else "pattern"
                })

        return matches

    def _search_tree(self, query: str, node: Optional[dict] = None, path: str = "") -> List[Dict[str, Any]]:
        """Search in accessibility tree recursively.

        Args:
            query: Search query
            node: Current node (None for root)
            path: Current path in tree

        Returns:
            List of matches with tree paths and element info
        """
        if node is None:
            node = self.accessibility_tree

        if not node or isinstance(node, str):
            return []

        matches = []

        # Check current node
        node_text = ""
        if "name" in node:
            node_text += node.get("name", "")
        if "value" in node:
            node_text += " " + str(node.get("value", ""))
        if "description" in node:
            node_text += " " + node.get("description", "")

        if query.lower() in node_text.lower():
            match = {
                "path": path,
                "role": node.get("role", "unknown"),
                "name": node.get("name", ""),
                "value": node.get("value", ""),
                "element_info": {
                    "role": node.get("role"),
                    "name": node.get("name"),
                    "value": node.get("value"),
                    "disabled": node.get("disabled", False),
                    "checked": node.get("checked"),
                    "modal": node.get("modal", False)
                }
            }
            matches.append(match)

        # Recurse into children
        if "children" in node and isinstance(node["children"], list):
            for i, child in enumerate(node["children"]):
                child_path = f"{path}/child[{i}]" if path else f"child[{i}]"
                matches.extend(self._search_tree(query, child, child_path))

        return matches

    def _generate_summary(self, results: Dict[str, Any]) -> str:
        """Generate human-readable summary of search results.

        Args:
            results: Search results dictionary

        Returns:
            Summary string
        """
        if not results["found"]:
            return f"❌ No matches found for '{results['query']}'"

        parts = []

        # Text matches summary
        if results["text_matches"]:
            count = len(results["text_matches"])
            lines = [str(m["line_number"]) for m in results["text_matches"][:5]]
            lines_str = ", ".join(lines)
            if count > 5:
                lines_str += f" and {count - 5} more"

            parts.append(f"📄 Found {count} text match(es) at line(s): {lines_str}")

            # Include first match content
            first_match = results["text_matches"][0]
            parts.append(f"   First match (line {first_match['line_number']}): \"{first_match['content'][:100]}\"")

        # Tree matches summary
        if results["tree_matches"]:
            count = len(results["tree_matches"])
            parts.append(f"🌲 Found {count} element(s) in accessibility tree:")

            # Include first few matches
            for i, match in enumerate(results["tree_matches"][:3]):
                role = match["role"]
                name = match["name"]
                parts.append(f"   {i+1}. {role}: \"{name}\"")

            if count > 3:
                parts.append(f"   ... and {count - 3} more")

        return "\n".join(parts)

    def find_codes(self, pattern: str = r'\b[A-Z0-9]{6}\b') -> Dict[str, Any]:
        """Convenience method to find 6-character codes.

        Args:
            pattern: Regex pattern for codes (default: 6 alphanumeric chars)

        Returns:
            Search results for codes
        """
        results = self.search(pattern, search_type="text")

        # Extract actual code values
        if results["found"]:
            codes = []
            for match in results["text_matches"]:
                # Extract the actual code from the line
                line = match["content"]
                matches = re.findall(pattern, line)
                codes.extend(matches)

            results["codes_found"] = list(set(codes))  # Unique codes
            results["summary"] = f"🔍 Found {len(results['codes_found'])} unique code(s): {', '.join(results['codes_found'])}\n" + results["summary"]

        return results

    def find_buttons(self, button_text: str = None) -> Dict[str, Any]:
        """Convenience method to find buttons in the tree.

        Args:
            button_text: Optional text to match button name (None for all buttons)

        Returns:
            Search results for buttons
        """
        # Search for button role
        if button_text:
            # Search for specific button
            return self.search(button_text, search_type="tree")
        else:
            # Find all buttons by searching tree for role=button
            matches = self._find_by_role("button")
            return {
                "query": "all buttons",
                "found": len(matches) > 0,
                "tree_matches": matches,
                "summary": f"Found {len(matches)} button(s)" if matches else "No buttons found"
            }

    def find_inputs(self, input_name: str = None) -> Dict[str, Any]:
        """Convenience method to find input fields.

        Args:
            input_name: Optional name to match (None for all inputs)

        Returns:
            Search results for inputs
        """
        if input_name:
            return self.search(input_name, search_type="tree")
        else:
            matches = self._find_by_role("textbox")
            return {
                "query": "all inputs",
                "found": len(matches) > 0,
                "tree_matches": matches,
                "summary": f"Found {len(matches)} input field(s)" if matches else "No input fields found"
            }

    def _find_by_role(self, role: str, node: Optional[dict] = None, path: str = "") -> List[Dict[str, Any]]:
        """Find all elements with specific role.

        Args:
            role: Role to search for
            node: Current node
            path: Current path

        Returns:
            List of matching elements
        """
        if node is None:
            node = self.accessibility_tree

        if not node or isinstance(node, str):
            return []

        matches = []

        # Check current node
        if node.get("role") == role:
            matches.append({
                "path": path,
                "role": node.get("role"),
                "name": node.get("name", ""),
                "value": node.get("value", ""),
                "element_info": {
                    "role": node.get("role"),
                    "name": node.get("name"),
                    "value": node.get("value"),
                    "disabled": node.get("disabled", False)
                }
            })

        # Recurse
        if "children" in node and isinstance(node["children"], list):
            for i, child in enumerate(node["children"]):
                child_path = f"{path}/child[{i}]" if path else f"child[{i}]"
                matches.extend(self._find_by_role(role, child, child_path))

        return matches
