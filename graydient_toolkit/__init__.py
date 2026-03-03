"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     Graydient Toolkit for CLI                                ║
║                                                                             ║
║  A toolkit for modifying inputs registered by the Graydient API             ║
║  to a local CLI for bridging media from SaaS to other applications.         ║
║                                                                             ║
║  Features:                                                                  ║
║    • Dynamic method discovery from Graydient API                            ║
║    • Telegram-style command parsing (/method and [negative])                ║
║    • Method metadata with descriptions and parameters                       ║
║    • Preview dataset management for images/videos                           ║
║    • Input transformation and validation                                    ║
║    • Configuration management                                               ║
║    • Interactive tutorial system                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Quick Start:
    >>> from graydient_toolkit import (
    ...     MethodRegistry,
    ...     CommandParserEngine,
    ...     InputModifier,
    ...     ConfigManager,
    ... )
    >>> from graydient_exchange import Exchange
    >>> 
    >>> # Initialize
    >>> exchange = Exchange(api_key="your_key")
    >>> registry = MethodRegistry(exchange)
    >>> parser = CommandParserEngine(registry)
    >>> modifier = InputModifier(registry)
    >>> 
    >>> # Parse a command
    >>> parsed = parser.parse("/draw a cyberpunk cat [blurry] --seed 42")
    >>> result = modifier.transform(parsed)
    >>> 
    >>> # Execute
    >>> output = exchange.run(result.workflow, result.params)
"""

__version__ = "1.0.0"
__author__ = "Graydient Toolkit"

# Core modules
from .method_metadata import (
    MethodMetadata,
    MethodCategory,
    ParameterDef,
    ParameterType,
    Capability,
    PreviewMedia,
    COMMON_PARAMETERS,
    create_workflow_metadata,
    create_concept_metadata,
)

from .method_registry import (
    MethodRegistry,
    CachePolicy,
)

from .command_parser import (
    CommandParserEngine,
    ParsedCommand,
    ParsedHandle,
    HandleType,
    ParseError,
    quick_parse,
)

from .input_modifier import (
    InputModifier,
    ModifierResult,
    PromptBuilder,
    ModifierChain,
    apply_quality_boost,
    apply_style_preset,
    apply_resolution_preset,
    apply_aspect_ratio,
    sanitize_prompt,
)

from .config_manager import (
    ConfigManager,
    ToolkitConfig,
    InputStyle,
    DisplayTheme,
)

from .preview_dataset import (
    PreviewDataset,
    PreviewInfo,
)

# Tutorial system (if available)
try:
    from .tutorial import (
        TutorialEngine,
        TutorialDefinition,
        TutorialStep,
        HighlightOverlay,
        AnnotationPanel,
    )
    _TUTORIAL_AVAILABLE = True
except ImportError:
    _TUTORIAL_AVAILABLE = False


__all__ = [
    # Version
    "__version__",
    
    # Method Metadata
    "MethodMetadata",
    "MethodCategory",
    "ParameterDef",
    "ParameterType",
    "Capability",
    "PreviewMedia",
    "COMMON_PARAMETERS",
    "create_workflow_metadata",
    "create_concept_metadata",
    
    # Method Registry
    "MethodRegistry",
    "CachePolicy",
    
    # Command Parser
    "CommandParserEngine",
    "ParsedCommand",
    "ParsedHandle",
    "HandleType",
    "ParseError",
    "quick_parse",
    
    # Input Modifier
    "InputModifier",
    "ModifierResult",
    "PromptBuilder",
    "ModifierChain",
    "apply_quality_boost",
    "apply_style_preset",
    "apply_resolution_preset",
    "apply_aspect_ratio",
    "sanitize_prompt",
    
    # Config Manager
    "ConfigManager",
    "ToolkitConfig",
    "InputStyle",
    "DisplayTheme",
    
    # Preview Dataset
    "PreviewDataset",
    "PreviewInfo",
]

# Add tutorial exports if available
if _TUTORIAL_AVAILABLE:
    __all__.extend([
        "TutorialEngine",
        "TutorialDefinition",
        "TutorialStep",
        "HighlightOverlay",
        "AnnotationPanel",
    ])


def get_version() -> str:
    """Get the toolkit version."""
    return __version__


def is_tutorial_available() -> bool:
    """Check if the tutorial system is available."""
    return _TUTORIAL_AVAILABLE


def create_toolkit(exchange: Any, config_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a complete toolkit instance with all components.
    
    Args:
        exchange: Graydient Exchange instance
        config_dir: Optional custom config directory
    
    Returns:
        Dictionary with all toolkit components
    """
    from pathlib import Path
    
    config_path = Path(config_dir) if config_dir else None
    
    return {
        "registry": MethodRegistry(exchange),
        "parser": CommandParserEngine(MethodRegistry(exchange)),
        "modifier": InputModifier(MethodRegistry(exchange)),
        "config": ConfigManager(config_dir=config_path),
        "previews": PreviewDataset(base_dir=config_path / "previews" if config_path else None),
    }
