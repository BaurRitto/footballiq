"""Deterministic analytics for fictional synthetic football events."""

from .match import PressureConfig, analyze_match, detect_pressure, validate_match

__all__ = ["PressureConfig", "analyze_match", "detect_pressure", "validate_match"]
