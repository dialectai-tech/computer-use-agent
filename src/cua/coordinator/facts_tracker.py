"""Simple critical facts tracking for maintaining task state."""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class CriticalFactsTracker:
    """Tracks critical information discovered during task execution.

    This is a simplified approach using pattern matching instead of
    complex extraction logic. Tracks:
    - Codes discovered (verification codes, passwords, etc.)
    - Selectors found (CSS selectors, XPath, button labels)
    - Completed steps/actions
    """

    codes: List[str] = field(default_factory=list)
    selectors: Dict[str, List[str]] = field(default_factory=dict)
    completed_steps: List[str] = field(default_factory=list)
    form_data: Dict[str, str] = field(default_factory=dict)

    # Pattern definitions
    CODE_PATTERNS = [
        r'\b[A-Z0-9]{4,8}\b',  # Uppercase codes like ABC123, XY789
        r'\b\d{4,6}\b',  # Numeric codes like 1234, 123456
    ]

    SELECTOR_PATTERNS = {
        'css': r'[#.][a-zA-Z0-9_-]+',
        'xpath': r'//[a-zA-Z0-9/@\[\]_-]+',
        'button': r'button.*?[\'"]([^"\']+)[\'"]',
    }

    def extract_from_text(self, text: str) -> None:
        """Extract facts from text using pattern matching.

        Args:
            text: Text to extract from (action result, page content, etc.)
        """
        if not text:
            return

        # Extract codes
        for pattern in self.CODE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                if match not in self.codes:
                    self.codes.append(match)

        # Extract selectors
        for selector_type, pattern in self.SELECTOR_PATTERNS.items():
            matches = re.findall(pattern, text)
            if selector_type not in self.selectors:
                self.selectors[selector_type] = []
            for match in matches:
                if match not in self.selectors[selector_type]:
                    self.selectors[selector_type].append(match)

    def add_completed_step(self, step: str) -> None:
        """Mark a step as completed.

        Args:
            step: Description of completed step
        """
        if step and step not in self.completed_steps:
            self.completed_steps.append(step)

    def add_form_data(self, field: str, value: str) -> None:
        """Store form field data.

        Args:
            field: Field name/id
            value: Field value
        """
        self.form_data[field] = value

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of tracked facts.

        Returns:
            Dictionary with all tracked facts
        """
        return {
            'codes': self.codes,
            'selectors': self.selectors,
            'completed_steps': self.completed_steps,
            'form_data': self.form_data,
        }

    def to_context_string(self) -> str:
        """Convert facts to string for LLM context.

        Returns:
            Formatted string of critical facts
        """
        lines = []

        if self.codes:
            lines.append(f"Discovered codes: {', '.join(self.codes)}")

        if self.completed_steps:
            lines.append(f"Completed steps: {', '.join(self.completed_steps)}")

        if self.form_data:
            lines.append("Form data:")
            for field, value in self.form_data.items():
                lines.append(f"  - {field}: {value}")

        return '\n'.join(lines) if lines else "No critical facts tracked yet."
