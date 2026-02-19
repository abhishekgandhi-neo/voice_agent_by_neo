import uvicorn
import threading
import time
import requests
import os
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000)

def run_tests():
    time.sleep(5)  # Wait for server to start
    print("Testing /respond endpoint...")
    url = "http://127.0.0.1:8000/respond"
    data = {"SpeechResult": "Who won the world cup in 2022?"}
    
    try:
        response = requests.post(url, data=data)
        print(f"Status Code: {response.status_code}")
        print("Response Content Preview:")
        print(response.text[:500])
        
        if response.status_code == 200 and "<Say>" in response.text:
            print("\nVERIFICATION SUCCESS: Server responded with TwiML.")
        else:
            print("\nVERIFICATION FAILURE: Unexpected response.")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
    finally:
        print("Verification complete. Exiting...")
        os._exit(0)

if __name__ == "__main__":
    # Start server in a thread
    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()
    
    # Run tests
    run_tests()
