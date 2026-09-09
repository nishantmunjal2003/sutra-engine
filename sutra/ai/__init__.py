"""
sutra.ai — Sūtra Press AI Assist Module
Provides opt-in AI tools for block classification, citation structuring,
and equation recognition per ai-addon.md.
"""
from .classifier import AIBlockClassifier
from .router import AIMultiRouter

__all__ = ["AIBlockClassifier", "AIMultiRouter"]
