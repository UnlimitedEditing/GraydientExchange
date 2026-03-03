#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         Graydient Launcher                                  ║
║              Authentication & Exchange Display Manager                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

A dedicated launcher application for Graydient Exchange that handles:
• API Key authentication with detailed debugging
• Virtual User (OTP) linking
• Integrated Exchange Display window with command input
• CLI debugging output
• User greeting and session management
• Telegram-style command support

USAGE:
    python graydient_launcher.py

FEATURES:
    - Automatic auth detection on startup
    - Detailed HTTP request/response logging
    - Built-in Exchange Display viewer with command input
    - Telegram-style commands (/draw, /animate, etc.)
    - Session persistence
    - One-click re-authentication
"""

import os
import sys
import json
import time
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Callable

# GUI imports
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox, simpledialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    print("ERROR: tkinter not available. Install with: apt-get install python3-tk")
    sys.exit(1)

# HTTP client
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LauncherConfig:
    """Launcher configuration."""
    ENV_PATH: Path = Path(__file__).parent / ".env"
    SESSION_PATH: Path = Path(__file__).parent / ".graydient_session.json"
    API_BASE: str = "https://app.graydient.ai/api/v3/"
    DISPLAY_PORT: int = 7788
    LAUNCHER_PORT: int = 7777
    DEBUG: bool = True

CONFIG = LauncherConfig()

# ══════════════════════════════════════════════════════════════════════════════
# Session State
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AuthSession:
    """Authentication session state."""
    api_key: Optional[str] = None
    api_key_valid: bool = False
    virtual_user_id: Optional[str] = None
    virtual_user_email: Optional[str] = None
    username: Optional[str] = None
    logged_in_at: Optional[float] = None
    last_error: Optional[str] = None
    
    @property
    def is_authenticated(self) -> bool:
        return self.api_key is not None and self.api_key_valid
    
    @property
    def is_fully_linked(self) -> bool:
        return self.is_authenticated and self.virtual_user_id is not None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthSession":
        return cls(**data)


# ══════════════════════════════════════════════════════════════════════════════
# Debug Logger
# ══════════════════════════════════════════════════════════════════════════════

class DebugLogger:
    """Thread-safe debug logger with callbacks."""
    
    def __init__(self):
        self.logs: list = []
        self.callbacks: list = []
        self.lock = threading.Lock()
    
    def add_callback(self, callback: Callable[[str], None]):
        """Add a callback to receive log messages."""
        self.callbacks.append(callback)
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted = f"[{timestamp}] [{level}] {message}"
        
        with self.lock:
            self.logs.append(formatted)
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]
        
        for cb in self.callbacks:
            try:
                cb(formatted)
            except Exception:
                pass
        
        print(formatted)
    
    def debug(self, message: str):
        self.log(message, "DEBUG")
    
    def info(self, message: str):
        self.log(message, "INFO")
    
    def warning(self, message: str):
        self.log(message, "WARN")
    
    def error(self, message: str):
        self.log(message, "ERROR")
    
    def get_logs(self) -> str:
        """Get all logs as a single string."""
        with self.lock:
            return "\n".join(self.logs)


LOGGER = DebugLogger()

# ══════════════════════════════════════════════════════════════════════════════
# Graydient API Client
# ══════════════════════════════════════════════════════════════════════════════

class GraydientAPIClient:
    """Direct Graydient API client with detailed debugging."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = CONFIG.API_BASE.rstrip("/")
        self.session = requests.Session()
        
    def _headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _log_request(self, method: str, url: str, data: Any = None):
        """Log HTTP request details."""
        LOGGER.debug(f"→ {method} {url}")
        if data:
            LOGGER.debug(f"  Body: {json.dumps(data, indent=2)[:500]}")
    
    def _log_response(self, response: requests.Response):
        """Log HTTP response details."""
        LOGGER.debug(f"← {response.status_code} {response.reason}")
        LOGGER.debug(f"  Headers: {dict(response.headers)}")
        try:
            body = response.json()
            LOGGER.debug(f"  Body: {json.dumps(body, indent=2)[:1000]}")
        except:
            LOGGER.debug(f"  Body: {response.text[:500]}")
    
    def validate_key(self) -> tuple[bool, Optional[Dict]]:
        """Validate the API key by calling /workflows."""
        if not self.api_key:
            LOGGER.error("No API key provided")
            return False, {"error": "No API key"}
        
        url = f"{self.base_url}/workflows"
        
        try:
            LOGGER.info("Validating API key...")
            LOGGER.debug(f"API URL: {url}")
            LOGGER.debug(f"Key (first 8): {self.api_key[:8]}...")
            
            self._log_request("GET", url)
            response = self.session.get(url, headers=self._headers(), timeout=15)
            self._log_response(response)
            
            if response.status_code == 200:
                LOGGER.info("✓ API key is valid!")
                return True, None
            elif response.status_code in (401, 403):
                LOGGER.error(f"✗ API key rejected (HTTP {response.status_code})")
                return False, {"error": "Invalid API key", "status": response.status_code}
            elif response.status_code == 429:
                LOGGER.error("✗ Rate limited - too many requests")
                return False, {"error": "Rate limited", "status": 429}
            else:
                LOGGER.error(f"✗ Unexpected response: HTTP {response.status_code}")
                return False, {"error": f"HTTP {response.status_code}", "body": response.text[:200]}
                
        except requests.exceptions.ConnectionError as e:
            LOGGER.error(f"✗ Connection error: {e}")
            return False, {"error": "Cannot connect to Graydient API", "details": str(e)}
        except requests.exceptions.Timeout:
            LOGGER.error("✗ Request timed out")
            return False, {"error": "Request timeout"}
        except Exception as e:
            LOGGER.error(f"✗ Validation error: {e}")
            return False, {"error": str(e)}
    
    def send_otp(self, email: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Send OTP to email."""
        url = f"{self.base_url}/virtualuser/otp/create"
        data = {"email": email, "source": "graydient_launcher"}
        
        try:
            LOGGER.info(f"Sending OTP to {email}...")
            self._log_request("POST", url, data)
            
            response = self.session.post(
                url, 
                headers=self._headers(),
                json=data,
                timeout=15
            )
            self._log_response(response)
            
            if response.status_code == 200:
                result = response.json()
                otp_id = result.get("data", {}).get("otp_id")
                LOGGER.info(f"✓ OTP sent! ID: {otp_id[:16]}...")
                return True, otp_id, None
            else:
                error = f"HTTP {response.status_code}: {response.text[:200]}"
                LOGGER.error(f"✗ Failed to send OTP: {error}")
                return False, None, error
                
        except Exception as e:
            LOGGER.error(f"✗ OTP send error: {e}")
            return False, None, str(e)
    
    def confirm_otp(self, otp_id: str, code: str) -> tuple[bool, Optional[Dict], Optional[str]]:
        """Confirm OTP code."""
        url = f"{self.base_url}/virtualuser/otp/confirm"
        data = {"otp_id": otp_id, "code": code.strip()}
        
        try:
            LOGGER.info(f"Confirming OTP...")
            self._log_request("POST", url, data)
            
            response = self.session.post(
                url,
                headers=self._headers(),
                json=data,
                timeout=15
            )
            self._log_response(response)
            
            if response.status_code == 200:
                result = response.json()
                user_id = list(result.get("data", {}).keys())[0]
                user_data = result["data"][user_id]
                LOGGER.info(f"✓ Account linked! User: {user_id[:16]}...")
                return True, {"id": user_id, "data": user_data}, None
            else:
                error = f"HTTP {response.status_code}: {response.text[:200]}"
                LOGGER.error(f"✗ OTP confirmation failed: {error}")
                return False, None, error
                
        except Exception as e:
            LOGGER.error(f"✗ OTP confirm error: {e}")
            return False, None, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# Session Manager
# ══════════════════════════════════════════════════════════════════════════════

class SessionManager:
    """Manages authentication session persistence."""
    
    def __init__(self):
        self.session = AuthSession()
        self._load()
    
    def _load(self):
        """Load session from disk."""
        if CONFIG.SESSION_PATH.exists():
            try:
                data = json.loads(CONFIG.SESSION_PATH.read_text())
                self.session = AuthSession.from_dict(data)
                LOGGER.info(f"Loaded session from {CONFIG.SESSION_PATH}")
            except Exception as e:
                LOGGER.warning(f"Failed to load session: {e}")
    
    def save(self):
        """Save session to disk."""
        try:
            CONFIG.SESSION_PATH.write_text(json.dumps(self.session.to_dict(), indent=2))
            LOGGER.debug("Session saved")
        except Exception as e:
            LOGGER.error(f"Failed to save session: {e}")
    
    def clear(self):
        """Clear session."""
        self.session = AuthSession()
        if CONFIG.SESSION_PATH.exists():
            CONFIG.SESSION_PATH.unlink()
        LOGGER.info("Session cleared")
    
    def set_api_key(self, key: str, valid: bool = False):
        """Set API key."""
        self.session.api_key = key
        self.session.api_key_valid = valid
        self.save()
    
    def set_virtual_user(self, user_id: str, email: Optional[str] = None):
        """Set virtual user."""
        self.session.virtual_user_id = user_id
        self.session.virtual_user_email = email
        self.session.logged_in_at = time.time()
        self.save()


# ══════════════════════════════════════════════════════════════════════════════
# Main Launcher Application
# ══════════════════════════════════════════════════════════════════════════════

class GraydientLauncher:
    """Main launcher application with GUI."""
    
    def __init__(self):
        self.root: Optional[tk.Tk] = None
        self.session_manager = SessionManager()
        self.api_client: Optional[GraydientAPIClient] = None
        self.display = None
        self.exchange = None
        
        # GUI elements
        self.status_label: Optional[tk.Label] = None
        self.user_label: Optional[tk.Label] = None
        self.log_text: Optional[scrolledtext.ScrolledText] = None
        self.auth_button: Optional[tk.Button] = None
        self.display_button: Optional[tk.Button] = None
        
        self._setup_gui()
        self._check_existing_auth()
    
    def _setup_gui(self):
        """Set up the GUI."""
        self.root = tk.Tk()
        self.root.title("Graydient Launcher")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Style
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica", 18, "bold"))
        style.configure("Status.TLabel", font=("Helvetica", 12))
        style.configure("User.TLabel", font=("Helvetica", 11))
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # === Header ===
        header = ttk.Frame(main_frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        title = ttk.Label(header, text="Graydient Launcher", style="Title.TLabel")
        title.pack(side=tk.LEFT)
        
        # === Status Panel ===
        status_frame = ttk.LabelFrame(main_frame, text="Authentication Status", padding="15")
        status_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(
            status_frame, 
            text="Checking authentication...",
            style="Status.TLabel"
        )
        self.status_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        self.user_label = ttk.Label(
            status_frame,
            text="",
            style="User.TLabel"
        )
        self.user_label.grid(row=1, column=0, sticky="w")
        
        # Button frame
        btn_frame = ttk.Frame(status_frame)
        btn_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        
        self.auth_button = ttk.Button(
            btn_frame,
            text="Authenticate",
            command=self._on_auth_click
        )
        self.auth_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.display_button = ttk.Button(
            btn_frame,
            text="Open Display",
            command=self._on_display_click,
            state=tk.DISABLED
        )
        self.display_button.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            btn_frame,
            text="Clear Session",
            command=self._on_clear_click
        ).pack(side=tk.LEFT)
        
        # === Debug Log ===
        log_frame = ttk.LabelFrame(main_frame, text="Debug Output", padding="10")
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white"
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        # Add log callback
        LOGGER.add_callback(self._on_log_message)
        
        # === Footer ===
        footer = ttk.Frame(main_frame)
        footer.grid(row=3, column=0, sticky="ew")
        
        ttk.Label(
            footer,
            text="Graydient Exchange Launcher v1.0",
            foreground="gray"
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            footer,
            text="Copy Logs",
            command=self._copy_logs
        ).pack(side=tk.RIGHT)
    
    def _on_log_message(self, message: str):
        """Handle new log message."""
        if self.log_text and self.root:
            self.root.after(0, lambda: self._append_log(message))
    
    def _append_log(self, message: str):
        """Append message to log text."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
    
    def _check_existing_auth(self):
        """Check for existing authentication."""
        session = self.session_manager.session
        
        if session.api_key:
            LOGGER.info("Found existing API key, validating...")
            self.api_client = GraydientAPIClient(session.api_key)
            
            def validate():
                valid, error = self.api_client.validate_key()
                self.session_manager.session.api_key_valid = valid
                if valid:
                    self.session_manager.session.logged_in_at = time.time()
                    # Initialize exchange with the key
                    self._init_exchange()
                else:
                    self.session_manager.session.last_error = str(error)
                self.session_manager.save()
                self.root.after(0, self._update_ui)
            
            threading.Thread(target=validate, daemon=True).start()
        else:
            LOGGER.info("No existing API key found")
            self._update_ui()
    
    def _init_exchange(self):
        """Initialize the Exchange with current auth."""
        try:
            from graydient_exchange_enhanced import Exchange, WorkflowDefinition, InputMapping
            
            key = self.session_manager.session.api_key
            self.exchange = Exchange(api_key=key)
            
            # Register default workflows
            self.exchange.register(WorkflowDefinition(
                name="txt2img",
                workflow="qwen",
                description="Generate images from text",
                input_map=InputMapping(prompt_key="prompt", seed_key="seed", negative_key="negative"),
            ))
            
            self.exchange.register(WorkflowDefinition(
                name="img2img",
                workflow="edit-qwen",
                description="Transform images",
                input_map=InputMapping(prompt_key="prompt", image_key="image", strength_key="strength"),
            ))
            
            self.exchange.register(WorkflowDefinition(
                name="animate",
                workflow="animate-wan22",
                description="Animate still images",
                input_map=InputMapping(prompt_key="prompt", image_key="image", seed_key="seed"),
            ))
            
            self.exchange.register(WorkflowDefinition(
                name="upscale",
                workflow="upscale",
                description="Upscale images",
                input_map=InputMapping(image_key="image"),
            ))
            
            LOGGER.info(f"Exchange initialized with {len(self.exchange.list_workflows())} workflows")
            
        except Exception as e:
            LOGGER.error(f"Failed to initialize Exchange: {e}")
    
    def _update_ui(self):
        """Update UI based on session state."""
        session = self.session_manager.session
        
        if session.is_fully_linked:
            self.status_label.config(
                text="✓ Fully authenticated and linked",
                foreground="green"
            )
            username = session.virtual_user_email or session.virtual_user_id[:16] + "..."
            self.user_label.config(text=f"Welcome, {username}!")
            self.auth_button.config(text="Re-authenticate")
            self.display_button.config(state=tk.NORMAL)
            
        elif session.is_authenticated:
            self.status_label.config(
                text="✓ API key valid (virtual user not linked)",
                foreground="orange"
            )
            self.user_label.config(text="Click 'Authenticate' to link your account")
            self.auth_button.config(text="Link Account")
            self.display_button.config(state=tk.NORMAL)
            
        else:
            self.status_label.config(
                text="✗ Not authenticated",
                foreground="red"
            )
            if session.last_error:
                self.user_label.config(text=f"Last error: {session.last_error}")
            else:
                self.user_label.config(text="Click 'Authenticate' to get started")
            self.auth_button.config(text="Authenticate")
            self.display_button.config(state=tk.DISABLED)
    
    def _on_auth_click(self):
        """Handle authenticate button click."""
        session = self.session_manager.session
        
        if session.is_authenticated and not session.virtual_user_id:
            self._link_virtual_user()
        else:
            self._do_full_auth()
    
    def _do_full_auth(self):
        """Perform full authentication flow."""
        key = simpledialog.askstring(
            "Graydient API Key",
            "Enter your Graydient API Key:\n\nGet it from: https://app.graydient.ai/account",
            show="*"
        )
        
        if not key:
            LOGGER.info("Authentication cancelled")
            return
        
        key = key.strip()
        LOGGER.info(f"API key entered (length: {len(key)})")
        
        self.api_client = GraydientAPIClient(key)
        
        def validate_and_continue():
            valid, error = self.api_client.validate_key()
            
            if valid:
                self.session_manager.set_api_key(key, valid=True)
                LOGGER.info("API key validated successfully!")
                self._init_exchange()
                self.root.after(0, self._ask_link_account)
            else:
                self.session_manager.set_api_key(key, valid=False)
                self.session_manager.session.last_error = str(error)
                self.session_manager.save()
                LOGGER.error(f"API key validation failed: {error}")
                self.root.after(0, lambda: messagebox.showerror(
                    "Authentication Failed",
                    f"Could not validate API key:\n\n{error}"
                ))
            
            self.root.after(0, self._update_ui)
        
        threading.Thread(target=validate_and_continue, daemon=True).start()
    
    def _ask_link_account(self):
        """Ask user if they want to link their Graydient account."""
        result = messagebox.askyesno(
            "Link Graydient Account",
            "Your API key is valid!\n\n"
            "Would you like to link your Graydient user account?\n"
            "This enables per-user render history and preferences.\n\n"
            "(You'll receive an OTP code by email)"
        )
        
        if result:
            self._link_virtual_user()
        else:
            LOGGER.info("User skipped virtual user linking")
    
    def _link_virtual_user(self):
        """Link virtual user via OTP."""
        email = simpledialog.askstring(
            "Link Account",
            "Enter your Graydient account email:"
        )
        
        if not email:
            return
        
        def send_otp():
            success, otp_id, error = self.api_client.send_otp(email)
            
            if success:
                LOGGER.info(f"OTP sent to {email}")
                self.root.after(0, lambda: self._ask_otp_code(otp_id, email))
            else:
                LOGGER.error(f"Failed to send OTP: {error}")
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Failed to send OTP:\n{error}"
                ))
        
        threading.Thread(target=send_otp, daemon=True).start()
    
    def _ask_otp_code(self, otp_id: str, email: str):
        """Ask for OTP code."""
        code = simpledialog.askstring(
            "Enter OTP Code",
            f"Enter the verification code sent to:\n{email}"
        )
        
        if not code:
            return
        
        def confirm():
            success, user_data, error = self.api_client.confirm_otp(otp_id, code)
            
            if success:
                self.session_manager.set_virtual_user(
                    user_data["id"],
                    email=email
                )
                LOGGER.info("Account linked successfully!")
                self.root.after(0, lambda: messagebox.showinfo(
                    "Success",
                    "Your Graydient account has been linked!"
                ))
            else:
                LOGGER.error(f"OTP confirmation failed: {error}")
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Invalid code or confirmation failed:\n{error}"
                ))
            
            self.root.after(0, self._update_ui)
        
        threading.Thread(target=confirm, daemon=True).start()
    
    def _on_display_click(self):
        """Open the Exchange Display."""
        if not self.exchange:
            LOGGER.error("Exchange not initialized")
            messagebox.showerror("Error", "Exchange not initialized. Please authenticate first.")
            return
        
        try:
            from graydient_display import Display, DisplayTheme
            
            # Create and start display
            self.display = Display(
                self.exchange,
                theme=DisplayTheme.phosphor(),
                title="Graydient Exchange"
            )
            self.display.start()
            
            LOGGER.info(f"Display opened at {self.display.viewer_url}")
            
        except Exception as e:
            LOGGER.error(f"Failed to open display: {e}")
            messagebox.showerror("Error", f"Could not open display:\n{e}")
    
    def _on_clear_click(self):
        """Clear session."""
        result = messagebox.askyesno(
            "Clear Session",
            "Are you sure you want to clear your authentication session?"
        )
        
        if result:
            self.session_manager.clear()
            self.api_client = None
            self.exchange = None
            if self.display:
                self.display.stop()
                self.display = None
            LOGGER.info("Session cleared by user")
            self._update_ui()
    
    def _copy_logs(self):
        """Copy logs to clipboard."""
        logs = LOGGER.get_logs()
        self.root.clipboard_clear()
        self.root.clipboard_append(logs)
        messagebox.showinfo("Copied", "Logs copied to clipboard!")
    
    def run(self):
        """Run the launcher."""
        LOGGER.info("=" * 60)
        LOGGER.info("Graydient Launcher Starting...")
        LOGGER.info("=" * 60)
        
        self.root.mainloop()
        
        # Cleanup
        if self.display:
            self.display.stop()
        LOGGER.info("Launcher exited")


# ══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point."""
    if not TKINTER_AVAILABLE:
        print("ERROR: tkinter is required but not available")
        print("Install with: sudo apt-get install python3-tk")
        sys.exit(1)
    
    if not REQUESTS_AVAILABLE:
        print("ERROR: requests is required but not installed")
        print("Install with: pip install requests")
        sys.exit(1)
    
    launcher = GraydientLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
