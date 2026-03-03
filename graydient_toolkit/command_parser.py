"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        command_parser.py                                     ║
║           Telegram-Style Command Parser for Graydient Toolkit               ║
║                                                                             ║
║  Parses commands like:                                                      ║
║    /draw a beautiful cat [blurry, low quality] --seed 42                    ║
║                                                                             ║
║  Supports:                                                                  ║
║    • /method syntax (positive handles)                                      ║
║    • [negative] syntax (negative handles)                                   ║
║    • --flag syntax (legacy support)                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union

from .method_metadata import MethodMetadata, ParameterType
from .method_registry import MethodRegistry


class HandleType(Enum):
    """Types of command handles."""
    POSITIVE = auto()   # /method (what to include)
    NEGATIVE = auto()   # [negative] (what to exclude)
    LEGACY = auto()     # --flag (traditional CLI)


class ParseError(Exception):
    """Raised when command parsing fails."""
    pass


@dataclass
class ParsedHandle:
    """
    A single parsed handle from a command.
    
    Attributes:
        type: HandleType (POSITIVE, NEGATIVE, LEGACY)
        raw: The raw text of this handle
        method: For POSITIVE handles, the method/command name
        content: The main content (prompt, value, etc.)
        parameters: Extracted parameters
    """
    type: HandleType
    raw: str
    method: Optional[str] = None  # For POSITIVE handles
    content: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        if self.type == HandleType.POSITIVE:
            return f"ParsedHandle(POSITIVE: {self.method}, content='{self.content[:30]}...')"
        elif self.type == HandleType.NEGATIVE:
            return f"ParsedHandle(NEGATIVE: {self.content[:30]}...)"
        else:
            return f"ParsedHandle(LEGACY: {self.raw[:30]}...)"


@dataclass
class ParsedCommand:
    """
    Complete parsed command with all handles.
    
    This is the output of the CommandParserEngine, containing:
    - The primary method/command to execute
    - The main prompt/content
    - Negative prompts (from [negative] handles)
    - All parameters extracted from the command
    - Any parse errors or warnings
    
    Attributes:
        raw_input: Original input string
        primary_handle: The main /method handle
        negative_handles: List of [negative] handles
        legacy_handles: List of --flag handles
        workflow: Resolved workflow slug
        prompt: Main prompt text
        negative_prompt: Combined negative prompt
        parameters: All extracted parameters
        is_valid: Whether parsing succeeded
        errors: List of parse errors
        warnings: List of warnings
    """
    raw_input: str
    primary_handle: Optional[ParsedHandle] = None
    negative_handles: List[ParsedHandle] = field(default_factory=list)
    legacy_handles: List[ParsedHandle] = field(default_factory=list)
    workflow: Optional[str] = None
    prompt: str = ""
    negative_prompt: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def has_negatives(self) -> bool:
        """Check if command has negative handles."""
        return len(self.negative_handles) > 0 or bool(self.negative_prompt)
    
    @property
    def has_legacy(self) -> bool:
        """Check if command uses legacy --flag syntax."""
        return len(self.legacy_handles) > 0
    
    def to_exchange_format(self) -> Dict[str, Any]:
        """
        Convert to format compatible with graydient_exchange.
        
        Returns:
            Dict with keys: workflow, prompt, negative, and parameters
        """
        result = {
            "workflow": self.workflow,
            "prompt": self.prompt,
        }
        
        if self.negative_prompt:
            result["negative"] = self.negative_prompt
        
        # Add other parameters
        for key, value in self.parameters.items():
            if key not in result:
                result[key] = value
        
        return result
    
    def format_for_display(self) -> str:
        """Format the parsed command for display."""
        lines = ["Parsed Command:", "=" * 40]
        
        if self.workflow:
            lines.append(f"Workflow: {self.workflow}")
        
        if self.prompt:
            lines.append(f"Prompt: {self.prompt[:80]}...")
        
        if self.negative_prompt:
            lines.append(f"Negative: {self.negative_prompt[:80]}...")
        
        if self.parameters:
            lines.append("Parameters:")
            for key, value in self.parameters.items():
                lines.append(f"  {key}: {value}")
        
        if self.errors:
            lines.append("Errors:")
            for error in self.errors:
                lines.append(f"  ✗ {error}")
        
        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")
        
        return "\n".join(lines)


class CommandParserEngine:
    """
    Parser for Telegram-style commands with /method and [negative] support.
    
    This parser supports three styles of command input:
    
    1. Telegram-style (recommended):
       /draw a beautiful cat [blurry, low quality] --seed 42
       
    2. Negative-only:
       [nsfw, violence, gore]
       
    3. Legacy flag-style:
       --prompt="a cat" --seed=42 --negative="blurry"
    
    Example:
        >>> from graydient_toolkit import CommandParserEngine, MethodRegistry
        >>> 
        >>> registry = MethodRegistry(exchange)
        >>> parser = CommandParserEngine(registry)
        >>> 
        >>> # Parse a command
        >>> cmd = parser.parse("/draw a cyberpunk cat --seed 42")
        >>> print(cmd.workflow)  # "qwen"
        >>> print(cmd.prompt)    # "a cyberpunk cat"
        >>> print(cmd.parameters)  # {"seed": 42}
        >>> 
        >>> # Parse with negatives
        >>> cmd = parser.parse("/draw a cat [blurry, low quality]")
        >>> print(cmd.negative_prompt)  # "blurry, low quality"
    """
    
    # Regex patterns for parsing
    POSITIVE_PATTERN = re.compile(
        r'^(/\w+)'  # Command like /draw
        r'(?:\s+|$)'  # Whitespace or end
        r'(.*)?$',  # Rest of the content
        re.DOTALL
    )
    
    NEGATIVE_PATTERN = re.compile(
        r'\['  # Opening bracket
        r'([^\]]+)'  # Content inside brackets
        r'\]',  # Closing bracket
        re.DOTALL
    )
    
    LEGACY_FLAG_PATTERN = re.compile(
        r'--(\w+)'  # Flag name
        r'(?:\s*[=\s]\s*)'  # Separator (= or space)
        r'('  # Value group
        r'"[^"]*"'  # Quoted string
        r'|\'[^\']*\''  # Single-quoted string
        r'|\S+'  # Non-whitespace
        r')',
        re.DOTALL
    )
    
    SHORT_FLAG_PATTERN = re.compile(
        r'--(\w+)'  # Flag name
        r'(?:\s+|$)',  # Whitespace or end
        re.DOTALL
    )
    
    def __init__(
        self,
        registry: Optional[MethodRegistry] = None,
        allow_legacy: bool = True,
        strict_mode: bool = False,
    ):
        """
        Initialize the command parser.
        
        Args:
            registry: MethodRegistry for resolving commands to workflows
            allow_legacy: Whether to allow --flag syntax
            strict_mode: If True, reject unknown commands
        """
        self._registry = registry
        self._allow_legacy = allow_legacy
        self._strict_mode = strict_mode
    
    def parse(self, input_text: str) -> ParsedCommand:
        """
        Parse a command string into a ParsedCommand.
        
        Args:
            input_text: The command to parse
        
        Returns:
            ParsedCommand with all extracted information
        """
        input_text = input_text.strip()
        result = ParsedCommand(raw_input=input_text)
        
        if not input_text:
            result.is_valid = False
            result.errors.append("Empty input")
            return result
        
        try:
            # Step 1: Extract negative handles [like this]
            input_without_negatives, negatives = self._extract_negatives(input_text)
            result.negative_handles = negatives
            result.negative_prompt = self._combine_negatives(negatives)
            
            # Step 2: Check for positive handle /command
            positive_match = self.POSITIVE_PATTERN.match(input_without_negatives)
            
            if positive_match:
                # Parse as Telegram-style command
                self._parse_positive(result, positive_match, input_without_negatives)
            
            elif self._allow_legacy and input_without_negatives.startswith('--'):
                # Parse as legacy flag-style
                self._parse_legacy(result, input_without_negatives)
            
            else:
                # No recognized format - treat as plain prompt
                result.prompt = input_without_negatives.strip()
                result.warnings.append("No command specified, treating as plain prompt")
            
            # Step 3: Resolve workflow if registry available
            if self._registry and result.primary_handle:
                self._resolve_workflow(result)
            
            # Step 4: Validate against method metadata if available
            if self._registry and result.workflow:
                self._validate_against_metadata(result)
        
        except ParseError as e:
            result.is_valid = False
            result.errors.append(str(e))
        
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Unexpected error: {e}")
        
        return result
    
    def parse_batch(self, inputs: List[str]) -> List[ParsedCommand]:
        """Parse multiple commands."""
        return [self.parse(inp) for inp in inputs]
    
    def autocomplete(self, partial: str) -> List[str]:
        """
        Get autocomplete suggestions for a partial command.
        
        Args:
            partial: Partial command string
        
        Returns:
            List of suggested completions
        """
        suggestions = []
        
        if not self._registry:
            return suggestions
        
        # Suggest commands
        if partial.startswith('/'):
            commands = self._registry.list_commands()
            suggestions = [cmd for cmd in commands if cmd.startswith(partial)]
        
        # Suggest workflows
        elif partial:
            workflows = self._registry.search_workflows(partial)
            suggestions = [wf.slug for wf in workflows]
        
        return suggestions
    
    def format_help(self) -> str:
        """Format help text for command syntax."""
        return """
╔══════════════════════════════════════════════════════════════════════════════╗
║                         COMMAND SYNTAX GUIDE                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

TELEGRAM-STYLE COMMANDS (Recommended)
═══════════════════════════════════════

    /draw <prompt> [negative prompts] [--parameters]

Examples:
    /draw a beautiful landscape
    /draw a cyberpunk cat [blurry, low quality] --seed 42
    /animate a walking character --fps 30
    /style oil painting --strength 0.8

Available Commands:
    /draw, /d       - Generate images from text
    /animate, /a    - Animate still images
    /style, /s      - Apply style transfer
    /upscale, /u    - Upscale images
    /img2img, /i2i  - Image-to-image transformation

POSITIVE HANDLES (/methods)
═══════════════════════════

    /method indicates what workflow to use:
    
    /draw   → Uses the "qwen" workflow
    /animate → Uses the "animate-wan22" workflow

NEGATIVE HANDLES ([negatives])
═══════════════════════════════

    [text inside brackets] specifies what to AVOID:
    
    [blurry, low quality, distorted]
    [nsfw, violence, gore]
    [watermark, signature, text]

    Multiple negative handles can be used:
    /draw a cat [blurry] [low quality] [distorted]

LEGACY SYNTAX (--flags)
═══════════════════════

    For backward compatibility, traditional flags are supported:
    
    --prompt="a cat" --seed=42 --guidance=7.5
    --negative="blurry, low quality"

COMMON PARAMETERS
═════════════════

    --seed N        Random seed for reproducibility
    --steps N       Number of inference steps (1-150)
    --guidance N    CFG scale (1.0-30.0)
    --width N       Output width in pixels
    --height N      Output height in pixels
    --strength N    Transformation strength 0.0-1.0
    --num_images N  Number of images to generate
    --format TYPE   Output format: png, jpg, webp

EXAMPLES
════════

    Simple generation:
    /draw a majestic eagle soaring over mountains

    With seed for reproducibility:
    /draw a red sports car --seed 12345

    With negative prompts:
    /draw a portrait [blurry, distorted, ugly]

    Image-to-image:
    /img2img make this cyberpunk --image https://example.com/photo.jpg

    Animation:
    /animate a dancing robot --fps 24 --length 48

"""
    
    # ─────────────────────────────────────────────────────────────────────────
    # Internal Parsing Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def _extract_negatives(self, text: str) -> Tuple[str, List[ParsedHandle]]:
        """
        Extract all [negative] handles from text.
        
        Returns:
            (text_without_negatives, list_of_negative_handles)
        """
        negatives = []
        
        def replace_negative(match):
            content = match.group(1).strip()
            negatives.append(ParsedHandle(
                type=HandleType.NEGATIVE,
                raw=match.group(0),
                content=content,
            ))
            return " "  # Replace with space to preserve word boundaries
        
        text_without = self.NEGATIVE_PATTERN.sub(replace_negative, text)
        
        return text_without, negatives
    
    def _combine_negatives(self, negatives: List[ParsedHandle]) -> str:
        """Combine multiple negative handles into a single string."""
        if not negatives:
            return ""
        
        # Extract content from each negative handle
        contents = [n.content for n in negatives]
        
        # Join with commas
        return ", ".join(contents)
    
    def _parse_positive(self, result: ParsedCommand, match, full_text: str) -> None:
        """Parse a positive /command handle."""
        command = match.group(1).lower()
        rest = (match.group(2) or "").strip()
        
        # Create the primary handle
        result.primary_handle = ParsedHandle(
            type=HandleType.POSITIVE,
            raw=command,
            method=command,
        )
        
        # Extract parameters from the rest
        result.prompt, result.parameters = self._extract_parameters(rest)
        result.primary_handle.content = result.prompt
        result.primary_handle.parameters = result.parameters
    
    def _parse_legacy(self, result: ParsedCommand, text: str) -> None:
        """Parse legacy --flag style command."""
        result.legacy_handles = []
        parameters = {}
        
        # Find all --flag=value patterns
        for match in self.LEGACY_FLAG_PATTERN.finditer(text):
            flag = match.group(1)
            value = match.group(2)
            
            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            
            # Convert types
            value = self._convert_value(value)
            
            parameters[flag] = value
            result.legacy_handles.append(ParsedHandle(
                type=HandleType.LEGACY,
                raw=match.group(0),
                content=f"{flag}={value}",
                parameters={flag: value},
            ))
        
        # Extract prompt
        result.prompt = parameters.get("prompt", "")
        result.parameters = {k: v for k, v in parameters.items() if k != "prompt"}
        
        # Check for workflow specification
        if "workflow" in parameters:
            result.workflow = parameters["workflow"]
    
    def _extract_parameters(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract --parameters from text.
        
        Returns:
            (prompt_without_params, parameters_dict)
        """
        parameters = {}
        
        # Find all --flag value patterns
        for match in self.LEGACY_FLAG_PATTERN.finditer(text):
            flag = match.group(1)
            value = match.group(2)
            
            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            
            # Convert types
            value = self._convert_value(value)
            
            parameters[flag] = value
        
        # Remove parameter declarations from text to get pure prompt
        prompt = self.LEGACY_FLAG_PATTERN.sub('', text).strip()
        
        return prompt, parameters
    
    def _convert_value(self, value: str) -> Union[str, int, float, bool]:
        """Convert a string value to its appropriate type."""
        # Try boolean
        if value.lower() in ("true", "yes", "on"):
            return True
        if value.lower() in ("false", "no", "off"):
            return False
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _resolve_workflow(self, result: ParsedCommand) -> None:
        """Resolve command to workflow slug using registry."""
        if not result.primary_handle:
            return
        
        command = result.primary_handle.method
        
        # Try to resolve via registry
        workflow_slug = self._registry.resolve_command(command)
        
        if workflow_slug:
            result.workflow = workflow_slug
        elif self._strict_mode:
            result.is_valid = False
            result.errors.append(f"Unknown command: {command}")
        else:
            # In non-strict mode, use command as workflow name
            result.workflow = command.lstrip('/')
            result.warnings.append(f"Unknown command '{command}', treating as workflow name")
    
    def _validate_against_metadata(self, result: ParsedCommand) -> None:
        """Validate parsed command against method metadata."""
        if not result.workflow:
            return
        
        method = self._registry.get_workflow(result.workflow)
        
        if not method:
            result.warnings.append(f"Workflow '{result.workflow}' not found in registry")
            return
        
        # Validate parameters
        is_valid, errors = method.validate_inputs(result.parameters)
        
        if not is_valid:
            for error in errors:
                result.warnings.append(error)
        
        # Apply defaults
        result.parameters = method.apply_defaults(result.parameters)


def quick_parse(text: str) -> ParsedCommand:
    """
    Quick parse without registry (basic parsing only).
    
    This is useful for simple parsing when you don't need
    workflow resolution or validation.
    
    Example:
        >>> cmd = quick_parse("/draw a cat --seed 42")
        >>> print(cmd.prompt)  # "a cat"
        >>> print(cmd.parameters)  # {"seed": 42}
    """
    parser = CommandParserEngine(registry=None, allow_legacy=True)
    return parser.parse(text)
