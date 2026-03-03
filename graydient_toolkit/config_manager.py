"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        config_manager.py                                     ║
║              Configuration Management for Graydient Toolkit                 ║
║                                                                             ║
║  Manages user preferences, method aliases, and default settings.            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class InputStyle(str, Enum):
    """Input style preferences."""
    TELEGRAM = "telegram"    # /method only
    NEGATIVE = "negative"    # [negative] only
    MIXED = "mixed"          # Both /method and [negative]
    LEGACY = "legacy"        # --flag style


class DisplayTheme(str, Enum):
    """Display theme options."""
    PHOSPHOR = "phosphor"
    AMBER = "amber"
    NEON = "neon"
    SLATE = "slate"


@dataclass
class ToolkitConfig:
    """
    Complete configuration for the Graydient Toolkit.
    
    Attributes:
        # Input Settings
        input_style: Preferred input style
        method_aliases: Custom command aliases
        
        # Default Parameters
        defaults: Default values for parameters
        
        # Display Settings
        display_theme: Visual theme
        auto_open_viewer: Auto-open browser viewer
        viewer_port: Port for viewer
        
        # Cache Settings
        cache_ttl_seconds: Cache time-to-live
        persist_cache: Save cache to disk
        
        # Behavior Settings
        auto_refresh_registry: Auto-refresh stale cache
        strict_mode: Reject unknown commands
        confirm_destructive: Confirm before clearing cache
        
        # Tutorial Settings
        show_tutorials: Show tutorials on first run
        completed_tutorials: List of completed tutorial IDs
        
        # Preview Settings
        preview_auto_download: Auto-download previews
        max_preview_size_mb: Max size for preview cache
    """
    
    # Input Settings
    input_style: InputStyle = InputStyle.MIXED
    method_aliases: Dict[str, str] = field(default_factory=dict)
    
    # Default Parameters
    defaults: Dict[str, Any] = field(default_factory=lambda: {
        "seed": None,
        "guidance": 7.5,
        "steps": 30,
        "width": 1024,
        "height": 1024,
        "num_images": 1,
        "format": "png",
    })
    
    # Display Settings
    display_theme: DisplayTheme = DisplayTheme.PHOSPHOR
    auto_open_viewer: bool = True
    viewer_port: int = 7788
    
    # Cache Settings
    cache_ttl_seconds: float = 3600  # 1 hour
    persist_cache: bool = True
    
    # Behavior Settings
    auto_refresh_registry: bool = True
    strict_mode: bool = False
    confirm_destructive: bool = True
    
    # Tutorial Settings
    show_tutorials: bool = True
    completed_tutorials: List[str] = field(default_factory=list)
    
    # Preview Settings
    preview_auto_download: bool = False
    max_preview_size_mb: float = 500
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "input_style": self.input_style.value,
            "method_aliases": self.method_aliases,
            "defaults": self.defaults,
            "display_theme": self.display_theme.value,
            "auto_open_viewer": self.auto_open_viewer,
            "viewer_port": self.viewer_port,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "persist_cache": self.persist_cache,
            "auto_refresh_registry": self.auto_refresh_registry,
            "strict_mode": self.strict_mode,
            "confirm_destructive": self.confirm_destructive,
            "show_tutorials": self.show_tutorials,
            "completed_tutorials": self.completed_tutorials,
            "preview_auto_download": self.preview_auto_download,
            "max_preview_size_mb": self.max_preview_size_mb,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ToolkitConfig:
        """Create from dictionary."""
        return cls(
            input_style=InputStyle(data.get("input_style", "mixed")),
            method_aliases=data.get("method_aliases", {}),
            defaults=data.get("defaults", {}),
            display_theme=DisplayTheme(data.get("display_theme", "phosphor")),
            auto_open_viewer=data.get("auto_open_viewer", True),
            viewer_port=data.get("viewer_port", 7788),
            cache_ttl_seconds=data.get("cache_ttl_seconds", 3600),
            persist_cache=data.get("persist_cache", True),
            auto_refresh_registry=data.get("auto_refresh_registry", True),
            strict_mode=data.get("strict_mode", False),
            confirm_destructive=data.get("confirm_destructive", True),
            show_tutorials=data.get("show_tutorials", True),
            completed_tutorials=data.get("completed_tutorials", []),
            preview_auto_download=data.get("preview_auto_download", False),
            max_preview_size_mb=data.get("max_preview_size_mb", 500),
        )


class ConfigManager:
    """
    Manages toolkit configuration with persistence.
    
    Handles loading, saving, and accessing user preferences.
    Supports both file-based and environment-based configuration.
    
    Example:
        >>> from graydient_toolkit import ConfigManager
        >>> 
        >>> config = ConfigManager()
        >>> 
        >>> # Get a setting
        >>> print(config.get("viewer_port"))  # 7788
        >>> 
        >>> # Set a setting
        >>> config.set("viewer_port", 8888)
        >>> 
        >>> # Add method alias
        >>> config.add_alias("p", "portrait")
        >>> 
        >>> # Save changes
        >>> config.save()
    """
    
    DEFAULT_ALIASES = {
        "d": "draw",
        "a": "animate",
        "s": "style",
        "u": "upscale",
        "i2i": "img2img",
        "e": "edit",
        "v": "video",
        "r": "remix",
    }
    
    def __init__(
        self,
        config_dir: Optional[Path] = None,
        config_file: str = "config.json",
        auto_save: bool = False,
    ):
        """
        Initialize the config manager.
        
        Args:
            config_dir: Directory for config files (default: ~/.graydient_toolkit)
            config_file: Name of config file
            auto_save: Auto-save on every change
        """
        self._config_dir = config_dir or Path.home() / ".graydient_toolkit"
        self._config_file = self._config_dir / config_file
        self._auto_save = auto_save
        
        # Ensure directory exists
        self._config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create config
        self._config = self._load()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Core Access Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key (supports dot notation: "defaults.seed")
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        # Support dot notation
        if "." in key:
            parts = key.split(".")
            value = self._config
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value
        
        return getattr(self._config, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
        """
        # Support dot notation for dict values
        if "." in key:
            parts = key.split(".")
            target = self._config
            for part in parts[:-1]:
                if not hasattr(target, part):
                    setattr(target, part, {})
                target = getattr(target, part)
            target[parts[-1]] = value
        else:
            setattr(self._config, key, value)
        
        if self._auto_save:
            self.save()
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get default parameters."""
        return dict(self._config.defaults)
    
    def set_default(self, param: str, value: Any) -> None:
        """Set a default parameter value."""
        self._config.defaults[param] = value
        if self._auto_save:
            self.save()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Method Aliases
    # ─────────────────────────────────────────────────────────────────────────
    
    def add_alias(self, alias: str, target: str) -> None:
        """
        Add a method alias.
        
        Args:
            alias: Short alias (e.g., "d")
            target: Full command (e.g., "draw")
        """
        self._config.method_aliases[alias] = target
        if self._auto_save:
            self.save()
    
    def remove_alias(self, alias: str) -> None:
        """Remove a method alias."""
        if alias in self._config.method_aliases:
            del self._config.method_aliases[alias]
            if self._auto_save:
                self.save()
    
    def get_aliases(self) -> Dict[str, str]:
        """Get all method aliases."""
        return {**self.DEFAULT_ALIASES, **self._config.method_aliases}
    
    def resolve_alias(self, alias: str) -> Optional[str]:
        """Resolve an alias to its target."""
        aliases = self.get_aliases()
        return aliases.get(alias)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Tutorial Tracking
    # ─────────────────────────────────────────────────────────────────────────
    
    def mark_tutorial_completed(self, tutorial_id: str) -> None:
        """Mark a tutorial as completed."""
        if tutorial_id not in self._config.completed_tutorials:
            self._config.completed_tutorials.append(tutorial_id)
            if self._auto_save:
                self.save()
    
    def is_tutorial_completed(self, tutorial_id: str) -> bool:
        """Check if a tutorial has been completed."""
        return tutorial_id in self._config.completed_tutorials
    
    def reset_tutorials(self) -> None:
        """Reset tutorial completion status."""
        self._config.completed_tutorials = []
        if self._auto_save:
            self.save()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────────────────
    
    def save(self) -> bool:
        """
        Save configuration to disk.
        
        Returns:
            True if successful
        """
        try:
            with open(self._config_file, 'w') as f:
                json.dump(self._config.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")
            return False
    
    def _load(self) -> ToolkitConfig:
        """Load configuration from disk or create default."""
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r') as f:
                    data = json.load(f)
                return ToolkitConfig.from_dict(data)
            except Exception as e:
                print(f"Warning: Failed to load config, using defaults: {e}")
        
        return ToolkitConfig()
    
    def reset(self) -> None:
        """Reset to default configuration."""
        self._config = ToolkitConfig()
        self.save()
    
    def export(self, filepath: str) -> bool:
        """Export configuration to a file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(self._config.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False
    
    def import_config(self, filepath: str) -> bool:
        """Import configuration from a file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            self._config = ToolkitConfig.from_dict(data)
            self.save()
            return True
        except Exception as e:
            print(f"Error importing config: {e}")
            return False
    
    # ─────────────────────────────────────────────────────────────────────────
    # Environment Integration
    # ─────────────────────────────────────────────────────────────────────────
    
    def load_from_env(self, prefix: str = "GRAYDIENT_") -> None:
        """
        Load configuration from environment variables.
        
        Environment variables should be named like:
            GRAYDIENT_VIEWER_PORT=8888
            GRAYDIENT_DEFAULTS_SEED=42
        """
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                
                # Try to parse value
                parsed_value = self._parse_env_value(value)
                
                # Handle nested keys
                if "_" in config_key:
                    parts = config_key.split("_")
                    if parts[0] == "defaults" and len(parts) > 1:
                        self.set_default("_".join(parts[1:]), parsed_value)
                    else:
                        self.set(config_key, parsed_value)
                else:
                    self.set(config_key, parsed_value)
    
    def _parse_env_value(self, value: str) -> Union[str, int, float, bool]:
        """Parse an environment variable value."""
        # Try boolean
        if value.lower() in ("true", "1", "yes"):
            return True
        if value.lower() in ("false", "0", "no"):
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
        
        return value
    
    # ─────────────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────────────
    
    def print_summary(self) -> None:
        """Print configuration summary."""
        print("=" * 50)
        print("Toolkit Configuration")
        print("=" * 50)
        print(f"Config file: {self._config_file}")
        print(f"Input style: {self._config.input_style.value}")
        print(f"Display theme: {self._config.display_theme.value}")
        print(f"Viewer port: {self._config.viewer_port}")
        print(f"Cache TTL: {self._config.cache_ttl_seconds}s")
        print(f"\nDefault Parameters:")
        for key, value in self._config.defaults.items():
            print(f"  {key}: {value}")
        print(f"\nMethod Aliases:")
        for alias, target in self.get_aliases().items():
            print(f"  {alias} → {target}")
        print(f"\nCompleted Tutorials: {len(self._config.completed_tutorials)}")
    
    @property
    def config(self) -> ToolkitConfig:
        """Get the raw config object."""
        return self._config
