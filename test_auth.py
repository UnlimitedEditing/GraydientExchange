#!/usr/bin/env python3
"""
Graydient Authentication Test
==============================

Tests the authentication flow with detailed output.
Run this to debug authentication issues.

Usage:
    python test_auth.py
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from graydient_auth_fixed import (
    auth_status, 
    ensure_authenticated,
    validate_key,
    load_env_key,
    _load_launcher_session,
    _load_auth_session
)


def test_session_files():
    """Test session file loading."""
    print("=" * 60)
    print("Testing Session Files")
    print("=" * 60)
    
    # Check launcher session
    launcher = _load_launcher_session()
    if launcher:
        print(f"✓ Launcher session found:")
        print(f"  API key present: {bool(launcher.get('api_key'))}")
        print(f"  API key valid: {launcher.get('api_key_valid')}")
        print(f"  Virtual user: {launcher.get('virtual_user_id', 'None')}")
    else:
        print("✗ No launcher session found")
    
    # Check auth session
    auth = _load_auth_session()
    if auth:
        print(f"✓ Auth session found:")
        print(f"  API key present: {bool(auth.get('api_key'))}")
        print(f"  API key valid: {auth.get('api_key_valid')}")
    else:
        print("✗ No auth session found")


def test_env_key():
    """Test loading key from environment."""
    print("\n" + "=" * 60)
    print("Testing Environment Key")
    print("=" * 60)
    
    key = load_env_key()
    if key:
        masked = key[:5] + "..." + key[-4:] if len(key) > 12 else "***"
        print(f"✓ Key found: {masked}")
        print(f"  Length: {len(key)}")
    else:
        print("✗ No key found in environment or .env")


def test_auth_status():
    """Test auth_status() function."""
    print("\n" + "=" * 60)
    print("Testing auth_status()")
    print("=" * 60)
    
    state = auth_status()
    print(f"API key set:    {state.api_key_set}")
    print(f"API key valid:  {state.api_key_valid}")
    print(f"Key source:     {state.api_key_source}")
    print(f"Virtual user:   {state.virtual_user_id or 'None'}")
    print(f"Email:          {state.virtual_user_email or 'None'}")
    print(f"Ready:          {state.ready}")
    print(f"Fully linked:   {state.fully_linked}")


def test_key_validation():
    """Test key validation."""
    print("\n" + "=" * 60)
    print("Testing Key Validation")
    print("=" * 60)
    
    key = load_env_key()
    if not key:
        print("✗ No key to validate")
        return
    
    print("Validating key against Graydient API...")
    is_valid, error = validate_key(key)
    
    if is_valid:
        print("✓ Key is VALID")
    else:
        print(f"✗ Key is INVALID: {error}")


def test_full_auth():
    """Test full authentication flow."""
    print("\n" + "=" * 60)
    print("Testing Full Authentication Flow")
    print("=" * 60)
    
    state = ensure_authenticated(quiet=True)
    
    if state.ready:
        print("✓ Authentication successful!")
        if state.username:
            print(f"  Welcome, {state.username}!")
        elif state.virtual_user_email:
            print(f"  Welcome, {state.virtual_user_email}!")
    else:
        print("✗ Authentication failed")
        if state.error:
            print(f"  Error: {state.error}")


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " Graydient Authentication Test ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    test_session_files()
    test_env_key()
    test_auth_status()
    test_key_validation()
    
    print("\n" + "=" * 60)
    print("Tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
