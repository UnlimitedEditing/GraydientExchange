"""
Graydient Exchange - Generic Bridge
====================================

A minimal Python bridge for any application to connect to Graydient.
Provides HTTP API and file server with all workflows pre-registered.

USAGE:
    python generic_bridge.py [--port 8787] [--file-port 8788]

Then from any application:
    POST http://127.0.0.1:8787/api/v1/render
    GET  http://127.0.0.1:8787/api/v1/jobs/{job_id}
"""

import argparse
import os
import sys
import time
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
except ImportError as e:
    print(f"ERROR: Cannot import graydient_exchange_enhanced: {e}")
    print("Make sure graydient_exchange_enhanced.py is in the parent directory")
    sys.exit(1)


def setup_exchange(api_key=None):
    """Setup exchange with common workflows."""
    ex = Exchange(api_key=api_key)
    
    # Text to Image
    ex.register(WorkflowDefinition(
        name="txt2img",
        workflow="qwen",
        input_map=InputMapping(prompt_key="prompt"),
        output_map=OutputMapping(image_url_key="image_url"),
    ))
    
    # Image to Image
    ex.register(WorkflowDefinition(
        name="img2img",
        workflow="edit-qwen",
        input_map=InputMapping(
            prompt_key="prompt",
            image_key="source_image",
        ),
        output_map=OutputMapping(image_url_key="image_url"),
    ))
    
    # Animation
    ex.register(WorkflowDefinition(
        name="animate",
        workflow="animate-wan22",
        input_map=InputMapping(
            prompt_key="motion_prompt",
            image_key="still_image",
        ),
        output_map=OutputMapping(video_url_key="video_url"),
    ))
    
    # Upscale
    ex.register(WorkflowDefinition(
        name="upscale",
        workflow="upscale",
        input_map=InputMapping(image_key="image"),
        output_map=OutputMapping(image_url_key="image_url"),
    ))
    
    return ex


def start_file_server(directory, port):
    """Start file server for image serving."""
    
    class CORSHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)
        
        def log_message(self, format, *args):
            pass
        
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()
    
    server = HTTPServer(("127.0.0.1", port), CORSHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main():
    parser = argparse.ArgumentParser(description="Graydient Exchange Generic Bridge")
    parser.add_argument("--port", type=int, default=8787, help="API server port")
    parser.add_argument("--file-port", type=int, default=8788, help="File server port")
    parser.add_argument("--api-key", type=str, default=None, help="Graydient API key")
    args = parser.parse_args()
    
    # Use provided API key or from environment
    api_key = args.api_key or os.environ.get("GRAYDIENT_KEY")
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              Graydient Exchange - Generic Bridge                 ║
╠══════════════════════════════════════════════════════════════════╣
║  API Server:   http://127.0.0.1:{}                            ║
║  File Server:  http://127.0.0.1:{}                            ║
╚══════════════════════════════════════════════════════════════════╝
""".format(args.port, args.file_port))
    
    # Setup exchange
    print("Setting up Exchange...")
    exchange = setup_exchange(api_key)
    
    print(f"\nRegistered workflows:")
    for wf in exchange.list_workflows():
        print(f"  • {wf['name']} - {wf['description'] or 'No description'}")
    
    # Start servers
    print(f"\nStarting servers...")
    api_url = exchange.start_api_server(port=args.port)
    print(f"✓ API server: {api_url}")
    
    temp_dir = Path(tempfile.gettempdir()) / "graydient_generic"
    temp_dir.mkdir(exist_ok=True)
    file_server = start_file_server(temp_dir, args.file_port)
    print(f"✓ File server: http://127.0.0.1:{args.file_port}")
    
    print("\n" + "="*60)
    print("Bridge is running! Press Ctrl+C to stop.")
    print("="*60 + "\n")
    
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
