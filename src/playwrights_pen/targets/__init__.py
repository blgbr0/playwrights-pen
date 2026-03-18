"""Test targets package for multi-platform testing support."""

from .base import TestTarget, TargetType, TargetConfig
from .web import WebTarget, WebTargetConfig
from .electron import ElectronTarget, ElectronTargetConfig

__all__ = [
    "TestTarget",
    "TargetType",
    "TargetConfig",
    "WebTarget",
    "WebTargetConfig",
    "ElectronTarget",
    "ElectronTargetConfig",
]
