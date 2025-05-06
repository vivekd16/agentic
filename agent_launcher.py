import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget, QComboBox, QTabWidget, QTextEdit, QHBoxLayout, QFrame
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import subprocess
import os
from pathlib import Path
import time
import webbrowser

import agentic
import transformers
import threading
import sys

print("\n".join(sys.path))

# Very early in agent_launcher.py
try:
    import runtime_hook
    print("Successfully ran runtime_hook from agent_launcher.py")
except Exception as e:
    print(f"Error running runtime_hook: {e}")

def debug_startup():
    import os
    import sys
    import traceback
    
    log_path = os.path.expanduser("~/agentic_debug.log")
    with open(log_path, "w") as f:
        f.write(f"Python: {sys.version}\n")
        f.write(f"Executable: {sys.executable}\n")
        f.write(f"Working directory: {os.getcwd()}\n")
        f.write(f"sys.path: {sys.path}\n")
        
        # Log environment variables
        f.write("\nEnvironment variables:\n")
        for key, value in os.environ.items():
            if key.startswith('PYTHON') or key.startswith('QT') or key.startswith('PATH'):
                f.write(f"{key}={value}\n")
        
        try:
            # Import key modules
            import PyQt5
            f.write(f"\nPyQt5 imported successfully from {PyQt5.__file__}\n")
            
            from PyQt5.QtWidgets import QApplication
            f.write("QApplication imported successfully\n")
            
            from PyQt5.QtCore import QLibraryInfo
            f.write(f"Qt library paths: {QLibraryInfo.location(QLibraryInfo.LibrariesPath)}\n")
            f.write(f"Qt plugin paths: {QLibraryInfo.location(QLibraryInfo.PluginsPath)}\n")
            
            # Try importing other key modules
            modules_to_check = ['import time', 'import os', 'import sys', 'import subprocess', 
                               'import httpx', 'import json', 'import webbrowser']
            
            for module_str in modules_to_check:
                try:
                    exec(module_str)
                    f.write(f"{module_str} - OK\n")
                except Exception as e:
                    f.write(f"{module_str} - ERROR: {str(e)}\n")
                    
        except Exception as e:
            f.write(f"\nError during imports: {str(e)}\n")
            f.write(traceback.format_exc())
    
    # Try to print to stdout/stderr as well
    print(f"Debug log written to {log_path}")

# Call debug function at startup
debug_startup()

def setup_qt_plugins():
    import os
    import sys
    from PyQt5.QtCore import QCoreApplication
    
    if getattr(sys, 'frozen', False):
        # We're in a bundle
        bundle_dir = os.path.dirname(os.path.dirname(sys.executable))
        
        # Get the actual PyQt5 plugin path from the bundle
        import PyQt5
        pyqt_dir = os.path.dirname(PyQt5.__file__)
        qt_plugin_path = os.path.join(pyqt_dir, 'Qt5', 'plugins')
        
        # Also check the standard locations
        plugin_paths = [
            qt_plugin_path,
            os.path.join(bundle_dir, 'PlugIns'),
            os.path.join(bundle_dir, 'Resources', 'plugins')
        ]
        
        # Use only existing paths
        existing_paths = [p for p in plugin_paths if os.path.exists(p)]
        
        if existing_paths:
            # Set the paths for Qt to find its plugins
            QCoreApplication.setLibraryPaths(existing_paths)
            
            # Also set environment variable as a backup
            os.environ['QT_PLUGIN_PATH'] = os.pathsep.join(existing_paths)
            
            # Debug output
            with open(os.path.expanduser("~/qt_paths.log"), "w") as f:
                f.write(f"Setting Qt plugin paths: {existing_paths}\n")
                
                # List what's in these directories
                for path in existing_paths:
                    f.write(f"\nContents of {path}:\n")
                    if os.path.exists(path):
                        f.write(str(os.listdir(path)))
                    else:
                        f.write("Directory does not exist")

# Call the function right after it's defined
setup_qt_plugins()

def find_examples():
    """Find examples directory with Python files in both app bundle and development environments"""
    from pathlib import Path
    import os
    import sys

    # Check environment variable first
    env_path = os.environ.get("AGENTIC_EXAMPLES_DIR")
    if env_path:
        path = Path(env_path)
        print(f"Using AGENTIC_EXAMPLES_DIR from environment: {path}")
        if path.exists() and path.is_dir():
            py_files = list(path.glob('*.py'))
            if py_files:
                print(f"Found examples directory with {len(py_files)} Python files")
                return path

    # Detect if we're running from a frozen app bundle
    is_frozen = getattr(sys, 'frozen', False)
    
    # Candidate paths - order matters
    candidate_paths = []
    
    if is_frozen:
        # App bundle paths
        base_dir = Path(sys.executable).parent.parent  # e.g., /Contents/MacOS/../..
        candidate_paths.extend([
            base_dir / "Resources" / "resources" / "examples",  # Main app bundle location
            base_dir / "Resources" / "examples",                # Fallback location
        ])
    
    # Development environment paths - add these regardless of frozen state
    # (as fallbacks for frozen state and primaries for dev mode)
    script_dir = Path(os.path.abspath(os.path.dirname(sys.argv[0] or '.')))
    candidate_paths.extend([
        script_dir / "examples",                     # Examples at same level as script
        script_dir.parent / "examples",              # Examples in parent directory
        Path.cwd() / "examples",                     # Examples in current directory
        Path(__file__).parent.parent / "examples",   # Examples relative to module
        Path.cwd() / "resources" / "examples",       # Examples in resources subdirectory
    ])
    
    # Try each path in order
    for path in candidate_paths:
        print(f"Checking for examples in: {path}")
        if path.exists() and path.is_dir():
            py_files = list(path.glob('*.py'))
            if py_files:
                print(f"Found examples directory with {len(py_files)} Python files")
                return path
    
    print("Examples directory not found.")
    # Return a default path even if nothing found (caller can check if it exists)
    return Path.cwd() / "examples"

#---------------------------- Initialzation steps -----------------------------------------#




#----------------------------- Ensure we're using the right attributes for high DPI displays on macOS
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


    
import logging
#---------------------------- Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("agentic.launcher")



#---------------------------- Initialize PyQt high DPI settings
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


    
#---------------------------- Import our path helpers
try:
    from path_helpers import get_examples_dir, get_resource_path, get_runtime_dir
except ImportError:
    logger.warning("path_helpers module not found, using default paths")
    
    def get_examples_dir():
        """Fallback implementation for examples directory"""
        if getattr(sys, 'frozen', False):
            if '.app/Contents/MacOS/' in sys.executable:
                return Path(sys.executable).parent.parent / "Resources" / "examples"
        return Path("examples")
    
    def get_resource_path(relative_path):
        """Fallback implementation for resource path"""
        if getattr(sys, 'frozen', False):
            if '.app/Contents/MacOS/' in sys.executable:
                base_path = Path(sys.executable).parent.parent / "Resources"
            else:
                base_path = Path(sys.executable).parent
        else:
            base_path = Path(os.path.abspath(os.path.dirname(__file__)))
        return base_path / relative_path
    
    def get_runtime_dir():
        """Fallback implementation for runtime directory"""
        if getattr(sys, 'frozen', False):
            if '.app/Contents/MacOS/' in sys.executable:
                runtime_dir = Path(sys.executable).parent.parent / "Resources" / "runtime"
            else:
                runtime_dir = Path(sys.executable).parent / "runtime"
        else:
            runtime_dir = Path("runtime")
        os.makedirs(runtime_dir, exist_ok=True)
        return runtime_dir

    
#------------------------------ Setup runtime directory
os.makedirs(get_runtime_dir(), exist_ok=True)
os.chdir(get_runtime_dir())
logger.info(f"Working directory set to {os.getcwd()}")










#-------------------------------------------- Agent and Dashboard threads -------------------------------#

class AgentThread(QThread):
    update_signal = pyqtSignal(str)
        
    def __init__(self, agent_path, env=None):
        super().__init__()
        self.agent_path = agent_path
        self.process = None
        self.running = True
        self.env = env or os.environ.copy()  # Use provided env or default
        
    def run(self):
        try:
            # Get the current Python executable - this is the one inside our app bundle
            python_exe = sys.executable
            
            # Log debugging info
            self.update_signal.emit(f"[debug] Python executable: {python_exe}")
            self.update_signal.emit(f"[debug] Agent path: {self.agent_path}")
            self.update_signal.emit(f"[debug] Current working directory: {os.getcwd()}")
            
            # Prepare environment with correct PYTHONPATH
            env = os.environ.copy()
            
            # Get app bundle directories
            app_dir = Path(python_exe).parent.parent  # /Contents/MacOS/python -> /Contents
            resources_dir = app_dir / "Resources"
            bundle_lib = resources_dir / "lib" / "python3.12"
            site_pkgs = bundle_lib / "site-packages"
            
            # Set PYTHONPATH to include our bundled paths
            env["PYTHONPATH"] = os.pathsep.join([
                str(site_pkgs),
                str(bundle_lib),
                str(resources_dir),
            ])
            
            # Explicitly unset PYTHONHOME if it exists (let the interpreter find its home directory)
            if "PYTHONHOME" in env:
                del env["PYTHONHOME"]
            
            # Make sure working directory is the runtime directory (could have been changed)
            runtime_dir = resources_dir / "runtime"
            os.makedirs(str(runtime_dir), exist_ok=True)
            os.chdir(str(runtime_dir))
            
            # Log the environment setup
            self.update_signal.emit(f"[debug] Environment for subprocess:")
            self.update_signal.emit(f"  PYTHONPATH = {env['PYTHONPATH']}")
            self.update_signal.emit(f"  Using Python: {python_exe}")
            self.update_signal.emit(f"  Working directory: {os.getcwd()}")
            
            # Construct command with the exact same Python executable
            cmd = [
                python_exe,
                "-m", "agentic.cli", "serve", str(self.agent_path)
            ]
            
            self.update_signal.emit(f"[debug] Launching agent subprocess with command: {' '.join(cmd)}")
            
            # Create the subprocess with the prepared environment
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
                cwd=str(runtime_dir)  # Ensure consistent working directory
            )
            
            # A buffer to collect error output in case of crash
            error_buffer = []
            max_error_lines = 50  # Keep the last 50 lines of error output
            
            # Read output in the thread loop
            while self.running and self.process and self.process.poll() is None:
                stdout_line = self.process.stdout.readline() if self.process.stdout else ""
                if stdout_line.strip():
                    self.update_signal.emit(stdout_line.strip())
                
                stderr_line = self.process.stderr.readline() if self.process.stderr else ""
                if stderr_line.strip():
                    # Add to error buffer for complete error context
                    error_buffer.append(stderr_line.strip())
                    if len(error_buffer) > max_error_lines:
                        error_buffer.pop(0)  # Keep buffer at max size
                    
                    # Output the error line to the UI
                    self.update_signal.emit(f"ERROR: {stderr_line.strip()}")
                
                # Short sleep to prevent high CPU usage
                time.sleep(0.01)
            
            # Check why the process ended
            exit_code = self.process.returncode if self.process else None
            
            # Collect any remaining output
            if self.process:
                # Get any remaining stdout
                for line in self.process.stdout:
                    if line.strip():
                        self.update_signal.emit(line.strip())
                
                # Get any remaining stderr
                for line in self.process.stderr:
                    if line.strip():
                        error_buffer.append(line.strip())
                        if len(error_buffer) > max_error_lines:
                            error_buffer.pop(0)
                        self.update_signal.emit(f"ERROR: {line.strip()}")
            
            # If process crashed (exit code != 0), show the complete error context
            if exit_code != 0:
                self.update_signal.emit(f"[debug] Agent process exited with code: {exit_code}")
                self.update_signal.emit(f"===== FULL ERROR CONTEXT =====")
                for line in error_buffer:
                    self.update_signal.emit(line)
                self.update_signal.emit(f"===== END ERROR CONTEXT =====")
            else:
                self.update_signal.emit(f"[debug] Agent process exited with code: {exit_code}")
                
        except Exception as e:
            import traceback
            self.update_signal.emit(f"Error: {str(e)}")
            self.update_signal.emit(f"Traceback: {traceback.format_exc()}")
    
    def stop(self):
        """Stop the agent process"""
        self.running = False
        
        if self.process:
            # First try a gentle terminate
            self.update_signal.emit("Terminating agent process...")
            try:
                self.process.terminate()
                
                # Give it a moment to terminate gracefully
                try:
                    self.process.wait(timeout=3)
                    self.update_signal.emit(f"Process terminated with exit code: {self.process.returncode}")
                except subprocess.TimeoutExpired:
                    # If it doesn't terminate within timeout, force kill
                    self.update_signal.emit("Force killing agent process...")
                    self.process.kill()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.update_signal.emit("WARNING: Process could not be killed within timeout")
            except Exception as e:
                self.update_signal.emit(f"Error during process termination: {str(e)}")
                
            # Make sure to close the pipes to avoid resource leaks
            try:
                if self.process.stdout:
                    self.process.stdout.close()
                if self.process.stderr:
                    self.process.stderr.close()
            except Exception as e:
                self.update_signal.emit(f"Error closing pipes: {str(e)}")
                
            # Set to None to ensure garbage collection
            self.process = None
            
            

            


class DashboardThread(QThread):
    update_signal = pyqtSignal(str)
    
    def __init__(self, port=3001, env=None):
        super().__init__()
        self.port = port
        self.process = None
        self.running = True
        self.env = env or os.environ.copy()
        self.server = None # for compiled dashboard


    def run(self):
        try:
            # Check if we should use static dashboard
            use_static = self.env.get("USE_STATIC_DASHBOARD", "0") == "1"
            
            if use_static:
                # Use static dashboard server
                from static_dashboard_server import start_dashboard
                
                self.update_signal.emit(f"Starting static dashboard server on port {self.port}...")
                
                # Get the API URL from environment
                api_url = self.env.get("AGENT_SERVER_URL", f"http://localhost:8086")
                self.update_signal.emit(f"Using API URL: {api_url}")
                
                # Start the dashboard
                self.server, dashboard_url = start_dashboard(
                    port=self.port,
                    api_url=api_url,
                    open_browser=False
                )
                
                self.update_signal.emit(f"Dashboard started at {dashboard_url}")
                
                # Keep the thread running
                while self.running and self.server:
                    time.sleep(1)
            else:
                # Use the CLI dashboard
                cmd = [sys.executable, "-m", "agentic.cli", "dashboard", "start", "--dev", "--port", str(self.port)]
                self.update_signal.emit(f"Running command: {' '.join(cmd)}")
                
                # Use the environment with our custom variables
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    env=self.env,
                    cwd=os.getcwd()
                )
                
                # Read output in the thread loop
                while self.running and self.process and self.process.poll() is None:
                    stdout_line = self.process.stdout.readline()
                    if stdout_line:
                        self.update_signal.emit(stdout_line.strip())
                    
                    stderr_line = self.process.stderr.readline()
                    if stderr_line:
                        self.update_signal.emit(stderr_line.strip())
                    
                    # Short sleep to prevent high CPU usage
                    time.sleep(0.01)
                
        except Exception as e:
            self.update_signal.emit(f"Error: {str(e)}")
            
    def stop(self): 
        self.running = False
        if self.server:
            self.update_signal.emit("Shutting down dashboard server...")
            self.server.shutdown()
            self.server = None
            
        #if self.process:
            #self.update_signal.emit("Terminating dashboard process...")
            #self.process.terminate()
            #time.sleep(1)
            #if self.process.poll() is None:
                #self.update_signal.emit("Force killing dashboard process...")
                #self.process.kill()

class AgenticApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # Kill any existing dashboard processes first
        self.cleanup_existing_processes()
        # Initialize UI and other components
        self.initUI()
        # Set up crash logging
        self.setup_crash_logging()
        self.current_error_message = None

    def cleanup_existing_processes(self):
        """Kill any existing dashboard processes that might be running"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.cmdline()
                    if any('dashboard' in cmd and 'start' in cmd for cmd in cmdline if isinstance(cmd, str)):
                        self.add_log(f"Terminating existing dashboard process: {proc.pid}")
                        proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass           
        except ImportError:
            # If psutil isn't available, we'll skip this step
            pass
    
    def initUI(self):
        # Force style to Fusion for better macOS compatibility
        QApplication.setStyle("Fusion")
        
        self.setWindowTitle("Agentic")
        self.setGeometry(100, 100, 900, 600)
        
        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # Create tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create agent tab
        self.agent_tab = QWidget()
        self.tabs.addTab(self.agent_tab, "Agent")
        
        agent_layout = QVBoxLayout()
        self.agent_tab.setLayout(agent_layout)
        
        # Agent selection
        selection_frame = QFrame()
        selection_frame.setFrameShape(QFrame.StyledPanel)
        selection_layout = QVBoxLayout()
        selection_frame.setLayout(selection_layout)
        
        title_label = QLabel("Select Agent:")
        title_label.setFont(QFont('Arial', 12))
        selection_layout.addWidget(title_label)
        
        self.agent_combo = QComboBox()
        self.agent_combo.setMinimumHeight(30)  # Increase height for better visibility
        selection_layout.addWidget(self.agent_combo)
        
        agent_layout.addWidget(selection_frame)
        
        # Agent controls
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.StyledPanel)
        control_layout = QVBoxLayout()
        control_frame.setLayout(control_layout)
        
        controls_label = QLabel("Controls")
        controls_label.setFont(QFont('Arial', 12))
        control_layout.addWidget(controls_label)
        
        # Agent buttons
        agent_buttons = QHBoxLayout()
        
        self.start_agent_btn = QPushButton("Start Agent")
        self.start_agent_btn.setMinimumHeight(40)
        self.start_agent_btn.clicked.connect(self.start_agent)
        agent_buttons.addWidget(self.start_agent_btn)
        
        self.stop_agent_btn = QPushButton("Stop Agent")
        self.stop_agent_btn.setMinimumHeight(40)
        self.stop_agent_btn.clicked.connect(self.stop_agent)
        self.stop_agent_btn.setEnabled(False)
        agent_buttons.addWidget(self.stop_agent_btn)
        
        control_layout.addLayout(agent_buttons)
        
        # Dashboard buttons
        dashboard_buttons = QHBoxLayout()
        
        self.start_dashboard_btn = QPushButton("Start Dashboard")
        self.start_dashboard_btn.setMinimumHeight(40)
        self.start_dashboard_btn.clicked.connect(self.start_dashboard)
        dashboard_buttons.addWidget(self.start_dashboard_btn)
        
        self.stop_dashboard_btn = QPushButton("Stop Dashboard")
        self.stop_dashboard_btn.setMinimumHeight(40)
        self.stop_dashboard_btn.clicked.connect(self.stop_dashboard)
        self.stop_dashboard_btn.setEnabled(False)
        dashboard_buttons.addWidget(self.stop_dashboard_btn)
        
        control_layout.addLayout(dashboard_buttons)
        
        # Browse button
        self.open_browser_btn = QPushButton("Open in Browser")
        self.open_browser_btn.setMinimumHeight(40)
        self.open_browser_btn.clicked.connect(self.open_browser)
        control_layout.addWidget(self.open_browser_btn)

        restart_btn = QPushButton("Restart All")
        restart_btn.setMinimumHeight(40)
        restart_btn.clicked.connect(self.restart_everything)
        control_layout.addWidget(restart_btn)
        
        agent_layout.addWidget(control_frame)
        
        # Status frame
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_layout = QVBoxLayout()
        status_frame.setLayout(status_layout)
        
        status_label = QLabel("Status")
        status_label.setFont(QFont('Arial', 12))
        status_layout.addWidget(status_label)
        
        self.agent_status = QLabel("Agent: Not running")
        status_layout.addWidget(self.agent_status)
        
        self.dashboard_status = QLabel("Dashboard: Not running")
        status_layout.addWidget(self.dashboard_status)
        
        agent_layout.addWidget(status_frame)
        
        # Add spacer
        agent_layout.addStretch()
        
        # Log tab
        self.log_tab = QWidget()
        self.tabs.addTab(self.log_tab, "Logs")
        
        log_layout = QVBoxLayout()
        self.log_tab.setLayout(log_layout)
        
        # Create scrollable text area for logs
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QTextEdit.WidgetWidth)
        log_layout.addWidget(self.log_output)
        
        log_buttons_layout = QHBoxLayout()  # Create a horizontal layout for the buttons

        # Create "Clear Logs" button
        self.clear_logs_btn = QPushButton("Clear Logs")
        self.clear_logs_btn.setMinimumHeight(40)
        self.clear_logs_btn.clicked.connect(self.clear_logs)
        log_buttons_layout.addWidget(self.clear_logs_btn)

        # Create "Copy Logs" button
        self.copy_logs_btn = QPushButton("Copy Logs")
        self.copy_logs_btn.setMinimumHeight(40)
        self.copy_logs_btn.clicked.connect(self.copy_logs)
        log_buttons_layout.addWidget(self.copy_logs_btn)

        # Add the button layout to the main log layout
        log_layout.addLayout(log_buttons_layout)
        
        # Initialize threads
        self.agent_thread = None
        self.dashboard_thread = None
        self.dashboard_port = 3001
        self.agent_port = 8086
        
        # Populate agents
        self.populate_agents()
        
        # Initial log
        self.add_log("Agentic App started")

    def populate_agents(self):
        """Find and list available agents"""
        self.agents = []

        # Use our path helper to find examples directory
        examples_dir = find_examples()
        self.add_log(f"Looking for examples in: {examples_dir}")

        if examples_dir and examples_dir.exists():
            # Log directory contents for debugging
            self.add_log(f"Examples directory contents: {list(examples_dir.glob('*'))}")

            # Find Python files
            for agent_file in examples_dir.glob("*.py"):
                # Skip __init__.py and other hidden files
                if agent_file.name.startswith("_"):
                    continue

                if agent_file.is_file():
                    self.add_log(f"Found agent file: {agent_file.name}")
                    self.agents.append((agent_file.name, agent_file))
                    self.agent_combo.addItem(agent_file.name)

            if self.agents:
                self.add_log(f"Found {len(self.agents)} agent(s)")
            else:
                self.add_log("No agent Python files found in examples directory")
        else:
            self.add_log(f"Examples directory not found: {examples_dir}")


    def is_port_in_use(self, port):
        """Check if a port is already in use"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def detect_module_error(self):
        """
        Detect the most recent ModuleNotFoundError in the log output.
        Returns the error message or None if no module error found.
        """
        try:
            # Get the log text and split into lines
            log_text = self.log_output.toPlainText()
            lines = log_text.split('\n')
            
            # Search for the most recent ModuleNotFoundError
            for line in reversed(lines):  # Start from the most recent log line
                if "ModuleNotFoundError:" in line:
                    # Extract the specific module name from the error
                    error_part = line.split("ModuleNotFoundError:")[1].strip()
                    return f"Missing module: {error_part}"
            
            # If no specific module error found
            return "Check the logs for more details."
        except Exception as e:
            self.add_log(f"Error detecting module error: {str(e)}")
            return "Check the logs for more details."

    def find_module_errors(self):
        """Find all ModuleNotFoundError instances in the log output"""
        try:
            # Get the log text
            log_text = self.log_output.toPlainText()
            
            # Find ModuleNotFoundError lines
            module_errors = []
            for line in log_text.split('\n'):
                # Look specifically for the ModuleNotFoundError line format
                if "ModuleNotFoundError: No module named" in line:
                    # Extract module name - be specific about the format
                    parts = line.split("ModuleNotFoundError: No module named")
                    if len(parts) > 1:
                        # The module name is usually in quotes in the error message
                        module_name = parts[1].strip()
                        # Remove quotes if present
                        module_name = module_name.strip("'").strip('"')
                        module_errors.append(f"Missing module: {module_name}")
            
            # If we found module errors, use those
            if module_errors:
                return "\n".join(module_errors)
            
            # If no module errors, check for import errors
            import_errors = []
            for line in log_text.split('\n'):
                if "ImportError:" in line:
                    parts = line.split("ImportError:")
                    if len(parts) > 1:
                        error_msg = parts[1].strip()
                        import_errors.append(f"Import error: {error_msg}")
            
            if import_errors:
                return "\n".join(import_errors)
                
            # If no specific errors found, return generic message
            return "Check the logs for more details."
            
        except Exception as e:
            return f"Error scanning logs: {str(e)}"

    def find_last_module_error(self):
        """Find the most recent ModuleNotFoundError in the logs for the current agent"""
        try:
            # First clear any old content from the log that might be from previous agents
            current_log = self.log_output.toPlainText()
            
            # Find the last instance of a ModuleNotFoundError in the current log
            last_error = None
            for line in current_log.split('\n'):
                if "ModuleNotFoundError: No module named" in line:
                    # Extract just the module name inside the quotes
                    import re
                    match = re.search(r"No module named '([^']+)'", line)
                    if match:
                        last_error = f"Missing module: {match.group(1)}"
            
            # Return the last module error found, or a generic message
            return last_error or "Check the logs for more details."
            
        except Exception as e:
            print(f"Error in find_last_module_error: {e}")
            return "Check the logs for more details."


        
#----------------------------- starting and stopping agent and dashboard -------------------#
    def start_agent(self):
        """Start the agent with focused error detection"""
        if not self.agents:
            self.add_log("No agents available")
            return

        selected_idx = self.agent_combo.currentIndex()
        if selected_idx < 0:
            self.add_log("No agent selected")
            return

        # First make sure any existing agent is stopped
        if self.agent_thread:
            self.stop_agent()
            time.sleep(2)

        # Clear the log buffer to start with fresh logs for this agent
        self.log_output.clear()
        self.add_log("Log cleared for new agent")

        # Get the selected agent
        agent_path = self.agents[selected_idx][1]
        agent_name = self.agents[selected_idx][0]

        # Reset working directory
        app_dir = Path(sys.executable).parent.parent
        runtime_dir = app_dir / "Resources" / "runtime"
        os.makedirs(str(runtime_dir), exist_ok=True)
        os.chdir(str(runtime_dir))
        self.add_log(f"Reset working directory to: {os.getcwd()}")

        # Check path exists
        if not os.path.exists(agent_path):
            self.add_log(f"Error: Agent file not found: {agent_path}")
            return

        # Make sure port is free
        if self.is_port_in_use(self.agent_port):
            self.add_log(f"Port {self.agent_port} is in use, freeing it")
            self.kill_process_on_port(self.agent_port)
            time.sleep(2)

        # Start the agent
        agent_absolute_path = os.path.abspath(agent_path)
        self.add_log(f"Starting agent: {agent_name} (using path: {agent_absolute_path})")

        # Create and start thread
        self.agent_thread = AgentThread(agent_absolute_path)
        self.agent_thread.update_signal.connect(self.add_log)
        self.agent_thread.start()

        # Update UI
        self.start_agent_btn.setEnabled(False)
        self.stop_agent_btn.setEnabled(True)
        self.agent_status.setText(f"Agent: Starting - {agent_name}")

        # Get the correct base name for the URL
        agent_base = os.path.splitext(os.path.basename(agent_absolute_path))[0].lower()
        self.add_log(f"Agent API will be available at: http://localhost:{self.agent_port}/{agent_base}")

        # Wait for agent server to start
        self.add_log("Waiting for agent server to initialize...")
        agent_started = False
        for i in range(10):
            if self.is_port_in_use(self.agent_port):
                self.add_log("Agent server is running")
                agent_started = True
                break
                
            # Check if process has exited with error
            if self.agent_thread and hasattr(self.agent_thread, 'process') and self.agent_thread.process:
                if self.agent_thread.process.poll() is not None:
                    # Process has terminated - wait for logs to be processed
                    self.add_log(f"Agent process exited with code: {self.agent_thread.process.returncode}")
                    break
                    
            time.sleep(1)
            
        # If agent didn't start properly
        if not agent_started:
            # Wait to ensure all logs are processed
            time.sleep(2)
            
            # Find the specific module error
            error_message = self.find_last_module_error()
            
            # Show error dialog
            from PyQt5.QtWidgets import QMessageBox
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Agent Start Error")
            msg_box.setText(f"The agent '{agent_name}' failed to start.")
            msg_box.setInformativeText(error_message)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
            
            # Reset UI
            self.stop_agent()
            self.start_agent_btn.setEnabled(True)
            self.stop_agent_btn.setEnabled(False)
            self.agent_status.setText("Agent: Failed to start")
            return

        # Start dashboard after agent is running
        self.start_dashboard()
    
    def stop_agent(self, show_messages=True):
        """Stop the agent with improved cleanup and optional silent mode
        
        Args:
            show_messages: Whether to show log messages during shutdown
        """
        if show_messages:
            self.add_log("Stopping agent...")
        
        if self.agent_thread:
            if show_messages:
                self.add_log("Terminating agent process...")
            
            # First check if the process has already exited
            process_exited = False
            if hasattr(self.agent_thread, 'process') and self.agent_thread.process:
                exit_code = self.agent_thread.process.poll()
                if exit_code is not None:
                    process_exited = True
                    if show_messages:
                        self.add_log(f"Agent process already exited with code: {exit_code}")
            
            # Only try to stop if not already stopped
            if not process_exited:
                try:
                    self.agent_thread.stop()
                except Exception as e:
                    if show_messages:
                        self.add_log(f"Error stopping agent thread: {str(e)}")

            # Wait for the thread to finish properly (with timeout)
            if self.agent_thread.isRunning():
                self.agent_thread.wait(5000)  # Wait up to 5 seconds
                
            # Ensure the agent thread is properly terminated if still running
            if self.agent_thread.isRunning():
                if show_messages:
                    self.add_log("Force terminating agent thread...")
                try:
                    self.agent_thread.terminate()
                    self.agent_thread.wait(2000)  # Wait a bit more
                except Exception as e:
                    if show_messages:
                        self.add_log(f"Error terminating thread: {str(e)}")

            # Always perform thorough cleanup to ensure the port is properly released
            try:
                if show_messages:
                    self.add_log(f"Killing any process using port {self.agent_port}")
                self.kill_process_on_port(self.agent_port)
            except Exception as e:
                if show_messages:
                    self.add_log(f"Error during port cleanup: {str(e)}")
            
            # Reset the thread object
            self.agent_thread = None
            
            # Wait a moment to ensure complete port release
            time.sleep(2)

            # Make sure we verify the port is actually free
            if self.is_port_in_use(self.agent_port):
                if show_messages:
                    self.add_log(f"WARNING: Port {self.agent_port} is still in use after cleanup!")
                    self.add_log("Attempting stronger cleanup...")
                try:
                    self.kill_process_on_port(self.agent_port)
                    time.sleep(1)
                except Exception as e:
                    if show_messages:
                        self.add_log(f"Error during extra cleanup: {str(e)}")
                
                # Check again
                if self.is_port_in_use(self.agent_port):
                    if show_messages:
                        self.add_log(f"CRITICAL: Port {self.agent_port} could not be freed!")
                elif show_messages:
                    self.add_log(f"Port {self.agent_port} successfully freed after extra cleanup")
            elif show_messages:
                self.add_log(f"Port {self.agent_port} successfully freed")

        # Always update UI
        self.start_agent_btn.setEnabled(True)
        self.stop_agent_btn.setEnabled(False)
        self.agent_status.setText("Agent: Not running")
        
    def initialize_dashboard_flag(self):
        """Initialize dashboard stop flag if it doesn't exist"""
        if not hasattr(self, "dashboard_stop_flag"):
            self.dashboard_stop_flag = False

    def start_dashboard(self):
        """Start the dashboard with minimal changes"""
        self.add_log("Starting dashboard...")

        # Initialize stop flag
        self.initialize_dashboard_flag()
        self.dashboard_stop_flag = False

        # Check if port is in use
        if self.is_port_in_use(self.dashboard_port):
            self.add_log(f"Warning: Port {self.dashboard_port} already in use, trying to kill process")
            self.kill_process_on_port(self.dashboard_port)
            time.sleep(1)  # Wait for port to be released

        # First stop any existing dashboard
        if hasattr(self, "dashboard_server") and self.dashboard_server:
            self.stop_dashboard()
            time.sleep(1)

        # Set environment variables
        dashboard_env = os.environ.copy()
        dashboard_env["AGENT_SERVER_URL"] = f"http://localhost:{self.agent_port}"

        # Try to use the static dashboard server directly within the main thread
        try:
            from static_dashboard_server import start_dashboard as static_start_dashboard

            self.add_log("Using static dashboard server")
            api_url = f"http://localhost:{self.agent_port}"

            # Simplify - start in the current thread but save server reference
            server, url = static_start_dashboard(
                port=self.dashboard_port,
                api_url=api_url,
                open_browser=False
            )

            # Store server reference - direct assignment, no threading
            self.dashboard_server = server
            self.add_log(f"Dashboard started at {url}")

        except ImportError as e:
            # Fall back to CLI if static server not available
            self.add_log(f"Static dashboard server not available, falling back to CLI: {e}")

            cmd = [
                sys.executable, 
                "-m", "agentic.cli", 
                "dashboard", "start", 
                "--dev", 
                "--port", str(self.dashboard_port)
            ]
            self.add_log(f"Running command: {' '.join(cmd)}")

            # Create subprocess
            self.dashboard_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=dashboard_env
            )

        # Update UI
        self.start_dashboard_btn.setEnabled(False)
        self.stop_dashboard_btn.setEnabled(True)
        self.dashboard_status.setText(f"Dashboard: Running (Port: {self.dashboard_port})")

        # Show dashboard URL
        dashboard_url = f"http://localhost:{self.dashboard_port}"
        self.add_log(f"Dashboard available at: {dashboard_url}")

        # Small delay to let things settle
        time.sleep(1) 

    
    def stop_dashboard(self):
        """Stop the dashboard with proven working approach"""
        self.add_log("Stopping dashboard...")
        
        try:
            # Set flag to stop dashboard thread if it's running
            if hasattr(self, "dashboard_stop_flag"):
                self.dashboard_stop_flag = True
            
            # Stop any running dashboard process
            if hasattr(self, "dashboard_process") and self.dashboard_process:
                try:
                    self.add_log("Terminating dashboard process...")
                    self.dashboard_process.terminate()
                    try:
                        self.dashboard_process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.add_log("Force killing dashboard process...")
                        self.dashboard_process.kill()
                except Exception as e:
                    self.add_log(f"Error while stopping dashboard process: {str(e)}")
                finally:
                    # Close pipes to avoid resource leaks
                    if hasattr(self.dashboard_process, 'stdout') and self.dashboard_process.stdout:
                        self.dashboard_process.stdout.close()
                    if hasattr(self.dashboard_process, 'stderr') and self.dashboard_process.stderr:
                        self.dashboard_process.stderr.close()
                    self.dashboard_process = None
            
            # Shutdown dashboard server if running
            if hasattr(self, "dashboard_server") and self.dashboard_server:
                try:
                    self.add_log("Shutting down dashboard server...")
                    # Use a thread to avoid blocking
                    def shutdown_server():
                        try:
                            self.dashboard_server.shutdown()
                        except Exception as e:
                            print(f"Error shutting down server: {e}")
                    
                    shutdown_thread = threading.Thread(target=shutdown_server)
                    shutdown_thread.daemon = True
                    shutdown_thread.start()
                    
                    # Only wait a short time for shutdown
                    shutdown_thread.join(3.0)
                    
                    self.dashboard_server = None
                except Exception as e:
                    self.add_log(f"Error shutting down dashboard server: {str(e)}")
            
            # Force kill any processes on the dashboard port
            self.add_log("Killing any process using port 3001...")
            self.kill_process_on_port(self.dashboard_port)
            
            # Wait a moment to ensure resources are released
            time.sleep(0.5)
            
            # Clean up threading resources
            if hasattr(self, "dashboard_thread") and self.dashboard_thread:
                self.dashboard_thread = None
                
            # Update UI
            self.start_dashboard_btn.setEnabled(True)
            self.stop_dashboard_btn.setEnabled(False)
            self.dashboard_status.setText("Dashboard: Not running")
            
        except Exception as e:
            # Catch any errors during shutdown to prevent app crashes
            import traceback
            self.add_log(f"Error during dashboard shutdown: {str(e)}")
            self.add_log(traceback.format_exc())
            
            # Still update UI even if there were errors
            self.start_dashboard_btn.setEnabled(True)
            self.stop_dashboard_btn.setEnabled(False)
            self.dashboard_status.setText("Dashboard: Error during shutdown")

    def dashboard_debug_log(self, message, log_type="info"):
        """Helper to log dashboard-related messages with consistent formatting

        Args:
            message: The message to log
            log_type: Type of log message (info, error, warning)
        """
        prefix = "[Dashboard] "
        if log_type == "error":
            self.add_log(f"{prefix}ERROR: {message}")
        elif log_type == "warning": 
            self.add_log(f"{prefix}WARNING: {message}")
        else:
            self.add_log(f"{prefix}{message}")

        # Print to stderr for console debugging
        import sys
        print(f"{prefix}{message}", file=sys.stderr)

    def setup_dashboard_environment(self, server_port=8086):
        """Prepare environment variables for dashboard startup"""
        dashboard_env = os.environ.copy()
        dashboard_env["AGENT_SERVER_URL"] = f"http://localhost:{server_port}"
        dashboard_env["DASHBOARD_DEBUG"] = "1"  # Enable more verbose logging

        # This is the most important part - different handling by platform
        if sys.platform == "darwin":  # macOS
            # On macOS, use static server mode for more stability
            dashboard_env["USE_STATIC_DASHBOARD"] = "1"
        else:
            dashboard_env["USE_STATIC_DASHBOARD"] = "0"

        return dashboard_env

    def capture_error_log(self, error_info, context=""):
        """Capture detailed error information to help with debugging

        Args:
            error_info: The exception or error string
            context: Optional context about what was happening
        """
        import traceback
        import os
        import sys
        import platform

        log_path = os.path.expanduser("~/agentic_crash.log")

        try:
            with open(log_path, "a") as f:
                f.write(f"\n\n===== ERROR LOG {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")

                if context:
                    f.write(f"Context: {context}\n")

                # Write error info
                if isinstance(error_info, Exception):
                    f.write(f"Error: {type(error_info).__name__}: {str(error_info)}\n")
                    f.write(traceback.format_exc())
                else:
                    f.write(f"Error: {error_info}\n")

                # System info
                f.write(f"\nSystem info:\n")
                f.write(f"Python: {sys.version}\n")
                f.write(f"Platform: {platform.platform()}\n")

                # Dashboard status
                dash_process = getattr(self, "dashboard_process", None)
                dash_server = getattr(self, "dashboard_server", None)
                f.write(f"\nDashboard status:\n")
                f.write(f"dashboard_process: {dash_process}\n")
                f.write(f"dashboard_server: {dash_server}\n")

                # Thread info if possible
                try:
                    import threading
                    f.write(f"\nActive threads: {threading.active_count()}\n")
                    for thread in threading.enumerate():
                        f.write(f"  {thread.name} - Daemon: {thread.daemon}\n")
                except:
                    f.write("Could not get thread info\n")

            self.add_log(f"Error details logged to {log_path}")
        except Exception as log_error:
            self.add_log(f"Failed to write error log: {log_error}")

    def setup_crash_logging(self):
        """
        Set up signal handlers to catch and log crashes
        """
        import signal
        import traceback
        
        def log_crash(sig, frame):
            """Signal handler to log crash information"""
            crash_file = os.path.expanduser("~/agentic_crash.log")
            try:
                with open(crash_file, 'a') as f:
                    f.write(f"\n\n===== CRASH DETECTED AT {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
                    f.write(f"Signal: {sig}\n")
                    f.write("Stack trace:\n")
                    f.write(''.join(traceback.format_stack(frame)))
                    
                    # Log the current state of dashboard-related attributes
                    f.write("\nDashboard state:\n")
                    for attr in ["dashboard_server", "dashboard_process", "dashboard_thread", "dashboard_stop_flag"]:
                        if hasattr(self, attr):
                            f.write(f"{attr}: {getattr(self, attr)}\n")
                        else:
                            f.write(f"{attr}: not found\n")
            except Exception as e:
                print(f"Error in crash handler: {e}")
                
        # Register handlers for common crash signals
        signal.signal(signal.SIGABRT, log_crash)
        signal.signal(signal.SIGSEGV, log_crash)
        signal.signal(signal.SIGILL, log_crash)
        signal.signal(signal.SIGFPE, log_crash)
        
        # Log message only if log_output is already initialized
        if hasattr(self, 'log_output'):
            self.add_log("Crash logging set up to ~/agentic_crash.log")
        
    def open_browser(self):
        dashboard_url = f"http://localhost:{self.dashboard_port}"
        self.add_log(f"Opening browser at {dashboard_url}")
        # Wait a bit longer for the dashboard to be ready
        time.sleep(2)
        webbrowser.open(dashboard_url)
    
    def add_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_output.append(log_entry)
        
        # Auto-scroll to bottom
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_logs(self):
        self.log_output.clear()
        self.add_log("Logs cleared")
        
    def copy_logs(self):
        """Copy all logs to clipboard"""
        text = self.log_output.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.add_log("Logs copied to clipboard")
    
    def closeEvent(self, event):
        """Clean up when window is closed"""
        self.add_log("Shutting down...")
        
        # Stop dashboard
        if self.dashboard_thread:
            self.stop_dashboard()
            
        # Stop agent
        if self.agent_thread:
            self.stop_agent()
            
        event.accept()


    def kill_process_on_port(self, port):
        """Kill any process using the specified port - with enhanced reliability"""
        self.add_log(f"Killing any process using port {port}")
        
        try:
            if sys.platform == "darwin":  # macOS
                # Try different approaches for more reliability
                # 1. First attempt with standard lsof command
                os.system(f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true")
                
                # 2. Second attempt with a more aggressive approach
                os.system(f"lsof -i:{port} | grep LISTEN | awk '{{print $2}}' | xargs kill -9 2>/dev/null || true")
                
            elif sys.platform.startswith("linux"):  # Linux
                os.system(f"fuser -k {port}/tcp 2>/dev/null || true")
                os.system(f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true")
                
            else:  # Windows
                os.system(f"FOR /F \"tokens=5\" %P IN ('netstat -a -n -o ^| findstr :{port}') DO TaskKill /PID %P /F 2>nul")
            
            # Small delay to ensure port is released
            time.sleep(0.5)
            
            # Verify port is actually free now
            if self.is_port_in_use(port):
                self.add_log(f"Warning: Port {port} is still in use after kill attempt")
                # Try one more approach - the nuclear option
                if sys.platform != "nt":  # Unix/macOS/Linux
                    # This harder approach might work for stubborn processes
                    os.system(f"pkill -f \".*:{port}.*\" 2>/dev/null || true")
                time.sleep(1)
            
        except Exception as e:
            # Log any errors but don't stop execution
            self.add_log(f"Error killing process on port {port}: {str(e)}")
            
        self.add_log(f"Completed port {port} kill operation")

    def restart_everything(self):
        """Complete system restart with improved error handling"""
        self.add_log("==== PERFORMING COMPLETE RESTART ====")

        # Stop everything with catch blocks to ensure we continue even if errors occur
        try:
            self.stop_dashboard()
        except Exception as e:
            self.add_log(f"Error stopping dashboard: {str(e)}")
        
        try:
            self.stop_agent()
        except Exception as e:
            self.add_log(f"Error stopping agent: {str(e)}")

        # Kill any remaining processes on our ports
        try:
            self.kill_process_on_port(self.agent_port)
        except Exception as e:
            self.add_log(f"Error killing agent port processes: {str(e)}")
            
        try:
            self.kill_process_on_port(self.dashboard_port)
        except Exception as e:
            self.add_log(f"Error killing dashboard port processes: {str(e)}")

        # Clear any Ray state
        try:
            self.clean_ray_completely()
        except Exception as e:
            self.add_log(f"Error cleaning Ray state: {str(e)}")

        # Reset member variables for threads
        self.agent_thread = None
        if hasattr(self, "dashboard_thread"):
            self.dashboard_thread = None
            
        # Reset all flags
        if hasattr(self, "dashboard_stop_flag"):
            self.dashboard_stop_flag = False

        # Reset to initial port values
        self.dashboard_port = 3001
        
        # Make sure the working directory is reset to runtime
        try:
            app_dir = Path(sys.executable).parent.parent
            runtime_dir = app_dir / "Resources" / "runtime"
            os.makedirs(str(runtime_dir), exist_ok=True)
            os.chdir(str(runtime_dir))
            self.add_log(f"Reset working directory to: {os.getcwd()}")
        except Exception as e:
            self.add_log(f"Error resetting working directory: {str(e)}")

        # Wait longer to ensure complete cleanup
        self.add_log("Waiting for resources to be completely released...")
        time.sleep(3)

        # Start fresh
        self.add_log("Starting fresh agent and dashboard...")

        # Get current selection
        selected_idx = self.agent_combo.currentIndex()
        if selected_idx >= 0:
            try:
                self.start_agent()
            except Exception as e:
                self.add_log(f"Error restarting agent: {str(e)}")
                import traceback
                self.add_log(traceback.format_exc())

    def clean_ray_completely(self):
        """Complete cleanup of Ray processes and state"""
        # 1. Try graceful shutdown first
        try:
            self.add_log("Attempting graceful Ray shutdown...")
            cleanup_cmd = [sys.executable, "-c", "import ray; ray.shutdown()"]
            subprocess.run(cleanup_cmd, timeout=5, capture_output=True)
        except Exception as e:
            self.add_log(f"Graceful Ray shutdown failed: {str(e)}")

        # 2. Target only our own processes that we have permission to kill
        self.add_log("Cleaning up Ray processes...")

        # Find our own processes
        if sys.platform == "darwin" or sys.platform.startswith("linux"):  # macOS or Linux
            try:
                # Find Python processes related to Ray that are owned by current user
                cmd = "ps -u $(id -u) -o pid,command | grep 'ray\\|serve' | grep -v grep"
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()

                if stdout:
                    for line in stdout.decode().splitlines():
                        parts = line.strip().split(None, 1)
                        if len(parts) >= 1:
                            try:
                                pid = int(parts[0])
                                self.add_log(f"Killing Ray-related process: {pid}")
                                os.kill(pid, 9)  # SIGKILL
                            except (ValueError, ProcessLookupError, PermissionError) as e:
                                self.add_log(f"Could not kill process {parts[0]}: {e}")
            except Exception as e:
                self.add_log(f"Error finding Ray processes: {e}")
        else:  # Windows
            try:
                # Find Python processes with "ray" in the command line
                cmd = "wmic process where \"name='python.exe' and commandline like '%ray%'\" get processid"
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()

                if stdout:
                    for line in stdout.decode().splitlines()[1:]:  # Skip header
                        pid = line.strip()
                        if pid and pid.isdigit():
                            self.add_log(f"Killing Ray-related process: {pid}")
                            try:
                                subprocess.run(f"taskkill /F /PID {pid}", shell=True)
                            except Exception as e:
                                self.add_log(f"Could not kill process {pid}: {e}")
            except Exception as e:
                self.add_log(f"Error finding Ray processes: {e}")

        # 3. Kill processes on our ports more safely
        self.kill_process_on_port(self.agent_port)

        # 4. Try to remove Ray temporary files that we own
        try:
            self.add_log("Cleaning Ray temporary files we have access to...")
            ray_temp = os.path.expanduser("~/ray")
            if os.path.exists(ray_temp) and os.access(ray_temp, os.W_OK):
                import shutil
                shutil.rmtree(ray_temp, ignore_errors=True)
        except Exception as e:
            self.add_log(f"Error cleaning Ray temp files: {str(e)}")

        # 5. Give system time to release resources
        self.add_log("Waiting for resources to be released...")
        time.sleep(3)

    def verify_agent_server(self, base_url: str, agent_name: str, max_retries=5, initial_delay=1) -> bool:
        """
        Verify that the agent server is running and accessible, with retries.

        Args:
            base_url: The base URL of the server (e.g., http://localhost:8086)
            agent_name: The name of the agent to check
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds (will be doubled each retry)

        Returns:
            bool: True if the server is accessible, False otherwise
        """
        import requests
        import time
        from urllib.parse import urljoin

        self.add_log(f"Verifying agent server at {base_url}/{agent_name}...")

        delay = initial_delay
        for attempt in range(max_retries):
            try:
                # First try the root endpoint to check if the server is running
                self.add_log(f"Verification attempt {attempt+1}/{max_retries}...")
                response = requests.get(base_url, timeout=2)

                if response.status_code == 200:
                    # Then try the agent-specific endpoint
                    agent_url = urljoin(base_url, f"/{agent_name}")
                    self.add_log(f"Base URL verified, checking agent endpoint: {agent_url}")

                    agent_response = requests.get(agent_url, timeout=2)
                    if agent_response.status_code == 200:
                        self.add_log(f"Agent server verification successful")
                        return True
                    else:
                        self.add_log(f"Agent endpoint returned status code {agent_response.status_code}, retrying...")
                else:
                    self.add_log(f"Base URL returned status code {response.status_code}, retrying...")

            except requests.RequestException as e:
                self.add_log(f"Connection attempt {attempt+1} failed: {str(e)}")

            # Wait before retrying, with exponential backoff
            if attempt < max_retries - 1:  # Don't sleep after the last attempt
                self.add_log(f"Waiting {delay} seconds before next attempt...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff

        self.add_log(f"Agent server verification failed after {max_retries} attempts")
        return False
    
    def is_port_available(self, port: int) -> bool:
        """
        Check if a port is available for use.
        
        Args:
            port: The port number to check
            
        Returns:
            bool: True if the port is available, False if it's in use
        """
        import socket
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', port))
            sock.close()
            return True
        except socket.error:
            sock.close()
            return False
def main():
    # Create QApplication before creating any QWidget
    app = QApplication(sys.argv)
    
    # Print some debug info
    
    # On macOS, it can be helpful to use the Fusion style
    app.setStyle("Fusion")
    
    # Create and show the main window
    window = AgenticApp()
    window.show()
    
    # Start event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
