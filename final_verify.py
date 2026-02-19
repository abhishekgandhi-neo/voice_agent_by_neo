import requests
import json
import time
import os
import threading
import uvicorn
from main import app

def test_voice_endpoint():
    print("\n--- Testing /voice Endpoint ---")
    try:
        url = "http://127.0.0.1:8000/voice"
        response = requests.post(url)
        print(f"Status: {response.status_code}")
        print("Content:")
        print(response.text)
        
        if "<Connect>" in response.text and "<Stream" in response.text:
            print("✓ SUCCESS: TwiML contains <Connect><Stream> for real-time audio.")
        else:
            print("✗ FAILURE: TwiML missing <Connect><Stream>.")
            
    except Exception as e:
        print(f"Error: {e}")

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    # Start server in thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    
    # Wait for server
    time.sleep(3)
    
    test_voice_endpoint()
    
    print("\n--- Verification Complete ---")
    os._exit(0)
