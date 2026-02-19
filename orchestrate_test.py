import subprocess
import time
import os
import signal
import sys

def run_test():
    print("Starting AI Voice Agent Server...")
    # Use the venv python
    python_path = os.path.join(os.getcwd(), "venv", "Scripts", "python.exe")
    
    # Start the server in the background and redirect output to a log file
    log_file = open("server_test.log", "w")
    server_process = subprocess.Popen(
        [python_path, "main.py"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )
    
    try:
        print("Waiting 10 seconds for server to initialize and ngrok to be ready (if applicable)...")
        time.sleep(10)
        
        print("Triggering outbound call to +918866887491...")
        # Trigger the call
        trigger_result = subprocess.run(
            [python_path, "trigger_call.py"],
            capture_output=True,
            text=True
        )
        print("Trigger Output:", trigger_result.stdout)
        if trigger_result.stderr:
            print("Trigger Errors:", trigger_result.stderr)
            
        print("Call triggered. Monitoring server logs for 60 seconds of interaction...")
        time.sleep(60)
        
    except KeyboardInterrupt:
        print("Test interrupted.")
    finally:
        print("Shutting down server...")
        # Terminate the server process group correctly on Windows
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(server_process.pid)])
        else:
            server_process.terminate()
        
        log_file.close()
        
        print("\n=== SERVER LOGS ===\n")
        if os.path.exists("server_test.log"):
            with open("server_test.log", "r") as f:
                print(f.read())
        else:
            print("Log file not found.")

if __name__ == "__main__":
    run_test()
