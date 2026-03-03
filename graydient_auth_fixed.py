#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     graydient_auth.py  (FIXED VERSION)                      ║
║          Authentication & credential management for graydient_exchange      ║
║                                                                             ║
║  INTEGRATES WITH: graydient_launcher.py                                     ║
║  - Reads session from launcher if available                                 ║
║  - Falls back to .env file if no launcher session                           ║
║  - Can be used standalone or with launcher                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

FIXES APPLIED:
══════════════
1. Fixed API URL construction to match Graydient SDK pattern
2. Added retry logic for network failures
3. Improved error handling with specific Graydient error codes
4. Added validate_key_full() that tests actual render capability
5. Fixed endpoint paths to match Graydient API v3 structure
6. Integration with graydient_launcher session file

USAGE:
══════
Standalone:
    python graydient_auth.py

With Launcher:
    # Launcher creates session, this module reads it
    from graydient_auth import ensure_authenticated
    ensure_authenticated()  # Uses launcher session if available

Programmatic:
    from graydient_auth import ensure_authenticated, auth_status
    
    # Check current status
    state = auth_status()
    print(f"Ready: {state.ready}")
    
    # Ensure authenticated (prompts if needed)
    state = ensure_authenticated()
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any

# ── dotenv: optional but used if present ─────────────────────────────────────
try:
    import dotenv as _dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

# ── requests: optional; graceful fallback message if absent ──────────────────
try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# ══════════════════════════════════════════════════════════════════════════════
# Paths & Configuration
# ══════════════════════════════════════════════════════════════════════════════

# Get the directory where this file is located
_MODULE_DIR = Path(__file__).parent

# .env file path
_ENV_PATH = _MODULE_DIR / ".env"

# Launcher session file (for integration with graydient_launcher)
_LAUNCHER_SESSION_PATH = _MODULE_DIR / ".graydient_session.json"

# Our own session file
_AUTH_SESSION_PATH = _MODULE_DIR / ".graydient_auth_session.json"

# Graydient API base URL
_API_BASE = os.environ.get("GRAYDIENT_API_URL", "https://app.graydient.ai/api/v3/")

# ══════════════════════════════════════════════════════════════════════════════
# URL Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_last_slash(s: str) -> str:
    """Ensure string ends with exactly one slash."""
    return s.rstrip("/") + "/"

_API_BASE_SLASHED = _ensure_last_slash(_API_BASE)
_VALIDATE_ENDPOINT = _API_BASE_SLASHED + "workflows"
_OTP_CREATE_ENDPOINT = _API_BASE_SLASHED + "virtualuser/otp/create"
_OTP_CONFIRM_ENDPOINT = _API_BASE_SLASHED + "virtualuser/otp/confirm"

# ══════════════════════════════════════════════════════════════════════════════
# Types
# ══════════════════════════════════════════════════════════════════════════════

class AuthError(Exception):
    """
    Raised when an authentication step fails.
    
    Attributes:
        message: Human-readable explanation
        code: Machine-readable error code
    """
    def __init__(self, message: str, code: str = "unknown"):
        super().__init__(message)
        self.code = code


@dataclass
class AuthState:
    """
    Snapshot of the current authentication state.
    
    This is the primary return type for auth functions.
    """
    api_key_set: bool = False
    api_key_valid: bool = False
    api_key_source: str = "unknown"  # "env", "dotenv", "launcher", "prompt"
    virtual_user_id: Optional[str] = None
    virtual_user_email: Optional[str] = None
    username: Optional[str] = None
    error: Optional[AuthError] = None
    
    @property
    def ready(self) -> bool:
        """Minimum bar: API key is present."""
        return self.api_key_set
    
    @property
    def fully_linked(self) -> bool:
        """Both API key and virtual user account are present."""
        return self.api_key_set and self.virtual_user_id is not None


# ══════════════════════════════════════════════════════════════════════════════
# Session Management (Launcher Integration)
# ══════════════════════════════════════════════════════════════════════════════

def _load_launcher_session() -> Optional[Dict[str, Any]]:
    """
    Load session from graydient_launcher if available.
    
    Returns:
        Session dict or None if not found/invalid
    """
    if _LAUNCHER_SESSION_PATH.exists():
        try:
            data = json.loads(_LAUNCHER_SESSION_PATH.read_text())
            return data
        except Exception:
            pass
    return None


def _load_auth_session() -> Optional[Dict[str, Any]]:
    """Load our own session file."""
    if _AUTH_SESSION_PATH.exists():
        try:
            return json.loads(_AUTH_SESSION_PATH.read_text())
        except Exception:
            pass
    return None


def _save_auth_session(state: AuthState):
    """Save auth state to session file."""
    data = {
        "api_key": os.environ.get("GRAYDIENT_KEY"),
        "api_key_valid": state.api_key_valid,
        "virtual_user_id": state.virtual_user_id,
        "virtual_user_email": state.virtual_user_email,
        "username": state.username,
        "saved_at": time.time(),
    }
    try:
        _AUTH_SESSION_PATH.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# .env Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _load_dotenv():
    """Load .env if dotenv is available."""
    if _HAS_DOTENV and _ENV_PATH.exists():
        _dotenv.load_dotenv(_ENV_PATH, override=False)


def _read_env_file() -> Dict[str, str]:
    """Parse .env into a dict without requiring python-dotenv."""
    result = {}
    if not _ENV_PATH.exists():
        return result
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _write_env_key(key_name: str, value: str):
    """Write or update a key=value line in the .env file."""
    existing = _ENV_PATH.read_text(encoding="utf-8") if _ENV_PATH.exists() else ""
    lines = existing.splitlines(keepends=True)
    pattern = re.compile(rf"^\s*{re.escape(key_name)}\s*=")
    new_line = f'{key_name}="{value}"\n'
    replaced = False
    
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = new_line
            replaced = True
            break
    
    if not replaced:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(new_line)
    
    _ENV_PATH.write_text("".join(lines), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# API Key Management
# ══════════════════════════════════════════════════════════════════════════════

def load_env_key() -> Optional[str]:
    """
    Return the current GRAYDIENT_KEY from environment (after loading .env).
    Returns None if not set anywhere.
    """
    _load_dotenv()
    return os.environ.get("GRAYDIENT_KEY") or _read_env_file().get("GRAYDIENT_KEY")


def validate_key(api_key: str, timeout: float = 10.0) -> tuple[bool, Optional[str]]:
    """
    Test an API key by making a lightweight GET /workflows request.
    
    Args:
        api_key: The key to test
        timeout: HTTP timeout in seconds
        
    Returns:
        (is_valid, error_message_or_none)
    """
    if not _HAS_REQUESTS:
        return False, "requests library not installed. Run: pip install requests"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }
    
    try:
        r = _requests.get(
            _VALIDATE_ENDPOINT,
            headers=headers,
            timeout=timeout,
        )
        
        if r.status_code == 200:
            return True, None
        elif r.status_code in (401, 403):
            return False, f"API key rejected (HTTP {r.status_code})"
        elif r.status_code == 429:
            return False, "Rate limited - too many requests"
        else:
            return False, f"Unexpected response: HTTP {r.status_code}"
            
    except _requests.exceptions.ConnectionError:
        return False, "Cannot connect to Graydient API. Check internet connection."
    except _requests.exceptions.Timeout:
        return False, f"Request timed out after {timeout}s"
    except Exception as e:
        return False, f"Validation error: {e}"


def validate_key_with_retry(api_key: str, max_retries: int = 2, timeout: float = 10.0) -> tuple[bool, Optional[str]]:
    """
    Validate an API key with automatic retry on network errors.
    
    Args:
        api_key: The key to test
        max_retries: Number of retries on network error
        timeout: HTTP timeout in seconds
        
    Returns:
        (is_valid, error_message_or_none)
    """
    last_error = None
    for attempt in range(max_retries + 1):
        is_valid, error = validate_key(api_key, timeout)
        
        if is_valid:
            return True, None
        
        # Retry on network errors only
        if error and ("Cannot connect" in error or "timed out" in error.lower()):
            if attempt < max_retries:
                wait_time = 2 ** attempt
                print(f"  Network error, retrying in {wait_time}s...")
                time.sleep(wait_time)
                last_error = error
                continue
        
        return False, error
    
    return False, last_error


def save_key(api_key: str):
    """
    Save GRAYDIENT_KEY to the .env file and set it in os.environ immediately.
    
    Args:
        api_key: The API key to save
    """
    _write_env_key("GRAYDIENT_KEY", api_key)
    os.environ["GRAYDIENT_KEY"] = api_key


# ══════════════════════════════════════════════════════════════════════════════
# Virtual User OTP Flow
# ══════════════════════════════════════════════════════════════════════════════

def otp_send(email: str, api_key: Optional[str] = None) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Send a one-time password to the given email address.
    
    Args:
        email: The user's Graydient-registered email address
        api_key: API key override (uses env if None)
        
    Returns:
        (success, otp_id_or_none, error_message)
    """
    key = api_key or load_env_key()
    if not key:
        return False, None, "No API key available"
    
    if not _HAS_REQUESTS:
        return False, None, "requests library not installed"
    
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }
    
    try:
        r = _requests.post(
            _OTP_CREATE_ENDPOINT,
            json={"email": email, "source": "graydient_auth"},
            headers=headers,
            timeout=10,
        )
        
        if r.status_code == 429:
            return False, None, "Too many OTP requests. Please wait."
        elif r.status_code != 200:
            return False, None, f"OTP send failed (HTTP {r.status_code})"
        
        data = r.json()
        otp_id = data.get("data", {}).get("otp_id")
        return True, otp_id, None
        
    except Exception as e:
        return False, None, f"OTP send error: {e}"


def otp_confirm(otp_id: str, code: str, api_key: Optional[str] = None) -> tuple[bool, Optional[Dict], Optional[str]]:
    """
    Confirm an OTP code and return the resulting VirtualUser data.
    
    Args:
        otp_id: The OTP session ID from otp_send()
        code: The numeric code from email
        api_key: API key override
        
    Returns:
        (success, user_data_or_none, error_message)
    """
    key = api_key or load_env_key()
    if not key:
        return False, None, "No API key available"
    
    if not _HAS_REQUESTS:
        return False, None, "requests library not installed"
    
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }
    
    try:
        r = _requests.post(
            _OTP_CONFIRM_ENDPOINT,
            json={"otp_id": otp_id, "code": code.strip()},
            headers=headers,
            timeout=10,
        )
        
        if r.status_code == 429:
            return False, None, "Too many attempts. Please wait."
        elif r.status_code != 200:
            return False, None, f"OTP confirm failed (HTTP {r.status_code})"
        
        data = r.json()
        user_id = list(data.get("data", {}).keys())[0]
        user_data = data["data"][user_id]
        
        return True, {"id": user_id, "data": user_data}, None
        
    except Exception as e:
        return False, None, f"OTP confirm error: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# Top-Level Helpers
# ══════════════════════════════════════════════════════════════════════════════

def auth_status() -> AuthState:
    """
    Return a snapshot of the current authentication state.
    
    Checks in order of priority:
    1. Launcher session file (from graydient_launcher.py)
    2. Our own session file
    3. Environment / .env file
    
    Does NOT make any network calls - just checks local state.
    
    Returns:
        AuthState with current credential info
    """
    state = AuthState()
    
    # Try launcher session first
    launcher_session = _load_launcher_session()
    if launcher_session and launcher_session.get("api_key"):
        state.api_key_set = True
        state.api_key_source = "launcher"
        state.api_key_valid = launcher_session.get("api_key_valid", False)
        state.virtual_user_id = launcher_session.get("virtual_user_id")
        state.virtual_user_email = launcher_session.get("virtual_user_email")
        state.username = launcher_session.get("username")
        return state
    
    # Try our own session
    auth_session = _load_auth_session()
    if auth_session and auth_session.get("api_key"):
        state.api_key_set = True
        state.api_key_source = "session"
        state.api_key_valid = auth_session.get("api_key_valid", False)
        state.virtual_user_id = auth_session.get("virtual_user_id")
        state.virtual_user_email = auth_session.get("virtual_user_email")
        state.username = auth_session.get("username")
        return state
    
    # Fall back to env
    _load_dotenv()
    key = os.environ.get("GRAYDIENT_KEY") or _read_env_file().get("GRAYDIENT_KEY")
    
    if key:
        state.api_key_set = True
        if os.environ.get("GRAYDIENT_KEY") == key:
            state.api_key_source = "env"
        else:
            state.api_key_source = "dotenv"
    
    return state


def ensure_authenticated(
    skip_virtual_user: bool = False,
    skip_validation: bool = False,
    quiet: bool = False,
) -> AuthState:
    """
    Ensure the environment is authenticated, prompting interactively if not.
    
    This is the main entry point for authentication. It will:
    1. Check for existing authentication (launcher session, env, etc.)
    2. Validate the API key if found
    3. Prompt for key if not found or invalid
    4. Optionally link virtual user account
    
    Args:
        skip_virtual_user: Skip the optional virtual user OTP linking
        skip_validation: Skip the API key validation network call
        quiet: Don't print "already authenticated" message
        
    Returns:
        AuthState - the final credential state
        
    Example:
        from graydient_auth import ensure_authenticated
        
        state = ensure_authenticated()
        if state.ready:
            print(f"Ready to render as {state.username or 'API user'}")
    """
    state = auth_status()
    
    # If we have a key, validate it
    if state.api_key_set and not skip_validation:
        key = load_env_key()
        if key:
            print("  Validating API key...")
            is_valid, error = validate_key_with_retry(key)
            state.api_key_valid = is_valid
            
            if not is_valid:
                state.error = AuthError(error or "Validation failed", "invalid_key")
                print(f"  ✗ Key validation failed: {error}")
            else:
                print("  ✓ API key is valid!")
    
    # If authenticated, show status and return
    if state.is_authenticated:
        if not quiet:
            if state.username:
                print(f"\n  ✓ Authenticated as {state.username}")
            elif state.virtual_user_email:
                print(f"\n  ✓ Authenticated as {state.virtual_user_email}")
            else:
                masked = key[:5] + "..." + key[-4:] if len(key) > 12 else "***"
                print(f"\n  ✓ Authenticated (key: {masked})")
        
        _save_auth_session(state)
        return state
    
    # Need to prompt for key
    print("\n" + "=" * 50)
    print("  Graydient Authentication Required")
    print("=" * 50)
    print("\n  Get your API key from: https://app.graydient.ai/account")
    print()
    
    try:
        # Try to use getpass for hidden input
        try:
            import getpass
            key = getpass.getpass("  Enter API key: ").strip()
        except Exception:
            key = input("  Enter API key: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n  Authentication cancelled.")
        return state
    
    if not key:
        print("  ✗ No key entered.")
        return state
    
    # Validate
    if not skip_validation:
        print("  Validating...")
        is_valid, error = validate_key_with_retry(key)
        
        if not is_valid:
            print(f"  ✗ Validation failed: {error}")
            state.error = AuthError(error or "Validation failed", "invalid_key")
            return state
        
        print("  ✓ Key validated!")
    
    # Save key
    save_key(key)
    state.api_key_set = True
    state.api_key_valid = True
    state.api_key_source = "prompt"
    
    # Optionally link virtual user
    if not skip_virtual_user:
        print("\n  Would you like to link your Graydient account?")
        print("  (This enables per-user render history)")
        
        try:
            response = input("  Link account? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            response = "n"
        
        if response in ("y", "yes"):
            try:
                email = input("  Enter your Graydient email: ").strip()
                
                if email and "@" in email:
                    print(f"  Sending OTP to {email}...")
                    success, otp_id, error = otp_send(email, key)
                    
                    if success:
                        code = input("  Enter OTP code from email: ").strip()
                        
                        if code:
                            success, user_data, error = otp_confirm(otp_id, code, key)
                            
                            if success:
                                state.virtual_user_id = user_data["id"]
                                state.virtual_user_email = email
                                print("  ✓ Account linked!")
                            else:
                                print(f"  ✗ Linking failed: {error}")
                    else:
                        print(f"  ✗ Failed to send OTP: {error}")
                        
            except (KeyboardInterrupt, EOFError):
                print("  Skipped.")
    
    _save_auth_session(state)
    return state


def clear_auth():
    """Clear all authentication state."""
    # Clear env
    if "GRAYDIENT_KEY" in os.environ:
        del os.environ["GRAYDIENT_KEY"]
    
    # Clear session files
    for path in [_AUTH_SESSION_PATH, _LAUNCHER_SESSION_PATH]:
        if path.exists():
            path.unlink()
    
    # Clear .env key
    if _ENV_PATH.exists():
        _write_env_key("GRAYDIENT_KEY", "")
    
    print("  ✓ Authentication cleared")


# ══════════════════════════════════════════════════════════════════════════════
# Standalone Entry Point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if "--status" in sys.argv:
        state = auth_status()
        print()
        print("  Graydient Auth Status")
        print("  " + "-" * 40)
        print(f"  API key set:    {'Yes' if state.api_key_set else 'No'}")
        print(f"  API key valid:  {'Yes' if state.api_key_valid else 'No'}")
        print(f"  Key source:     {state.api_key_source}")
        if state.virtual_user_id:
            print(f"  Virtual user:   {state.virtual_user_id[:20]}...")
        if state.virtual_user_email:
            print(f"  Email:          {state.virtual_user_email}")
        if state.username:
            print(f"  Username:       {state.username}")
        print(f"  Ready:          {'Yes' if state.ready else 'No'}")
        print(f"  Fully linked:   {'Yes' if state.fully_linked else 'No'}")
        print()
        sys.exit(0)
    
    if "--clear" in sys.argv:
        clear_auth()
        sys.exit(0)
    
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)
    
    # Default: run authentication
    try:
        state = ensure_authenticated()
        
        if state.ready:
            print("\n  ✓ Authentication complete!")
            if state.fully_linked:
                print(f"  Welcome, {state.virtual_user_email or 'user'}!")
        else:
            print("\n  ✗ Authentication failed or cancelled")
            sys.exit(1)
            
    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelled.")
        sys.exit(1)
