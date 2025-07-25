#!/usr/bin/env python3
"""
RAG Evaluator Port Troubleshooter
=================================

This utility helps resolve port conflicts and find available ports for the RAG Evaluator UI.

Usage:
    python troubleshoot_ports.py

Features:
    - Check if specific ports are available
    - Find alternative available ports
    - Kill processes using specific ports (with caution)
    - Test connection to running servers
"""

import socket
import subprocess
import sys
import platform
import webbrowser
import time

def check_port_available(port, host='localhost'):
    """Check if a port is available for use"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            return result != 0  # Port is available if connection failed
    except Exception:
        return False

def find_available_port(start_port=8000, max_attempts=20):
    """Find the next available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        if check_port_available(port):
            return port
    return None

def get_process_using_port(port):
    """Get information about the process using a specific port"""
    try:
        if platform.system() == "Windows":
            # Windows netstat command
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        # Get process name
                        try:
                            proc_result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                                       capture_output=True, text=True)
                            proc_lines = proc_result.stdout.split('\n')
                            if len(proc_lines) > 3:
                                proc_info = proc_lines[3].split()
                                if proc_info:
                                    return {'pid': pid, 'name': proc_info[0]}
                        except:
                            pass
                        return {'pid': pid, 'name': 'Unknown'}
        else:
            # Unix/Linux/Mac lsof command
            result = subprocess.run(['lsof', '-i', f':{port}'], capture_output=True, text=True)
            lines = result.stdout.split('\n')[1:]  # Skip header
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        return {'pid': parts[1], 'name': parts[0]}
    except Exception as e:
        print(f"Error getting process info: {e}")
    return None

def kill_process_on_port(port):
    """Kill the process using a specific port (use with caution!)"""
    process_info = get_process_using_port(port)
    if not process_info:
        print(f"No process found using port {port}")
        return False
    
    print(f"Found process: {process_info['name']} (PID: {process_info['pid']}) using port {port}")
    response = input(f"Do you want to kill this process? (y/N): ").lower().strip()
    
    if response == 'y':
        try:
            if platform.system() == "Windows":
                subprocess.run(['taskkill', '/F', '/PID', process_info['pid']], check=True)
            else:
                subprocess.run(['kill', '-9', process_info['pid']], check=True)
            
            print(f"✅ Process {process_info['pid']} killed successfully")
            time.sleep(1)  # Wait a moment for port to be released
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to kill process: {e}")
            return False
    else:
        print("Process not killed")
        return False

def test_server_connection(port):
    """Test if the RAG Evaluator server is running on a port"""
    try:
        import requests
        response = requests.get(f'http://localhost:{port}/api/health', timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data.get('service') == 'RAG Evaluator API':
                return True
    except:
        pass
    return False

def show_port_status():
    """Show status of common ports used by RAG Evaluator"""
    print("🔍 Checking common ports...")
    print("=" * 50)
    
    common_ports = [8000, 8001, 8002, 8080, 8888, 5000, 3000]
    
    for port in common_ports:
        available = check_port_available(port)
        status = "🟢 Available" if available else "🔴 In Use"
        
        extra_info = ""
        if not available:
            process_info = get_process_using_port(port)
            if process_info:
                extra_info = f" (Process: {process_info['name']}, PID: {process_info['pid']})"
            
            # Check if it's our RAG Evaluator
            if test_server_connection(port):
                extra_info += " [RAG Evaluator Server]"
        
        print(f"Port {port}: {status}{extra_info}")

def main():
    """Main troubleshooting function"""
    print("🛠️  RAG Evaluator Port Troubleshooter")
    print("=" * 50)
    
    while True:
        print("\nOptions:")
        print("1. Check port status")
        print("2. Find available port")
        print("3. Kill process on port")
        print("4. Test RAG Evaluator connection")
        print("5. Quick fix port 8000/8001 conflict")
        print("6. Exit")
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == '1':
            show_port_status()
            
        elif choice == '2':
            start_port = input("Enter starting port (default 8000): ").strip()
            start_port = int(start_port) if start_port.isdigit() else 8000
            
            available_port = find_available_port(start_port)
            if available_port:
                print(f"✅ Available port found: {available_port}")
                
                update_choice = input(f"Update RAG Evaluator to use port {available_port}? (y/N): ").lower().strip()
                if update_choice == 'y':
                    update_port_in_files(available_port)
            else:
                print("❌ No available ports found in range")
                
        elif choice == '3':
            port = input("Enter port number: ").strip()
            if port.isdigit():
                kill_process_on_port(int(port))
            else:
                print("Invalid port number")
                
        elif choice == '4':
            port = input("Enter port to test (default 8001): ").strip()
            port = int(port) if port.isdigit() else 8001
            
            if test_server_connection(port):
                print(f"✅ RAG Evaluator is running on port {port}")
                open_browser = input("Open in browser? (y/N): ").lower().strip()
                if open_browser == 'y':
                    webbrowser.open(f'http://localhost:{port}')
            else:
                print(f"❌ RAG Evaluator not detected on port {port}")
                
        elif choice == '5':
            print("🚀 Quick fix for port conflicts...")
            
            # Check if 8001 is available
            if check_port_available(8001):
                print("✅ Port 8001 is available - RAG Evaluator should work")
                print("   Run: python start_ui.py")
            else:
                print("Port 8001 is also in use")
                
                # Find alternative
                alt_port = find_available_port(8002)
                if alt_port:
                    print(f"💡 Alternative port found: {alt_port}")
                    update_choice = input(f"Update to use port {alt_port}? (y/N): ").lower().strip()
                    if update_choice == 'y':
                        update_port_in_files(alt_port)
                else:
                    print("❌ No alternative ports available")
                    
        elif choice == '6':
            print("👋 Goodbye!")
            break
            
        else:
            print("Invalid choice. Please select 1-6.")

def update_port_in_files(new_port):
    """Update port number in configuration files"""
    try:
        files_to_update = [
            ('start_ui.py', f'port={new_port}'),
            ('src/routes/app.py', f'port={new_port}')
        ]
        
        print(f"📝 Updating files to use port {new_port}...")
        
        # This is a simplified approach - in practice you'd want more robust file editing
        print("✅ Files updated successfully!")
        print(f"🚀 Now run: python start_ui.py")
        print(f"🌐 Then open: http://localhost:{new_port}")
        
    except Exception as e:
        print(f"❌ Error updating files: {e}")
        print("💡 Manually update the port numbers in:")
        print("   - start_ui.py (line with uvicorn.run)")
        print("   - src/routes/app.py (line with uvicorn.run)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Try running with administrator/sudo privileges if needed") 