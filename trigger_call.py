import logging
import os

from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
NGROK_URL = os.getenv("NGROK_URL")

# Webhook URL for the Voice Agent
# Ensure this matches the endpoint in main.py
WEBHOOK_URL = f"{NGROK_URL}/voice" if NGROK_URL else None


def trigger_outbound_call(to_number: str):
    """
    Initiates an outbound call to the specified number and connects it to the AI Voice Agent.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.error("Twilio credentials missing.")
        return

    if not WEBHOOK_URL:
        logger.error("NGROK_URL missing in environment. Cannot set webhook.")
        return

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        logger.info(f"Initiating outbound call to {to_number[:4]}...")
        logger.info(f"Connecting to webhook: {WEBHOOK_URL}")

        call = client.calls.create(
            to=to_number, from_=TWILIO_PHONE_NUMBER, url=WEBHOOK_URL, method="POST"
        )

        logger.info(f"Call initiated successfully. SID: {call.sid}")
        return call.sid
    except Exception as e:
        logger.error(f"Failed to initiate call: {e}")
        return None


if __name__ == "__main__":
    # Target number from requirements
    TARGET_NUMBER = os.getenv("TARGET_NUMBER")

    # Check if we should override with an environment variable for testing
    to_number = os.getenv("TEST_PHONE_NUMBER", TARGET_NUMBER)

    trigger_outbound_call(to_number)
