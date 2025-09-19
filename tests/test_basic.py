# tests/test_basic.py
"""
Basic tests to verify test setup and imports work correctly.
"""

import sys
import os

def test_src_in_path():
    """Test that src directory is in Python path."""
    assert 'src' in sys.path[0]

def test_imports():
    """Test that basic imports work."""
    try:
        from config import validate_configuration
        from main import app
        from provider_openrouter import generate_with_openrouter
        assert True
    except ImportError as e:
        assert False, f"Import failed: {e}"

def test_app_creation():
    """Test that Flask app can be created."""
    from main import app
    assert app is not None
    assert app.name is not None

def test_config_validation():
    """Test that configuration validation works."""
    from config import validate_configuration
    # This should work even with minimal config
    is_valid, issues = validate_configuration()
    # We don't assert validity since it depends on environment
    # but we verify the function runs without error
    assert isinstance(is_valid, bool)
    assert isinstance(issues, list)