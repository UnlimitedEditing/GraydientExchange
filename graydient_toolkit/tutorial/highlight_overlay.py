"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    tutorial/highlight_overlay.py                             ║
║                    Screen Highlighting Component                            ║
║                                                                             ║
║  Provides visual highlighting of screen regions for tutorials.              ║
║  Can be used with tkinter, web, or other UI frameworks.                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .engine import HighlightRegion


@dataclass
class RenderedHighlight:
    """A highlight that has been rendered to a UI."""
    region: HighlightRegion
    elements: List[Any]  # UI-specific element references
    canvas_id: Optional[str] = None


class HighlightOverlay:
    """
    Manages screen highlight overlays for tutorials.
    
    This is an abstract base class. Framework-specific implementations
    should subclass this and implement the render methods.
    
    Example (Tkinter implementation):
        >>> from graydient_toolkit.tutorial import HighlightOverlay, HighlightRegion
        >>> 
        >>> class TkinterHighlightOverlay(HighlightOverlay):
        ...     def __init__(self, canvas):
        ...         super().__init__()
        ...         self.canvas = canvas
        ...     
        ...     def _render_impl(self, region):
        ...         # Draw highlight on canvas
        ...         x, y, w, h = self._to_pixels(region)
        ...         rect = self.canvas.create_rectangle(
        ...             x, y, x+w, y+h,
        ...             outline=region.color,
        ...             width=3
        ...         )
        ...         return RenderedHighlight(region, [rect])
    """
    
    def __init__(self):
        self._active_highlights: Dict[str, RenderedHighlight] = {}
        self._container_width: int = 1920
        self._container_height: int = 1080
        self._on_click: Optional[Callable[[float, float], None]] = None
    
    def set_container_size(self, width: int, height: int) -> None:
        """Set the container dimensions for coordinate conversion."""
        self._container_width = width
        self._container_height = height
    
    def set_click_handler(self, handler: Callable[[float, float], None]) -> None:
        """Set a handler for click events on the overlay."""
        self._on_click = handler
    
    def show(self, region: HighlightRegion, highlight_id: str = "default") -> RenderedHighlight:
        """
        Show a highlight region.
        
        Args:
            region: Region to highlight
            highlight_id: Unique identifier for this highlight
        
        Returns:
            RenderedHighlight instance
        """
        # Clear existing highlight with same ID
        self.hide(highlight_id)
        
        # Render new highlight
        rendered = self._render_impl(region)
        self._active_highlights[highlight_id] = rendered
        
        return rendered
    
    def hide(self, highlight_id: str = "default") -> None:
        """Hide a specific highlight."""
        if highlight_id in self._active_highlights:
            rendered = self._active_highlights[highlight_id]
            self._clear_impl(rendered)
            del self._active_highlights[highlight_id]
    
    def hide_all(self) -> None:
        """Hide all active highlights."""
        for highlight_id in list(self._active_highlights.keys()):
            self.hide(highlight_id)
    
    def update(self, highlight_id: str, region: HighlightRegion) -> None:
        """Update an existing highlight."""
        self.hide(highlight_id)
        self.show(region, highlight_id)
    
    def pulse(self, highlight_id: str = "default", duration_ms: int = 1000) -> None:
        """
        Add a pulsing animation to a highlight.
        
        Args:
            highlight_id: Highlight to animate
            duration_ms: Animation duration in milliseconds
        """
        if highlight_id in self._active_highlights:
            self._pulse_impl(self._active_highlights[highlight_id], duration_ms)
    
    def _to_pixels(self, region: HighlightRegion) -> Tuple[int, int, int, int]:
        """Convert region coordinates to pixels."""
        if region.use_percent:
            x = int((region.x / 100) * self._container_width)
            y = int((region.y / 100) * self._container_height)
            w = int((region.width / 100) * self._container_width)
            h = int((region.height / 100) * self._container_height)
        else:
            x, y, w, h = int(region.x), int(region.y), int(region.width), int(region.height)
        
        # Apply padding
        x -= region.padding
        y -= region.padding
        w += region.padding * 2
        h += region.padding * 2
        
        return x, y, w, h
    
    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Methods (to be implemented by subclasses)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_impl(self, region: HighlightRegion) -> RenderedHighlight:
        """
        Render a highlight region to the UI.
        
        Must be implemented by subclasses.
        
        Returns:
            RenderedHighlight with UI element references
        """
        raise NotImplementedError("Subclasses must implement _render_impl")
    
    def _clear_impl(self, rendered: RenderedHighlight) -> None:
        """
        Clear a rendered highlight from the UI.
        
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _clear_impl")
    
    def _pulse_impl(self, rendered: RenderedHighlight, duration_ms: int) -> None:
        """
        Add pulsing animation to a highlight.
        
        Optional - can be implemented by subclasses.
        """
        pass  # Optional implementation


class HTMLHighlightOverlay(HighlightOverlay):
    """
    Highlight overlay for web/HTML-based UIs.
    
    Generates HTML/CSS/JS for highlighting regions in a web interface.
    
    Example:
        >>> overlay = HTMLHighlightOverlay()
        >>> region = HighlightRegion(x=10, y=20, width=200, height=100)
        >>> html = overlay.generate_html(region)
        >>> # Inject html into your web page
    """
    
    def __init__(self, container_id: str = "tutorial-overlay"):
        super().__init__()
        self.container_id = container_id
    
    def generate_html(self, region: HighlightRegion, include_styles: bool = True) -> str:
        """
        Generate HTML for a highlight overlay.
        
        Args:
            region: Region to highlight
            include_styles: Include CSS styles
        
        Returns:
            HTML string
        """
        styles = self._generate_css(region) if include_styles else ""
        
        html = f"""
        <div id="{self.container_id}" class="tutorial-overlay">
            <div class="tutorial-dim"></div>
            <div class="tutorial-highlight" id="{self.container_id}-highlight"></div>
            {styles}
        </div>
        """
        
        return html
    
    def generate_js(self, region: HighlightRegion) -> str:
        """
        Generate JavaScript for interactive highlighting.
        
        Args:
            region: Region to highlight
        
        Returns:
            JavaScript string
        """
        x, y, w, h = self._to_pixels(region)
        
        js = f"""
        (function() {{
            const overlay = document.getElementById('{self.container_id}');
            const highlight = document.getElementById('{self.container_id}-highlight');
            const dim = overlay.querySelector('.tutorial-dim');
            
            // Position highlight
            highlight.style.left = '{x}px';
            highlight.style.top = '{y}px';
            highlight.style.width = '{w}px';
            highlight.style.height = '{h}px';
            
            // Create hole in dim overlay using clip-path
            dim.style.clipPath = `polygon(
                0% 0%, 0% 100%, {x}px 100%, {x}px {y}px, {x+w}px {y}px, 
                {x+w}px {y+h}px, {x}px {y+h}px, {x}px 100%, 100% 100%, 100% 0%
            )`;
            
            // Click handler
            overlay.addEventListener('click', function(e) {{
                const rect = highlight.getBoundingClientRect();
                const inHighlight = (
                    e.clientX >= rect.left && e.clientX <= rect.right &&
                    e.clientY >= rect.top && e.clientY <= rect.bottom
                );
                
                if (inHighlight) {{
                    // Dispatch custom event
                    window.dispatchEvent(new CustomEvent('tutorialHighlightClick', {{
                        detail: {{ x: e.clientX, y: e.clientY }}
                    }}));
                }}
            }});
        }})();
        """
        
        return js
    
    def _generate_css(self, region: HighlightRegion) -> str:
        """Generate CSS styles for the overlay."""
        return f"""
        <style>
        #{self.container_id} {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: auto;
            z-index: 9999;
        }}
        
        #{self.container_id} .tutorial-dim {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, {region.opacity});
            transition: clip-path 0.3s ease;
        }}
        
        #{self.container_id} .tutorial-highlight {{
            position: absolute;
            border: 3px solid {region.color};
            border-radius: {'50%' if region.shape == 'circle' else '8px' if region.shape == 'rounded' else '0'};
            box-shadow: 0 0 20px {region.color}80, 0 0 40px {region.color}40, inset 0 0 20px {region.color}20;
            pointer-events: none;
            animation: tutorialPulse 2s ease-in-out infinite;
        }}
        
        @keyframes tutorialPulse {{
            0%, 100% {{ box-shadow: 0 0 20px {region.color}80, 0 0 40px {region.color}40; }}
            50% {{ box-shadow: 0 0 30px {region.color}FF, 0 0 60px {region.color}80; }}
        }}
        </style>
        """
    
    def _render_impl(self, region: HighlightRegion) -> RenderedHighlight:
        """Not used for HTML overlay - use generate_html instead."""
        raise NotImplementedError("Use generate_html() and generate_js() for HTML overlay")
    
    def _clear_impl(self, rendered: RenderedHighlight) -> None:
        """Not used for HTML overlay."""
        pass


class TkinterHighlightOverlay(HighlightOverlay):
    """
    Highlight overlay for Tkinter-based UIs.
    
    Example:
        >>> import tkinter as tk
        >>> from graydient_toolkit.tutorial import TkinterHighlightOverlay, HighlightRegion
        >>> 
        >>> root = tk.Tk()
        >>> canvas = tk.Canvas(root, width=800, height=600)
        >>> canvas.pack()
        >>> 
        >>> overlay = TkinterHighlightOverlay(canvas)
        >>> region = HighlightRegion(x=100, y=100, width=200, height=150)
        >>> overlay.show(region)
    """
    
    def __init__(self, canvas: Any):
        super().__init__()
        self.canvas = canvas
        self._pulse_after_id: Optional[str] = None
    
    def _render_impl(self, region: HighlightRegion) -> RenderedHighlight:
        """Render highlight on Tkinter canvas."""
        x, y, w, h = self._to_pixels(region)
        
        elements = []
        
        # Create dim overlay (using a rectangle with transparency if supported)
        # Note: Tkinter doesn't support true alpha, so we use stippling
        dim_rect = self.canvas.create_rectangle(
            0, 0, self._container_width, self._container_height,
            fill="black",
            stipple="gray50",
            tags=("tutorial_dim",)
        )
        elements.append(dim_rect)
        
        # Create highlight rectangle
        if region.shape == "circle":
            highlight = self.canvas.create_oval(
                x, y, x + w, y + h,
                outline=region.color,
                width=3,
                tags=("tutorial_highlight",)
            )
        else:
            highlight = self.canvas.create_rectangle(
                x, y, x + w, y + h,
                outline=region.color,
                width=3,
                tags=("tutorial_highlight",)
            )
        elements.append(highlight)
        
        # Create glow effect (multiple outlines)
        for i in range(1, 4):
            offset = i * 3
            glow = self.canvas.create_rectangle(
                x - offset, y - offset, x + w + offset, y + h + offset,
                outline=region.color,
                width=1,
                stipple="gray" + str(50 + i * 12),
                tags=("tutorial_glow",)
            )
            elements.append(glow)
        
        # Bind click event
        self.canvas.tag_bind("tutorial_highlight", "<Button-1>", self._on_canvas_click)
        
        return RenderedHighlight(region, elements)
    
    def _clear_impl(self, rendered: RenderedHighlight) -> None:
        """Clear highlight from canvas."""
        for element in rendered.elements:
            self.canvas.delete(element)
        
        # Cancel any pending pulse animation
        if self._pulse_after_id:
            self.canvas.after_cancel(self._pulse_after_id)
            self._pulse_after_id = None
    
    def _pulse_impl(self, rendered: RenderedHighlight, duration_ms: int) -> None:
        """Add pulsing animation."""
        # Simple pulse by toggling visibility of glow elements
        glow_elements = [e for e in rendered.elements if "glow" in str(self.canvas.gettags(e))]
        
        def toggle_pulse(visible: bool = True):
            for elem in glow_elements:
                state = "normal" if visible else "hidden"
                self.canvas.itemconfig(elem, state=state)
            
            # Schedule next toggle
            self._pulse_after_id = self.canvas.after(
                500,  # Toggle every 500ms
                lambda: toggle_pulse(not visible)
            )
        
        toggle_pulse()
        
        # Stop after duration
        self.canvas.after(duration_ms, lambda: self._stop_pulse(rendered))
    
    def _stop_pulse(self, rendered: RenderedHighlight) -> None:
        """Stop pulsing animation."""
        if self._pulse_after_id:
            self.canvas.after_cancel(self._pulse_after_id)
            self._pulse_after_id = None
        
        # Make all glow elements visible
        for elem in rendered.elements:
            if "glow" in str(self.canvas.gettags(elem)):
                self.canvas.itemconfig(elem, state="normal")
    
    def _on_canvas_click(self, event: Any) -> None:
        """Handle click on canvas."""
        if self._on_click:
            self._on_click(event.x, event.y)


def create_highlight_overlay(
    ui_framework: str,
    **kwargs
) -> HighlightOverlay:
    """
    Factory function to create the appropriate highlight overlay.
    
    Args:
        ui_framework: "tkinter", "html", or "qt"
        **kwargs: Framework-specific arguments
    
    Returns:
        HighlightOverlay instance
    """
    if ui_framework == "tkinter":
        return TkinterHighlightOverlay(kwargs.get("canvas"))
    elif ui_framework == "html":
        return HTMLHighlightOverlay(kwargs.get("container_id", "tutorial-overlay"))
    else:
        raise ValueError(f"Unsupported UI framework: {ui_framework}")
