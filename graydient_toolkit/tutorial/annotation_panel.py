"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    tutorial/annotation_panel.py                              ║
║                     Annotation Display Component                            ║
║                                                                             ║
║  Displays tutorial annotations with support for:                            ║
║    • Text content                                                           ║
║    • Images                                                                 ║
║    • Videos                                                                 ║
║    • Slideshows (multiple images)                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from .engine import MediaContent


class MediaType(Enum):
    """Types of media content for annotations."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    SLIDESHOW = "slideshow"
    MIXED = "mixed"


@dataclass
class AnnotationContent:
    """
    Content for a tutorial annotation.
    
    Attributes:
        title: Annotation title
        text: Main text content (supports Markdown)
        media: Optional media content
        tips: List of tip/warning boxes
        code_example: Optional code example
        links: List of related links
    """
    title: str
    text: str = ""
    media: Optional[MediaContent] = None
    tips: List[Dict[str, str]] = field(default_factory=list)
    code_example: Optional[str] = None
    links: List[Dict[str, str]] = field(default_factory=list)
    
    @property
    def has_media(self) -> bool:
        """Check if annotation has media content."""
        return self.media is not None
    
    @property
    def media_type(self) -> MediaType:
        """Get the type of media content."""
        if not self.media:
            return MediaType.TEXT
        return MediaType(self.media.media_type)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "text": self.text,
            "media": self.media.to_dict() if self.media else None,
            "tips": self.tips,
            "code_example": self.code_example,
            "links": self.links,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AnnotationContent:
        return cls(
            title=data["title"],
            text=data.get("text", ""),
            media=MediaContent.from_dict(data["media"]) if data.get("media") else None,
            tips=data.get("tips", []),
            code_example=data.get("code_example"),
            links=data.get("links", []),
        )


class AnnotationPanel:
    """
    Displays tutorial annotations with rich content support.
    
    This is an abstract base class. Framework-specific implementations
    should subclass this and implement the render methods.
    
    Example:
        >>> from graydient_toolkit.tutorial import AnnotationPanel, AnnotationContent
        >>> 
        >>> content = AnnotationContent(
        ...     title="Welcome",
        ...     text="This is a tutorial step.",
        ...     media=MediaContent(
        ...         media_type="image",
        ...         src="/path/to/image.png",
        ...         caption="Example output"
        ...     )
        ... )
        >>> 
        >>> panel = MyAnnotationPanel(parent_widget)
        >>> panel.show(content)
    """
    
    def __init__(self):
        self._current_content: Optional[AnnotationContent] = None
        self._on_next: Optional[Callable[[], None]] = None
        self._on_back: Optional[Callable[[], None]] = None
        self._on_skip: Optional[Callable[[], None]] = None
        self._slideshow_index: int = 0
    
    def set_callbacks(
        self,
        on_next: Optional[Callable[[], None]] = None,
        on_back: Optional[Callable[[], None]] = None,
        on_skip: Optional[Callable[[], None]] = None,
    ) -> None:
        """Set navigation callbacks."""
        self._on_next = on_next
        self._on_back = on_back
        self._on_skip = on_skip
    
    def show(self, content: AnnotationContent) -> None:
        """
        Show annotation content.
        
        Args:
            content: Content to display
        """
        self._current_content = content
        self._slideshow_index = 0
        self._render_impl(content)
    
    def hide(self) -> None:
        """Hide the annotation panel."""
        self._current_content = None
        self._hide_impl()
    
    def update_text(self, text: str) -> None:
        """Update just the text content."""
        if self._current_content:
            self._current_content.text = text
            self._update_text_impl(text)
    
    def next_slideshow_image(self) -> None:
        """Advance to next image in slideshow."""
        if not self._current_content or not self._current_content.media:
            return
        
        media = self._current_content.media
        if media.media_type != "slideshow":
            return
        
        images = media.src if isinstance(media.src, list) else [media.src]
        self._slideshow_index = (self._slideshow_index + 1) % len(images)
        self._update_slideshow_impl(self._slideshow_index)
    
    def previous_slideshow_image(self) -> None:
        """Go to previous image in slideshow."""
        if not self._current_content or not self._current_content.media:
            return
        
        media = self._current_content.media
        if media.media_type != "slideshow":
            return
        
        images = media.src if isinstance(media.src, list) else [media.src]
        self._slideshow_index = (self._slideshow_index - 1) % len(images)
        self._update_slideshow_impl(self._slideshow_index)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Methods (to be implemented by subclasses)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_impl(self, content: AnnotationContent) -> None:
        """Render the annotation content. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _render_impl")
    
    def _hide_impl(self) -> None:
        """Hide the annotation panel. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _hide_impl")
    
    def _update_text_impl(self, text: str) -> None:
        """Update just the text content. Optional."""
        pass
    
    def _update_slideshow_impl(self, index: int) -> None:
        """Update slideshow to show image at index. Optional."""
        pass


class HTMLAnnotationPanel(AnnotationPanel):
    """
    HTML-based annotation panel for web interfaces.
    
    Generates HTML/CSS/JS for displaying annotations.
    
    Example:
        >>> panel = HTMLAnnotationPanel(container_id="tutorial-panel")
        >>> html = panel.generate_html(content)
        >>> # Inject into your web page
    """
    
    def __init__(self, container_id: str = "tutorial-annotation"):
        super().__init__()
        self.container_id = container_id
    
    def generate_html(self, content: AnnotationContent, show_navigation: bool = True) -> str:
        """
        Generate HTML for the annotation panel.
        
        Args:
            content: Content to display
            show_navigation: Show next/back/skip buttons
        
        Returns:
            HTML string
        """
        media_html = self._generate_media_html(content.media) if content.media else ""
        tips_html = self._generate_tips_html(content.tips)
        code_html = self._generate_code_html(content.code_example)
        links_html = self._generate_links_html(content.links)
        nav_html = self._generate_navigation_html() if show_navigation else ""
        
        html = f"""
        <div id="{self.container_id}" class="tutorial-annotation">
            <div class="annotation-header">
                <h3 class="annotation-title">{self._escape_html(content.title)}</h3>
            </div>
            <div class="annotation-body">
                <div class="annotation-text">{self._markdown_to_html(content.text)}</div>
                {media_html}
                {tips_html}
                {code_html}
                {links_html}
            </div>
            {nav_html}
        </div>
        """
        
        return html + self._generate_css()
    
    def generate_js(self) -> str:
        """Generate JavaScript for interactive elements."""
        return f"""
        <script>
        (function() {{
            const panel = document.getElementById('{self.container_id}');
            
            // Navigation buttons
            const nextBtn = panel.querySelector('.annotation-next');
            const backBtn = panel.querySelector('.annotation-back');
            const skipBtn = panel.querySelector('.annotation-skip');
            
            if (nextBtn) {{
                nextBtn.addEventListener('click', function() {{
                    window.dispatchEvent(new CustomEvent('tutorialNext'));
                }});
            }}
            
            if (backBtn) {{
                backBtn.addEventListener('click', function() {{
                    window.dispatchEvent(new CustomEvent('tutorialBack'));
                }});
            }}
            
            if (skipBtn) {{
                skipBtn.addEventListener('click', function() {{
                    window.dispatchEvent(new CustomEvent('tutorialSkip'));
                }});
            }}
            
            // Slideshow controls
            const slideshowPrev = panel.querySelector('.slideshow-prev');
            const slideshowNext = panel.querySelector('.slideshow-next');
            
            if (slideshowPrev) {{
                slideshowPrev.addEventListener('click', function() {{
                    window.dispatchEvent(new CustomEvent('tutorialSlideshowPrev'));
                }});
            }}
            
            if (slideshowNext) {{
                slideshowNext.addEventListener('click', function() {{
                    window.dispatchEvent(new CustomEvent('tutorialSlideshowNext'));
                }});
            }}
        }})();
        </script>
        """
    
    def _generate_media_html(self, media: MediaContent) -> str:
        """Generate HTML for media content."""
        if media.media_type == "image":
            src = media.src if isinstance(media.src, str) else media.src[0]
            return f"""
            <div class="annotation-media">
                <img src="{src}" alt="{media.caption}" class="annotation-image">
                {f'<p class="media-caption">{self._escape_html(media.caption)}</p>' if media.caption else ''}
            </div>
            """
        
        elif media.media_type == "video":
            src = media.src if isinstance(media.src, str) else media.src[0]
            autoplay = "autoplay" if media.autoplay else ""
            loop = "loop" if media.loop else ""
            return f"""
            <div class="annotation-media">
                <video src="{src}" {autoplay} {loop} controls class="annotation-video"></video>
                {f'<p class="media-caption">{self._escape_html(media.caption)}</p>' if media.caption else ''}
            </div>
            """
        
        elif media.media_type == "slideshow":
            images = media.src if isinstance(media.src, list) else [media.src]
            slides_html = "".join([
                f'<div class="slideshow-slide" data-index="{i}"><img src="{src}" alt="Slide {i+1}"></div>'
                for i, src in enumerate(images)
            ])
            return f"""
            <div class="annotation-media">
                <div class="annotation-slideshow">
                    {slides_html}
                </div>
                <div class="slideshow-controls">
                    <button class="slideshow-prev">← Previous</button>
                    <span class="slideshow-counter">1 / {len(images)}</span>
                    <button class="slideshow-next">Next →</button>
                </div>
                {f'<p class="media-caption">{self._escape_html(media.caption)}</p>' if media.caption else ''}
            </div>
            """
        
        return ""
    
    def _generate_tips_html(self, tips: List[Dict[str, str]]) -> str:
        """Generate HTML for tip boxes."""
        if not tips:
            return ""
        
        tips_html = ""
        for tip in tips:
            tip_type = tip.get("type", "tip")  # tip, warning, info
            tip_text = tip.get("text", "")
            tips_html += f"""
            <div class="annotation-tip annotation-tip-{tip_type}">
                <span class="tip-icon">{self._get_tip_icon(tip_type)}</span>
                <span class="tip-text">{self._escape_html(tip_text)}</span>
            </div>
            """
        
        return f'<div class="annotation-tips">{tips_html}</div>'
    
    def _generate_code_html(self, code: Optional[str]) -> str:
        """Generate HTML for code example."""
        if not code:
            return ""
        
        escaped_code = self._escape_html(code)
        return f"""
        <div class="annotation-code">
            <pre><code>{escaped_code}</code></pre>
        </div>
        """
    
    def _generate_links_html(self, links: List[Dict[str, str]]) -> str:
        """Generate HTML for related links."""
        if not links:
            return ""
        
        links_html = "".join([
            f'<li><a href="{link.get("url", "#")}" target="_blank">{self._escape_html(link.get("text", "Link"))}</a></li>'
            for link in links
        ])
        
        return f'<div class="annotation-links"><h4>Related Links</h4><ul>{links_html}</ul></div>'
    
    def _generate_navigation_html(self) -> str:
        """Generate HTML for navigation buttons."""
        return """
        <div class="annotation-navigation">
            <button class="annotation-back">← Back</button>
            <button class="annotation-skip">Skip</button>
            <button class="annotation-next">Next →</button>
        </div>
        """
    
    def _generate_css(self) -> str:
        """Generate CSS styles."""
        return """
        <style>
        .tutorial-annotation {
            background: #1a1a2e;
            border: 2px solid #00ff41;
            border-radius: 12px;
            max-width: 500px;
            box-shadow: 0 0 30px rgba(0, 255, 65, 0.3);
            font-family: 'Segoe UI', system-ui, sans-serif;
            color: #e0e0e0;
            overflow: hidden;
        }
        
        .annotation-header {
            background: linear-gradient(135deg, #00ff41 0%, #00cc33 100%);
            padding: 16px 20px;
        }
        
        .annotation-title {
            margin: 0;
            color: #0d1117;
            font-size: 18px;
            font-weight: 600;
        }
        
        .annotation-body {
            padding: 20px;
        }
        
        .annotation-text {
            line-height: 1.6;
            margin-bottom: 16px;
        }
        
        .annotation-text p {
            margin: 0 0 12px 0;
        }
        
        .annotation-text strong {
            color: #00ff41;
        }
        
        .annotation-text code {
            background: #0d1117;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Consolas', monospace;
            font-size: 14px;
        }
        
        .annotation-media {
            margin: 16px 0;
            text-align: center;
        }
        
        .annotation-image,
        .annotation-video {
            max-width: 100%;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .media-caption {
            margin-top: 8px;
            font-size: 13px;
            color: #888;
            font-style: italic;
        }
        
        .annotation-slideshow {
            position: relative;
            overflow: hidden;
        }
        
        .slideshow-slide {
            display: none;
        }
        
        .slideshow-slide:first-child {
            display: block;
        }
        
        .slideshow-controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 12px;
        }
        
        .slideshow-controls button {
            background: #0d1117;
            border: 1px solid #00ff41;
            color: #00ff41;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .slideshow-controls button:hover {
            background: #00ff41;
            color: #0d1117;
        }
        
        .slideshow-counter {
            font-size: 13px;
            color: #888;
        }
        
        .annotation-tips {
            margin: 16px 0;
        }
        
        .annotation-tip {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        
        .annotation-tip-tip {
            background: rgba(0, 255, 65, 0.1);
            border-left: 3px solid #00ff41;
        }
        
        .annotation-tip-warning {
            background: rgba(255, 170, 0, 0.1);
            border-left: 3px solid #ffaa00;
        }
        
        .annotation-tip-info {
            background: rgba(0, 170, 255, 0.1);
            border-left: 3px solid #00aaff;
        }
        
        .tip-icon {
            font-size: 18px;
        }
        
        .tip-text {
            font-size: 14px;
            line-height: 1.5;
        }
        
        .annotation-code {
            background: #0d1117;
            border-radius: 8px;
            padding: 16px;
            margin: 16px 0;
            overflow-x: auto;
        }
        
        .annotation-code pre {
            margin: 0;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            line-height: 1.5;
        }
        
        .annotation-code code {
            color: #00ff41;
        }
        
        .annotation-links {
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #333;
        }
        
        .annotation-links h4 {
            margin: 0 0 8px 0;
            color: #888;
            font-size: 14px;
        }
        
        .annotation-links ul {
            margin: 0;
            padding-left: 20px;
        }
        
        .annotation-links li {
            margin-bottom: 4px;
        }
        
        .annotation-links a {
            color: #00ff41;
            text-decoration: none;
        }
        
        .annotation-links a:hover {
            text-decoration: underline;
        }
        
        .annotation-navigation {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            padding: 16px 20px;
            background: #0d1117;
            border-top: 1px solid #333;
        }
        
        .annotation-navigation button {
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .annotation-back {
            background: transparent;
            border: 1px solid #666;
            color: #888;
        }
        
        .annotation-back:hover {
            border-color: #aaa;
            color: #ccc;
        }
        
        .annotation-skip {
            background: transparent;
            border: 1px solid #666;
            color: #888;
        }
        
        .annotation-skip:hover {
            border-color: #ff6666;
            color: #ff6666;
        }
        
        .annotation-next {
            background: #00ff41;
            border: none;
            color: #0d1117;
            margin-left: auto;
        }
        
        .annotation-next:hover {
            background: #00cc33;
        }
        </style>
        """
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
    
    def _markdown_to_html(self, text: str) -> str:
        """Simple Markdown to HTML conversion."""
        # Bold
        text = text.replace("**", "<strong>", 1)
        while "**" in text:
            text = text.replace("**", "</strong>", 1)
            if "**" in text:
                text = text.replace("**", "<strong>", 1)
        
        # Italic
        text = text.replace("*", "<em>", 1)
        while "*" in text:
            text = text.replace("*", "</em>", 1)
            if "*" in text:
                text = text.replace("*", "<em>", 1)
        
        # Code
        text = text.replace("`", "<code>", 1)
        while "`" in text:
            text = text.replace("`", "</code>", 1)
            if "`" in text:
                text = text.replace("`", "<code>", 1)
        
        # Paragraphs
        paragraphs = text.split("\n\n")
        text = "".join(f"<p>{p}</p>" for p in paragraphs if p.strip())
        
        return text
    
    def _get_tip_icon(self, tip_type: str) -> str:
        """Get icon for tip type."""
        icons = {
            "tip": "💡",
            "warning": "⚠️",
            "info": "ℹ️",
        }
        return icons.get(tip_type, "💡")
    
    # Abstract method implementations (not used for HTML)
    def _render_impl(self, content: AnnotationContent) -> None:
        pass
    
    def _hide_impl(self) -> None:
        pass


def create_annotation_panel(
    ui_framework: str,
    **kwargs
) -> AnnotationPanel:
    """
    Factory function to create the appropriate annotation panel.
    
    Args:
        ui_framework: "html", "tkinter", or "qt"
        **kwargs: Framework-specific arguments
    
    Returns:
        AnnotationPanel instance
    """
    if ui_framework == "html":
        return HTMLAnnotationPanel(kwargs.get("container_id", "tutorial-annotation"))
    else:
        raise ValueError(f"Unsupported UI framework: {ui_framework}")
