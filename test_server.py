import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_respond_endpoint():
    print("Testing /respond endpoint (simulating Twilio SpeechResult)...")
    url = "http://localhost:8000/respond"
    data = {"SpeechResult": "Hello assistant, tell me a short joke."}
    
    try:
        response = requests.post(url, data=data)
        print(f"Status Code: {response.status_code}")
        print("Response Content:")
        print(response.text)
        
        if response.status_code == 200 and "<Say>" in response.text:
            print("\nSUCCESS: LLM generated a response and TwiML is correct.")
        else:
            print("\nFAILURE: Response status or content is not what was expected.")
            
    except Exception as e:
        print(f"Error connecting to server: {e}")

if __name__ == "__main__":
    test_respond_endpoint()
