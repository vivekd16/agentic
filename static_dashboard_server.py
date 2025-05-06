"""
Simple HTTP server for serving the static dashboard files

This replaces the Node.js server used during development.
"""

import os
import sys
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("dashboard")

class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom handler to serve dashboard files and proxy API requests"""
    
    def __init__(self, *args, api_url=None, **kwargs):
        self.api_url = api_url
        super().__init__(*args, **kwargs)
        
    def do_GET(self):
        """Handle GET requests"""
        # Handle API requests by proxying to the actual API server
        if self.path.startswith('/api/'):
            self.proxy_api_request('GET')
            return
            
        # Serve the static files
        return super().do_GET()
        
    def do_GET(self):
        """Handle GET requests"""
        # Handle API requests by proxying to the actual API server
        if self.path.startswith('/api/'):
            self.proxy_api_request('GET')
            return
            
        # Serve index.html for root path and client-side routing paths
        if self.path == '/' or not '.' in self.path.split('/')[-1]:
            self.path = '/index.html'
            
        # Serve the static files
        return super().do_GET()
    
    def do_POST(self):
        """Handle POST requests by proxying them to the API server"""
        if self.path.startswith('/api/'):
            self.proxy_api_request('POST')
            return
            
        self.send_error(404, "Post only supported for API endpoints")
        
    def proxy_api_request(self, method):
        """Proxy requests to the API server"""
        import requests
        
        if not self.api_url:
            self.send_error(500, "API URL not configured")
            return
            
        # Remove the /api prefix
        target_path = self.path[4:]  # Remove /api
        target_url = f"{self.api_url}{target_path}"
        
        logger.info(f"Proxying {method} request to {target_url}")
        
        # Get request body for POST requests
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        
        # Forward the request to the API server
        try:
            headers = {key: val for key, val in self.headers.items() 
                       if key.lower() not in ('host', 'content-length')}
                       
            if method == 'GET':
                response = requests.get(target_url, headers=headers, stream=True)
            else: # POST
                response = requests.post(target_url, headers=headers, data=body, stream=True)
                
            # Send response status and headers
            self.send_response(response.status_code)
            for key, val in response.headers.items():
                if key.lower() not in ('transfer-encoding', 'connection'):
                    self.send_header(key, val)
            self.end_headers()
            
            # Send response body
            self.wfile.write(response.content)
            
        except Exception as e:
            logger.error(f"Error proxying request: {e}")
            self.send_error(502, f"Error proxying request: {str(e)}")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

def find_free_port(start_port=3000, max_attempts=100):
    """Find a free port starting from start_port"""
    import socket
    
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    
    # If we couldn't find a free port, just return the start port
    # It will fail later when we try to bind to it
    return start_port
            
def get_dashboard_dir():
    """
    Get the location of the dashboard files.
    Works for both development and bundled application.
    """
    import os
    import sys
    from pathlib import Path
    
    # Define all possible locations to look for dashboard files
    possible_locations = []
    
    # Check if running from py2app or PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # py2app bundle structure
        if hasattr(sys, 'executable') and '.app/Contents/MacOS/' in sys.executable:
            app_resources = Path(sys.executable).parent.parent / "Resources"
            possible_locations.extend([
                app_resources / "resources" / "dashboard",      # For nested resources dir
                app_resources / "dashboard",                    # For direct resources
            ])
        
        # PyInstaller bundle structure (kept for compatibility)
        if hasattr(sys, '_MEIPASS'):
            base_dir = Path(sys._MEIPASS)
            possible_locations.extend([
                base_dir / "resources" / "dashboard",
                base_dir / "dashboard",
            ])
            
        # Additional search in app bundle parent directories
        executable_parent = Path(sys.executable).parent
        possible_locations.extend([
            executable_parent / "resources" / "dashboard",
            executable_parent.parent / "Resources" / "dashboard",
            executable_parent.parent / "Resources" / "resources" / "dashboard",
            executable_parent.parent.parent / "Resources" / "dashboard",
            executable_parent.parent.parent / "Resources" / "resources" / "dashboard",
        ])
    
    # Development mode locations
    script_dir = Path(os.path.abspath(os.path.dirname(__file__)))
    possible_locations.extend([
        script_dir / "resources" / "dashboard",
        script_dir.parent / "resources" / "dashboard",
        Path(os.getcwd()) / "resources" / "dashboard",
    ])
    
    # Log search locations for debugging
    search_paths = "\n - ".join([str(p) for p in possible_locations])
    print(f"Searching for dashboard in:\n - {search_paths}")
    
    # Try each location
    for location in possible_locations:
        if location.exists():
            if location.is_dir():
                # Verify it contains expected dashboard files
                if (location / "index.html").exists() or (location / "_next").exists():
                    print(f"Found dashboard at: {location}")
                    return str(location)
                else:
                    print(f"Found directory at {location} but it doesn't contain dashboard files")
            else:
                print(f"Found {location} but it's not a directory")
    
    # If we get here, we didn't find the dashboard
    raise FileNotFoundError(f"Could not find dashboard files. Looked in: {search_paths}")

def get_dashboard_dir():
    # NEW: Allow override via env var
    env_override = os.environ.get("DASHBOARD_DIR")
    if env_override:
        path = Path(env_override).resolve()
        if (path / "index.html").exists():
            return path
        else:
            print(f"[static_dashboard_server] DASHBOARD_DIR override '{path}' does not contain index.html")

    # Fallback to previous hardcoded search paths
    search_paths = [
        Path(__file__).parent / "resources" / "dashboard",
        Path(__file__).parent.parent / "resources" / "dashboard",
        Path(__file__).parent.parent.parent / "resources" / "dashboard",
    ]

    for path in search_paths:
        if (path / "index.html").exists():
            return path

    raise FileNotFoundError(f"Could not find dashboard files. Looked in: {search_paths}")

def start_dashboard(port=None, api_url=None, open_browser=True):
    """Start the dashboard server
    
    Args:
        port: Optional port to use, otherwise finds a free port
        api_url: URL of the agent API server
        open_browser: Whether to open a browser window
        
    Returns:
        tuple: (server, url) - The server instance and the dashboard URL
    """
    dashboard_dir = get_dashboard_dir()
    logger.info(f"Using dashboard files from: {dashboard_dir}")
    
    # Change to the dashboard directory
    os.chdir(dashboard_dir)
    
    # Find a free port if not specified
    if port is None:
        port = find_free_port()
    
    # Define handler with the API URL
    handler = lambda *args, **kwargs: DashboardHandler(*args, api_url=api_url, **kwargs)
    
    # Create the server
    server = ThreadedHTTPServer(("", port), handler)
    
    # Get the server URL
    dashboard_url = f"http://localhost:{port}"
    
    # Start the server in a new thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    logger.info(f"Dashboard server started at {dashboard_url}")
    logger.info(f"API proxy pointing to: {api_url}")
    
    # Open browser if requested
    if open_browser:
        webbrowser.open(dashboard_url)
    
    return server, dashboard_url

def main():
    """Main entry point when run as a script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Static Dashboard Server")
    parser.add_argument("--port", type=int, default=None, help="Port to run the dashboard on")
    parser.add_argument("--api-url", type=str, default="http://localhost:8086", 
                       help="URL of the agent API server")
    parser.add_argument("--no-browser", action="store_true", 
                       help="Don't open a browser window")
    
    args = parser.parse_args()
    
    try:
        server, url = start_dashboard(
            port=args.port,
            api_url=args.api_url,
            open_browser=not args.no_browser
        )
        
        # Keep the server running
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
            server.shutdown()
            
    except Exception as e:
        logger.error(f"Error starting dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
