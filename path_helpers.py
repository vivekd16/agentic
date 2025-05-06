"""
Path helpers for Agentic application.
"""
import os
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("path_helpers")

def get_examples_dir():
    """Get the examples directory path"""
    app_path = None
    
    # Check if we're running in a bundle
    if getattr(sys, 'frozen', False):
        # In a py2app bundle
        if '.app/Contents/MacOS/' in sys.executable:
            app_path = Path(sys.executable).parent.parent
            
    if not app_path:
        # Fallback to current directory if not in a bundle
        app_path = Path.cwd()
    
    # Define potential examples locations
    potential_paths = [
        app_path / 'Resources' / 'resources' / 'examples',
        app_path / 'Resources' / 'examples',
        Path.cwd() / 'examples',
        Path.cwd().parent / 'examples',
        Path(__file__).parent / 'examples',
        Path(__file__).parent / 'resources' / 'examples',
    ]
    
    # Log all potential paths
    for path in potential_paths:
        logger.info(f"Checking for examples at: {path}")
        if path.exists() and path.is_dir():
            logger.info(f"Found examples directory at: {path}")
            # Check if it actually contains Python files
            py_files = list(path.glob('*.py'))
            logger.info(f"Contains {len(py_files)} Python files")
            if py_files:
                return path
    
    # If we get here, we didn't find a suitable directory
    logger.warning("No examples directory found with Python files")
    return Path.cwd() / 'examples'  # Return a default path

def get_resource_path(relative_path):
    """Get absolute path to a resource"""
    if getattr(sys, 'frozen', False):
        # In a py2app bundle
        if '.app/Contents/MacOS/' in sys.executable:
            app_path = Path(sys.executable).parent.parent
            return app_path / 'Resources' / relative_path
    
    # Fallback to relative path from current directory
    return Path.cwd() / relative_path

def get_runtime_dir():
    """Get the runtime directory"""
    # Create runtime directory in app resources if possible
    if getattr(sys, 'frozen', False) and '.app/Contents/MacOS/' in sys.executable:
        runtime_dir = Path(sys.executable).parent.parent / 'Resources' / 'runtime'
    else:
        runtime_dir = Path.cwd() / 'runtime'
    
    # Ensure it exists
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir
