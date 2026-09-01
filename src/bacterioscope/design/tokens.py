"""Clinical Slate design system — single source of truth for color, typography and spacing.

Rules enforced by this module:
- Category colors (cat_susceptible, cat_intermediate, cat_resistant) are reserved
  exclusively for S / I / R classification results. No other element uses them.
- Quality indicators use quality_warning, never the resistant red.
- Every category representation includes the letter S, I or R — color alone is
  insufficient.
- No color literal may appear outside this module.
"""

from __future__ import annotations

import re
from typing import Literal

Mode = Literal["dark", "light"]

# ---------------------------------------------------------------------------
# Palette — Clinical Slate
# ---------------------------------------------------------------------------

_DARK: dict[str, str] = {
    "bg_base": "#0E1418",
    "bg_surface": "#161D22",
    "bg_raised": "#1E272D",
    "border": "#2C3940",
    "text_primary": "#E8EDEF",
    "text_secondary": "#93A3AA",
    "cat_susceptible": "#3E8E6B",
    "cat_intermediate": "#C9902F",
    "cat_resistant": "#C0574F",
    "signal": "#4B87B5",
    "quality_warning": "#8A7A3F",
}

_LIGHT: dict[str, str] = {
    "bg_base": "#F7F9F9",
    "bg_surface": "#FFFFFF",
    "bg_raised": "#EEF3F3",
    "border": "#D6DEE0",
    "text_primary": "#101619",
    "text_secondary": "#5B6B72",
    "cat_susceptible": "#2F6F5A",
    "cat_intermediate": "#A87418",
    "cat_resistant": "#A8423B",
    "signal": "#2F6690",
    "quality_warning": "#7A6A2F",
}

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

FONT_INTERFACE = "IBM Plex Sans"
FONT_MONO = "IBM Plex Mono"
FONT_STACK_SANS = f'"{FONT_INTERFACE}", "Segoe UI", system-ui, sans-serif'
FONT_STACK_MONO = f'"{FONT_MONO}", "Cascadia Code", "Consolas", monospace'

TYPE_SCALE_PX: tuple[int, ...] = (12, 14, 15, 18, 22, 28)
BODY_SIZE_PX: int = 15
BODY_LINE_HEIGHT: float = 1.5

# ---------------------------------------------------------------------------
# Spacing (8 px grid)
# ---------------------------------------------------------------------------

SPACE: dict[str, int] = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "2xl": 32,
    "3xl": 48,
}

RADIUS_CONTAINER: int = 6
RADIUS_CONTROL: int = 4


# ---------------------------------------------------------------------------
# Semantic rules (enforced via assertion in tests)
# ---------------------------------------------------------------------------

CATEGORY_TOKENS: frozenset[str] = frozenset(
    {"cat_susceptible", "cat_intermediate", "cat_resistant"}
)

CATEGORY_MAP: dict[str, str] = {
    "S": "cat_susceptible",
    "I": "cat_intermediate",
    "R": "cat_resistant",
}


# ---------------------------------------------------------------------------
# WCAG contrast helpers
# ---------------------------------------------------------------------------

def _hex_to_srgb(hex_color: str) -> tuple[float, float, float]:
    """Convert a 6-digit hex color to linear sRGB components.

    Args:
        hex_color: A 6-digit hex string, with or without leading '#'.

    Returns:
        Tuple of (r, g, b) in [0, 1] sRGB range.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r / 255.0, g / 255.0, b / 255.0


def _relative_luminance(hex_color: str) -> float:
    """Compute WCAG 2.1 relative luminance for a hex color.

    Args:
        hex_color: A 6-digit hex string.

    Returns:
        Relative luminance in [0, 1].
    """
    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _hex_to_srgb(hex_color)
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two hex colors.

    Args:
        fg: Foreground color hex string.
        bg: Background color hex string.

    Returns:
        Contrast ratio in [1, 21].
    """
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def palette(mode: Mode) -> dict[str, str]:
    """Return the complete color token dictionary for the given mode.

    Args:
        mode: Either 'dark' or 'light'.

    Returns:
        Dictionary mapping token names to hex color strings.
    """
    return dict(_DARK if mode == "dark" else _LIGHT)


def category_color(category: str, mode: Mode) -> str:
    """Return the hex color for a classification category.

    Args:
        category: One of 'S', 'I', 'R'.
        mode: Either 'dark' or 'light'.

    Returns:
        Hex color string for the given category.

    Raises:
        KeyError: When category is not one of S, I, R.
    """
    token = CATEGORY_MAP[category]
    return palette(mode)[token]


def css_variables(mode: Mode) -> str:
    """Emit a CSS :root block with all --bs-* custom properties.

    Args:
        mode: Either 'dark' or 'light'.

    Returns:
        CSS string ready to embed in a <style> tag.
    """
    tokens = palette(mode)
    lines = [":root {"]
    for name, value in tokens.items():
        lines.append(f"  --bs-{name.replace('_', '-')}: {value};")
    lines.append(f"  --bs-font-sans: {FONT_STACK_SANS};")
    lines.append(f"  --bs-font-mono: {FONT_STACK_MONO};")
    lines.append(f"  --bs-body-size: {BODY_SIZE_PX}px;")
    lines.append(f"  --bs-body-lh: {BODY_LINE_HEIGHT};")
    lines.append(f"  --bs-radius-container: {RADIUS_CONTAINER}px;")
    lines.append(f"  --bs-radius-control: {RADIUS_CONTROL}px;")
    lines.append("}")
    return "\n".join(lines)


def is_valid_hex(color: str) -> bool:
    """Return True if color is a valid 6-digit hex color string.

    Args:
        color: String to validate.

    Returns:
        True if the string matches #RRGGBB format.
    """
    return bool(re.match(r"^#[0-9A-Fa-f]{6}$", color))
