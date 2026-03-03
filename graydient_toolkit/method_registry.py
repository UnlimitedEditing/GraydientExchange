"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        method_registry.py                                    ║
║              Dynamic Method Discovery for Graydient Toolkit                 ║
║                                                                             ║
║  Fetches and caches workflows and concepts from the Graydient API.          ║
║  Provides auto-refresh, search, and metadata management.                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

from .method_metadata import (
    MethodMetadata,
    MethodCategory,
    create_workflow_metadata,
    create_concept_metadata,
)


class CachePolicy:
    """Configuration for caching behavior."""
    
    def __init__(
        self,
        ttl_seconds: float = 3600,  # 1 hour default
        max_cache_size_mb: float = 100,
        persist_to_disk: bool = True,
        cache_dir: Optional[Path] = None,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_cache_size_mb = max_cache_size_mb
        self.persist_to_disk = persist_to_disk
        self.cache_dir = cache_dir or Path.home() / ".graydient_toolkit" / "cache"


class MethodRegistry:
    """
    Registry for Graydient methods with dynamic discovery and caching.
    
    This class manages the discovery, caching, and retrieval of workflows
    and concepts from the Graydient API. It provides:
    
    - Dynamic fetching from API endpoints
    - In-memory and disk caching with TTL
    - Search and filtering capabilities
    - Command name mapping for Telegram-style commands
    - Offline mode with cached data
    
    Example:
        >>> from graydient_exchange import Exchange
        >>> from graydient_toolkit import MethodRegistry
        >>> 
        >>> exchange = Exchange(api_key="your_key")
        >>> registry = MethodRegistry(exchange)
        >>> 
        >>> # Refresh from API
        >>> registry.refresh()
        >>> 
        >>> # Search workflows
        >>> workflows = registry.search_workflows("portrait")
        >>> 
        >>> # Get by slug
        >>> qwen = registry.get_workflow("qwen")
        >>> print(qwen.description)
        
        >>> # Get command mapping
        >>> cmd_map = registry.get_command_mapping()
        >>> print(cmd_map["/draw"])  # "qwen"
    """
    
    # Default command mappings for Telegram-style commands
    DEFAULT_COMMAND_MAP = {
        "/draw": "qwen",
        "/d": "qwen",
        "/animate": "animate-wan22",
        "/a": "animate-wan22",
        "/style": "edit-qwen",
        "/s": "edit-qwen",
        "/upscale": "upscale",
        "/u": "upscale",
        "/img2img": "edit-qwen",
        "/i2i": "edit-qwen",
        "/edit": "edit-qwen",
        "/e": "edit-qwen",
        "/video": "txt2vid",
        "/v": "txt2vid",
        "/remix": "remix",
        "/r": "remix",
    }
    
    def __init__(
        self,
        exchange: Any,  # Graydient Exchange instance
        cache_policy: Optional[CachePolicy] = None,
        command_map: Optional[Dict[str, str]] = None,
        auto_refresh: bool = False,
    ):
        """
        Initialize the MethodRegistry.
        
        Args:
            exchange: Graydient Exchange instance for API calls
            cache_policy: Caching configuration
            command_map: Custom command → workflow mappings
            auto_refresh: Whether to auto-refresh on stale cache access
        """
        self._exchange = exchange
        self._cache_policy = cache_policy or CachePolicy()
        self._command_map = {**self.DEFAULT_COMMAND_MAP, **(command_map or {})}
        self._auto_refresh = auto_refresh
        
        # In-memory cache
        self._workflows: Dict[str, MethodMetadata] = {}
        self._concepts: Dict[str, MethodMetadata] = {}
        self._commands: Dict[str, MethodMetadata] = {}  # Command methods
        self._last_refresh: Optional[datetime] = None
        
        # Ensure cache directory exists
        if self._cache_policy.persist_to_disk:
            self._cache_policy.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to load from disk cache
        self._load_from_disk()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    def is_cached(self) -> bool:
        """Check if we have any cached data."""
        return len(self._workflows) > 0 or len(self._concepts) > 0
    
    @property
    def is_stale(self) -> bool:
        """Check if the cache is stale (past TTL)."""
        if self._last_refresh is None:
            return True
        age = (datetime.utcnow() - self._last_refresh).total_seconds()
        return age > self._cache_policy.ttl_seconds
    
    @property
    def cache_age_seconds(self) -> float:
        """Get the age of the cache in seconds."""
        if self._last_refresh is None:
            return float('inf')
        return (datetime.utcnow() - self._last_refresh).total_seconds()
    
    @property
    def all_workflows(self) -> List[MethodMetadata]:
        """Get all cached workflows."""
        if self._auto_refresh and self.is_stale:
            self.refresh()
        return list(self._workflows.values())
    
    @property
    def all_concepts(self) -> List[MethodMetadata]:
        """Get all cached concepts."""
        if self._auto_refresh and self.is_stale:
            self.refresh()
        return list(self._concepts.values())
    
    @property
    def all_methods(self) -> List[MethodMetadata]:
        """Get all cached methods (workflows + concepts + commands)."""
        if self._auto_refresh and self.is_stale:
            self.refresh()
        return list(self._workflows.values()) + list(self._concepts.values()) + list(self._commands.values())
    
    # ─────────────────────────────────────────────────────────────────────────
    # Core API Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def refresh(self, force: bool = False) -> Dict[str, int]:
        """
        Refresh the registry from the Graydient API.
        
        Args:
            force: Force refresh even if cache is not stale
        
        Returns:
            Dict with counts: {"workflows": N, "concepts": M}
        """
        if not force and not self.is_stale and self.is_cached:
            return {"workflows": len(self._workflows), "concepts": len(self._concepts)}
        
        results = {"workflows": 0, "concepts": 0}
        
        try:
            # Fetch workflows
            workflow_list = self._exchange.workflows.list()
            self._workflows = {}
            
            for wf_data in workflow_list:
                slug = wf_data.get("name", "")
                if slug:
                    # Create a simple object with attributes
                    wf_obj = type('Workflow', (), wf_data)()
                    metadata = create_workflow_metadata(slug, wf_obj)
                    metadata.cached_at = datetime.utcnow()
                    self._workflows[slug] = metadata
            
            results["workflows"] = len(self._workflows)
            
            # Fetch concepts
            concept_list = self._exchange.concepts.all()
            self._concepts = {}
            
            for concept_data in concept_list:
                slug = concept_data.get("name", "") or concept_data.get("token", "")
                if slug:
                    concept_obj = type('Concept', (), concept_data)()
                    metadata = create_concept_metadata(slug, concept_obj)
                    metadata.cached_at = datetime.utcnow()
                    self._concepts[slug] = metadata
            
            results["concepts"] = len(self._concepts)
            
            # Build command methods
            self._rebuild_commands()
            
            # Update timestamp
            self._last_refresh = datetime.utcnow()
            
            # Save to disk
            self._save_to_disk()
            
        except Exception as e:
            # Log error but don't fail - use cached data if available
            print(f"Warning: Failed to refresh from API: {e}")
            if not self.is_cached:
                raise
        
        return results
    
    def get_workflow(self, slug: str) -> Optional[MethodMetadata]:
        """
        Get a workflow by its slug.
        
        Args:
            slug: Workflow slug (e.g., "qwen", "edit-qwen")
        
        Returns:
            MethodMetadata or None if not found
        """
        if self._auto_refresh and self.is_stale:
            self.refresh()
        return self._workflows.get(slug)
    
    def get_concept(self, slug: str) -> Optional[MethodMetadata]:
        """
        Get a concept by its slug/token.
        
        Args:
            slug: Concept name or token
        
        Returns:
            MethodMetadata or None if not found
        """
        if self._auto_refresh and self.is_stale:
            self.refresh()
        return self._concepts.get(slug)
    
    def get_method(self, identifier: str) -> Optional[MethodMetadata]:
        """
        Get any method (workflow, concept, or command) by identifier.
        
        Args:
            identifier: Slug, command, or name
        
        Returns:
            MethodMetadata or None if not found
        """
        if self._auto_refresh and self.is_stale:
            self.refresh()
        
        # Try workflows first
        if identifier in self._workflows:
            return self._workflows[identifier]
        
        # Try concepts
        if identifier in self._concepts:
            return self._concepts[identifier]
        
        # Try commands (resolve to workflow)
        if identifier in self._commands:
            return self._commands[identifier]
        
        # Try command map
        if identifier in self._command_map:
            workflow_slug = self._command_map[identifier]
            if workflow_slug in self._workflows:
                return self._workflows[workflow_slug]
        
        return None
    
    # ─────────────────────────────────────────────────────────────────────────
    # Search & Discovery
    # ─────────────────────────────────────────────────────────────────────────
    
    def search_workflows(
        self,
        query: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[MethodMetadata]:
        """
        Search workflows by query, capabilities, or tags.
        
        Args:
            query: Text to search in name/description
            capabilities: Filter by supported capabilities
            tags: Filter by tags
        
        Returns:
            List of matching workflows
        """
        if self._auto_refresh and self.is_stale:
            self.refresh()
        
        results = list(self._workflows.values())
        
        if query:
            query_lower = query.lower()
            results = [
                wf for wf in results
                if query_lower in wf.slug.lower()
                or query_lower in wf.display_name.lower()
                or query_lower in wf.description.lower()
                or any(query_lower in tag.lower() for tag in wf.tags)
            ]
        
        if capabilities:
            results = [
                wf for wf in results
                if all(wf.supports(cap) for cap in capabilities)
            ]
        
        if tags:
            results = [
                wf for wf in results
                if any(tag in wf.tags for tag in tags)
            ]
        
        return results
    
    def search_concepts(
        self,
        query: Optional[str] = None,
        model_family: Optional[str] = None,
        exclude_nsfw: bool = True,
    ) -> List[MethodMetadata]:
        """
        Search concepts by query or filters.
        
        Args:
            query: Text to search in name/description
            model_family: Filter by compatible model family
            exclude_nsfw: Exclude NSFW concepts
        
        Returns:
            List of matching concepts
        """
        if self._auto_refresh and self.is_stale:
            self.refresh()
        
        results = list(self._concepts.values())
        
        if query:
            query_lower = query.lower()
            results = [
                c for c in results
                if query_lower in c.slug.lower()
                or query_lower in c.display_name.lower()
                or query_lower in c.description.lower()
                or any(query_lower in tag.lower() for tag in c.tags)
            ]
        
        if model_family:
            results = [
                c for c in results
                if c.extra_data.get("model_family") == model_family
            ]
        
        if exclude_nsfw:
            results = [
                c for c in results
                if not c.extra_data.get("is_nsfw", False)
            ]
        
        return results
    
    def search(self, query: str) -> List[MethodMetadata]:
        """
        Search across all methods (workflows and concepts).
        
        Args:
            query: Search query
        
        Returns:
            List of matching methods
        """
        workflows = self.search_workflows(query)
        concepts = self.search_concepts(query)
        return workflows + concepts
    
    def get_by_capability(self, capability: str) -> List[MethodMetadata]:
        """
        Get all workflows that support a specific capability.
        
        Args:
            capability: Capability name (e.g., "txt2img", "img2vid")
        
        Returns:
            List of supporting workflows
        """
        if self._auto_refresh and self.is_stale:
            self.refresh()
        
        from .method_metadata import Capability
        cap = Capability(capability)
        
        return [wf for wf in self._workflows.values() if wf.supports(cap)]
    
    # ─────────────────────────────────────────────────────────────────────────
    # Command Mapping
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_command_mapping(self) -> Dict[str, str]:
        """
        Get the mapping of Telegram-style commands to workflow slugs.
        
        Returns:
            Dict mapping command (e.g., "/draw") to workflow slug (e.g., "qwen")
        """
        return dict(self._command_map)
    
    def set_command_mapping(self, command: str, workflow_slug: str) -> None:
        """
        Set or override a command mapping.
        
        Args:
            command: Command string (e.g., "/draw")
            workflow_slug: Target workflow slug
        """
        self._command_map[command] = workflow_slug
        self._rebuild_commands()
    
    def resolve_command(self, command: str) -> Optional[str]:
        """
        Resolve a command to its workflow slug.
        
        Args:
            command: Command string (e.g., "/draw")
        
        Returns:
            Workflow slug or None if not mapped
        """
        return self._command_map.get(command)
    
    def list_commands(self) -> List[str]:
        """Get list of all registered commands."""
        return list(self._command_map.keys())
    
    def _rebuild_commands(self) -> None:
        """Rebuild the command methods dictionary."""
        self._commands = {}
        for command, workflow_slug in self._command_map.items():
            if workflow_slug in self._workflows:
                # Create a copy with command-specific metadata
                wf = self._workflows[workflow_slug]
                cmd_metadata = MethodMetadata(
                    slug=command,
                    display_name=f"Command: {command}",
                    category=MethodCategory.COMMAND,
                    description=f"Telegram-style command that runs the '{workflow_slug}' workflow",
                    short_description=f"Runs {workflow_slug}",
                    capabilities=wf.capabilities,
                    parameters=wf.parameters,
                    examples=[f"{command} {ex}" for ex in wf.examples],
                    tags=["command"] + wf.tags,
                    extra_data={"target_workflow": workflow_slug},
                )
                self._commands[command] = cmd_metadata
    
    # ─────────────────────────────────────────────────────────────────────────
    # Cache Management
    # ─────────────────────────────────────────────────────────────────────────
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._workflows = {}
        self._concepts = {}
        self._commands = {}
        self._last_refresh = None
        
        if self._cache_policy.persist_to_disk:
            cache_file = self._cache_policy.cache_dir / "registry_cache.json"
            if cache_file.exists():
                cache_file.unlink()
    
    def _save_to_disk(self) -> None:
        """Save cache to disk."""
        if not self._cache_policy.persist_to_disk:
            return
        
        try:
            cache_data = {
                "workflows": {k: v.to_dict() for k, v in self._workflows.items()},
                "concepts": {k: v.to_dict() for k, v in self._concepts.items()},
                "command_map": self._command_map,
                "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            }
            
            cache_file = self._cache_policy.cache_dir / "registry_cache.json"
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        
        except Exception as e:
            print(f"Warning: Failed to save cache to disk: {e}")
    
    def _load_from_disk(self) -> bool:
        """Load cache from disk. Returns True if successful."""
        if not self._cache_policy.persist_to_disk:
            return False
        
        try:
            cache_file = self._cache_policy.cache_dir / "registry_cache.json"
            if not cache_file.exists():
                return False
            
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Load workflows
            for slug, data in cache_data.get("workflows", {}).items():
                self._workflows[slug] = MethodMetadata.from_dict(data)
            
            # Load concepts
            for slug, data in cache_data.get("concepts", {}).items():
                self._concepts[slug] = MethodMetadata.from_dict(data)
            
            # Load command map
            self._command_map.update(cache_data.get("command_map", {}))
            
            # Load timestamp
            last_refresh_str = cache_data.get("last_refresh")
            if last_refresh_str:
                self._last_refresh = datetime.fromisoformat(last_refresh_str)
            
            # Rebuild command methods
            self._rebuild_commands()
            
            return True
        
        except Exception as e:
            print(f"Warning: Failed to load cache from disk: {e}")
            return False
    
    # ─────────────────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the registry."""
        return {
            "workflows_count": len(self._workflows),
            "concepts_count": len(self._concepts),
            "commands_count": len(self._commands),
            "is_cached": self.is_cached,
            "is_stale": self.is_stale,
            "cache_age_seconds": self.cache_age_seconds,
            "cache_ttl_seconds": self._cache_policy.ttl_seconds,
        }
    
    def print_summary(self) -> None:
        """Print a summary of the registry contents."""
        stats = self.get_stats()
        
        print("=" * 50)
        print("Method Registry Summary")
        print("=" * 50)
        print(f"Workflows: {stats['workflows_count']}")
        print(f"Concepts:  {stats['concepts_count']}")
        print(f"Commands:  {stats['commands_count']}")
        print(f"Cached:    {'Yes' if stats['is_cached'] else 'No'}")
        print(f"Stale:     {'Yes' if stats['is_stale'] else 'No'}")
        
        if stats['cache_age_seconds'] < float('inf'):
            age_mins = stats['cache_age_seconds'] / 60
            print(f"Cache Age: {age_mins:.1f} minutes")
        
        print("\nAvailable Commands:")
        for cmd in sorted(self._command_map.keys()):
            target = self._command_map[cmd]
            print(f"  {cmd:12} → {target}")
    
    def export_to_json(self, filepath: str) -> None:
        """Export all metadata to a JSON file."""
        data = {
            "workflows": {k: v.to_dict() for k, v in self._workflows.items()},
            "concepts": {k: v.to_dict() for k, v in self._concepts.items()},
            "command_map": self._command_map,
            "exported_at": datetime.utcnow().isoformat(),
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def import_from_json(self, filepath: str) -> None:
        """Import metadata from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        for slug, wf_data in data.get("workflows", {}).items():
            self._workflows[slug] = MethodMetadata.from_dict(wf_data)
        
        for slug, c_data in data.get("concepts", {}).items():
            self._concepts[slug] = MethodMetadata.from_dict(c_data)
        
        self._command_map.update(data.get("command_map", {}))
        self._rebuild_commands()
