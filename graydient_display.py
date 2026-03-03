#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        graydient_display.py                                 ║
║         Terminal UI + Browser Viewport for graydient_exchange               ║
║                                                                             ║
║  INTEGRATED WITH: graydient_launcher.py                                     ║
║  - Uses launcher session for authentication                                 ║
║  - Adds command input for Telegram-style commands                           ║
║  - Displays images and videos from API results                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

OVERVIEW
════════
Two display layers for the Exchange, usable independently or together:

  TERMINAL PANEL   Live colour-coded Rich panel in your console showing
                   the job queue, event stream, and statistics.
                   Requires:  pip install rich

  BROWSER VIEWER   Local HTTP server + SSE-driven web page.
                   Opens automatically in your browser; renders appear as
                   they land. No external services, stdlib HTTP only.
                   Requires:  nothing beyond Python stdlib

TELEGRAM-STYLE COMMANDS
═══════════════════════
The display supports the same shorthand commands as Pirate Diffusion:

    /draw <prompt>              - Generate an image
    /animate <prompt>           - Animate an image
    /style <style> <prompt>     - Apply style transfer
    /upscale <image>            - Upscale an image
    /img2img <image> <prompt>   - Image to image transformation

    Parameters:
    --seed <number>             - Set random seed
    --steps <number>            - Number of inference steps
    --guidance <number>         - Guidance scale
    --width <number>            - Output width
    --height <number>           - Output height
    --negative <prompt>         - Negative prompt

QUICK START
═══════════
    from graydient_exchange import Exchange, WorkflowDefinition, InputMapping
    from graydient_display   import Display, DisplayTheme

    ex = Exchange()
    ex.register(WorkflowDefinition(name="gen", workflow="qwen",
                input_map=InputMapping(prompt_key="prompt")))

    with Display(ex, title="My Studio").live():
        result = ex.run("gen", {"prompt": "a crystal fox"})

VIEWER ONLY (no renders needed — great for previewing themes)
═════════════════════════════════════════════════════════════
    python graydient_display.py [theme] [port]

    python graydient_display.py phosphor 7788
    python graydient_display.py amber    7789
    python graydient_display.py neon     7790
    python graydient_display.py slate    7791

THEMES
══════
    DisplayTheme.phosphor()   Classic green-on-black CRT (default)
    DisplayTheme.amber()      Warm amber — retro 1980s feel
    DisplayTheme.neon()       Cyberpunk magenta/cyan on deep navy
    DisplayTheme.slate()      Clean dark slate — minimal, professional

    Or build your own: DisplayTheme(bg="#...", primary="#...", ...)
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import threading
import time
import webbrowser
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("graydient_display")

# ── Rich: optional, graceful degradation ─────────────────────────────────────
try:
    from rich.console import Console
    from rich.live    import Live
    from rich.table   import Table
    from rich.panel   import Panel
    from rich.text    import Text
    from rich.columns import Columns
    from rich         import box
    from rich.console import Group
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# ══════════════════════════════════════════════════════════════════════════════
# DisplayTheme
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DisplayTheme:
    """
    Colour palette and symbol set for the terminal panel and browser viewer.
    """
    name         : str  = "phosphor"
    bg           : str  = "#0d1117"
    primary      : str  = "#00ff41"
    secondary    : str  = "#008f11"
    accent       : str  = "#39ff14"
    text         : str  = "#ccffcc"
    dim          : str  = "#2d5a27"
    success      : str  = "#00ff41"
    warning      : str  = "#ffcc00"
    error        : str  = "#ff3333"
    running      : str  = "#00ccff"
    border_style : str  = "bold green"
    font_mono    : str  = "'Share Tech Mono', 'Courier New', monospace"
    scanlines    : bool = True
    glow         : bool = True
    status_icons : Dict[str, str] = field(default_factory=lambda: {
        "pending" : "○",
        "running" : "◉",
        "done"    : "●",
        "error"   : "✗",
        "timeout" : "⏱",
    })

    @classmethod
    def phosphor(cls) -> "DisplayTheme":
        """Classic green phosphor terminal — the default."""
        return cls()

    @classmethod
    def amber(cls) -> "DisplayTheme":
        """Warm amber phosphor — 1980s retro feel."""
        return cls(
            name="amber", bg="#110a00",
            primary="#ffb000", secondary="#cc8800",
            accent="#ffe066", text="#ffe4a0",
            dim="#4a3500", success="#ffb000",
            warning="#ff6600", error="#ff2200",
            running="#ffdd44", border_style="bold yellow",
        )

    @classmethod
    def neon(cls) -> "DisplayTheme":
        """Cyberpunk neon on deep navy."""
        return cls(
            name="neon", bg="#05001a",
            primary="#ff00ff", secondary="#00ffff",
            accent="#ff6fff", text="#e0e0ff",
            dim="#2a1a4a", success="#00ff88",
            warning="#ffaa00", error="#ff0055",
            running="#00ffff", border_style="bold magenta",
            font_mono="'Fira Code', 'Courier New', monospace",
        )

    @classmethod
    def slate(cls) -> "DisplayTheme":
        """Clean dark slate — minimal and professional."""
        return cls(
            name="slate", bg="#0f172a",
            primary="#94a3b8", secondary="#64748b",
            accent="#38bdf8", text="#e2e8f0",
            dim="#334155", success="#4ade80",
            warning="#facc15", error="#f87171",
            running="#38bdf8", border_style="bold #94a3b8",
            scanlines=False, glow=False,
        )


# ══════════════════════════════════════════════════════════════════════════════
# DisplayConfig
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DisplayConfig:
    """Behaviour settings for the Display system."""
    viewer_port  : int   = 7788
    viewer_host  : str   = "127.0.0.1"
    auto_open    : bool  = True
    refresh_rate : float = 4.0
    max_log_rows : int   = 20
    max_job_rows : int   = 15
    title        : str   = "Graydient Exchange"
    subtitle     : str   = ""


# ══════════════════════════════════════════════════════════════════════════════
# Telegram Command Parser
# ══════════════════════════════════════════════════════════════════════════════

class TelegramCommandParser:
    """
    Parse Telegram-style commands for the Graydient Exchange.
    
    Supports commands from https://graydient.ai/pirate-diffusion-guide/
    """
    
    # Command to workflow mapping
    COMMANDS = {
        "/draw": "txt2img",
        "/d": "txt2img",
        "/animate": "animate",
        "/a": "animate",
        "/style": "img2img",
        "/s": "img2img",
        "/upscale": "upscale",
        "/u": "upscale",
        "/img2img": "img2img",
        "/i2i": "img2img",
        "/edit": "img2img",
        "/e": "img2img",
    }
    
    @classmethod
    def parse(cls, command_text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse a Telegram-style command.
        
        Args:
            command_text: The command string (e.g., "/draw a cat --seed 42")
            
        Returns:
            (workflow_name, params_dict)
            
        Example:
            >>> TelegramCommandParser.parse("/draw a cyberpunk cat --seed 42")
            ("txt2img", {"prompt": "a cyberpunk cat", "seed": 42})
        """
        text = command_text.strip()
        
        # Extract command
        match = re.match(r'^(/\w+)(?:\s+(.*))?$', text, re.DOTALL)
        if not match:
            return "", {"error": "Invalid command format"}
        
        cmd = match.group(1).lower()
        rest = match.group(2) or ""
        
        # Get workflow name
        workflow = cls.COMMANDS.get(cmd)
        if not workflow:
            return "", {"error": f"Unknown command: {cmd}"}
        
        # Parse parameters
        params = cls._parse_params(rest)
        
        return workflow, params
    
    @classmethod
    def _parse_params(cls, text: str) -> Dict[str, Any]:
        """Parse parameters from command text."""
        params = {}
        
        # Extract --flags
        flag_pattern = r'--(\w+)\s+("[^"]*"|\S+)'
        flags = re.findall(flag_pattern, text)
        
        for flag, value in flags:
            # Remove quotes if present
            value = value.strip('"')
            
            # Convert types
            if flag in ("seed", "steps", "width", "height"):
                try:
                    params[flag] = int(value)
                except ValueError:
                    params[flag] = value
            elif flag in ("guidance", "strength"):
                try:
                    params[flag] = float(value)
                except ValueError:
                    params[flag] = value
            else:
                params[flag] = value
        
        # Remove flags from text to get prompt
        prompt = re.sub(flag_pattern, '', text).strip()
        
        if prompt:
            params["prompt"] = prompt
        
        return params
    
    @classmethod
    def get_help(cls) -> str:
        """Get help text for available commands."""
        return """
Available Commands:
  /draw <prompt> [--seed N] [--steps N] [--guidance N]
      Generate an image from text
      
  /animate <prompt> [--seed N]
      Animate a still image
      
  /style <prompt> [--image URL] [--strength 0.7]
      Apply style transfer to an image
      
  /upscale [--image URL]
      Upscale an image resolution
      
  /img2img <prompt> [--image URL] [--strength 0.7]
      Transform an image based on prompt

Parameters:
  --seed N         Set random seed for reproducibility
  --steps N        Number of inference steps (default: 30)
  --guidance N     Guidance scale (default: 7.5)
  --width N        Output width in pixels
  --height N       Output height in pixels
  --negative TEXT  Negative prompt (what to avoid)
  --strength N     Transformation strength 0-1 (default: 0.7)
  --image URL      Source image URL for img2img operations
"""


# ══════════════════════════════════════════════════════════════════════════════
# Launcher Session Integration
# ══════════════════════════════════════════════════════════════════════════════

def load_launcher_session() -> Optional[Dict[str, Any]]:
    """Load authentication session from graydient_launcher."""
    session_path = Path(__file__).parent / ".graydient_session.json"
    if session_path.exists():
        try:
            return json.loads(session_path.read_text())
        except Exception:
            pass
    return None


def get_api_key_from_session() -> Optional[str]:
    """Get API key from launcher session."""
    session = load_launcher_session()
    if session and session.get("api_key") and session.get("api_key_valid"):
        return session["api_key"]
    return None


# ══════════════════════════════════════════════════════════════════════════════
# RichPanel
# ══════════════════════════════════════════════════════════════════════════════

class RichPanel:
    """Live terminal display using the Rich library."""

    def __init__(self, exchange, theme: DisplayTheme, config: DisplayConfig):
        self._exchange = exchange
        self._theme = theme
        self._config = config
        self._console = Console() if RICH_AVAILABLE else None
        self._live = None
        self._log_lines: List[str] = []

    def add_log(self, line: str):
        """Append a timestamped line to the event log."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_lines.append(f"[{ts}]  {line}")
        if len(self._log_lines) > self._config.max_log_rows * 4:
            self._log_lines = self._log_lines[-self._config.max_log_rows * 2:]

    def _build(self):
        """Build the current Rich renderable."""
        t = self._theme
        cfg = self._config

        # Header
        clock = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        hdr_left = Text()
        hdr_left.append(cfg.title, style=f"bold {t.primary}")
        if cfg.subtitle:
            hdr_left.append(f"  {cfg.subtitle}", style=t.secondary)
        hdr_right = Text(clock, style=t.dim)
        header = Panel(
            Columns([hdr_left, hdr_right], equal=False, expand=True),
            border_style=t.border_style, padding=(0, 1),
        )

        # Jobs table
        from graydient_exchange import JobStatus
        tbl = Table(show_header=True, header_style=f"bold {t.primary}",
                    border_style=t.dim, box=box.SIMPLE_HEAVY, expand=True)
        tbl.add_column("ID", style=t.dim, width=10)
        tbl.add_column("Workflow", style=t.text, min_width=16)
        tbl.add_column("Status", style=t.text, width=11)
        tbl.add_column("Prog%", style=t.secondary, width=7)
        tbl.add_column("Elapsed", style=t.dim, width=9)
        tbl.add_column("Summary", style=t.text, min_width=20)

        records = self._exchange.job_history(limit=cfg.max_job_rows)
        if not records:
            tbl.add_row("—", "no jobs yet", "—", "—", "—", "—")
        else:
            STATUS_COLOUR = {
                JobStatus.DONE: t.success, JobStatus.ERROR: t.error,
                JobStatus.TIMEOUT: t.warning, JobStatus.RUNNING: t.running,
                JobStatus.PENDING: t.dim,
            }
            for rec in records:
                icon = t.status_icons.get(rec.status.value, "?")
                pct = f"{rec.progress_pct:.0f}%" if rec.progress_pct is not None else "—"
                col = STATUS_COLOUR.get(rec.status, t.text)
                st_tx = Text(f"{icon} {rec.status.value}", style=col)
                tbl.add_row(
                    rec.job_id[:8], rec.workflow_name, st_tx, pct,
                    f"{rec.elapsed_seconds:.1f}s",
                    rec.latest_event_summary[:42],
                )
        jobs_panel = Panel(tbl, title=f"[{t.primary}]JOBS[/]",
                           border_style=t.border_style, padding=(0, 1))

        # Event log
        log_tx = Text()
        for line in self._log_lines[-cfg.max_log_rows:]:
            ll = line.lower()
            if "done" in ll or "●" in line:
                log_tx.append(line + "\n", style=t.success)
            elif "error" in ll or "✗" in line:
                log_tx.append(line + "\n", style=t.error)
            elif "running" in ll or "◉" in line:
                log_tx.append(line + "\n", style=t.running)
            elif "rendering" in ll:
                log_tx.append(line + "\n", style=t.secondary)
            else:
                log_tx.append(line + "\n", style=t.dim)
        log_panel = Panel(log_tx, title=f"[{t.primary}]EVENT LOG[/]",
                          border_style=t.border_style, padding=(0, 1))

        # Stats bar
        all_r = self._exchange.job_history(limit=9999)
        done = [r for r in all_r if r.status == JobStatus.DONE]
        errors = sum(1 for r in all_r if r.status == JobStatus.ERROR)
        running = sum(1 for r in all_r if r.status == JobStatus.RUNNING)
        avg_el = sum(r.elapsed_seconds for r in done) / len(done) if done else 0
        pct = f"{len(done)/len(all_r)*100:.0f}%" if all_r else "—"
        url = f"http://{cfg.viewer_host}:{cfg.viewer_port}"
        stats = Text()
        stats.append(f" TOTAL {len(all_r)} ", style=f"bold {t.text}")
        stats.append(f" DONE {len(done)} ", style=f"bold {t.success}")
        stats.append(f" RUNNING {running} ", style=f"bold {t.running}")
        stats.append(f" ERRORS {errors} ", style=f"bold {t.error}")
        stats.append(f" SUCCESS {pct} ", style=f"bold {t.secondary}")
        stats.append(f" AVG {avg_el:.1f}s ", style=t.dim)
        stats.append(f" VIEWER → {url}", style=t.accent)
        stats_panel = Panel(stats, border_style=t.dim, padding=(0, 1))

        return Panel(
            Group(header, jobs_panel, log_panel, stats_panel),
            border_style=t.dim, padding=0,
        )

    def _plain_log(self, line: str):
        """Fallback when Rich not available."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}]  {line}")

    def start(self):
        if RICH_AVAILABLE and self._console:
            self._live = Live(self._build(), console=self._console,
                              refresh_per_second=self._config.refresh_rate, screen=False)
            self._live.__enter__()
        else:
            url = f"http://{self._config.viewer_host}:{self._config.viewer_port}"
            print(f"\n  {self._config.title} — Exchange running")
            print(f"  Viewer: {url}")
            print(f"  (Install rich for the terminal panel: pip install rich)\n")

    def stop(self):
        if self._live:
            try:
                self._live.__exit__(None, None, None)
            except Exception:
                pass

    def refresh(self, record=None):
        if self._live:
            try:
                self._live.update(self._build())
            except Exception:
                pass
        elif not RICH_AVAILABLE and record:
            self._plain_log(self._log_lines[-1] if self._log_lines else "")


# ══════════════════════════════════════════════════════════════════════════════
# ViewerServer
# ══════════════════════════════════════════════════════════════════════════════

class ViewerServer:
    """
    Local HTTP server that serves the browser viewer page
    and pushes updates via Server-Sent Events.
    """

    def __init__(self, theme: DisplayTheme, config: DisplayConfig, exchange):
        self._theme = theme
        self._config = config
        self._exchange = exchange
        self._clients: List[queue.Queue] = []
        self._lock = threading.Lock()
        self._server: Optional[HTTPServer] = None
        self._command_handler: Optional[Callable] = None

    def set_command_handler(self, handler: Callable[[str], None]):
        """Set handler for text commands from the viewer."""
        self._command_handler = handler

    def push_event(self, data: Dict[str, Any]):
        """Push a JSON dict to all connected browser clients via SSE."""
        payload = f"data: {json.dumps(data)}\n\n"
        with self._lock:
            alive = []
            for q in self._clients:
                try:
                    q.put_nowait(payload)
                    alive.append(q)
                except queue.Full:
                    pass
            self._clients = alive

    def start(self):
        """Bind and serve in a daemon thread."""
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                if self.path == "/":
                    self._html()
                elif self.path == "/events":
                    self._sse()
                elif self.path == "/state":
                    self._state()
                elif self.path.startswith("/api/"):
                    self._api()
                else:
                    self.send_response(204)
                    self.end_headers()

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                
                if self.path == "/api/command":
                    self._handle_command(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def _json(self, data: dict):
                payload = json.dumps(data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)

            def _html(self):
                data = server_ref._build_html().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _sse(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                q = queue.Queue(maxsize=200)
                with server_ref._lock:
                    server_ref._clients.append(q)
                init_data = {"type": "init", "state": server_ref._state_dict()}
                init = json.dumps(init_data)
                try:
                    self.wfile.write(f"data: {init}\n\n".encode())
                    self.wfile.flush()
                    while True:
                        try:
                            msg = q.get(timeout=20)
                            self.wfile.write(msg.encode())
                            self.wfile.flush()
                        except queue.Empty:
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    with server_ref._lock:
                        try:
                            server_ref._clients.remove(q)
                        except ValueError:
                            pass

            def _state(self):
                data = json.dumps(server_ref._state_dict()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _api(self):
                """Handle API requests."""
                if self.path == "/api/help":
                    self._json({"help": TelegramCommandParser.get_help()})
                else:
                    self.send_response(404)
                    self.end_headers()

            def _handle_command(self, body: bytes):
                """Handle command from viewer."""
                try:
                    data = json.loads(body.decode("utf-8"))
                    command = data.get("command", "")
                    
                    # Parse command
                    workflow, params = TelegramCommandParser.parse(command)
                    
                    if not workflow:
                        self._json({"ok": False, "error": params.get("error", "Invalid command")})
                        return
                    
                    # Call handler if set
                    if server_ref._command_handler:
                        server_ref._command_handler(command)
                    
                    self._json({
                        "ok": True,
                        "workflow": workflow,
                        "params": params
                    })
                except Exception as e:
                    self._json({"ok": False, "error": str(e)})

        try:
            self._server = HTTPServer((self._config.viewer_host, self._config.viewer_port), Handler)
        except OSError as e:
            logger.error("Viewer server failed to start: %s (port %d in use?)", e, self._config.viewer_port)
            print(f"\n  ⚠  Viewer port {self._config.viewer_port} already in use.")
            print(f"     Change it with: DisplayConfig(viewer_port=7789)\n")
            return

        t = threading.Thread(target=self._server.serve_forever, daemon=True, name="gex-viewer")
        t.start()
        logger.info("Viewer at http://%s:%d", self._config.viewer_host, self._config.viewer_port)

    def stop(self):
        if self._server:
            self._server.shutdown()

    def _state_dict(self) -> Dict:
        from graydient_exchange import JobStatus
        records = self._exchange.job_history(limit=50)
        all_r = self._exchange.job_history(limit=9999)
        done = [r for r in all_r if r.status == JobStatus.DONE]
        errors = sum(1 for r in all_r if r.status == JobStatus.ERROR)
        running = sum(1 for r in all_r if r.status == JobStatus.RUNNING)
        avg_el = sum(r.elapsed_seconds for r in done) / len(done) if done else 0
        return {
            "stats": {
                "total": len(all_r),
                "done": len(done),
                "errors": errors,
                "running": running,
                "success_pct": round(len(done) / len(all_r) * 100, 1) if all_r else 0,
                "avg_elapsed": round(avg_el, 2),
            },
            "jobs": [
                {
                    "job_id": r.job_id,
                    "workflow_name": r.workflow_name,
                    "workflow_slug": r.workflow_slug,
                    "status": r.status.value,
                    "progress_pct": r.progress_pct,
                    "elapsed": round(r.elapsed_seconds, 1),
                    "render_hash": r.render_hash,
                    "summary": r.latest_event_summary,
                    "result": r.result,
                    "started_at": r.started_at,
                }
                for r in records
            ],
        }

    def _build_html(self) -> str:
        t = self._theme
        cfg = self._config

        scanlines_css = """
        body.scanlines::after {
          content:''; position:fixed; top:0; left:0; width:100%; height:100%;
          background:repeating-linear-gradient(0deg,transparent,transparent 2px,
            rgba(0,0,0,0.07) 2px,rgba(0,0,0,0.07) 4px);
          pointer-events:none; z-index:9000;
        }""" if t.scanlines else ""

        glow_css = f"""
        .glow  {{ text-shadow: 0 0 8px {t.primary}, 0 0 20px {t.primary}55; }}
        .glow2 {{ box-shadow:  0 0 14px {t.primary}44, inset 0 0 14px {t.primary}11; }}
        """ if t.glow else ".glow{} .glow2{}"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{cfg.title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=VT323&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:{t.bg}; --pr:{t.primary}; --sc:{t.secondary}; --ac:{t.accent};
  --tx:{t.text}; --dm:{t.dim};   --ok:{t.success};   --rn:{t.running};
  --er:{t.error}; --wn:{t.warning};
  --font:{t.font_mono};
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:var(--bg);color:var(--tx);font-family:var(--font);
  font-size:13px;height:100%;overflow:hidden}}
{scanlines_css}
{glow_css}

/* Shell layout */
.shell{{display:grid;grid-template-rows:54px 1fr 34px;
  grid-template-columns:300px 1fr;height:100vh}}

/* Header */
.hdr{{grid-column:1/-1;border-bottom:1px solid var(--dm);
  display:flex;align-items:center;padding:0 18px;gap:14px;
  background:linear-gradient(90deg,var(--bg),color-mix(in srgb,var(--pr) 7%,var(--bg)))}}
.logo{{font-family:'VT323',monospace;font-size:26px;color:var(--pr);letter-spacing:3px}}
.sub{{color:var(--dm);font-size:11px;flex:1}}
.clk{{color:var(--sc);font-size:12px;letter-spacing:1px}}
.dot{{width:8px;height:8px;border-radius:50%;background:var(--dm);transition:background .4s}}
.dot.on{{background:var(--ok)}}

/* Sidebar */
.side{{border-right:1px solid var(--dm);display:flex;flex-direction:column;overflow:hidden}}
.sec{{padding:10px 12px 8px;border-bottom:1px solid var(--dm);flex-shrink:0}}
.lbl{{color:var(--pr);font-size:10px;letter-spacing:2px;text-transform:uppercase;margin-bottom:7px}}
.sgrid{{display:grid;grid-template-columns:1fr 1fr;gap:3px 10px}}
.si{{display:flex;justify-content:space-between}}
.sk{{color:var(--dm);font-size:11px}}.sv{{color:var(--pr);font-size:11px;font-weight:bold}}
.jscroll{{flex:1;overflow-y:auto}}
.jscroll::-webkit-scrollbar{{width:3px}}
.jscroll::-webkit-scrollbar-thumb{{background:var(--dm)}}
.ji{{padding:6px 12px;border-bottom:1px solid color-mix(in srgb,var(--dm) 35%,transparent);
  cursor:pointer;transition:background .12s}}
.ji:hover{{background:color-mix(in srgb,var(--pr) 6%,transparent)}}
.ji.active{{background:color-mix(in srgb,var(--pr) 10%,transparent);
  border-left:2px solid var(--pr)}}
.ji-top{{display:flex;justify-content:space-between;margin-bottom:2px}}
.ji-name{{color:var(--tx);font-size:12px;overflow:hidden;white-space:nowrap;
  text-overflow:ellipsis;max-width:155px}}
.ji-id{{color:var(--dm);font-size:10px}}
.ji-st{{font-size:11px}}
.jibar{{height:2px;background:var(--dm);margin-top:4px;border-radius:1px}}
.jibar-f{{height:100%;border-radius:1px;transition:width .4s}}
.sp{{color:var(--dm)}}.sr{{color:var(--rn)}}.sd{{color:var(--ok)}}
.se{{color:var(--er)}}.st{{color:var(--wn)}}

/* Command input */
.cmd-box{{padding:10px 12px;border-bottom:1px solid var(--dm);background:color-mix(in srgb,var(--pr) 3%,var(--bg))}}
.cmd-input-wrap{{display:flex;gap:8px}}
.cmd-input{{
  flex:1;background:color-mix(in srgb,var(--pr) 5%,var(--bg));
  border:1px solid var(--dm);color:var(--tx);
  font-family:var(--font);font-size:13px;padding:8px 12px;
  outline:none;transition:border-color .15s;
}}
.cmd-input:focus{{border-color:var(--pr)}}
.cmd-input::placeholder{{color:var(--dm)}}
.cmd-btn{{
  background:transparent;border:1px solid var(--pr);color:var(--pr);
  font-family:var(--font);font-size:11px;letter-spacing:1px;
  padding:8px 16px;cursor:pointer;text-transform:uppercase;
  transition:background .15s;
}}
.cmd-btn:hover{{background:color-mix(in srgb,var(--pr) 12%,transparent)}}
.cmd-help{{
  color:var(--dm);font-size:10px;margin-top:6px;cursor:pointer;
  text-decoration:underline;text-underline-offset:2px;
}}
.cmd-help:hover{{color:var(--sc)}}

/* Viewport */
.vp{{display:flex;flex-direction:column;overflow:hidden}}
.tabs{{display:flex;border-bottom:1px solid var(--dm);flex-shrink:0;
  background:color-mix(in srgb,var(--bg) 95%,var(--pr))}}
.tab{{padding:8px 18px;font-size:11px;letter-spacing:1px;text-transform:uppercase;
  color:var(--dm);cursor:pointer;border-right:1px solid var(--dm);
  transition:color .15s,background .15s;user-select:none}}
.tab:hover{{color:var(--tx)}}
.tab.on{{color:var(--pr);background:color-mix(in srgb,var(--pr) 8%,transparent);
  border-bottom:2px solid var(--pr)}}
.tc{{flex:1;overflow:auto;padding:14px;display:none;flex-direction:column;gap:10px}}
.tc.on{{display:flex}}
.tc::-webkit-scrollbar{{width:4px}}
.tc::-webkit-scrollbar-thumb{{background:var(--dm)}}

/* Renders */
.rgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
  gap:10px;align-content:start}}
.rc{{border:1px solid var(--dm);
  background:color-mix(in srgb,var(--pr) 3%,var(--bg));overflow:hidden;
  transition:border-color .2s,transform .15s;animation:cardIn .3s ease}}
@keyframes cardIn{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
.rc:hover{{border-color:var(--pr);transform:scale(1.015)}}
.rc img,.rc video{{width:100%;display:block;background:var(--bg);
  max-height:200px;object-fit:contain}}
.rcmeta{{padding:7px 9px;font-size:10px;color:var(--sc);border-top:1px solid var(--dm)}}
.rcwf{{color:var(--pr);font-size:11px;margin-bottom:1px}}
.rctm{{color:var(--dm)}}
.empty{{color:var(--dm);text-align:center;padding:60px 20px;
  font-family:'VT323',monospace;font-size:22px;letter-spacing:2px;line-height:2.2}}
.blink{{animation:blink 1s step-end infinite}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:0}}}}

/* Help modal */
.help-overlay{{
  position:fixed;top:0;left:0;width:100%;height:100%;z-index:9000;
  background:color-mix(in srgb,var(--bg) 92%,transparent);
  backdrop-filter:blur(4px);
  display:none;align-items:center;justify-content:center;
}}
.help-overlay.on{{display:flex}}
.help-box{{
  border:1px solid var(--pr);background:var(--bg);
  padding:24px 28px;max-width:600px;max-height:80vh;overflow-y:auto;
  box-shadow:0 0 40px color-mix(in srgb,var(--pr) 20%,transparent);
}}
.help-box h2{{font-family:'VT323',monospace;font-size:24px;color:var(--pr);
  letter-spacing:2px;margin-bottom:16px}}
.help-box pre{{background:color-mix(in srgb,var(--pr) 5%,var(--bg));
  border:1px solid var(--dm);padding:12px;font-size:11px;color:var(--tx);
  white-space:pre-wrap;overflow-x:auto;margin:10px 0}}
.help-box code{{color:var(--pr);font-family:var(--font)}}
.help-box p{{color:var(--sc);font-size:12px;line-height:1.7;margin:8px 0}}
.help-close{{
  background:transparent;border:1px solid var(--dm);color:var(--dm);
  font-family:var(--font);font-size:11px;padding:8px 16px;cursor:pointer;
  margin-top:16px;transition:all .15s;
}}
.help-close:hover{{border-color:var(--pr);color:var(--pr)}}

/* Event log */
.elog{{font-size:12px;line-height:1.7;display:flex;flex-direction:column;gap:0}}
.ev{{display:flex;gap:9px;padding:2px 6px;border-left:2px solid transparent}}
.ev:hover{{background:color-mix(in srgb,var(--pr) 4%,transparent)}}
.ev-t{{color:var(--dm);flex-shrink:0;font-size:10px;padding-top:1px}}
.ev-w{{color:var(--sc);flex-shrink:0;min-width:88px}}
.ev-m{{color:var(--tx)}}
.ev.done{{border-left-color:var(--ok)}}
.ev.error{{border-left-color:var(--er)}}
.ev.running{{border-left-color:var(--rn)}}

/* Detail */
.djson{{background:color-mix(in srgb,var(--pr) 4%,var(--bg));
  border:1px solid var(--dm);padding:12px;font-size:11px;color:var(--sc);
  white-space:pre-wrap;word-break:break-all;flex:1;overflow-y:auto}}

/* Footer */
.ftr{{grid-column:1/-1;border-top:1px solid var(--dm);display:flex;
  align-items:center;padding:0 14px;gap:16px;
  background:color-mix(in srgb,var(--dm) 10%,var(--bg));
  font-size:10px;color:var(--dm);letter-spacing:1px}}
.ftr span{{color:var(--sc)}}
</style>
</head>
<body class="{'scanlines' if t.scanlines else ''}">
<div class="shell glow2">

  <header class="hdr">
    <div class="logo glow">{cfg.title.upper()}</div>
    <div class="sub">{cfg.subtitle or 'graydient exchange · live viewer'}</div>
    <div class="clk" id="clk">--:--:--</div>
    <div class="dot" id="dot" title="SSE connection"></div>
  </header>

  <aside class="side">
    <div class="cmd-box">
      <div class="cmd-input-wrap">
        <input class="cmd-input" id="cmdInput" type="text"
               placeholder="/draw a cyberpunk cat --seed 42"
               onkeydown="if(event.key==='Enter') sendCommand()">
        <button class="cmd-btn" onclick="sendCommand()">Run</button>
      </div>
      <div class="cmd-help" onclick="showHelp()">Show command help</div>
    </div>
    <div class="sec">
      <div class="lbl">Stats</div>
      <div class="sgrid">
        <div class="si"><span class="sk">TOTAL</span>  <span class="sv" id="sTotal">0</span></div>
        <div class="si"><span class="sk">DONE</span>   <span class="sv" id="sDone">0</span></div>
        <div class="si"><span class="sk">RUNNING</span><span class="sv" id="sRun">0</span></div>
        <div class="si"><span class="sk">ERRORS</span> <span class="sv" id="sErr">0</span></div>
        <div class="si"><span class="sk">SUCCESS</span><span class="sv" id="sPct">—</span></div>
        <div class="si"><span class="sk">AVG</span>    <span class="sv" id="sAvg">—</span></div>
      </div>
    </div>
    <div class="sec" style="flex-shrink:0"><div class="lbl">Jobs</div></div>
    <div class="jscroll" id="jlist"></div>
  </aside>

  <main class="vp">
    <nav class="tabs">
      <div class="tab on" data-tab="renders">Renders</div>
      <div class="tab"    data-tab="events">Event Log</div>
      <div class="tab"    data-tab="detail">Detail</div>
    </nav>
    <div class="tc on" id="tab-renders">
      <div class="rgrid" id="rgrid">
        <div class="empty" id="empty">WAITING FOR RENDERS<br><span class="blink">_</span></div>
      </div>
    </div>
    <div class="tc" id="tab-events"><div class="elog" id="elog"></div></div>
    <div class="tc" id="tab-detail">
      <div class="djson" id="djson">// select a job in the sidebar</div>
    </div>
  </main>

  <footer class="ftr">
    <span>GRAYDIENT EXCHANGE</span>
    · viewer @ http://{self._config.viewer_host}:{self._config.viewer_port}
    · <span id="fjobs">0 jobs</span>
  </footer>

</div>

<!-- Help Modal -->
<div class="help-overlay" id="helpOverlay">
  <div class="help-box">
    <h2>COMMANDS</h2>
    <pre><code>/draw &lt;prompt&gt; [--seed N] [--steps N] [--guidance N]
    Generate an image from text

/animate &lt;prompt&gt; [--seed N]
    Animate a still image

/style &lt;prompt&gt; [--image URL] [--strength 0.7]
    Apply style transfer to an image

/upscale [--image URL]
    Upscale an image resolution

/img2img &lt;prompt&gt; [--image URL] [--strength 0.7]
    Transform an image based on prompt</code></pre>
    <p><strong>Parameters:</strong></p>
    <p><code>--seed N</code> — Set random seed for reproducibility</p>
    <p><code>--steps N</code> — Number of inference steps (default: 30)</p>
    <p><code>--guidance N</code> — Guidance scale (default: 7.5)</p>
    <p><code>--width N</code> — Output width in pixels</p>
    <p><code>--height N</code> — Output height in pixels</p>
    <p><code>--negative TEXT</code> — Negative prompt (what to avoid)</p>
    <p><code>--strength N</code> — Transformation strength 0-1 (default: 0.7)</p>
    <p><code>--image URL</code> — Source image URL for img2img operations</p>
    <button class="help-close" onclick="hideHelp()">Close</button>
  </div>
</div>

<script>
const PR=getComputedStyle(document.documentElement).getPropertyValue('--pr').trim();
const OK=getComputedStyle(document.documentElement).getPropertyValue('--ok').trim();
const ER=getComputedStyle(document.documentElement).getPropertyValue('--er').trim();
const RN=getComputedStyle(document.documentElement).getPropertyValue('--rn').trim();
const DM=getComputedStyle(document.documentElement).getPropertyValue('--dm').trim();
const WN=getComputedStyle(document.documentElement).getPropertyValue('--wn').trim();

let jobs={{}};
let renders=[];
let evlog=[];
let selId=null;

// Clock
setInterval(()=>{{document.getElementById('clk').textContent=
  new Date().toTimeString().slice(0,8);}},1000);

// Help modal
function showHelp(){{ document.getElementById('helpOverlay').classList.add('on'); }}
function hideHelp(){{ document.getElementById('helpOverlay').classList.remove('on'); }}
document.getElementById('helpOverlay').addEventListener('click', e=>{{
  if(e.target===document.getElementById('helpOverlay')) hideHelp();
}});

// Command input
async function sendCommand(){{
  const input = document.getElementById('cmdInput');
  const command = input.value.trim();
  if(!command) return;
  
  // Clear input
  input.value = '';
  
  // Add to event log
  evlog.push({{t:new Date().toLocaleTimeString(),w:'COMMAND',s:'pending',msg:command,id:null}});
  drawEventLog();
  
  try{{
    const r = await fetch('/api/command', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{command}})
    }});
    const d = await r.json();
    
    if(d.ok){{
      evlog.push({{t:new Date().toLocaleTimeString(),w:d.workflow,s:'running',msg:'Started: '+d.params.prompt,id:null}});
    }} else {{
      evlog.push({{t:new Date().toLocaleTimeString(),w:'ERROR',s:'error',msg:d.error,id:null}});
    }}
    drawEventLog();
  }} catch(e){{
    evlog.push({{t:new Date().toLocaleTimeString(),w:'ERROR',s:'error',msg:'Failed: '+e.message,id:null}});
    drawEventLog();
  }}
}}

// Tabs
document.querySelectorAll('.tab').forEach(t=>{{
  t.addEventListener('click',()=>{{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
    document.querySelectorAll('.tc').forEach(x=>x.classList.remove('on'));
    t.classList.add('on');
    document.getElementById('tab-'+t.dataset.tab).classList.add('on');
  }});
}});

// SSE
function connect(){{
  const dot=document.getElementById('dot');
  const es=new EventSource('/events');
  es.onopen=()=>dot.classList.add('on');
  es.onerror=()=>{{dot.classList.remove('on');es.close();setTimeout(connect,3000);}};
  es.onmessage=e=>{{
    const m=JSON.parse(e.data);
    if(m.type==='init'){{
      applyState(m.state);
    }} else {{
      handleUpdate(m);
    }}
  }};
}}

function applyState(s){{
  jobs={{}};
  (s.jobs||[]).forEach(j=>jobs[j.job_id]=j);
  renders=Object.values(jobs)
    .filter(j=>j.status==='done'&&j.result)
    .sort((a,b)=>b.started_at-a.started_at)
    .map(j=>{{return{{...j.result,_job:j}}}});
  updateStats(s.stats); drawJobs(); drawRenders();
  document.getElementById('fjobs').textContent=Object.keys(jobs).length+' jobs';
}}

function handleUpdate(m){{
  if(!m.job_id) return;
  if(!jobs[m.job_id]) jobs[m.job_id]={{}};
  Object.assign(jobs[m.job_id],m);
  if(m.status==='done'&&m.result){{
    if(!renders.find(r=>r._job&&r._job.job_id===m.job_id)){{
      renders.unshift({{...m.result,_job:jobs[m.job_id]}});
      drawRenders();
    }}
  }}
  evlog.push({{t:new Date().toLocaleTimeString(),w:m.workflow_name||'?',
    s:m.status,msg:m.summary||m.status,id:m.job_id}});
  if(evlog.length>500) evlog=evlog.slice(-400);
  drawEventLog(); drawJobs();
  if(selId===m.job_id) drawDetail(m.job_id);
  clearTimeout(window._sd);
  window._sd=setTimeout(()=>fetch('/state').then(r=>r.json()).then(d=>updateStats(d.stats)),500);
  document.getElementById('fjobs').textContent=Object.keys(jobs).length+' jobs';
}}

function updateStats(s){{
  if(!s) return;
  document.getElementById('sTotal').textContent=s.total||0;
  document.getElementById('sDone').textContent=s.done||0;
  document.getElementById('sRun').textContent=s.running||0;
  document.getElementById('sErr').textContent=s.errors||0;
  document.getElementById('sPct').textContent=(s.success_pct||0)+'%';
  document.getElementById('sAvg').textContent=(s.avg_elapsed||0)+'s';
}}

const ICON={{pending:'○',running:'◉',done:'●',error:'✗',timeout:'⏱'}};
const COL={{pending:DM,running:RN,done:OK,error:ER,timeout:WN}};

function drawJobs(){{
  const el=document.getElementById('jlist');
  const arr=Object.values(jobs).sort((a,b)=>(b.started_at||0)-(a.started_at||0));
  if(!arr.length){{el.innerHTML='<div style="padding:12px;color:var(--dm);font-size:11px">no jobs yet</div>';return;}}
  el.innerHTML=arr.map(j=>{{
    const pct=j.progress_pct!=null?j.progress_pct:(j.status==='done'?100:0);
    const col=COL[j.status]||DM;
    const act=selId===j.job_id?' active':'';
    return `<div class="ji${{act}}" onclick="sel('${{j.job_id}}')">
      <div class="ji-top">
        <span class="ji-name">${{j.workflow_name||j.workflow_slug||'?'}}</span>
        <span class="ji-st s${{j.status[0]}}">${{ICON[j.status]||'?'}} ${{j.status}}</span>
      </div>
      <div class="ji-id">${{(j.job_id||'').slice(0,8)}} · ${{(j.elapsed||0).toFixed(1)}}s</div>
      <div class="jibar"><div class="jibar-f" style="width:${{pct}}%;background:${{col}}"></div></div>
    </div>`;
  }}).join('');
}}

function drawRenders(){{
  const grid=document.getElementById('rgrid');
  const empty=document.getElementById('empty');
  if(!renders.length){{ if(empty) empty.style.display='block'; return; }}
  if(empty) empty.remove();
  const seen=new Set([...grid.querySelectorAll('.rc')].map(c=>c.dataset.jid));
  renders.forEach(r=>{{
    const jid=r._job&&r._job.job_id;
    if(seen.has(jid)) return;
    const url=r.video_url||r.image_url;
    if(!url) return;
    const isVid=url.endsWith('.mp4')||!!r.video_url;
    const ts=r._job?new Date(r._job.started_at*1000).toLocaleTimeString():'';
    const wf=r._job?(r._job.workflow_name||r._job.workflow_slug||''):'';
    const card=document.createElement('div');
    card.className='rc'; card.dataset.jid=jid;
    card.innerHTML=(isVid?`<video src="${{url}}" autoplay loop muted playsinline></video>`
      :`<img src="${{url}}" loading="lazy" alt="render">`)+
      `<div class="rcmeta"><div class="rcwf">${{wf}}</div>`+
      `<div class="rctm">${{(jid||'').slice(0,8)}} · ${{ts}}</div></div>`;
    grid.insertBefore(card,grid.firstChild);
  }});
}}

function drawEventLog(){{
  const el=document.getElementById('elog');
  el.innerHTML=evlog.slice(-120).reverse().map(e=>{{
    const cls='ev '+(e.s==='done'?'done':e.s==='error'?'error':e.s==='running'?'running':'');
    return `<div class="${{cls}}">
      <span class="ev-t">${{e.t}}</span>
      <span class="ev-w">${{e.w}}</span>
      <span class="ev-m">${{e.msg}}</span>
    </div>`;
  }}).join('');
}}

function drawDetail(id){{
  const j=jobs[id];
  document.getElementById('djson').textContent=j?JSON.stringify(j,null,2):'// not found';
}}

function sel(id){{
  selId=id; drawJobs(); drawDetail(id);
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  document.querySelectorAll('.tc').forEach(t=>t.classList.remove('on'));
  document.querySelector('[data-tab="detail"]').classList.add('on');
  document.getElementById('tab-detail').classList.add('on');
}}

connect();
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Display — top-level facade
# ══════════════════════════════════════════════════════════════════════════════

class Display:
    """
    Attach the terminal panel and browser viewer to an Exchange instance.
    
    Wraps any Exchange with two optional display layers:
    • RichPanel    — live terminal panel (requires: pip install rich)
    • ViewerServer — browser viewer, no extra deps needed
    
    Either layer can be used standalone. Both update whenever the Exchange
    dispatches or receives render events.
    
    Constructor
    ───────────
    Display(exchange, theme=None, config=None, title=None)
    
    Parameters
    ──────────
    exchange : Exchange    The exchange instance to attach to.
    theme    : DisplayTheme  Optional colour theme. Default: phosphor (green).
    config   : DisplayConfig Optional behaviour config. Default: port 7788.
    title    : str           Quick title override.
    
    Usage
    ─────
        with Display(ex, theme=DisplayTheme.neon()).live():
            result = ex.run("my-workflow", {...})
    
    Properties
    ──────────
    viewer_url    str  URL of the browser viewer (e.g. "http://127.0.0.1:7788")
    """

    def __init__(
        self,
        exchange,
        theme: Optional[DisplayTheme]  = None,
        config: Optional[DisplayConfig] = None,
        title: Optional[str]           = None,
    ):
        self._exchange = exchange
        self._theme = theme or DisplayTheme.phosphor()
        self._config = config or DisplayConfig()
        if title:
            self._config.title = title

        self._panel = RichPanel(exchange, self._theme, self._config)
        self._server = ViewerServer(self._theme, self._config, exchange)
        self._started = False
        
        # Set up command handler
        self._server.set_command_handler(self._handle_command)
        
        exchange.add_observer(self._on_update)

    @property
    def viewer_url(self) -> str:
        return f"http://{self._config.viewer_host}:{self._config.viewer_port}"

    def start(self):
        """
        Start the viewer server and terminal panel.
        Auto-opens browser if DisplayConfig.auto_open is True (default).
        Safe to call multiple times.
        """
        if self._started:
            return
        self._server.start()
        self._panel.start()
        self._started = True
        if self._config.auto_open:
            threading.Timer(0.7, lambda: webbrowser.open(self.viewer_url)).start()
        print(f"\n  ▶  Viewer → {self.viewer_url}\n")

    def stop(self):
        """Stop the viewer server and terminal panel."""
        if not self._started:
            return
        self._panel.stop()
        self._server.stop()
        self._started = False

    @contextmanager
    def live(self):
        """
        Context manager: starts on enter, stops on exit.
        
            with display.live():
                result = exchange.run("my-workflow", {...})
        """
        self.start()
        try:
            yield self
        finally:
            self.stop()

    def _handle_command(self, command: str):
        """Handle a command from the viewer."""
        from graydient_exchange import JobStatus
        
        workflow, params = TelegramCommandParser.parse(command)
        
        if not workflow:
            self._panel.add_log(f"✗ Invalid command: {params.get('error', 'Unknown error')}")
            return
        
        # Log the command
        prompt = params.get("prompt", "")
        self._panel.add_log(f"◉ [{workflow}] {prompt[:50]}...")
        
        # Execute via exchange (async)
        def callback(result):
            if "error" in result:
                self._panel.add_log(f"✗ [{workflow}] {result['error']}")
            else:
                url = result.get("image_url") or result.get("video_url", "")
                self._panel.add_log(f"● [{workflow}] Done: {url[:60]}...")
        
        # Run async so we don't block
        self._exchange.run_async(
            name=workflow,
            input_data=params,
            callback=callback
        )

    def _on_update(self, record):
        """Exchange observer: route every job state change to panel + viewer."""
        from graydient_exchange import JobStatus
        
        icon = self._theme.status_icons.get(record.status.value, "?")
        log_line = f"{icon} [{record.workflow_name}] {record.latest_event_summary}"
        self._panel.add_log(log_line)
        self._panel.refresh(record)
        self._server.push_event({
            "type": "job_update",
            "job_id": record.job_id,
            "workflow_name": record.workflow_name,
            "workflow_slug": record.workflow_slug,
            "status": record.status.value,
            "progress_pct": record.progress_pct,
            "elapsed": round(record.elapsed_seconds, 1),
            "render_hash": record.render_hash,
            "summary": record.latest_event_summary,
            "result": record.result,
            "started_at": record.started_at,
        })


# ══════════════════════════════════════════════════════════════════════════════
# Standalone entry point — preview any theme without running renders
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Preview the browser viewer for any theme without needing an API key
    or running any actual renders.
    
    Usage:
        python graydient_display.py [theme] [port]
    
    Examples:
        python graydient_display.py
        python graydient_display.py amber
        python graydient_display.py neon  7790
        python graydient_display.py slate 7791
    """
    import sys

    THEMES = {
        "phosphor": DisplayTheme.phosphor,
        "amber": DisplayTheme.amber,
        "neon": DisplayTheme.neon,
        "slate": DisplayTheme.slate,
    }

    theme_name = sys.argv[1] if len(sys.argv) > 1 else "phosphor"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7788
    theme = THEMES.get(theme_name, DisplayTheme.phosphor)()

    # Minimal stub exchange — no API needed
    class _Stub:
        def job_history(self, limit=100): return []
        def add_observer(self, cb): pass

    stub = _Stub()
    config = DisplayConfig(viewer_port=port, auto_open=False)
    server = ViewerServer(theme=theme, config=config, exchange=stub)
    server.start()

    url = f"http://127.0.0.1:{port}"
    print(f"\n  Graydient Exchange — Viewer Preview")
    print(f"  Theme   : {theme.name}")
    print(f"  Viewer  : {url}")
    print(f"  Themes  : phosphor | amber | neon | slate")
    print(f"\n  Press Ctrl+C to stop.\n")
    webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print("\n  Stopped.")
