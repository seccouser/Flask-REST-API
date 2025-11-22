"""
Process Manager Module
Manages starting and monitoring external processes
"""

import subprocess
import logging
import psutil
import os

logger = logging.getLogger(__name__)


class ProcessManager:
    """
    Manager for starting and monitoring external processes.
    Prevents duplicate process starts.
    """
    
    def __init__(self):
        """Initialize the process manager."""
        self.managed_processes = {}  # Maps process names to PIDs
        logger.info("Process manager initialized")
    
    def is_process_running(self, process_name):
        """
        Check if a process with the given name is running.
        
        Args:
            process_name: Name or path of the process
            
        Returns:
            tuple: (is_running, pid or None)
        """
        # Check if we have it in our managed processes
        if process_name in self.managed_processes:
            pid = self.managed_processes[process_name]
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                        return True, pid
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # Remove stale entry
            del self.managed_processes[process_name]
        
        # Check system-wide for the process
        process_basename = os.path.basename(process_name)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check process name
                if proc.info['name'] == process_basename:
                    return True, proc.info['pid']
                
                # Check command line
                cmdline = proc.info.get('cmdline')
                if cmdline and any(process_name in arg for arg in cmdline):
                    return True, proc.info['pid']
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        return False, None
    
    def start_process(self, command, check_running=True, cwd=None, env=None):
        """
        Start a process.
        
        Args:
            command: Command to execute (string or list)
            check_running: If True, check if process is already running
            cwd: Working directory for the process
            env: Environment variables dictionary
            
        Returns:
            dict: Status information including pid and whether it was started
        """
        # Parse command if it's a string
        if isinstance(command, str):
            cmd_list = command.split()
        else:
            cmd_list = command
        
        if not cmd_list:
            raise ValueError("Command cannot be empty")
        
        process_name = cmd_list[0]
        
        # Check if already running
        if check_running:
            is_running, pid = self.is_process_running(process_name)
            if is_running:
                logger.info(f"Process {process_name} already running with PID {pid}")
                return {
                    'status': 'already_running',
                    'pid': pid,
                    'process': process_name,
                    'message': f'Process is already running with PID {pid}'
                }
        
        # Start the process
        try:
            # Merge environment variables - preserve DISPLAY for GUI apps
            proc_env = os.environ.copy()
            
            # Ensure DISPLAY is set for GUI applications
            if 'DISPLAY' not in proc_env:
                proc_env['DISPLAY'] = ':0'
            
            if env:
                proc_env.update(env)
            
            # Use devnull for stdout/stderr to avoid zombie processes
            # GUI applications need to run independently
            process = subprocess.Popen(
                cmd_list,
                cwd=cwd,
                env=proc_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent
                preexec_fn=os.setpgrp if hasattr(os, 'setpgrp') else None  # Create new process group
            )
            
            pid = process.pid
            self.managed_processes[process_name] = pid
            
            logger.info(f"Started process {process_name} with PID {pid}")
            
            return {
                'status': 'started',
                'pid': pid,
                'process': process_name,
                'command': ' '.join(cmd_list),
                'message': f'Process started successfully with PID {pid}'
            }
            
        except FileNotFoundError:
            logger.error(f"Command not found: {process_name}")
            raise FileNotFoundError(f"Command not found: {process_name}")
        except Exception as ex:
            logger.error(f"Failed to start process {process_name}: {ex}")
            raise
    
    def stop_process(self, process_name):
        """
        Stop a managed process.
        
        Args:
            process_name: Name of the process to stop
            
        Returns:
            dict: Status information
        """
        is_running, pid = self.is_process_running(process_name)
        
        if not is_running:
            return {
                'status': 'not_running',
                'process': process_name,
                'message': 'Process is not running'
            }
        
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            
            # Wait for process to terminate (max 5 seconds)
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Force kill if not terminated
                proc.kill()
                proc.wait(timeout=2)
            
            # Remove from managed processes
            if process_name in self.managed_processes:
                del self.managed_processes[process_name]
            
            logger.info(f"Stopped process {process_name} (PID {pid})")
            
            return {
                'status': 'stopped',
                'pid': pid,
                'process': process_name,
                'message': f'Process stopped successfully (PID {pid})'
            }
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as ex:
            logger.error(f"Failed to stop process {process_name}: {ex}")
            raise
    
    def get_process_status(self, process_name):
        """
        Get status of a process.
        
        Args:
            process_name: Name of the process
            
        Returns:
            dict: Process status information
        """
        is_running, pid = self.is_process_running(process_name)
        
        if not is_running:
            return {
                'running': False,
                'process': process_name,
                'pid': None
            }
        
        try:
            proc = psutil.Process(pid)
            return {
                'running': True,
                'process': process_name,
                'pid': pid,
                'status': proc.status(),
                'cpu_percent': proc.cpu_percent(interval=0.1),
                'memory_mb': proc.memory_info().rss / 1024 / 1024,
                'create_time': proc.create_time()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as ex:
            logger.error(f"Failed to get process status for {process_name}: {ex}")
            return {
                'running': False,
                'process': process_name,
                'pid': None,
                'error': str(ex)
            }
    
    def list_managed_processes(self):
        """
        List all managed processes and their status.
        
        Returns:
            list: List of process information dictionaries
        """
        processes = []
        
        # Clean up stale entries
        stale_processes = []
        for process_name, pid in self.managed_processes.items():
            if not psutil.pid_exists(pid):
                stale_processes.append(process_name)
        
        for process_name in stale_processes:
            del self.managed_processes[process_name]
        
        # Get status for all managed processes
        for process_name in self.managed_processes.keys():
            status = self.get_process_status(process_name)
            processes.append(status)
        
        return processes
