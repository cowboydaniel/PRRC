from __future__ import annotations

import importlib.util

import pytest

from fieldops.gui import (
    COLOR_TOKENS,
    TYPOGRAPHY,
    component_styles,
    focus_ring_stylesheet,
)


def test_color_tokens_match_style_guide() -> None:
    expected_hex = {
        "primary": "#0C3D5B",
        "primary_light": "#145A80",
        "primary_contrast": "#E8F4FF",
        "secondary": "#1F6F43",
        "accent": "#F6A000",
        "success": "#3FA776",
        "danger": "#C4373B",
        "neutral_900": "#121417",
        "neutral_700": "#2D3035",
        "neutral_200": "#C9CFD6",
        "surface_light": "#F5F7FA",
        "surface_dark": "#1B1E22",
    }
    assert {name: token.hex for name, token in COLOR_TOKENS.items()} == expected_hex


def test_typography_tokens_cover_key_roles() -> None:
    assert TYPOGRAPHY["section_header"].size_pt == 20
    assert TYPOGRAPHY["navigation_label"].letter_case == "uppercase"
    assert pytest.approx(TYPOGRAPHY["navigation_label"].letter_spacing_em, rel=1e-6) == 0.08


def test_component_stylesheet_alignment() -> None:
    styles = component_styles()
    assert "NavigationRail" in styles.navigation_rail
    assert "border-bottom" in styles.mission_tab_bar
    assert "OfflineQueue" in styles.offline_queue_row
    assert "TelemetryCard" in styles.telemetry_card
    assert "ConflictResolution" in styles.conflict_dialog


def test_focus_ring_stylesheet_matches_spec() -> None:
    focus_css = focus_ring_stylesheet()
    assert "3px solid #7AC1FF" in focus_css
    assert "outline-offset: 2px" in focus_css


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is not None,
    reason="PySide6 available; palette creation should be covered in integration tests",
)
def test_build_palette_requires_pyside6() -> None:
    from fieldops.gui import build_palette

    with pytest.raises(RuntimeError):
        build_palette()
