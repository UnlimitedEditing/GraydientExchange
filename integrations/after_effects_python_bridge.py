"""
Graydient Exchange - After Effects Python Bridge
================================================

This Python script runs alongside Adobe After Effects to provide:
1. Graydient Exchange API server
2. File server for image uploads/downloads
3. Automatic workflow registration optimized for AE workflows

USAGE:
    python after_effects_python_bridge.py

Then in After Effects:
    File > Scripts > Run Script File > after_effects_bridge.jsx

Or copy to ScriptUI Panels for dockable panel:
    Windows: C:\Program Files\Adobe\Adobe After Effects\Support Files\Scripts\ScriptUI Panels
    Mac: /Applications/Adobe After Effects/Scripts/ScriptUI Panels
"""

import os
import sys
import time
import json
import shutil
import tempfile
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from graydient_exchange_enhanced import (
        Exchange, WorkflowDefinition, InputMapping, OutputMapping
    )
except ImportError:
    print("ERROR: graydient_exchange_enhanced.py not found!")
    sys.exit(1)

# Configuration
CONFIG = {
    "api_port": 8787,
    "file_port": 8788,
    "temp_dir": Path(tempfile.gettempdir()) / "graydient_ae",
}

# Ensure temp directory exists
CONFIG["temp_dir"].mkdir(parents=True, exist_ok=True)


def setup_exchange():
    """Initialize the Graydient Exchange with workflows for After Effects."""
    ex = Exchange()
    
    # Text to Image - for generating source footage
    ex.register(WorkflowDefinition(
        name="txt2img",
        workflow="qwen",
        description="Generate images from text prompts",
        input_map=InputMapping(
            prompt_key="prompt",
            seed_key="seed",
            negative_key="negative",
        ),
        output_map=OutputMapping(image_url_key="image_url"),
        default_params={"num_images": 1, "format": "png"},
    ))
    
    # Image to Image - for style transfer and enhancement
    ex.register(WorkflowDefinition(
        name="img2img",
        workflow="edit-qwen",
        description="Transform or enhance existing images",
        input_map=InputMapping(
            prompt_key="prompt",
            image_key="source_image",
            strength_key="strength",
        ),
        output_map=OutputMapping(image_url_key="image_url"),
    ))
    
    # Animation - for image to video
    ex.register(WorkflowDefinition(
        name="animate",
        workflow="animate-wan22",
        description="Animate still images to video",
        input_map=InputMapping(
            prompt_key="motion_prompt",
            image_key="still_image",
            seed_key="seed",
        ),
        output_map=OutputMapping(
            video_url_key="video_url",
            image_url_key="image_url",
        ),
    ))
    
    # Upscale - for resolution enhancement
    ex.register(WorkflowDefinition(
        name="upscale",
        workflow="upscale",
        description="Upscale image resolution",
        input_map=InputMapping(image_key="image"),
        output_map=OutputMapping(image_url_key="image_url"),
    ))
    
    # Inpainting - for object removal/replacement
    ex.register(WorkflowDefinition(
        name="inpaint",
        workflow="inpaint",
        description="Inpaint/edit specific regions",
        input_map=InputMapping(
            prompt_key="prompt",
            image_key="image",
            mask_key="mask",
        ),
        output_map=OutputMapping(image_url_key="image_url"),
    ))
    
    print(f"✓ Registered {len(ex.list_workflows())} workflows for After Effects")
    return ex


def start_file_server(directory: Path, port: int):
    """Start a simple file server for image uploads/downloads."""
    
    class CORSRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)
        
        def log_message(self, format, *args):
            pass
        
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
    return server


def print_banner():
    """Print startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║          Graydient Exchange - After Effects Bridge               ║
╠══════════════════════════════════════════════════════════════════╣
║  API Server:   http://127.0.0.1:8787                            ║
║  File Server:  http://127.0.0.1:8788                            ║
║  Temp Dir:     {}║
╚══════════════════════════════════════════════════════════════════╝
""".format(str(CONFIG["temp_dir"])[:50].ljust(50)))
    print("\nWorkflows registered:")
    print("  • txt2img  - Generate images from text")
    print("  • img2img  - Style transfer/enhancement")
    print("  • animate  - Image to video animation")
    print("  • upscale  - Resolution enhancement")
    print("  • inpaint  - Object removal/editing")


def main():
    """Main entry point."""
    print_banner()
    
    # Setup Exchange
    print("\nInitializing Graydient Exchange...")
    exchange = setup_exchange()
    
    # Start servers
    print("\nStarting servers...")
    api_url = exchange.start_api_server(port=CONFIG["api_port"])
    print(f"✓ API server running at {api_url}")
    
    file_server = start_file_server(CONFIG["temp_dir"], CONFIG["file_port"])
    
    print("\n" + "="*60)
    print("Bridge is running! After Effects can now connect.")
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
