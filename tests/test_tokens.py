"""Tests for design/tokens.py — Clinical Slate design system."""

from __future__ import annotations

import re

import pytest

from bacterioscope.design.tokens import (
    CATEGORY_TOKENS,
    contrast_ratio,
    css_variables,
    is_valid_hex,
    palette,
)


class TestPalette:
    def test_dark_and_light_have_same_keys(self) -> None:
        assert set(palette("dark").keys()) == set(palette("light").keys())

    def test_all_values_are_valid_hex(self) -> None:
        for mode in ("dark", "light"):
            for key, value in palette(mode).items():
                assert is_valid_hex(value), f"{mode}.{key} = {value!r} is not valid hex"

    def test_no_duplicate_values_within_semantic_boundary(self) -> None:
        for mode in ("dark", "light"):
            p = palette(mode)
            non_cat = {k: v for k, v in p.items() if k not in CATEGORY_TOKENS}
            cat = {k: v for k, v in p.items() if k in CATEGORY_TOKENS}
            for k_cat, v_cat in cat.items():
                for k_other, v_other in non_cat.items():
                    assert v_cat != v_other, (
                        f"{mode}: category token {k_cat} shares value {v_cat} "
                        f"with non-category token {k_other}"
                    )

    def test_returns_copy(self) -> None:
        p = palette("dark")
        p["bg_base"] = "#000000"
        assert palette("dark")["bg_base"] != "#000000"


class TestContrastWCAG:
    def test_text_primary_on_bg_base_dark_exceeds_4_5(self) -> None:
        p = palette("dark")
        ratio = contrast_ratio(p["text_primary"], p["bg_base"])
        assert ratio >= 4.5, f"Dark text_primary / bg_base contrast = {ratio:.2f} < 4.5"

    def test_text_primary_on_bg_base_light_exceeds_4_5(self) -> None:
        p = palette("light")
        ratio = contrast_ratio(p["text_primary"], p["bg_base"])
        assert ratio >= 4.5, f"Light text_primary / bg_base contrast = {ratio:.2f} < 4.5"

    def test_cat_susceptible_on_surface_dark_exceeds_3(self) -> None:
        p = palette("dark")
        ratio = contrast_ratio(p["cat_susceptible"], p["bg_surface"])
        assert ratio >= 3.0, f"Dark cat_susceptible / bg_surface = {ratio:.2f} < 3.0"

    def test_cat_intermediate_on_surface_dark_exceeds_3(self) -> None:
        p = palette("dark")
        ratio = contrast_ratio(p["cat_intermediate"], p["bg_surface"])
        assert ratio >= 3.0, f"Dark cat_intermediate / bg_surface = {ratio:.2f} < 3.0"

    def test_cat_resistant_on_surface_dark_exceeds_3(self) -> None:
        p = palette("dark")
        ratio = contrast_ratio(p["cat_resistant"], p["bg_surface"])
        assert ratio >= 3.0, f"Dark cat_resistant / bg_surface = {ratio:.2f} < 3.0"

    def test_cat_susceptible_on_surface_light_exceeds_3(self) -> None:
        p = palette("light")
        ratio = contrast_ratio(p["cat_susceptible"], p["bg_surface"])
        assert ratio >= 3.0, f"Light cat_susceptible / bg_surface = {ratio:.2f} < 3.0"

    def test_contrast_ratio_white_black(self) -> None:
        assert abs(contrast_ratio("#FFFFFF", "#000000") - 21.0) < 0.1

    def test_contrast_ratio_identical_colors(self) -> None:
        assert contrast_ratio("#555555", "#555555") == pytest.approx(1.0)


class TestCssVariables:
    def test_contains_root_block(self) -> None:
        css = css_variables("dark")
        assert ":root {" in css
        assert "}" in css

    def test_all_palette_tokens_present(self) -> None:
        css = css_variables("dark")
        for key in palette("dark"):
            var = f"--bs-{key.replace('_', '-')}:"
            assert var in css, f"CSS variable {var} missing from dark mode output"

    def test_light_mode_tokens_present(self) -> None:
        css = css_variables("light")
        for key in palette("light"):
            var = f"--bs-{key.replace('_', '-')}:"
            assert var in css

    def test_font_variables_present(self) -> None:
        css = css_variables("dark")
        assert "--bs-font-sans:" in css
        assert "--bs-font-mono:" in css

    def test_dark_and_light_same_variable_names(self) -> None:
        def extract_names(css: str) -> set[str]:
            return set(re.findall(r"--bs-[\w-]+", css))
        assert extract_names(css_variables("dark")) == extract_names(css_variables("light"))


class TestIsValidHex:
    def test_valid_lowercase(self) -> None:
        assert is_valid_hex("#aabbcc")

    def test_valid_uppercase(self) -> None:
        assert is_valid_hex("#AABBCC")

    def test_invalid_short(self) -> None:
        assert not is_valid_hex("#abc")

    def test_invalid_no_hash(self) -> None:
        assert not is_valid_hex("aabbcc")

    def test_invalid_out_of_range(self) -> None:
        assert not is_valid_hex("#GGHHII")
