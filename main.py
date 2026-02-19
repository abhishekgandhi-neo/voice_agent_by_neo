import asyncio
import base64
import json
import logging
import os
from typing import Optional

import httpx
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveOptions,
    LiveTranscriptionEvents,
)
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from twilio.twiml.voice_response import Connect, VoiceResponse

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

# -----------------------------------------------------------------------------
# Configuration & Clients
# -----------------------------------------------------------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Initialize LLM via OpenRouter
llm = ChatOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
    default_headers={
        "HTTP-Referer": "https://github.com/langchain-ai/langchain",
        "X-Title": "Cloud-Integrated Voice Agent",
    },
)

SYSTEM_PROMPT = """You are a helpful and concise voice assistant. 
Since you are speaking over the phone, keep your responses brief, clear, and natural for speech. 
Avoid long lists or complex explanations. You are having a real-time conversation."""

# -----------------------------------------------------------------------------
# Webhook Endpoints (HTTP)
# -----------------------------------------------------------------------------


@app.post("/voice")
async def voice_webhook(request: Request):
    """Initial TwiML to connect to WebSocket stream."""
    response = VoiceResponse()

    # Use <Connect><Stream> for real-time audio
    connect = Connect()
    host = request.url.netloc

    # Twilio requires WSS for public connections (ngrok uses https/wss)
    # We'll detect if we are on a secure connection
    is_secure = request.headers.get("x-forwarded-proto") == "https" or "ngrok" in host
    scheme = "wss" if is_secure else "ws"
    stream_url = f"{scheme}://{host}/media-stream"

    logger.info(f"Connecting Twilio to Stream URL: {stream_url}")
    connect.stream(url=stream_url)
    response.append(connect)

    return Response(content=str(response), media_type="application/xml")


# -----------------------------------------------------------------------------
# WebSocket Handler (STT -> LLM -> TTS)
# -----------------------------------------------------------------------------


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle Twilio Media Stream WebSocket."""
    await websocket.accept()
    logger.info("Twilio WebSocket connected.")

    stream_sid = None
    dg_connection = None

    # Initialize Deepgram
    try:
        dg_client = DeepgramClient(DEEPGRAM_API_KEY)
        dg_connection = dg_client.listen.asynclive.v("1")
    except Exception as e:
        logger.error(f"Deepgram Init Error: {e}")
        await websocket.close()
        return

    async def on_message(self, result, **kwargs):
        """Callback for Deepgram results."""
        nonlocal stream_sid
        if result.channel.alternatives:
            sentence = result.channel.alternatives[0].transcript
            if sentence and result.is_final:
                logger.info(f"User (Deepgram): {sentence}")
                # Use create_task to avoid blocking the STT loop
                asyncio.create_task(get_llm_response(sentence, websocket, stream_sid))

    async def get_llm_response(text, ws, sid):
        """Process text with LLM and output via TTS."""
        try:
            logger.info(f"Requesting LLM response for: {text}")
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=text),
            ]
            ai_msg = await llm.ainvoke(messages)
            response_text = ai_msg.content
            logger.info(f"AI Response: {response_text}")

            await handle_tts(response_text, ws, sid)
        except Exception as e:
            logger.error(f"LLM/Pipeline Error: {e}")

    async def handle_tts(text, ws, sid):
        """Generate audio using ElevenLabs (mulaw 8000Hz) and send to Twilio."""
        logger.info(f"Initiating ElevenLabs TTS for: {text[:50]}...")

        # ElevenLabs URL for mulaw 8k (Twilio standard)
        # Using Voice ID: '21m00Tcm4TlvDq8ikWAM' (Rachel) or environment variable
        voice_id = "21m00Tcm4TlvDq8ikWAM"
        # Twilio Media Streams expect audio/x-mulaw;rate=8000
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

        headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}

        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }

        params = {"output_format": "ulaw_8000"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, json=data, headers=headers, params=params, timeout=30.0
                )
                if response.status_code == 200:
                    audio_raw = response.content
                    logger.info(
                        f"Received {len(audio_raw)} bytes of mulaw audio from ElevenLabs"
                    )

                    # Twilio expects base64 encoded payload in a 'media' event
                    payload = base64.b64encode(audio_raw).decode("utf-8")

                    message = {
                        "event": "media",
                        "streamSid": sid,
                        "media": {"payload": payload},
                    }
                    await ws.send_text(json.dumps(message))
                    logger.info(f"Sent media event to Twilio for StreamSid: {sid}")
                else:
                    logger.error(
                        f"ElevenLabs API Error: {response.status_code} - {response.text}"
                    )
        except Exception as e:
            logger.error(f"TTS Handling Error: {e}")

    # Register Deepgram event handlers
    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    dg_connection.on(
        LiveTranscriptionEvents.Error,
        lambda self, error, **kwargs: logger.error(f"Deepgram Error: {error}"),
    )

    options = LiveOptions(
        model="nova-2",
        language="en-US",
        smart_format=True,
        encoding="mulaw",
        sample_rate=8000,
    )

    # Start Deepgram connection
    if not await dg_connection.start(options):
        logger.error("Failed to start Deepgram connection")
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg["event"] == "start":
                stream_sid = msg["start"]["streamSid"]
                logger.info(f"Twilio Stream started: {stream_sid}")
                # Initial greeting (optional, but good for UX)
                # asyncio.create_task(handle_tts("Hello! I am your AI assistant. How can I help you today?", websocket, stream_sid))

            elif msg["event"] == "media":
                payload = msg["media"]["payload"]
                chunk = base64.b64decode(payload)
                await dg_connection.send(chunk)

            elif msg["event"] == "mark":
                # Marks are used to synchronize state, just log for now
                logger.info(f"Twilio Mark received: {msg.get('mark', {}).get('name')}")

            elif msg["event"] == "stop":
                logger.info("Twilio Stream stopped.")
                break

    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected.")
    except Exception as e:
        logger.error(f"WS Handling Error: {e}")
    finally:
        logger.info("Closing Deepgram connection...")
        await dg_connection.finish()
        logger.info("WebSocket cleanup complete.")


if __name__ == "__main__":
    import os

    # Auto-shutdown for safety in sandbox
    import threading
    import time

    import uvicorn

    def auto_exit():
        time.sleep(600)
        logger.info("Auto-shutdown timer reached. Exiting.")
        os._exit(0)

    threading.Thread(target=auto_exit, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=8000)
