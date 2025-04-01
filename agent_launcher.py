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
    """Find examples directory using environment variable or fallback paths"""
    from pathlib import Path
    import os
    import sys

    env_path = os.environ.get("AGENTIC_EXAMPLES_DIR")
    if env_path:
        path = Path(env_path)
        print(f"Using AGENTIC_EXAMPLES_DIR from environment: {path}")
        if path.exists() and path.is_dir():
            py_files = list(path.glob('*.py'))
            if py_files:
                print(f"Found examples directory with {len(py_files)} Python files")
                return path

    # Fallback locations in order of likelihood
    base_dir = Path(sys.executable).parent.parent  # e.g., /Contents/MacOS/../..
    candidate_paths = [
        base_dir / "Resources" / "resources" / "examples",  # main correct location
        base_dir / "Resources" / "examples",                # fallback
        Path.cwd() / "resources" / "examples",
        Path.cwd() / "examples"
    ]

    for path in candidate_paths:
        print(f"Checking for examples in: {path}")
        if path.exists() and any(path.glob("*.py")):
            print(f"Found examples in: {path}")
            return path

    print("Examples directory not found.")
    return None

        
# Import our path helpers
from path_helpers import get_examples_dir, get_resource_path, get_runtime_dir

# Ensure we're using the right attributes for high DPI displays on macOS
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# --- [Rest of the agent_launcher.py file] ---

# Import our path helpers
from path_helpers import get_examples_dir, get_resource_path, get_runtime_dir

# Ensure we're using the right attributes for high DPI displays on macOS
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# --- [Rest of the agent_launcher.py file] ---

# Import our path helpers
from path_helpers import get_examples_dir, get_resource_path, get_runtime_dir

# Ensure we're using the right attributes for high DPI displays on macOS
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# --- [Rest of the agent_launcher.py file] ---
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("agentic.launcher")

# Initialize PyQt high DPI settings
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# Import path helpers
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

# Setup runtime directory
os.makedirs(get_runtime_dir(), exist_ok=True)
os.chdir(get_runtime_dir())
logger.info(f"Working directory set to {os.getcwd()}")

class AgentThread(QThread):
    update_signal = pyqtSignal(str)
    
    def __init__(self, agent_path):
        super().__init__()
        self.agent_path = agent_path
        self.process = None
        self.running = True
        
    def __init__(self, agent_path, env=None):
        super().__init__()
        self.agent_path = agent_path
        self.process = None
        self.running = True
        self.env = env or os.environ.copy()  # Use provided env or default
        
    def run(self):
        try:

            env = os.environ.copy()
            # Add project source directory to PYTHONPATH
            env["PYTHONPATH"] = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "src") + os.pathsep + env.get("PYTHONPATH", "")

            cmd = [sys.executable, "-m", "agentic.cli", "serve", agent_absolute_path]
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env
            )
            #______________
            # cmd = [sys.executable, "-m", "agentic.cli", "serve", str(self.agent_path)]
            # self.update_signal.emit(f"Running command: {' '.join(cmd)}")
            
            # self.process = subprocess.Popen(
            #     cmd,
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.PIPE,
            #     text=True,
            #     bufsize=1
            # )
            
            # Create separate threads for stdout and stderr
            while self.running and self.process and self.process.poll() is None:
                stdout_line = self.process.stdout.readline()
                if stdout_line:
                    self.update_signal.emit(stdout_line.strip())
                
                stderr_line = self.process.stderr.readline()
                if stderr_line:
                    self.update_signal.emit(f"ERROR: {stderr_line.strip()}")
                
                # Short sleep to prevent high CPU usage
                time.sleep(0.01)
                
        except Exception as e:
            self.update_signal.emit(f"Error: {str(e)}")

    def run(self):
        try:
            cmd = [sys.executable, "-m", "agentic.cli", "serve", str(self.agent_path)]
            self.update_signal.emit(f"Running command: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=self.env  # Use the environment
            )
            
            # Create separate threads for stdout and stderr
            while self.running and self.process and self.process.poll() is None:
                stdout_line = self.process.stdout.readline()
                if stdout_line:
                    self.update_signal.emit(stdout_line.strip())
                
                stderr_line = self.process.stderr.readline()
                if stderr_line:
                    self.update_signal.emit(f"ERROR: {stderr_line.strip()}")
                
                # Short sleep to prevent high CPU usage
                time.sleep(0.01)
                
        except Exception as e:
            self.update_signal.emit(f"Error: {str(e)}")
            
    def stop(self):
        self.running = False
        if self.process:
            self.update_signal.emit("Terminating agent process...")
            self.process.terminate()
            time.sleep(1)
            if self.process.poll() is None:
                self.update_signal.emit("Force killing agent process...")
                self.process.kill()

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
            # Import our static dashboard server
            from static_dashboard_server import start_dashboard
            
            self.update_signal.emit(f"Starting static dashboard server on port {self.port}...")
            
            # Get the API URL from environment
            api_url = self.env.get("AGENT_SERVER_URL", f"http://localhost:8086")
            self.update_signal.emit(f"Using API URL: {api_url}")
            
            # Start the dashboard
            self.server, dashboard_url = start_dashboard(
                port=self.port,
                api_url=api_url,
                open_browser=False  # We'll open the browser separately
            )
            
            self.update_signal.emit(f"Dashboard started at {dashboard_url}")
            
            # Keep the thread running
            while self.running and self.server:
                time.sleep(1)

            
            # Use the same command as the CLI version
            #cmd = [sys.executable, "-m", "agentic.cli", "dashboard", "start", "--dev", "--port", str(self.port)]
            #self.update_signal.emit(f"Running command: {' '.join(cmd)}")
            
            # Use the environment with our custom variables
            #self.process = subprocess.Popen(
                #cmd,
                #stdout=subprocess.PIPE,
                #stderr=subprocess.PIPE,
                #text=True,
                #bufsize=1,
                #env=self.env,  # Use our env with AGENT_SERVER_URL
                #cwd=os.getcwd()  # Use current working directory
            #)
            
            # Read output in the thread loop
            #while self.running and self.process and self.process.poll() is None:
                #stdout_line = self.process.stdout.readline()
                #if stdout_line:
                    #self.update_signal.emit(stdout_line.strip())
                
                #stderr_line = self.process.stderr.readline()
                #if stderr_line:
                    #self.update_signal.emit(stderr_line.strip())
                
                # Short sleep to prevent high CPU usage
                #time.sleep(0.01)
                
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
        self.initUI()

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

    def start_agent(self):
        import sys
        import os
        self.add_log(f"Python executable: {sys.executable}")
        self.add_log(f"Python path: {sys.path}")
        
        if not self.agents:
            self.add_log("No agents available")
            return
        
        # First make sure any existing dashboard is stopped
        if self.dashboard_thread:
            self.add_log("Stopping existing dashboard before starting new agent...")
            self.stop_dashboard()
            time.sleep(2)  # Give it time to fully stop
        
        selected_idx = self.agent_combo.currentIndex()
        if selected_idx < 0:
            self.add_log("No agent selected")
            return

        # First make sure any existing agent is stopped
        if self.agent_thread:
            self.stop_agent()

        # Get the selected agent
        agent_path = self.agents[selected_idx][1]
        agent_name = self.agents[selected_idx][0]

        # Set current directory to runtime dir
        runtime_dir = get_runtime_dir()
        os.chdir(runtime_dir)
        self.add_log(f"Working directory set to: {runtime_dir}")

        # Use the absolute path for the agent
        agent_absolute_path = str(agent_path.absolute())
        self.add_log(f"Starting agent: {agent_name} (using path: {agent_absolute_path})")
        
        # Get the agentic module path
        import sys
        import os
        agentic_path = None
        for path in sys.path:
            if 'agentic' in path and os.path.exists(path):
                agentic_path = path
                break
        
        if not agentic_path:
            # Try to find the parent directory of the agentic module
            try:
                import agentic
                agentic_path = os.path.dirname(os.path.dirname(agentic.__file__))
                self.add_log(f"Found agentic parent directory at: {agentic_path}")
            except ImportError:
                self.add_log("Could not import agentic module")
        
        # Set up environment for subprocess
        env = os.environ.copy()
        if agentic_path:
            self.add_log(f"Adding {agentic_path} to PYTHONPATH for subprocess")
            if 'PYTHONPATH' in env:
                env['PYTHONPATH'] = f"{agentic_path}:{env['PYTHONPATH']}"
            else:
                env['PYTHONPATH'] = agentic_path
        
        # Run the command with the modified environment
        cmd = [sys.executable, "-m", "agentic.cli", "serve", agent_absolute_path]
        self.add_log(f"Running command: {' '.join(cmd)} with custom PYTHONPATH")
        
        self.agent_thread = AgentThread(agent_absolute_path, env=env)
        self.agent_thread.update_signal.connect(self.add_log)
        self.agent_thread.start()

        self.start_agent_btn.setEnabled(False)
        self.stop_agent_btn.setEnabled(True)

        # Get the correct base name for the URL
        agent_base = os.path.splitext(os.path.basename(agent_absolute_path))[0].lower()
        self.agent_status.setText(f"Agent: Running - {agent_name}")
        self.add_log(f"Agent API will be available at: http://localhost:{self.agent_port}/{agent_base}")

        # Give the agent server a moment to start up
        time.sleep(2)

        # Start a fresh dashboard
        self.start_dashboard()
        
    def stop_agent(self, thorough_cleanup=False):
        if self.agent_thread:
            self.add_log("Stopping agent...")
            self.agent_thread.stop()

            # Wait for the thread to finish properly (with timeout)
            if self.agent_thread.isRunning():
                self.agent_thread.wait(5000)  # Wait up to 5 seconds

            # More thorough cleanup if requested
            if thorough_cleanup:
                self.clean_ray_completely()

            self.agent_thread = None

        self.start_agent_btn.setEnabled(True)
        self.stop_agent_btn.setEnabled(False)
        self.agent_status.setText("Agent: Not running")

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

    def kill_process_on_port(self, port):
        """Kill any process using the specified port (only processes we have permission to kill)"""
        self.add_log(f"Killing any process using port {port}...")

        if sys.platform == "darwin":  # macOS
            try:
                # First find the PID using the port
                cmd = f"lsof -i :{port} -sTCP:LISTEN -t"
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()

                if stdout:
                    for pid in stdout.decode().strip().split('\n'):
                        if pid:
                            try:
                                # Check if we own this process
                                owner_cmd = f"ps -o user= -p {pid}"
                                owner_process = subprocess.Popen(owner_cmd, shell=True, stdout=subprocess.PIPE)
                                owner = owner_process.communicate()[0].decode().strip()

                                # Get current username
                                current_user = os.environ.get('USER') or subprocess.check_output(['whoami']).decode().strip()

                                if owner == current_user:
                                    self.add_log(f"Killing process {pid} using port {port}")
                                    os.kill(int(pid), 9)  # SIGKILL
                                else:
                                    self.add_log(f"Process {pid} on port {port} is owned by {owner}, not current user")
                            except Exception as e:
                                self.add_log(f"Could not kill process {pid}: {e}")
            except Exception as e:
                self.add_log(f"Error finding/killing process on port {port}: {e}")
        elif sys.platform.startswith("linux"):  # Linux
            try:
                # Similar to macOS but with ss command as alternative
                cmd = f"ss -lptn 'sport = :{port}'"
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()

                if stdout:
                    for line in stdout.decode().strip().split('\n')[1:]:  # Skip header
                        if 'pid=' in line:
                            pid_match = re.search(r'pid=(\d+)', line)
                            if pid_match:
                                pid = pid_match.group(1)
                                try:
                                    # Check if we own this process
                                    current_user = subprocess.check_output(['whoami']).decode().strip()
                                    owner_cmd = f"ps -o user= -p {pid}"
                                    owner = subprocess.check_output(owner_cmd, shell=True).decode().strip()

                                    if owner == current_user:
                                        self.add_log(f"Killing process {pid} using port {port}")
                                        os.kill(int(pid), 9)  # SIGKILL
                                    else:
                                        self.add_log(f"Process {pid} on port {port} is owned by {owner}, not current user")
                                except Exception as e:
                                    self.add_log(f"Could not kill process {pid}: {e}")
            except Exception as e:
                self.add_log(f"Error finding/killing process on port {port}: {e}")
        else:  # Windows
            try:
                cmd = f"netstat -ano | findstr :{port}"
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()

                if stdout:
                    for line in stdout.decode().strip().split('\n'):
                        if 'LISTENING' in line:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                pid = parts[4]
                                self.add_log(f"Attempting to kill process {pid} using port {port}")
                                try:
                                    subprocess.run(f"taskkill /F /PID {pid}", shell=True)
                                except Exception as e:
                                    self.add_log(f"Could not kill process {pid}: {e}")
            except Exception as e:
                self.add_log(f"Error finding/killing process on port {port}: {e}")

        # Check if port is now available
        time.sleep(1)
        if not self.is_port_available(port):
            self.add_log(f"Warning: Port {port} is still in use after cleanup attempt")

    def verify_agent_server(self, base_url: str, agent_name: str) -> bool:
        """
        Verify that the agent server is running and accessible.
        
        Args:
            base_url: The base URL of the server (e.g., http://localhost:8086)
            agent_name: The name of the agent to check
            
        Returns:
            bool: True if the server is accessible, False otherwise
        """
        import requests
        from urllib.parse import urljoin
        
        self.add_log(f"Verifying agent server at {base_url}/{agent_name}...")
        
        try:
            # First try the root endpoint to check if the server is running
            response = requests.get(base_url, timeout=2)
            if response.status_code != 200:
                self.add_log(f"Agent server base URL returned status code {response.status_code}")
                return False
                
            # Then try the agent-specific endpoint
            agent_url = urljoin(base_url, f"/{agent_name}")
            self.add_log(f"Checking agent endpoint: {agent_url}")
            
            response = requests.get(agent_url, timeout=2)
            if response.status_code != 200:
                self.add_log(f"Agent endpoint returned status code {response.status_code}")
                return False
                
            self.add_log(f"Agent server verification successful")
            return True
            
        except requests.RequestException as e:
            self.add_log(f"Error connecting to agent server: {str(e)}")
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
        
    def start_dashboard(self):
        self.add_log("Starting dashboard...")

        # First verify the agent server is running
        if self.agent_thread:
            # Get the agent name from the running agent
            agent_name = os.path.splitext(os.path.basename(self.agent_thread.agent_path))[0].lower()

            # Verify server is running
            if not self.verify_agent_server(f"http://localhost:{self.agent_port}", agent_name):
                self.add_log("WARNING: Agent server verification failed, dashboard might not connect properly")
        else:
            self.add_log("WARNING: No agent server is running, dashboard will not have any agents to display")
        
        # Try to find an available port starting from dashboard_port
        port = self.dashboard_port
        max_attempts = 5
        
        for attempt in range(max_attempts):
            # Build the dashboard command with the current port
            cmd = [sys.executable, "-m", "agentic.cli", "dashboard", "start", "--dev", "--port", str(port)]
            self.add_log(f"Trying port {port}, attempt {attempt+1}/{max_attempts}")
            self.add_log(f"Running command: {' '.join(cmd)}")
            
            # First check if the port is already in use
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(('localhost', port))
                sock.close()
                # Port is available
                break
            except socket.error:
                sock.close()
                self.add_log(f"Port {port} is already in use, trying another...")
                port += 1
                
        # Update the dashboard port to what we found
        self.dashboard_port = port
        dashboard_env = os.environ.copy()
        dashboard_env["AGENT_SERVER_URL"] = f"http://localhost:{self.agent_port}"
    
        # Use the environment in the process
        self.dashboard_thread = DashboardThread(self.dashboard_port, env=dashboard_env)
        self.dashboard_thread.update_signal.connect(self.add_log)
        self.dashboard_thread.start()
        
        self.start_dashboard_btn.setEnabled(False)
        self.stop_dashboard_btn.setEnabled(True)
        self.dashboard_status.setText(f"Dashboard: Running (Port: {self.dashboard_port})")
        
        # Show dashboard URL
        self.add_log(f"Dashboard will be available at: http://localhost:{self.dashboard_port}")

    
    def stop_dashboard(self):
        if self.dashboard_thread:
            self.add_log("Stopping dashboard...")
            self.dashboard_thread.stop()

            # Wait for thread to finish
            if self.dashboard_thread.isRunning():
                self.dashboard_thread.wait(5000)  # Wait up to 5 seconds

            # Force kill any remaining Next.js processes
            if os.name != 'nt':  # Unix/macOS
                os.system("pkill -f 'node' || true")
                os.system("pkill -f 'next' || true")
            else:  # Windows
                os.system("taskkill /f /im node.exe /t 2>nul")

            self.dashboard_thread = None

        self.start_dashboard_btn.setEnabled(True)
        self.stop_dashboard_btn.setEnabled(False)
        self.dashboard_status.setText("Dashboard: Not running")

        # Check for and kill any lingering processes on the dashboard ports
        self.kill_process_on_port(self.dashboard_port)

    def kill_process_on_port(self, port):
        """Kill any process using the specified port"""
        if os.name != 'nt':  # Unix/macOS
            self.add_log(f"Killing any process using port {port}...")
            os.system(f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true")
        else:  # Windows
            os.system(f"FOR /F \"tokens=5\" %P IN ('netstat -a -n -o ^| findstr :{port}') DO TaskKill /PID %P /F 2>nul")

    def restart_everything(self):
        """Complete system restart"""
        self.add_log("==== PERFORMING COMPLETE RESTART ====")

        # Stop everything
        self.stop_dashboard()
        self.stop_agent()

        # Additional cleanup
        self.clean_ray_completely()

        # Kill any processes on our ports
        self.kill_process_on_port(self.agent_port)
        self.kill_process_on_port(self.dashboard_port)

        # Clear all ports in use
        self.dashboard_port = 3001  # Reset to initial value

        # Wait longer
        time.sleep(10)

        # Start fresh
        self.add_log("Starting fresh agent and dashboard...")

        # Get current selection
        selected_idx = self.agent_combo.currentIndex()
        if selected_idx >= 0:
            self.start_agent()
    
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
