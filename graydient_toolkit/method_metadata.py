"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        method_metadata.py                                    ║
║              Method Metadata Schema for Graydient Toolkit                   ║
║                                                                             ║
║  Defines data structures for storing detailed information about             ║
║  workflows, concepts, and their parameters.                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class MethodCategory(str, Enum):
    """Categories of methods available in Graydient."""
    WORKFLOW = "workflow"
    CONCEPT = "concept"
    COMMAND = "command"  # Telegram-style commands like /draw


class ParameterType(str, Enum):
    """Data types for method parameters."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    IMAGE_URL = "image_url"
    VIDEO_URL = "video_url"
    LIST = "list"
    DICT = "dict"


class Capability(str, Enum):
    """Capabilities that workflows may support."""
    TXT2IMG = "txt2img"
    IMG2IMG = "img2img"
    TXT2VID = "txt2vid"
    VID2VID = "vid2vid"
    IMG2VID = "img2vid"
    VID2IMG = "vid2img"
    TXT2WAV = "txt2wav"
    VID2WAV = "vid2wav"
    WAV2TXT = "wav2txt"
    UPSCALE = "upscale"
    ANIMATE = "animate"
    LOW_MEMORY = "low_memory"


@dataclass
class ParameterDef:
    """
    Definition of a single parameter for a method.
    
    Attributes:
        name: Parameter name (e.g., "seed", "guidance")
        type: Data type of the parameter
        description: Human-readable description
        default: Default value if not specified
        required: Whether this parameter must be provided
        min_value: Minimum value (for numeric types)
        max_value: Maximum value (for numeric types)
        allowed_values: List of allowed values (for enum-like parameters)
        help_text: Extended help text for CLI display
        example: Example value for documentation
    """
    name: str
    type: ParameterType
    description: str = ""
    default: Optional[Any] = None
    required: bool = False
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    help_text: str = ""
    example: Optional[Any] = None
    
    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate a value against this parameter definition.
        
        Returns:
            (is_valid, error_message)
        """
        if value is None:
            if self.required:
                return False, f"Parameter '{self.name}' is required"
            return True, None
        
        # Type validation
        if self.type == ParameterType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return False, f"Parameter '{self.name}' must be an integer"
        
        elif self.type == ParameterType.FLOAT:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return False, f"Parameter '{self.name}' must be a number"
        
        elif self.type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                if isinstance(value, str):
                    value = value.lower() in ("true", "1", "yes", "on")
                else:
                    return False, f"Parameter '{self.name}' must be a boolean"
        
        elif self.type == ParameterType.STRING:
            if not isinstance(value, str):
                value = str(value)
        
        # Range validation
        if self.min_value is not None and value < self.min_value:
            return False, f"Parameter '{self.name}' must be >= {self.min_value}"
        
        if self.max_value is not None and value > self.max_value:
            return False, f"Parameter '{self.name}' must be <= {self.max_value}"
        
        # Allowed values validation
        if self.allowed_values is not None and value not in self.allowed_values:
            return False, f"Parameter '{self.name}' must be one of: {self.allowed_values}"
        
        return True, None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "default": self.default,
            "required": self.required,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "allowed_values": self.allowed_values,
            "help_text": self.help_text,
            "example": self.example,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ParameterDef:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=ParameterType(data.get("type", "string")),
            description=data.get("description", ""),
            default=data.get("default"),
            required=data.get("required", False),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            allowed_values=data.get("allowed_values"),
            help_text=data.get("help_text", ""),
            example=data.get("example"),
        )


@dataclass
class PreviewMedia:
    """
    Reference to a preview image or video for a method.
    
    Attributes:
        type: "image" or "video"
        path: Local path to the media file
        url: Optional remote URL
        caption: Description of what this preview shows
        thumbnail: Path to thumbnail (for videos)
    """
    type: str  # "image" or "video"
    path: Optional[str] = None
    url: Optional[str] = None
    caption: str = ""
    thumbnail: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "path": self.path,
            "url": self.url,
            "caption": self.caption,
            "thumbnail": self.thumbnail,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PreviewMedia:
        return cls(**data)


@dataclass
class MethodMetadata:
    """
    Complete metadata for a Graydient method (workflow or concept).
    
    This is the primary data structure for storing information about
    available methods, their parameters, capabilities, and previews.
    
    Attributes:
        slug: Unique API identifier (e.g., "qwen", "edit-qwen")
        display_name: Human-readable name (e.g., "Qwen Image Gen")
        category: Type of method (workflow, concept, command)
        description: Full description of what this method does
        short_description: One-line summary for lists
        capabilities: List of supported capabilities
        parameters: List of parameter definitions
        preview_media: List of preview images/videos
        examples: Example prompts or usage strings
        tags: Categorization tags
        version: API version
        is_public: Whether this is a public workflow
        platform: Execution platform (e.g., "comfyui", "tensorrt")
        author: Creator of the workflow/concept
        source_url: Link to more information
        extra_data: Additional API-specific data
        last_updated: When this metadata was last refreshed
        cached_at: When this was cached locally
    """
    slug: str
    display_name: str
    category: MethodCategory
    description: str = ""
    short_description: str = ""
    capabilities: List[Capability] = field(default_factory=list)
    parameters: List[ParameterDef] = field(default_factory=list)
    preview_media: List[PreviewMedia] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    version: int = 1
    is_public: bool = True
    platform: str = ""
    author: str = ""
    source_url: str = ""
    extra_data: Dict[str, Any] = field(default_factory=dict)
    last_updated: Optional[datetime] = None
    cached_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Set default display_name if not provided."""
        if not self.display_name:
            self.display_name = self.slug.replace("-", " ").replace("_", " ").title()
    
    @property
    def has_previews(self) -> bool:
        """Check if this method has any preview media."""
        return len(self.preview_media) > 0
    
    @property
    def required_parameters(self) -> List[ParameterDef]:
        """Get list of required parameters."""
        return [p for p in self.parameters if p.required]
    
    @property
    def optional_parameters(self) -> List[ParameterDef]:
        """Get list of optional parameters."""
        return [p for p in self.parameters if not p.required]
    
    def get_parameter(self, name: str) -> Optional[ParameterDef]:
        """Get a parameter definition by name."""
        for param in self.parameters:
            if param.name == name:
                return param
        return None
    
    def supports(self, capability: Capability) -> bool:
        """Check if this method supports a given capability."""
        return capability in self.capabilities
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate a dictionary of inputs against this method's parameters.
        
        Returns:
            (is_valid, list_of_error_messages)
        """
        errors = []
        
        # Check required parameters
        for param in self.required_parameters:
            if param.name not in inputs or inputs[param.name] is None:
                errors.append(f"Missing required parameter: '{param.name}'")
        
        # Validate each provided input
        for name, value in inputs.items():
            param = self.get_parameter(name)
            if param:
                is_valid, error = param.validate(value)
                if not is_valid:
                    errors.append(error)
            # Allow unknown parameters (they might be handled by the API)
        
        return len(errors) == 0, errors
    
    def apply_defaults(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply default values to inputs where not provided.
        
        Returns:
            New dictionary with defaults applied
        """
        result = dict(inputs)
        for param in self.parameters:
            if param.name not in result and param.default is not None:
                result[param.name] = param.default
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "category": self.category.value,
            "description": self.description,
            "short_description": self.short_description,
            "capabilities": [c.value for c in self.capabilities],
            "parameters": [p.to_dict() for p in self.parameters],
            "preview_media": [m.to_dict() for m in self.preview_media],
            "examples": self.examples,
            "tags": self.tags,
            "version": self.version,
            "is_public": self.is_public,
            "platform": self.platform,
            "author": self.author,
            "source_url": self.source_url,
            "extra_data": self.extra_data,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "cached_at": self.cached_at.isoformat() if self.cached_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MethodMetadata:
        """Create from dictionary."""
        return cls(
            slug=data["slug"],
            display_name=data.get("display_name", data["slug"]),
            category=MethodCategory(data.get("category", "workflow")),
            description=data.get("description", ""),
            short_description=data.get("short_description", ""),
            capabilities=[Capability(c) for c in data.get("capabilities", [])],
            parameters=[ParameterDef.from_dict(p) for p in data.get("parameters", [])],
            preview_media=[PreviewMedia.from_dict(m) for m in data.get("preview_media", [])],
            examples=data.get("examples", []),
            tags=data.get("tags", []),
            version=data.get("version", 1),
            is_public=data.get("is_public", True),
            platform=data.get("platform", ""),
            author=data.get("author", ""),
            source_url=data.get("source_url", ""),
            extra_data=data.get("extra_data", {}),
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None,
            cached_at=datetime.fromisoformat(data["cached_at"]) if data.get("cached_at") else None,
        )
    
    def format_help(self) -> str:
        """Format a help string for CLI display."""
        lines = [
            f"{self.display_name} ({self.slug})",
            "=" * 50,
            self.description or "No description available.",
            "",
            "Capabilities:",
        ]
        
        if self.capabilities:
            for cap in self.capabilities:
                lines.append(f"  • {cap.value}")
        else:
            lines.append("  (none specified)")
        
        lines.extend(["", "Parameters:"])
        
        if self.parameters:
            for param in self.parameters:
                req = "(required)" if param.required else "(optional)"
                default = f" [default: {param.default}]" if param.default is not None else ""
                lines.append(f"  --{param.name} <{param.type.value}> {req}{default}")
                if param.description:
                    lines.append(f"      {param.description}")
        else:
            lines.append("  (none specified)")
        
        if self.examples:
            lines.extend(["", "Examples:"])
            for ex in self.examples:
                lines.append(f"  {ex}")
        
        return "\n".join(lines)


# Predefined parameter definitions for common Graydient parameters
COMMON_PARAMETERS = {
    "prompt": ParameterDef(
        name="prompt",
        type=ParameterType.STRING,
        description="The main text prompt describing what to generate",
        required=True,
        help_text="Be descriptive! Include subject, style, lighting, mood, etc.",
        example="a cyberpunk cat wearing neon sunglasses, digital art",
    ),
    "negative": ParameterDef(
        name="negative",
        type=ParameterType.STRING,
        description="Things to avoid in the generation",
        default="",
        help_text="Describe what you don't want to see in the output",
        example="blurry, low quality, distorted, ugly",
    ),
    "seed": ParameterDef(
        name="seed",
        type=ParameterType.INTEGER,
        description="Random seed for reproducible results",
        default=None,
        min_value=0,
        max_value=2**32 - 1,
        help_text="Use the same seed to get similar results",
        example=42,
    ),
    "guidance": ParameterDef(
        name="guidance",
        type=ParameterType.FLOAT,
        description="How closely to follow the prompt (CFG scale)",
        default=7.5,
        min_value=1.0,
        max_value=30.0,
        help_text="Higher values = more literal interpretation of prompt",
        example=7.5,
    ),
    "steps": ParameterDef(
        name="steps",
        type=ParameterType.INTEGER,
        description="Number of denoising steps",
        default=30,
        min_value=1,
        max_value=150,
        help_text="More steps = better quality but slower",
        example=30,
    ),
    "width": ParameterDef(
        name="width",
        type=ParameterType.INTEGER,
        description="Output image width in pixels",
        default=1024,
        min_value=64,
        max_value=4096,
        help_text="Must be divisible by 8",
        example=1024,
    ),
    "height": ParameterDef(
        name="height",
        type=ParameterType.INTEGER,
        description="Output image height in pixels",
        default=1024,
        min_value=64,
        max_value=4096,
        help_text="Must be divisible by 8",
        example=1024,
    ),
    "strength": ParameterDef(
        name="strength",
        type=ParameterType.FLOAT,
        description="How much to change the input image (for img2img)",
        default=0.7,
        min_value=0.0,
        max_value=1.0,
        help_text="0.0 = no change, 1.0 = complete replacement",
        example=0.7,
    ),
    "num_images": ParameterDef(
        name="num_images",
        type=ParameterType.INTEGER,
        description="Number of images to generate",
        default=1,
        min_value=1,
        max_value=10,
        help_text="How many variations to create",
        example=1,
    ),
    "init_image": ParameterDef(
        name="init_image",
        type=ParameterType.IMAGE_URL,
        description="URL of input image for img2img operations",
        help_text="Must be a publicly accessible URL",
        example="https://example.com/image.png",
    ),
    "format": ParameterDef(
        name="format",
        type=ParameterType.STRING,
        description="Output image format",
        default="png",
        allowed_values=["png", "jpg", "webp"],
        help_text="File format for the generated image",
        example="png",
    ),
    "fps": ParameterDef(
        name="fps",
        type=ParameterType.INTEGER,
        description="Frames per second for video output",
        default=24,
        min_value=1,
        max_value=60,
        help_text="Video playback frame rate",
        example=24,
    ),
    "length": ParameterDef(
        name="length",
        type=ParameterType.INTEGER,
        description="Video length in frames",
        default=24,
        min_value=1,
        max_value=120,
        help_text="Total number of frames to generate",
        example=24,
    ),
}


def create_workflow_metadata(
    slug: str,
    api_workflow: Any,  # Graydient Workflow object
    extra_params: Optional[List[ParameterDef]] = None,
) -> MethodMetadata:
    """
    Create MethodMetadata from a Graydient API Workflow object.
    
    Args:
        slug: The workflow slug
        api_workflow: Workflow object from graydient.workflow.all()
        extra_params: Additional parameters specific to this workflow
    
    Returns:
        Populated MethodMetadata instance
    """
    # Extract capabilities from workflow
    capabilities = []
    if hasattr(api_workflow, 'supports_txt2img') and api_workflow.supports_txt2img:
        capabilities.append(Capability.TXT2IMG)
    if hasattr(api_workflow, 'supports_img2img') and api_workflow.supports_img2img:
        capabilities.append(Capability.IMG2IMG)
    if hasattr(api_workflow, 'supports_txt2vid') and api_workflow.supports_txt2vid:
        capabilities.append(Capability.TXT2VID)
    if hasattr(api_workflow, 'supports_vid2vid') and api_workflow.supports_vid2vid:
        capabilities.append(Capability.VID2VID)
    if hasattr(api_workflow, 'supports_img2vid') and api_workflow.supports_img2vid:
        capabilities.append(Capability.IMG2VID)
    if hasattr(api_workflow, 'supports_low_memory') and api_workflow.supports_low_memory:
        capabilities.append(Capability.LOW_MEMORY)
    
    # Build parameter list
    params = []
    
    # Always include prompt
    params.append(COMMON_PARAMETERS["prompt"])
    
    # Include common parameters based on capabilities
    if Capability.IMG2IMG in capabilities or Capability.IMG2VID in capabilities:
        params.append(COMMON_PARAMETERS["init_image"])
        params.append(COMMON_PARAMETERS["strength"])
    
    params.extend([
        COMMON_PARAMETERS["negative"],
        COMMON_PARAMETERS["seed"],
        COMMON_PARAMETERS["guidance"],
        COMMON_PARAMETERS["steps"],
        COMMON_PARAMETERS["width"],
        COMMON_PARAMETERS["height"],
        COMMON_PARAMETERS["num_images"],
        COMMON_PARAMETERS["format"],
    ])
    
    if Capability.TXT2VID in capabilities or Capability.IMG2VID in capabilities:
        params.extend([
            COMMON_PARAMETERS["fps"],
            COMMON_PARAMETERS["length"],
        ])
    
    # Add extra parameters
    if extra_params:
        params.extend(extra_params)
    
    # Extract field mappings if available
    if hasattr(api_workflow, 'field_mapping') and api_workflow.field_mapping:
        for fm in api_workflow.field_mapping:
            if hasattr(fm, 'local_field') and fm.local_field:
                # Check if we already have this parameter
                existing = [p for p in params if p.name == fm.local_field]
                if not existing:
                    params.append(ParameterDef(
                        name=fm.local_field,
                        type=ParameterType.STRING,
                        description=fm.help_text or "",
                        default=fm.default_value,
                    ))
    
    return MethodMetadata(
        slug=slug,
        display_name=slug.replace("-", " ").replace("_", " ").title(),
        category=MethodCategory.WORKFLOW,
        description=api_workflow.description or "",
        short_description=api_workflow.description[:100] + "..." if api_workflow.description and len(api_workflow.description) > 100 else (api_workflow.description or ""),
        capabilities=capabilities,
        parameters=params,
        version=getattr(api_workflow, 'version', 1),
        is_public=getattr(api_workflow, 'is_public', True),
        platform=getattr(api_workflow, 'platform', ""),
        extra_data={
            "concept_mapping": getattr(api_workflow, 'concept_mapping', None),
            "field_mapping": getattr(api_workflow, 'field_mapping', None),
            "requirements": getattr(api_workflow, 'requirements', None),
            "avg_elapsed": getattr(api_workflow, 'avg_elapsed', None),
            "peak_vram_usage": getattr(api_workflow, 'peak_vram_usage', None),
        },
        last_updated=datetime.utcnow(),
    )


def create_concept_metadata(
    slug: str,
    api_concept: Any,  # Graydient Concept object
) -> MethodMetadata:
    """
    Create MethodMetadata from a Graydient API Concept object.
    
    Args:
        slug: The concept identifier
        api_concept: Concept object from graydient.concept.all()
    
    Returns:
        Populated MethodMetadata instance
    """
    capabilities = [Capability.TXT2IMG]  # Concepts generally work with txt2img
    
    # Build preview media if available
    previews = []
    if hasattr(api_concept, 'example_url') and api_concept.example_url:
        previews.append(PreviewMedia(
            type="image",
            url=api_concept.example_url,
            caption=f"Example of {api_concept.name}",
        ))
    
    # Build tags
    tags = []
    if hasattr(api_concept, 'tags') and api_concept.tags:
        tags.extend(api_concept.tags)
    if hasattr(api_concept, 'type') and api_concept.type:
        tags.append(api_concept.type)
    if hasattr(api_concept, 'subtype_1') and api_concept.subtype_1:
        tags.append(api_concept.subtype_1)
    if hasattr(api_concept, 'subtype_2') and api_concept.subtype_2:
        tags.append(api_concept.subtype_2)
    
    return MethodMetadata(
        slug=slug,
        display_name=getattr(api_concept, 'name', slug),
        category=MethodCategory.CONCEPT,
        description=getattr(api_concept, 'description', "") or "",
        short_description=(getattr(api_concept, 'description', "") or "")[:100] + "..." if (getattr(api_concept, 'description', "") or "") else "",
        capabilities=capabilities,
        parameters=[],  # Concepts don't have parameters - they're used within prompts
        preview_media=previews,
        examples=[f"<{slug}>"],
        tags=tags,
        extra_data={
            "token": getattr(api_concept, 'token', None),
            "model_family": getattr(api_concept, 'model_family', None),
            "is_nsfw": getattr(api_concept, 'is_nsfw', False),
            "concept_hash": getattr(api_concept, 'concept_hash', None),
            "info_url": getattr(api_concept, 'info_url', None),
        },
        last_updated=datetime.utcnow(),
    )
