"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        input_modifier.py                                     ║
║              Input Transformation for Graydient Toolkit                     ║
║                                                                             ║
║  Transforms parsed commands into Exchange-compatible format.                ║
║  Applies defaults, validates inputs, and chains modifiers.                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from .command_parser import ParsedCommand, HandleType
from .method_metadata import MethodMetadata, ParameterType, COMMON_PARAMETERS
from .method_registry import MethodRegistry


@dataclass
class ModifierResult:
    """
    Result of input modification.
    
    Attributes:
        workflow: Target workflow slug
        params: Parameters for the workflow
        is_valid: Whether modification succeeded
        errors: List of errors
        warnings: List of warnings
        applied_modifiers: List of modifiers that were applied
    """
    workflow: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    applied_modifiers: List[str] = field(default_factory=list)
    
    def to_exchange_format(self) -> Dict[str, Any]:
        """Convert to format expected by graydient_exchange."""
        return {
            "workflow": self.workflow,
            "params": self.params,
        }


class InputModifier:
    """
    Transforms parsed commands into Exchange-compatible input format.
    
    This class bridges the gap between the command parser and the
    graydient_exchange module, handling:
    
    - Workflow resolution
    - Parameter transformation
    - Default value application
    - Input validation
    - Custom modifier chains
    
    Example:
        >>> from graydient_toolkit import CommandParserEngine, InputModifier
        >>> 
        >>> registry = MethodRegistry(exchange)
        >>> parser = CommandParserEngine(registry)
        >>> modifier = InputModifier(registry)
        >>> 
        >>> # Parse and modify
        >>> parsed = parser.parse("/draw a cat --seed 42")
        >>> result = modifier.transform(parsed)
        >>> 
        >>> # Use with Exchange
        >>> exchange.run(result.workflow, result.params)
    """
    
    def __init__(
        self,
        registry: Optional[MethodRegistry] = None,
        default_workflow: Optional[str] = None,
        global_defaults: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the input modifier.
        
        Args:
            registry: MethodRegistry for workflow lookup
            default_workflow: Fallback workflow if none specified
            global_defaults: Default parameters to apply to all calls
        """
        self._registry = registry
        self._default_workflow = default_workflow
        self._global_defaults = global_defaults or {}
        self._custom_modifiers: List[Callable[[ModifierResult], ModifierResult]] = []
    
    def add_modifier(self, modifier: Callable[[ModifierResult], ModifierResult]) -> "InputModifier":
        """
        Add a custom modifier function to the chain.
        
        Modifiers are applied in order after standard transformation.
        
        Args:
            modifier: Function that takes and returns ModifierResult
        
        Returns:
            Self for chaining
        """
        self._custom_modifiers.append(modifier)
        return self
    
    def transform(
        self,
        parsed: ParsedCommand,
        extra_defaults: Optional[Dict[str, Any]] = None,
    ) -> ModifierResult:
        """
        Transform a ParsedCommand into ModifierResult.
        
        Args:
            parsed: The parsed command
            extra_defaults: Additional defaults for this specific call
        
        Returns:
            ModifierResult ready for Exchange
        """
        result = ModifierResult()
        
        # Step 1: Determine workflow
        workflow = self._resolve_workflow(parsed)
        if not workflow:
            result.is_valid = False
            result.errors.append("No workflow specified and no default available")
            return result
        
        result.workflow = workflow
        
        # Step 2: Build base parameters
        params = self._build_parameters(parsed)
        
        # Step 3: Apply global defaults
        params = self._apply_defaults(params, self._global_defaults)
        
        # Step 4: Apply extra defaults
        if extra_defaults:
            params = self._apply_defaults(params, extra_defaults)
        
        # Step 5: Get method metadata and apply its defaults
        if self._registry:
            method = self._registry.get_workflow(workflow)
            if method:
                params = method.apply_defaults(params)
                
                # Validate
                is_valid, errors = method.validate_inputs(params)
                if not is_valid:
                    result.is_valid = False
                    result.errors.extend(errors)
                
                result.applied_modifiers.append("method_defaults")
        
        result.params = params
        
        # Step 6: Apply custom modifiers
        for modifier in self._custom_modifiers:
            try:
                result = modifier(result)
                result.applied_modifiers.append(modifier.__name__)
            except Exception as e:
                result.warnings.append(f"Modifier {modifier.__name__} failed: {e}")
        
        return result
    
    def transform_batch(
        self,
        parsed_commands: List[ParsedCommand],
    ) -> List[ModifierResult]:
        """Transform multiple parsed commands."""
        return [self.transform(cmd) for cmd in parsed_commands]
    
    def create_prompt_builder(self) -> "PromptBuilder":
        """Create a PromptBuilder for fluent prompt construction."""
        return PromptBuilder(self)
    
    def _resolve_workflow(self, parsed: ParsedCommand) -> Optional[str]:
        """Determine the target workflow."""
        # Use parsed workflow if available
        if parsed.workflow:
            return parsed.workflow
        
        # Use default
        return self._default_workflow
    
    def _build_parameters(self, parsed: ParsedCommand) -> Dict[str, Any]:
        """Build parameter dict from parsed command."""
        params = {}
        
        # Add prompt
        if parsed.prompt:
            params["prompt"] = parsed.prompt
        
        # Add negative prompt
        if parsed.negative_prompt:
            params["negative"] = parsed.negative_prompt
        
        # Add other parameters
        params.update(parsed.parameters)
        
        return params
    
    def _apply_defaults(
        self,
        params: Dict[str, Any],
        defaults: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply default values where not already set."""
        result = dict(params)
        
        for key, value in defaults.items():
            if key not in result or result[key] is None:
                result[key] = value
        
        return result


class PromptBuilder:
    """
    Fluent interface for building prompts with modifiers.
    
    Example:
        >>> builder = modifier.create_prompt_builder()
        >>> result = (builder
        ...     .workflow("qwen")
        ...     .prompt("a cyberpunk cat")
        ...     .negative("blurry, low quality")
        ...     .seed(42)
        ...     .guidance(7.5)
        ...     .build())
    """
    
    def __init__(self, modifier: InputModifier):
        self._modifier = modifier
        self._workflow: Optional[str] = None
        self._prompt: str = ""
        self._negative: str = ""
        self._params: Dict[str, Any] = {}
    
    def workflow(self, slug: str) -> "PromptBuilder":
        """Set the workflow."""
        self._workflow = slug
        return self
    
    def prompt(self, text: str) -> "PromptBuilder":
        """Set the main prompt."""
        self._prompt = text
        return self
    
    def negative(self, text: str) -> "PromptBuilder":
        """Set the negative prompt."""
        self._negative = text
        return self
    
    def seed(self, value: int) -> "PromptBuilder":
        """Set the seed."""
        self._params["seed"] = value
        return self
    
    def guidance(self, value: float) -> "PromptBuilder":
        """Set the guidance scale."""
        self._params["guidance"] = value
        return self
    
    def steps(self, value: int) -> "PromptBuilder":
        """Set the number of steps."""
        self._params["steps"] = value
        return self
    
    def width(self, value: int) -> "PromptBuilder":
        """Set the output width."""
        self._params["width"] = value
        return self
    
    def height(self, value: int) -> "PromptBuilder":
        """Set the output height."""
        self._params["height"] = value
        return self
    
    def strength(self, value: float) -> "PromptBuilder":
        """Set the transformation strength."""
        self._params["strength"] = value
        return self
    
    def num_images(self, value: int) -> "PromptBuilder":
        """Set the number of images."""
        self._params["num_images"] = value
        return self
    
    def format(self, value: str) -> "PromptBuilder":
        """Set the output format."""
        self._params["format"] = value
        return self
    
    def image(self, url: str) -> "PromptBuilder":
        """Set the input image URL."""
        self._params["init_image"] = url
        return self
    
    def param(self, name: str, value: Any) -> "PromptBuilder":
        """Set a custom parameter."""
        self._params[name] = value
        return self
    
    def build(self) -> ModifierResult:
        """Build and return the ModifierResult."""
        # Create a synthetic ParsedCommand
        from .command_parser import ParsedCommand, ParsedHandle, HandleType
        
        parsed = ParsedCommand(raw_input="")
        parsed.workflow = self._workflow
        parsed.prompt = self._prompt
        parsed.negative_prompt = self._negative
        parsed.parameters = self._params
        
        return self._modifier.transform(parsed)


class ModifierChain:
    """
    Chain multiple modifiers together.
    
    Example:
        >>> chain = ModifierChain()
        >>> chain.add(apply_quality_boost)
        >>> chain.add(apply_style_preset)
        >>> result = chain.apply(parsed)
    """
    
    def __init__(self):
        self._modifiers: List[Callable[[ModifierResult], ModifierResult]] = []
    
    def add(self, modifier: Callable[[ModifierResult], ModifierResult]) -> "ModifierChain":
        """Add a modifier to the chain."""
        self._modifiers.append(modifier)
        return self
    
    def apply(self, initial: ModifierResult) -> ModifierResult:
        """Apply all modifiers in sequence."""
        result = initial
        
        for modifier in self._modifiers:
            try:
                result = modifier(result)
            except Exception as e:
                result.warnings.append(f"Modifier failed: {e}")
        
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Common Modifier Functions
# ─────────────────────────────────────────────────────────────────────────────

def apply_quality_boost(result: ModifierResult) -> ModifierResult:
    """
    Modifier that adds quality-enhancing terms to prompts.
    
    Automatically appends quality keywords to the prompt.
    """
    if "prompt" in result.params:
        quality_terms = "high quality, detailed, sharp focus"
        result.params["prompt"] = f"{result.params['prompt']}, {quality_terms}"
        result.applied_modifiers.append("quality_boost")
    
    return result


def apply_style_preset(style: str) -> Callable[[ModifierResult], ModifierResult]:
    """
    Create a modifier that applies a style preset.
    
    Args:
        style: Style name (e.g., "digital art", "oil painting")
    
    Returns:
        Modifier function
    """
    def modifier(result: ModifierResult) -> ModifierResult:
        if "prompt" in result.params:
            result.params["prompt"] = f"{result.params['prompt']}, {style} style"
            result.applied_modifiers.append(f"style:{style}")
        return result
    
    return modifier


def apply_resolution_preset(
    width: int,
    height: int,
) -> Callable[[ModifierResult], ModifierResult]:
    """
    Create a modifier that applies a resolution preset.
    
    Args:
        width: Output width
        height: Output height
    
    Returns:
        Modifier function
    """
    def modifier(result: ModifierResult) -> ModifierResult:
        result.params["width"] = width
        result.params["height"] = height
        result.applied_modifiers.append(f"resolution:{width}x{height}")
        return result
    
    return modifier


def apply_aspect_ratio(ratio: str) -> Callable[[ModifierResult], ModifierResult]:
    """
    Create a modifier that applies an aspect ratio.
    
    Args:
        ratio: Aspect ratio ("16:9", "4:3", "1:1", "9:16")
    
    Returns:
        Modifier function
    """
    ratios = {
        "16:9": (1920, 1080),
        "4:3": (1024, 768),
        "1:1": (1024, 1024),
        "9:16": (1080, 1920),
        "3:2": (1536, 1024),
        "2:3": (1024, 1536),
    }
    
    if ratio not in ratios:
        raise ValueError(f"Unknown aspect ratio: {ratio}. Use: {list(ratios.keys())}")
    
    width, height = ratios[ratio]
    return apply_resolution_preset(width, height)


def sanitize_prompt(result: ModifierResult) -> ModifierResult:
    """
    Modifier that sanitizes prompt text.
    
    Removes extra whitespace and normalizes punctuation.
    """
    if "prompt" in result.params:
        prompt = result.params["prompt"]
        # Normalize whitespace
        prompt = " ".join(prompt.split())
        # Normalize commas
        prompt = re.sub(r'\s*,\s*', ', ', prompt)
        result.params["prompt"] = prompt.strip()
        result.applied_modifiers.append("sanitize")
    
    if "negative" in result.params:
        negative = result.params["negative"]
        negative = " ".join(negative.split())
        negative = re.sub(r'\s*,\s*', ', ', negative)
        result.params["negative"] = negative.strip()
    
    return result


# Regex for sanitize_prompt
import re
