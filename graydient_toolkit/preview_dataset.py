"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        preview_dataset.py                                    ║
║              Preview Media Management for Graydient Toolkit                 ║
║                                                                             ║
║  Manages image and video previews for workflows and concepts.               ║
║  Supports downloading, caching, and slideshow display.                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

# Optional imports for downloading
_urllib_available = True
try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
except ImportError:
    _urllib_available = False

_requests_available = True
try:
    import requests
except ImportError:
    _requests_available = False


@dataclass
class PreviewInfo:
    """Information about a preview file."""
    path: Path
    media_type: str  # "image" or "video"
    source_url: Optional[str] = None
    caption: str = ""
    thumbnail_path: Optional[Path] = None
    downloaded_at: Optional[datetime] = None
    file_size_bytes: int = 0
    
    @property
    def exists(self) -> bool:
        """Check if the preview file exists."""
        return self.path.exists()
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return self.file_size_bytes / (1024 * 1024)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "media_type": self.media_type,
            "source_url": self.source_url,
            "caption": self.caption,
            "thumbnail_path": str(self.thumbnail_path) if self.thumbnail_path else None,
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else None,
            "file_size_bytes": self.file_size_bytes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PreviewInfo:
        return cls(
            path=Path(data["path"]),
            media_type=data["media_type"],
            source_url=data.get("source_url"),
            caption=data.get("caption", ""),
            thumbnail_path=Path(data["thumbnail_path"]) if data.get("thumbnail_path") else None,
            downloaded_at=datetime.fromisoformat(data["downloaded_at"]) if data.get("downloaded_at") else None,
            file_size_bytes=data.get("file_size_bytes", 0),
        )


class PreviewDataset:
    """
    Manages preview images and videos for Graydient methods.
    
    This class handles:
    - Downloading previews from URLs
    - Organizing previews by method slug
    - Managing cache size and cleanup
    - Serving previews for display
    
    Directory Structure:
        previews/
        ├── workflows/
        │   ├── qwen/
        │   │   ├── preview_01.jpg
        │   │   └── info.json
        │   └── edit-qwen/
        │       └── preview_01.jpg
        └── concepts/
            └── lora-style/
                └── preview.jpg
    
    Example:
        >>> from graydient_toolkit import PreviewDataset
        >>> 
        >>> previews = PreviewDataset()
        >>> 
        >>> # Download a preview
        >>> previews.download(
        ...     method_slug="qwen",
        ...     category="workflow",
        ...     url="https://example.com/preview.jpg"
        ... )
        >>> 
        >>> # Get all previews for a method
        >>> qwen_previews = previews.get_previews("qwen", "workflow")
        >>> for preview in qwen_previews:
        ...     print(preview.path)
    """
    
    SUPPORTED_IMAGE_TYPES = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    SUPPORTED_VIDEO_TYPES = {'.mp4', '.webm', '.mov'}
    
    def __init__(
        self,
        base_dir: Optional[Path] = None,
        max_size_mb: float = 500,
        auto_download: bool = False,
    ):
        """
        Initialize the preview dataset.
        
        Args:
            base_dir: Base directory for previews (default: ~/.graydient_toolkit/previews)
            max_size_mb: Maximum cache size in MB
            auto_download: Auto-download previews when requested
        """
        self._base_dir = base_dir or Path.home() / ".graydient_toolkit" / "previews"
        self._max_size_mb = max_size_mb
        self._auto_download = auto_download
        
        # Create directory structure
        self._workflows_dir = self._base_dir / "workflows"
        self._concepts_dir = self._base_dir / "concepts"
        
        self._workflows_dir.mkdir(parents=True, exist_ok=True)
        self._concepts_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for preview info
        self._preview_cache: Dict[str, List[PreviewInfo]] = {}
    
    # ─────────────────────────────────────────────────────────────────────────
    # Core Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def download(
        self,
        method_slug: str,
        category: str,  # "workflow" or "concept"
        url: str,
        caption: str = "",
        filename: Optional[str] = None,
        force: bool = False,
    ) -> Optional[PreviewInfo]:
        """
        Download a preview from a URL.
        
        Args:
            method_slug: Method identifier
            category: "workflow" or "concept"
            url: Source URL
            caption: Description of the preview
            filename: Optional custom filename
            force: Re-download even if exists
        
        Returns:
            PreviewInfo or None if download failed
        """
        if not _urllib_available and not _requests_available:
            print("Error: No HTTP library available. Install requests.")
            return None
        
        # Determine target directory
        target_dir = self._get_category_dir(category) / self._sanitize_slug(method_slug)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine filename
        if not filename:
            # Extract from URL or generate
            parsed = urlparse(url)
            filename = Path(parsed.path).name
            if not filename or '.' not in filename:
                ext = self._guess_extension(url)
                filename = f"preview_{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}"
        
        target_path = target_dir / filename
        
        # Check if already exists
        if target_path.exists() and not force:
            return self._get_preview_info(target_path, url, caption)
        
        # Download
        try:
            if _requests_available:
                response = requests.get(url, timeout=30, stream=True)
                response.raise_for_status()
                
                with open(target_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            else:
                req = Request(url, headers={'User-Agent': 'GraydientToolkit/1.0'})
                with urlopen(req, timeout=30) as response:
                    with open(target_path, 'wb') as f:
                        f.write(response.read())
            
            # Create info
            preview_info = PreviewInfo(
                path=target_path,
                media_type=self._get_media_type(target_path),
                source_url=url,
                caption=caption,
                downloaded_at=datetime.utcnow(),
                file_size_bytes=target_path.stat().st_size,
            )
            
            # Save metadata
            self._save_preview_info(method_slug, category, preview_info)
            
            # Clear cache
            cache_key = f"{category}:{method_slug}"
            if cache_key in self._preview_cache:
                del self._preview_cache[cache_key]
            
            # Check cache size
            self._enforce_size_limit()
            
            return preview_info
        
        except Exception as e:
            print(f"Error downloading preview: {e}")
            if target_path.exists():
                target_path.unlink()
            return None
    
    def add_local(
        self,
        method_slug: str,
        category: str,
        source_path: Path,
        caption: str = "",
        copy: bool = True,
    ) -> Optional[PreviewInfo]:
        """
        Add a local file as a preview.
        
        Args:
            method_slug: Method identifier
            category: "workflow" or "concept"
            source_path: Path to local file
            caption: Description
            copy: Copy file (if False, create symlink)
        
        Returns:
            PreviewInfo or None if failed
        """
        if not source_path.exists():
            print(f"Error: Source file not found: {source_path}")
            return None
        
        # Determine target directory
        target_dir = self._get_category_dir(category) / self._sanitize_slug(method_slug)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine target path
        target_path = target_dir / source_path.name
        
        try:
            if copy:
                shutil.copy2(source_path, target_path)
            else:
                if target_path.exists() or target_path.is_symlink():
                    target_path.unlink()
                target_path.symlink_to(source_path.resolve())
            
            preview_info = PreviewInfo(
                path=target_path,
                media_type=self._get_media_type(target_path),
                caption=caption,
                downloaded_at=datetime.utcnow(),
                file_size_bytes=target_path.stat().st_size,
            )
            
            self._save_preview_info(method_slug, category, preview_info)
            
            # Clear cache
            cache_key = f"{category}:{method_slug}"
            if cache_key in self._preview_cache:
                del self._preview_cache[cache_key]
            
            return preview_info
        
        except Exception as e:
            print(f"Error adding local preview: {e}")
            return None
    
    def get_previews(
        self,
        method_slug: str,
        category: str,
    ) -> List[PreviewInfo]:
        """
        Get all previews for a method.
        
        Args:
            method_slug: Method identifier
            category: "workflow" or "concept"
        
        Returns:
            List of PreviewInfo objects
        """
        cache_key = f"{category}:{method_slug}"
        
        # Check cache
        if cache_key in self._preview_cache:
            return self._preview_cache[cache_key]
        
        # Load from disk
        target_dir = self._get_category_dir(category) / self._sanitize_slug(method_slug)
        
        if not target_dir.exists():
            return []
        
        previews = []
        
        # Load from info.json if exists
        info_path = target_dir / "info.json"
        if info_path.exists():
            try:
                with open(info_path, 'r') as f:
                    data = json.load(f)
                for item in data.get("previews", []):
                    preview_info = PreviewInfo.from_dict(item)
                    if preview_info.exists:
                        previews.append(preview_info)
            except Exception:
                pass
        
        # Scan directory for files not in info.json
        existing_paths = {p.path for p in previews}
        for file_path in target_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_IMAGE_TYPES | self.SUPPORTED_VIDEO_TYPES:
                if file_path not in existing_paths:
                    preview_info = self._get_preview_info(file_path)
                    previews.append(preview_info)
        
        # Cache and return
        self._preview_cache[cache_key] = previews
        return previews
    
    def get_first_preview(
        self,
        method_slug: str,
        category: str,
    ) -> Optional[PreviewInfo]:
        """Get the first available preview for a method."""
        previews = self.get_previews(method_slug, category)
        return previews[0] if previews else None
    
    def has_preview(
        self,
        method_slug: str,
        category: str,
    ) -> bool:
        """Check if a method has any previews."""
        return len(self.get_previews(method_slug, category)) > 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # Management
    # ─────────────────────────────────────────────────────────────────────────
    
    def delete_preview(
        self,
        method_slug: str,
        category: str,
        filename: str,
    ) -> bool:
        """Delete a specific preview."""
        target_dir = self._get_category_dir(category) / self._sanitize_slug(method_slug)
        target_path = target_dir / filename
        
        if target_path.exists():
            target_path.unlink()
            
            # Clear cache
            cache_key = f"{category}:{method_slug}"
            if cache_key in self._preview_cache:
                del self._preview_cache[cache_key]
            
            return True
        
        return False
    
    def delete_all_previews(
        self,
        method_slug: str,
        category: str,
    ) -> bool:
        """Delete all previews for a method."""
        target_dir = self._get_category_dir(category) / self._sanitize_slug(method_slug)
        
        if target_dir.exists():
            shutil.rmtree(target_dir)
            
            # Clear cache
            cache_key = f"{category}:{method_slug}"
            if cache_key in self._preview_cache:
                del self._preview_cache[cache_key]
            
            return True
        
        return False
    
    def clear_cache(self) -> None:
        """Clear all cached preview info."""
        self._preview_cache.clear()
    
    def cleanup_orphans(self) -> int:
        """
        Remove orphaned preview files not tracked in info.json.
        
        Returns:
            Number of files removed
        """
        removed = 0
        
        for category_dir in [self._workflows_dir, self._concepts_dir]:
            if not category_dir.exists():
                continue
            
            for method_dir in category_dir.iterdir():
                if not method_dir.is_dir():
                    continue
                
                info_path = method_dir / "info.json"
                tracked_files = set()
                
                if info_path.exists():
                    try:
                        with open(info_path, 'r') as f:
                            data = json.load(f)
                        for item in data.get("previews", []):
                            tracked_files.add(Path(item["path"]).name)
                    except Exception:
                        pass
                
                for file_path in method_dir.iterdir():
                    if file_path.is_file() and file_path.name not in tracked_files:
                        if file_path.name != "info.json":
                            file_path.unlink()
                            removed += 1
        
        return removed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the preview dataset."""
        total_files = 0
        total_size = 0
        method_counts = {"workflows": 0, "concepts": 0}
        
        for category, category_dir in [("workflows", self._workflows_dir), ("concepts", self._concepts_dir)]:
            if not category_dir.exists():
                continue
            
            for method_dir in category_dir.iterdir():
                if not method_dir.is_dir():
                    continue
                
                method_counts[category] += 1
                
                for file_path in method_dir.iterdir():
                    if file_path.is_file() and file_path.name != "info.json":
                        total_files += 1
                        total_size += file_path.stat().st_size
        
        return {
            "total_files": total_files,
            "total_size_mb": total_size / (1024 * 1024),
            "max_size_mb": self._max_size_mb,
            "workflow_methods": method_counts["workflows"],
            "concept_methods": method_counts["concepts"],
        }
    
    def print_summary(self) -> None:
        """Print a summary of the preview dataset."""
        stats = self.get_stats()
        
        print("=" * 50)
        print("Preview Dataset Summary")
        print("=" * 50)
        print(f"Base directory: {self._base_dir}")
        print(f"Total files: {stats['total_files']}")
        print(f"Total size: {stats['total_size_mb']:.2f} MB / {stats['max_size_mb']} MB")
        print(f"Workflow methods with previews: {stats['workflow_methods']}")
        print(f"Concept methods with previews: {stats['concept_methods']}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Internal Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def _get_category_dir(self, category: str) -> Path:
        """Get the directory for a category."""
        if category == "workflow":
            return self._workflows_dir
        elif category == "concept":
            return self._concepts_dir
        else:
            raise ValueError(f"Unknown category: {category}")
    
    def _sanitize_slug(self, slug: str) -> str:
        """Sanitize a method slug for use as directory name."""
        # Replace characters that might cause issues
        return re.sub(r'[^\w\-_.]', '_', slug)
    
    def _guess_extension(self, url: str) -> str:
        """Guess file extension from URL."""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        for ext in self.SUPPORTED_IMAGE_TYPES | self.SUPPORTED_VIDEO_TYPES:
            if path.endswith(ext):
                return ext
        
        # Default to jpg
        return '.jpg'
    
    def _get_media_type(self, path: Path) -> str:
        """Determine if file is image or video."""
        ext = path.suffix.lower()
        
        if ext in self.SUPPORTED_IMAGE_TYPES:
            return "image"
        elif ext in self.SUPPORTED_VIDEO_TYPES:
            return "video"
        else:
            return "unknown"
    
    def _get_preview_info(
        self,
        path: Path,
        source_url: Optional[str] = None,
        caption: str = "",
    ) -> PreviewInfo:
        """Create PreviewInfo from a file path."""
        file_size = path.stat().st_size if path.exists() else 0
        
        return PreviewInfo(
            path=path,
            media_type=self._get_media_type(path),
            source_url=source_url,
            caption=caption,
            file_size_bytes=file_size,
        )
    
    def _save_preview_info(
        self,
        method_slug: str,
        category: str,
        preview_info: PreviewInfo,
    ) -> None:
        """Save preview info to info.json."""
        target_dir = self._get_category_dir(category) / self._sanitize_slug(method_slug)
        info_path = target_dir / "info.json"
        
        # Load existing
        data = {"previews": []}
        if info_path.exists():
            try:
                with open(info_path, 'r') as f:
                    data = json.load(f)
            except Exception:
                pass
        
        # Add or update
        previews = data.get("previews", [])
        existing = [p for p in previews if p.get("path") == str(preview_info.path)]
        
        if existing:
            existing[0].update(preview_info.to_dict())
        else:
            previews.append(preview_info.to_dict())
        
        data["previews"] = previews
        
        # Save
        with open(info_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _enforce_size_limit(self) -> None:
        """Remove old previews if cache exceeds size limit."""
        stats = self.get_stats()
        
        if stats["total_size_mb"] <= self._max_size_mb:
            return
        
        # Collect all previews with their ages
        all_previews: List[Tuple[Path, datetime, int]] = []
        
        for category_dir in [self._workflows_dir, self._concepts_dir]:
            if not category_dir.exists():
                continue
            
            for method_dir in category_dir.iterdir():
                if not method_dir.is_dir():
                    continue
                
                for file_path in method_dir.iterdir():
                    if file_path.is_file() and file_path.name != "info.json":
                        stat = file_path.stat()
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        all_previews.append((file_path, mtime, stat.st_size))
        
        # Sort by modification time (oldest first)
        all_previews.sort(key=lambda x: x[1])
        
        # Remove oldest until under limit
        current_size = stats["total_size_mb"]
        for file_path, _, file_size in all_previews:
            if current_size <= self._max_size_mb:
                break
            
            file_path.unlink()
            current_size -= file_size / (1024 * 1024)


# Regex for _sanitize_slug
import re
