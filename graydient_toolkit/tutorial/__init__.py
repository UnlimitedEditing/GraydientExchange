"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        Tutorial System                                       ║
║           Interactive Onboarding with Screen Highlighting                   ║
║                                                                             ║
║  Provides step-by-step tutorials with:                                      ║
║    • Screen region highlighting                                             ║
║    • Rich annotations with images/videos                                    ║
║    • Progress tracking                                                      ║
║    • Tutorial editor for creating custom tutorials                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from .engine import TutorialEngine, TutorialDefinition, TutorialStep
from .highlight_overlay import HighlightOverlay, HighlightRegion
from .annotation_panel import AnnotationPanel, AnnotationContent, MediaType

__all__ = [
    "TutorialEngine",
    "TutorialDefinition",
    "TutorialStep",
    "HighlightOverlay",
    "HighlightRegion",
    "AnnotationPanel",
    "AnnotationContent",
    "MediaType",
]
