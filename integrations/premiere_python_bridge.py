"""
Graydient Exchange - Premiere Pro Python Bridge
===============================================

This Python script runs alongside Adobe Premiere Pro to provide:
1. Graydient Exchange API server
2. File server for frame uploads/downloads
3. Automatic workflow registration

USAGE:
    python premiere_python_bridge.py

Then in Premiere Pro:
    File > Scripts > Run Script File > premiere_pro_bridge.jsx

Or install as extension panel.
"""

import os
import sys
import time
import json
import shutil
import tempfile
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler
import threading
import socketserver

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from graydient_exchange_enhanced import (
        Exchange, WorkflowDefinition, InputMapping, OutputMapping
    )
except ImportError:
    print("ERROR: graydient_exchange_enhanced.py not found!")
    print("Please ensure it's in the parent directory.")
    sys.exit(1)

# Configuration
CONFIG = {
    "api_port": 8787,
    "file_port": 8788,
    "temp_dir": Path(tempfile.gettempdir()) / "graydient_premiere",
}

# Ensure temp directory exists
CONFIG["temp_dir"].mkdir(parents=True, exist_ok=True)


def setup_exchange():
    """Initialize the Graydient Exchange with workflows for Premiere."""
    ex = Exchange()
    
    # Text to Image workflow
    ex.register(WorkflowDefinition(
        name="txt2img",
        workflow="qwen",
        description="Generate images from text prompts",
        input_map=InputMapping(prompt_key="prompt"),
        output_map=OutputMapping(image_url_key="image_url"),
    ))
    
    # Image to Image (style transfer/enhancement)
    ex.register(WorkflowDefinition(
        name="img2img",
        workflow="edit-qwen",
        description="Enhance or transform existing images",
        input_map=InputMapping(
            prompt_key="prompt",
            image_key="source_image",
        ),
        output_map=OutputMapping(image_url_key="image_url"),
    ))
    
    # Animation workflow
    ex.register(WorkflowDefinition(
        name="animate",
        workflow="animate-wan22",
        description="Animate still images",
        input_map=InputMapping(
            prompt_key="motion_prompt",
            image_key="still_image",
        ),
        output_map=OutputMapping(
            image_url_key="image_url",
            video_url_key="video_url",
        ),
    ))
    
    # Upscale workflow (if available)
    ex.register(WorkflowDefinition(
        name="upscale",
        workflow="upscale",
        description="Upscale image resolution",
        input_map=InputMapping(image_key="image"),
        output_map=OutputMapping(image_url_key="image_url"),
    ))
    
    print(f"✓ Registered {len(ex.list_workflows())} workflows")
    return ex


def start_file_server(directory: Path, port: int):
    """Start a simple file server for frame uploads/downloads."""
    
    class CORSRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)
        
        def log_message(self, format, *args):
            pass  # Suppress logs
        
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()
        
        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
    
    server = HTTPServer(("127.0.0.1", port), CORSRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    print(f"✓ File server running at http://127.0.0.1:{port}")
    print(f"  Serving files from: {directory}")
    return server


def print_banner():
    """Print startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           Graydient Exchange - Premiere Pro Bridge               ║
╠══════════════════════════════════════════════════════════════════╣
║  API Server:   http://127.0.0.1:8787                            ║
║  File Server:  http://127.0.0.1:8788                            ║
║  Temp Dir:     {}║
╚══════════════════════════════════════════════════════════════════╝
""".format(str(CONFIG["temp_dir"])[:50].ljust(50)))


def main():
    """Main entry point."""
    print_banner()
    
    # Setup Exchange
    print("Setting up Graydient Exchange...")
    exchange = setup_exchange()
    
    # Start API server
    print("\nStarting servers...")
    api_url = exchange.start_api_server(port=CONFIG["api_port"])
    print(f"✓ API server running at {api_url}")
    
    # Start file server
    file_server = start_file_server(CONFIG["temp_dir"], CONFIG["file_port"])
    
    print("\n" + "="*60)
    print("Bridge is running! Premiere Pro can now connect.")
    print("="*60)
    print("\nPress Ctrl+C to stop.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        exchange.stop_api_server()
        file_server.shutdown()
        print("Goodbye!")


if __name__ == "__main__":
    main()
