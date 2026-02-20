import asyncio
import base64
import json
import logging
import os
import smtplib
from email.mime.text import MIMEText
from typing import List, Optional

import httpx
from ddgs import DDGS
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveOptions,
    LiveTranscriptionEvents,
)
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
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
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# Initialize LLM via OpenRouter
llm = ChatOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
    default_headers={
        "HTTP-Referer": "https://github.com/langchain-ai/langchain",
        "X-Title": "Company Support Voice Agent",
    },
)

# -----------------------------------------------------------------------------
# Tools Definition
# -----------------------------------------------------------------------------


@tool
def send_email(recipient: str, subject: str, body: str) -> str:
    """Useful for sending an email to a specific person.
    Requires recipient email address, subject, and the message body."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        logger.warning("Email credentials not configured.")
        return "Error: Email credentials not configured on server."

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = recipient

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            try:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            except smtplib.SMTPAuthenticationError as e:
                # Check for 535 Authentication Failed
                if e.smtp_code == 535:
                    error_msg = (
                        "Authentication failed (535). If you are using Gmail, you MUST use an 'App Password', "
                        "not your regular account password."
                    )
                    logger.error(error_msg)
                    return f"Error: {error_msg}"
                raise
            server.send_message(msg)

        logger.info(f"Email sent to {recipient}")
        return f"Successfully sent email to {recipient}."
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return f"Failed to send email: {str(e)}"


@tool
def web_search(query: str) -> str:
    """Useful for finding information about the company or real-time data on the internet."""
    try:
        # Using DDGS directly for more control and robustness
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if not results:
                return "No results found for the query."
            return "\n".join([f"{r.get('title')}: {r.get('body')}" for r in results])
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Search failed due to connectivity issues. Please try again later."


tools = [send_email, web_search]
llm_with_tools = llm.bind_tools(tools)

SYSTEM_PROMPT = """You are a professional Company Support Assistant. 
Your goal is to help users with their inquiries. 

Greeting: Start every NEW conversation with 'Hello, how can I help you today?'

Capabilities:
1. If the user asks to send an email, use the send_email tool. 
   Ask for the recipient's email address if not provided.
2. If the user asks about company details or information you don't know, use the web_search tool.

Constraints:
- Keep responses brief and natural for a phone conversation.
- Do not use markdown (no bold, no lists).
- If you use a tool, explain to the user what you are doing (e.g., 'I am looking that up for you now').
"""

# -----------------------------------------------------------------------------
# Webhook Endpoints
# -----------------------------------------------------------------------------


@app.post("/voice")
async def voice_webhook(request: Request):
    response = VoiceResponse()
    connect = Connect()
    host = request.url.netloc

    is_secure = request.headers.get("x-forwarded-proto") == "https" or "ngrok" in host
    scheme = "wss" if is_secure else "ws"
    stream_url = f"{scheme}://{host}/media-stream"

    logger.info(f"Twilio connecting to: {stream_url}")
    connect.stream(url=stream_url)
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")


# -----------------------------------------------------------------------------
# WebSocket Handler
# -----------------------------------------------------------------------------


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected.")

    stream_sid = None
    chat_history = [SystemMessage(content=SYSTEM_PROMPT)]
    processing_lock = asyncio.Lock()  # Ensures sequential turn processing

    dg_client = DeepgramClient(DEEPGRAM_API_KEY)
    dg_connection = dg_client.listen.asyncwebsocket.v("1")

    async def handle_tts(text, ws, sid):
        if not text:
            return
        logger.info(f"TTS: {text}")
        voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?output_format=ulaw_8000"
        headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=data, headers=headers, timeout=30.0)
                if resp.status_code == 200:
                    payload = base64.b64encode(resp.content).decode("utf-8")
                    message = {
                        "event": "media",
                        "streamSid": sid,
                        "media": {"payload": payload},
                    }
                    await ws.send_text(json.dumps(message))
                else:
                    logger.error(f"TTS Error: {resp.status_code}")
        except Exception as e:
            logger.error(f"TTS Exception: {e}")

    async def process_agent_turn(ws, sid, user_text):
        nonlocal chat_history
        async with processing_lock:
            try:
                # Append user message once we have the lock
                chat_history.append(HumanMessage(content=user_text))

                while True:
                    # Invoke LLM
                    response = await llm_with_tools.ainvoke(chat_history)
                    chat_history.append(response)

                    if not response.tool_calls:
                        if response.content:
                            await handle_tts(response.content, ws, sid)
                        break

                    # If tool calls exist, process them
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        args = tool_call["args"]

                        # TTS Feedback
                        if tool_name == "web_search":
                            await handle_tts(
                                "One moment, I'm looking that up for you.", ws, sid
                            )
                        elif tool_name == "send_email":
                            await handle_tts(
                                "Certainly, I'll send that email for you now.", ws, sid
                            )

                        # Execute Tool
                        observation = ""
                        if tool_name == "send_email":
                            observation = send_email.invoke(args)
                        elif tool_name == "web_search":
                            observation = web_search.invoke(args)

                        chat_history.append(
                            ToolMessage(
                                content=str(observation), tool_call_id=tool_call["id"]
                            )
                        )

                    # Loop back to let the LLM see the tool outputs
            except Exception as e:
                logger.error(f"Agent Logic Error: {e}")

    async def on_message(self, result, **kwargs):
        nonlocal stream_sid
        if result.channel.alternatives:
            sentence = result.channel.alternatives[0].transcript
            if sentence and result.is_final:
                logger.info(f"User Transcribed: {sentence}")
                # Dispatch agent logical turn
                asyncio.create_task(process_agent_turn(websocket, stream_sid, sentence))

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    options = LiveOptions(
        model="nova-2",
        language="en-US",
        smart_format=True,
        encoding="mulaw",
        sample_rate=8000,
    )

    if not await dg_connection.start(options):
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg["event"] == "start":
                stream_sid = msg["start"]["streamSid"]
                logger.info(f"Stream started: {stream_sid}")
                # Initial Greeting
                await handle_tts(
                    "Hello, how can I help you today?", websocket, stream_sid
                )
            elif msg["event"] == "media":
                await dg_connection.send(base64.b64decode(msg["media"]["payload"]))
            elif msg["event"] == "stop":
                break
    except Exception as e:
        logger.error(f"WS Loop Error: {e}")
    finally:
        await dg_connection.finish()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
