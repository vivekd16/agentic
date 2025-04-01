#!/usr/bin/env python3
import subprocess
import webbrowser
import sys
import time
import threading
import os
from pathlib import Path
import re

class AgenticCLI:
    def __init__(self):
        self.current_agent = None
        self.server_process = None
        self.dashboard_process = None
        self.agent_port = 8086  # Agent/server port
        self.dashboard_port = 3001  # Dashboard port
        self.agent_path = None
        self.running = True
        self.log_lines = []
        self.max_log_lines = 100
        
        # Scan for examples
        self.scan_examples()
        
        # Main menu loop
        self.main_loop()
    
    def scan_examples(self):
        """Scan for example agents"""
        self.agents = []
        examples_dir = Path("examples")
        
        if examples_dir.exists():
            for agent_file in examples_dir.glob("*.py"):
                if agent_file.is_file():  # Skip directories
                    self.agents.append((agent_file.name, agent_file))
        
        # Sort by name
        self.agents.sort(key=lambda x: x[0])
    
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_menu(self):
        """Display the main menu"""
        self.clear_screen()
        print("\n" + "=" * 40)
        print("AGENTIC LAUNCHER")
        print("=" * 40)
        
        print("\nAvailable Agents:")
        for i, (name, _) in enumerate(self.agents, 1):
            is_current = self.current_agent and name == self.current_agent.name
            print(f"{i}. {name} {'(SELECTED)' if is_current else ''}")
        
        print("\nOptions:")
        print("a. Select agent")
        print("b. Browse for custom agent")
        print("c. Start server")
        print("d. Stop server")
        print("e. Start dashboard")
        print("f. Stop dashboard")
        print("g. Open dashboard in browser")
        print("l. View logs")
        print("q. Quit")
        
        if self.current_agent:
            print(f"\nCurrent agent: {self.current_agent.name}")
        else:
            print("\nNo agent selected")
        
        # Display server status
        if self.server_process and self.server_process.poll() is None:
            agent_base = self.current_agent.stem.lower() if self.current_agent else "unknown"
            print(f"Server status: RUNNING (http://localhost:{self.agent_port}/{agent_base})")
        else:
            print("Server status: STOPPED")
            
        # Display dashboard status
        if self.dashboard_process and self.dashboard_process.poll() is None:
            print(f"Dashboard status: RUNNING (http://localhost:{self.dashboard_port})")
        else:
            print("Dashboard status: STOPPED")
        
        # Display last few log lines
        if self.log_lines:
            print("\nRecent logs:")
            for line in self.log_lines[-5:]:  # Show last 5 lines
                print(line)
        
        print("\nEnter your choice: ", end="", flush=True)
    
    def main_loop(self):
        """Main menu loop"""
        while self.running:
            self.display_menu()
            choice = input().strip().lower()
            
            if choice == 'q':
                self.quit()
            elif choice == 'a':
                self.select_agent()
            elif choice == 'b':
                self.browse_agent()
            elif choice == 'c':
                self.start_server()
            elif choice == 'd':
                self.stop_server()
            elif choice == 'e':
                self.start_dashboard()
            elif choice == 'f':
                self.stop_dashboard()
            elif choice == 'g':
                self.open_dashboard()
            elif choice == 'l':
                self.view_logs()
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(self.agents):
                    self.current_agent = self.agents[idx][1]
                    self.add_log(f"Selected agent: {self.current_agent.name}")
                else:
                    self.add_log("Invalid agent number")
            else:
                self.add_log("Invalid choice, please try again")
            
            time.sleep(0.5)
    
    def select_agent(self):
        """Select an agent from the list"""
        self.clear_screen()
        print("\nAvailable Agents:")
        for i, (name, _) in enumerate(self.agents, 1):
            print(f"{i}. {name}")
        
        print("\nEnter agent number (or 'c' to cancel): ", end="", flush=True)
        choice = input().strip()
        
        if choice.lower() == 'c':
            return
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(self.agents):
                self.current_agent = self.agents[idx][1]
                self.add_log(f"Selected agent: {self.current_agent.name}")
            else:
                self.add_log("Invalid agent number")
    
    def browse_agent(self):
        """Browse for a custom agent file"""
        self.clear_screen()
        print("\nEnter path to Python agent file (or 'c' to cancel): ", end="", flush=True)
        path = input().strip()
        
        if path.lower() == 'c':
            return
        
        agent_path = Path(path)
        if agent_path.exists() and agent_path.suffix == '.py':
            self.current_agent = agent_path
            self.add_log(f"Selected custom agent: {agent_path}")
            
            # Add to agents list if not already there
            agent_name = agent_path.name
            if not any(name == agent_name for name, _ in self.agents):
                self.agents.append((agent_name, agent_path))
                self.agents.sort(key=lambda x: x[0])
        else:
            self.add_log(f"Invalid file path or not a Python file: {path}")
    
    def start_server(self):
        """Start the agentic server with selected agent"""
        if not self.current_agent:
            self.add_log("No agent selected. Please select an agent first.")
            return
        
        if self.server_process and self.server_process.poll() is None:
            self.add_log("Server is already running")
            return
        
        try:
            # Start server using the agentic cli
            cmd = [sys.executable, "-m", "agentic.cli", "serve", str(self.current_agent)]
            self.add_log(f"Running command: {' '.join(cmd)}")
            
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Start threads to read output
            threading.Thread(target=self.read_output, args=(self.server_process.stdout, False, "SERVER"), daemon=True).start()
            threading.Thread(target=self.read_output, args=(self.server_process.stderr, True, "SERVER"), daemon=True).start()
            
            # Wait a bit for server to start
            time.sleep(2)
            
            self.add_log("Server started successfully")
            
            # Automatically start dashboard if not already running
            if not self.dashboard_process or self.dashboard_process.poll() is not None:
                self.start_dashboard()
            
        except Exception as e:
            self.add_log(f"Error starting server: {e}", error=True)
    
    def stop_server(self):
        """Stop the agentic server"""
        if not self.server_process or self.server_process.poll() is not None:
            self.add_log("Server is not running")
            return
        
        try:
            self.add_log("Stopping server...")
            self.server_process.terminate()
            
            # Give it a moment to terminate
            time.sleep(1)
            
            if self.server_process.poll() is None:
                self.add_log("Server did not terminate gracefully, forcing...")
                self.server_process.kill()
            
            self.add_log("Server stopped")
            
        except Exception as e:
            self.add_log(f"Error stopping server: {e}", error=True)
    
    def start_dashboard(self):
        """Start the dashboard"""
        if self.dashboard_process and self.dashboard_process.poll() is None:
            self.add_log("Dashboard is already running")
            return
        
        try:
            # Start dashboard
            cmd = [sys.executable, "-m", "agentic.cli", "dashboard", "start", "--dev", "--port", str(self.dashboard_port)]
            self.add_log(f"Running command: {' '.join(cmd)}")
            
            self.dashboard_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Start threads to read output
            threading.Thread(target=self.read_output, args=(self.dashboard_process.stdout, False, "DASHBOARD"), daemon=True).start()
            threading.Thread(target=self.read_output, args=(self.dashboard_process.stderr, True, "DASHBOARD"), daemon=True).start()
            
            # Wait a bit for dashboard to start
            time.sleep(2)
            
            self.add_log("Dashboard started successfully")
            
            # Automatically open dashboard in browser
            self.open_dashboard()
            
        except Exception as e:
            self.add_log(f"Error starting dashboard: {e}", error=True)
    
    def stop_dashboard(self):
        """Stop the dashboard"""
        if not self.dashboard_process or self.dashboard_process.poll() is not None:
            self.add_log("Dashboard is not running")
            return
        
        try:
            self.add_log("Stopping dashboard...")
            self.dashboard_process.terminate()
            
            # Give it a moment to terminate
            time.sleep(1)
            
            if self.dashboard_process.poll() is None:
                self.add_log("Dashboard did not terminate gracefully, forcing...")
                self.dashboard_process.kill()
            
            self.add_log("Dashboard stopped")
            
        except Exception as e:
            self.add_log(f"Error stopping dashboard: {e}", error=True)
    
    def read_output(self, pipe, is_error, source):
        """Read output from a process pipe"""
        for line in iter(pipe.readline, ''):
            if line:
                if is_error and 'ERROR' in line and not (
                    # Filter out common INFO lines incorrectly labeled as ERROR
                    'INFO' in line or 'WARNING' in line
                ):
                    self.add_log(f"{source} ERROR: {line.strip()}", error=True)
                else:
                    self.add_log(f"{source}: {line.strip()}")
        pipe.close()
    
    def open_dashboard(self):
        """Open dashboard in default browser"""
        if not self.dashboard_process or self.dashboard_process.poll() is not None:
            self.add_log("Dashboard is not running. Start the dashboard first.")
            return
        
        try:
            dashboard_url = f"http://localhost:{self.dashboard_port}"
            self.add_log(f"Opening dashboard at {dashboard_url}")
            webbrowser.open(dashboard_url)
        except Exception as e:
            self.add_log(f"Error opening dashboard: {e}", error=True)
    
    def view_logs(self):
        """View full logs"""
        self.clear_screen()
        print("\n" + "=" * 40)
        print("LOGS")
        print("=" * 40 + "\n")
        
        if not self.log_lines:
            print("No logs to display")
        else:
            for line in self.log_lines:
                print(line)
        
        print("\nPress Enter to return to main menu...", end="", flush=True)
        input()
    
    def add_log(self, message, error=False):
        """Add message to log"""
        if error:
            log_entry = f"\033[91m{message}\033[0m"  # Red text for errors
        else:
            log_entry = message
        
        self.log_lines.append(log_entry)
        
        # Keep log size limited
        if len(self.log_lines) > self.max_log_lines:
            self.log_lines = self.log_lines[-self.max_log_lines:]
    
    def quit(self):
        """Quit the application"""
        print("Exiting Agentic Launcher...")
        
        # Stop dashboard
        if self.dashboard_process and self.dashboard_process.poll() is None:
            print("Stopping dashboard...")
            self.dashboard_process.terminate()
            time.sleep(1)
        
        # Stop server
        if self.server_process and self.server_process.poll() is None:
            print("Stopping server...")
            self.server_process.terminate()
            time.sleep(1)
        
        self.running = False
        sys.exit(0)

if __name__ == "__main__":
    try:
        AgenticCLI()
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt. Exiting...")
        sys.exit(0)
