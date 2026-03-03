"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        tutorial/engine.py                                    ║
║                    Tutorial Engine Core                                     ║
║                                                                             ║
║  Manages tutorial state, step progression, and event handling.              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union


class TutorialStatus(Enum):
    """Status of a tutorial session."""
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    PAUSED = auto()
    COMPLETED = auto()
    SKIPPED = auto()


class StepTrigger(Enum):
    """Types of triggers that can advance a tutorial step."""
    CLICK = auto()           # User clicks on highlighted element
    INPUT = auto()           # User types input
    DELAY = auto()           # Time-based delay
    MANUAL = auto()          # User clicks "Next" button
    EVENT = auto()           # Custom event
    CONDITION = auto()       # Condition becomes true


@dataclass
class HighlightRegion:
    """
    Defines a screen region to highlight.
    
    Attributes:
        x: X coordinate (pixels or percentage)
        y: Y coordinate (pixels or percentage)
        width: Region width
        height: Region height
        use_percent: If True, coordinates are percentages (0-100)
        padding: Extra padding around the region
        shape: "rectangle", "circle", or "rounded"
        color: Highlight color (hex)
        opacity: Background dim opacity (0-1)
    """
    x: float
    y: float
    width: float
    height: float
    use_percent: bool = True
    padding: int = 10
    shape: str = "rectangle"
    color: str = "#00ff41"
    opacity: float = 0.7
    
    def to_css(self, container_width: int = 1920, container_height: int = 1080) -> Dict[str, str]:
        """Convert to CSS style dictionary."""
        if self.use_percent:
            left = f"{self.x}%"
            top = f"{self.y}%"
            width = f"{self.width}%"
            height = f"{self.height}%"
        else:
            left = f"{self.x}px"
            top = f"{self.y}px"
            width = f"{self.width}px"
            height = f"{self.height}px"
        
        border_radius = "50%" if self.shape == "circle" else "8px" if self.shape == "rounded" else "0"
        
        return {
            "position": "absolute",
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "border": f"3px solid {self.color}",
            "borderRadius": border_radius,
            "boxShadow": f"0 0 20px {self.color}80, 0 0 40px {self.color}40",
            "pointerEvents": "none",
            "zIndex": "10000",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "use_percent": self.use_percent,
            "padding": self.padding,
            "shape": self.shape,
            "color": self.color,
            "opacity": self.opacity,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HighlightRegion:
        return cls(**data)


@dataclass
class MediaContent:
    """Media content for annotations (image, video, slideshow)."""
    media_type: str  # "image", "video", "slideshow"
    src: Union[str, List[str]]  # Path or list of paths for slideshow
    caption: str = ""
    autoplay: bool = False
    loop: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "media_type": self.media_type,
            "src": self.src,
            "caption": self.caption,
            "autoplay": self.autoplay,
            "loop": self.loop,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MediaContent:
        return cls(**data)


@dataclass
class TutorialStep:
    """
    A single step in a tutorial.
    
    Attributes:
        id: Unique step identifier
        title: Step title
        text: Main instructional text
        highlight: Screen region to highlight
        media: Optional media content (image/video/slideshow)
        trigger: How to advance to next step
        trigger_data: Additional data for the trigger
        actions: List of allowed user actions
        skippable: Whether this step can be skipped
        auto_advance_delay: Auto-advance delay in seconds
    """
    id: str
    title: str
    text: str
    highlight: Optional[HighlightRegion] = None
    media: Optional[MediaContent] = None
    trigger: StepTrigger = StepTrigger.MANUAL
    trigger_data: Dict[str, Any] = field(default_factory=dict)
    actions: List[str] = field(default_factory=lambda: ["next", "skip", "back"])
    skippable: bool = True
    auto_advance_delay: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "highlight": self.highlight.to_dict() if self.highlight else None,
            "media": self.media.to_dict() if self.media else None,
            "trigger": self.trigger.name,
            "trigger_data": self.trigger_data,
            "actions": self.actions,
            "skippable": self.skippable,
            "auto_advance_delay": self.auto_advance_delay,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TutorialStep:
        return cls(
            id=data["id"],
            title=data["title"],
            text=data["text"],
            highlight=HighlightRegion.from_dict(data["highlight"]) if data.get("highlight") else None,
            media=MediaContent.from_dict(data["media"]) if data.get("media") else None,
            trigger=StepTrigger[data.get("trigger", "MANUAL")],
            trigger_data=data.get("trigger_data", {}),
            actions=data.get("actions", ["next", "skip", "back"]),
            skippable=data.get("skippable", True),
            auto_advance_delay=data.get("auto_advance_delay"),
        )


@dataclass
class TutorialDefinition:
    """
    Complete tutorial definition.
    
    Attributes:
        id: Unique tutorial identifier
        title: Tutorial title
        description: Brief description
        version: Tutorial version
        author: Tutorial creator
        category: Tutorial category
        difficulty: "beginner", "intermediate", "advanced"
        estimated_duration_minutes: Estimated time to complete
        steps: List of tutorial steps
        prerequisites: List of prerequisite tutorial IDs
        tags: Categorization tags
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    id: str
    title: str
    description: str = ""
    version: str = "1.0"
    author: str = ""
    category: str = "general"
    difficulty: str = "beginner"
    estimated_duration_minutes: int = 5
    steps: List[TutorialStep] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    @property
    def step_count(self) -> int:
        """Get the number of steps."""
        return len(self.steps)
    
    def get_step(self, step_id: str) -> Optional[TutorialStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_step_index(self, step_id: str) -> int:
        """Get the index of a step."""
        for i, step in enumerate(self.steps):
            if step.id == step_id:
                return i
        return -1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "category": self.category,
            "difficulty": self.difficulty,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "steps": [s.to_dict() for s in self.steps],
            "prerequisites": self.prerequisites,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TutorialDefinition:
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            author=data.get("author", ""),
            category=data.get("category", "general"),
            difficulty=data.get("difficulty", "beginner"),
            estimated_duration_minutes=data.get("estimated_duration_minutes", 5),
            steps=[TutorialStep.from_dict(s) for s in data.get("steps", [])],
            prerequisites=data.get("prerequisites", []),
            tags=data.get("tags", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )
    
    def save(self, filepath: Union[str, Path]) -> None:
        """Save tutorial to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, filepath: Union[str, Path]) -> TutorialDefinition:
        """Load tutorial from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class TutorialSession:
    """Tracks the state of an active tutorial session."""
    tutorial_id: str
    current_step_index: int = 0
    status: TutorialStatus = TutorialStatus.NOT_STARTED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_steps: List[str] = field(default_factory=list)
    skipped_steps: List[str] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def progress_percent(self) -> float:
        """Get completion percentage."""
        if not self.completed_steps:
            return 0.0
        # This will be calculated based on total steps
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tutorial_id": self.tutorial_id,
            "current_step_index": self.current_step_index,
            "status": self.status.name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "completed_steps": self.completed_steps,
            "skipped_steps": self.skipped_steps,
            "events": self.events,
        }


class TutorialEngine:
    """
    Engine for running interactive tutorials.
    
    Manages tutorial state, step progression, and coordinates
    between the highlight overlay and annotation panel.
    
    Example:
        >>> from graydient_toolkit.tutorial import TutorialEngine
        >>> 
        >>> engine = TutorialEngine()
        >>> engine.load_tutorial("getting-started")
        >>> 
        >>> # Start the tutorial
        >>> engine.start()
        >>> 
        >>> # Navigate steps
        >>> engine.next_step()
        >>> engine.previous_step()
        >>> 
        >>> # Get current step info
        >>> step = engine.current_step
        >>> print(step.title)
        >>> print(step.text)
    """
    
    def __init__(
        self,
        tutorials_dir: Optional[Path] = None,
        on_step_change: Optional[Callable[[TutorialStep, int], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
        on_skip: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the tutorial engine.
        
        Args:
            tutorials_dir: Directory containing tutorial JSON files
            on_step_change: Callback when step changes
            on_complete: Callback when tutorial completes
            on_skip: Callback when tutorial is skipped
        """
        self._tutorials_dir = tutorials_dir or Path.home() / ".graydient_toolkit" / "tutorials"
        self._tutorials_dir.mkdir(parents=True, exist_ok=True)
        
        self._on_step_change = on_step_change
        self._on_complete = on_complete
        self._on_skip = on_skip
        
        self._current_tutorial: Optional[TutorialDefinition] = None
        self._session: Optional[TutorialSession] = None
        self._tutorials: Dict[str, TutorialDefinition] = {}
        
        # Load available tutorials
        self._load_tutorials()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Tutorial Management
    # ─────────────────────────────────────────────────────────────────────────
    
    def _load_tutorials(self) -> None:
        """Load all tutorial definitions from disk."""
        if not self._tutorials_dir.exists():
            return
        
        for file_path in self._tutorials_dir.glob("*.json"):
            try:
                tutorial = TutorialDefinition.load(file_path)
                self._tutorials[tutorial.id] = tutorial
            except Exception as e:
                print(f"Warning: Failed to load tutorial {file_path}: {e}")
    
    def list_tutorials(self) -> List[Dict[str, Any]]:
        """List all available tutorials."""
        return [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "difficulty": t.difficulty,
                "estimated_duration": t.estimated_duration_minutes,
                "step_count": t.step_count,
                "category": t.category,
                "tags": t.tags,
            }
            for t in self._tutorials.values()
        ]
    
    def get_tutorial(self, tutorial_id: str) -> Optional[TutorialDefinition]:
        """Get a tutorial by ID."""
        return self._tutorials.get(tutorial_id)
    
    def load_tutorial(self, tutorial_id: str) -> bool:
        """
        Load a tutorial for execution.
        
        Args:
            tutorial_id: Tutorial identifier
        
        Returns:
            True if loaded successfully
        """
        tutorial = self._tutorials.get(tutorial_id)
        if not tutorial:
            # Try loading from file
            file_path = self._tutorials_dir / f"{tutorial_id}.json"
            if file_path.exists():
                try:
                    tutorial = TutorialDefinition.load(file_path)
                    self._tutorials[tutorial_id] = tutorial
                except Exception as e:
                    print(f"Error loading tutorial: {e}")
                    return False
            else:
                print(f"Tutorial not found: {tutorial_id}")
                return False
        
        self._current_tutorial = tutorial
        self._session = TutorialSession(tutorial_id=tutorial_id)
        return True
    
    def register_tutorial(self, tutorial: TutorialDefinition) -> None:
        """Register a tutorial definition."""
        self._tutorials[tutorial.id] = tutorial
        
        # Save to disk
        file_path = self._tutorials_dir / f"{tutorial.id}.json"
        tutorial.save(file_path)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Session Control
    # ─────────────────────────────────────────────────────────────────────────
    
    def start(self) -> bool:
        """
        Start the loaded tutorial.
        
        Returns:
            True if started successfully
        """
        if not self._current_tutorial or not self._session:
            print("No tutorial loaded. Call load_tutorial() first.")
            return False
        
        self._session.status = TutorialStatus.IN_PROGRESS
        self._session.started_at = datetime.utcnow()
        self._session.current_step_index = 0
        
        # Trigger step change callback
        if self._on_step_change:
            self._on_step_change(self.current_step, 0)
        
        return True
    
    def stop(self) -> None:
        """Stop the current tutorial."""
        if self._session:
            self._session.status = TutorialStatus.PAUSED
    
    def skip(self) -> None:
        """Skip the current tutorial."""
        if self._session:
            self._session.status = TutorialStatus.SKIPPED
            if self._on_skip:
                self._on_skip()
    
    def complete(self) -> None:
        """Mark the tutorial as completed."""
        if self._session:
            self._session.status = TutorialStatus.COMPLETED
            self._session.completed_at = datetime.utcnow()
            if self._on_complete:
                self._on_complete()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step Navigation
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    def current_step(self) -> Optional[TutorialStep]:
        """Get the current tutorial step."""
        if not self._current_tutorial or not self._session:
            return None
        
        idx = self._session.current_step_index
        if 0 <= idx < len(self._current_tutorial.steps):
            return self._current_tutorial.steps[idx]
        return None
    
    @property
    def current_step_number(self) -> int:
        """Get the current step number (1-indexed)."""
        if self._session:
            return self._session.current_step_index + 1
        return 0
    
    @property
    def total_steps(self) -> int:
        """Get the total number of steps."""
        if self._current_tutorial:
            return len(self._current_tutorial.steps)
        return 0
    
    @property
    def progress_percent(self) -> float:
        """Get the completion percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.current_step_number / self.total_steps) * 100
    
    def next_step(self) -> bool:
        """
        Advance to the next step.
        
        Returns:
            True if advanced, False if at end
        """
        if not self._current_tutorial or not self._session:
            return False
        
        # Mark current step as completed
        current = self.current_step
        if current and current.id not in self._session.completed_steps:
            self._session.completed_steps.append(current.id)
        
        # Advance
        if self._session.current_step_index < len(self._current_tutorial.steps) - 1:
            self._session.current_step_index += 1
            
            if self._on_step_change:
                self._on_step_change(self.current_step, self._session.current_step_index)
            
            return True
        else:
            # At end - complete tutorial
            self.complete()
            return False
    
    def previous_step(self) -> bool:
        """
        Go back to the previous step.
        
        Returns:
            True if went back, False if at start
        """
        if not self._session:
            return False
        
        if self._session.current_step_index > 0:
            self._session.current_step_index -= 1
            
            if self._on_step_change:
                self._on_step_change(self.current_step, self._session.current_step_index)
            
            return True
        return False
    
    def go_to_step(self, step_id: str) -> bool:
        """
        Jump to a specific step.
        
        Args:
            step_id: Step identifier
        
        Returns:
            True if step found and jumped to
        """
        if not self._current_tutorial:
            return False
        
        idx = self._current_tutorial.get_step_index(step_id)
        if idx >= 0:
            self._session.current_step_index = idx
            
            if self._on_step_change:
                self._on_step_change(self.current_step, idx)
            
            return True
        return False
    
    def skip_step(self) -> bool:
        """
        Skip the current step.
        
        Returns:
            True if skipped, False if step not skippable
        """
        current = self.current_step
        if not current or not current.skippable:
            return False
        
        if current.id not in self._session.skipped_steps:
            self._session.skipped_steps.append(current.id)
        
        return self.next_step()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Event Handling
    # ─────────────────────────────────────────────────────────────────────────
    
    def handle_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Handle a user event.
        
        Args:
            event_type: Type of event ("click", "input", etc.)
            data: Event data
        """
        if not self._session:
            return
        
        # Log event
        self._session.events.append({
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "step_index": self._session.current_step_index,
        })
        
        # Check if event triggers step advancement
        current = self.current_step
        if not current:
            return
        
        if current.trigger == StepTrigger.CLICK and event_type == "click":
            # Check if click was in highlighted region
            if self._is_click_in_highlight(data):
                self.next_step()
        
        elif current.trigger == StepTrigger.INPUT and event_type == "input":
            # Check if input matches expected
            expected = current.trigger_data.get("expected_value")
            if expected and data.get("value") == expected:
                self.next_step()
        
        elif current.trigger == StepTrigger.EVENT and event_type == current.trigger_data.get("event_type"):
            self.next_step()
    
    def _is_click_in_highlight(self, click_data: Dict[str, Any]) -> bool:
        """Check if a click was within the highlighted region."""
        current = self.current_step
        if not current or not current.highlight:
            return False
        
        highlight = current.highlight
        click_x = click_data.get("x", 0)
        click_y = click_data.get("y", 0)
        
        # Simple rectangle check (can be enhanced for circles)
        if highlight.use_percent:
            # Assume click is also in percent
            return (
                highlight.x <= click_x <= highlight.x + highlight.width
                and highlight.y <= click_y <= highlight.y + highlight.height
            )
        else:
            return (
                highlight.x <= click_x <= highlight.x + highlight.width
                and highlight.y <= click_y <= highlight.y + highlight.height
            )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the current session."""
        if not self._session:
            return {}
        
        return {
            "tutorial_id": self._session.tutorial_id,
            "status": self._session.status.name,
            "current_step": self.current_step_number,
            "total_steps": self.total_steps,
            "progress_percent": self.progress_percent,
            "completed_steps": len(self._session.completed_steps),
            "skipped_steps": len(self._session.skipped_steps),
        }
    
    def save_session(self) -> None:
        """Save the current session state."""
        if not self._session:
            return
        
        sessions_dir = self._tutorials_dir / "sessions"
        sessions_dir.mkdir(exist_ok=True)
        
        file_path = sessions_dir / f"{self._session.tutorial_id}_session.json"
        with open(file_path, 'w') as f:
            json.dump(self._session.to_dict(), f, indent=2)
    
    def load_session(self, tutorial_id: str) -> bool:
        """Load a saved session."""
        sessions_dir = self._tutorials_dir / "sessions"
        file_path = sessions_dir / f"{tutorial_id}_session.json"
        
        if not file_path.exists():
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            self._session = TutorialSession(**data)
            return self.load_tutorial(tutorial_id)
        except Exception as e:
            print(f"Error loading session: {e}")
            return False
