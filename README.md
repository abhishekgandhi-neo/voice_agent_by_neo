# AI Voice Agent

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Built by NEO](https://img.shields.io/badge/built%20by-NEO-black.svg)](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo)

A real-time AI voice agent that answers and places phone calls. It listens, thinks, acts, and talks — all in seconds.

---

## Why it's good

| What | How |
|------|-----|
| **Zero-delay transcription** | Deepgram Nova-2 streams audio as you speak — no waiting for silence |
| **Thinks on the call** | LangChain agent (GPT-4o-mini) can search the web or send an email mid-conversation |
| **Natural voice** | ElevenLabs Rachel voice at 8 kHz — sounds like a real support agent |
| **Full duplex audio** | Twilio Media Streams WebSocket — no polling, no round-trips |
| **One file to run** | Everything lives in `main.py`. Start with `python main.py`. |

---

## How it works

```
Caller ──▶ Twilio ──▶ /media-stream (WebSocket)
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
             Deepgram Nova-2      LangChain Agent
              (live STT)          (GPT-4o-mini)
                    │                    │
                    └─────────┬──────────┘
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
              web_search            send_email
              (DuckDuckGo)          (SMTP/Gmail)
                              │
                              ▼
                       ElevenLabs TTS
                              │
                              ▼
                    Audio ──▶ Twilio ──▶ Caller
```

**Per-turn flow:**
1. Caller speaks → Twilio streams μlaw audio chunks over WebSocket
2. Deepgram fires a transcript on every final sentence
3. LangChain agent decides: respond directly, search the web, or send an email
4. ElevenLabs converts the reply to voice → streamed back to the caller instantly

---

## Quick Start

```bash
# 1. Clone & activate venv
git clone <repo-url> && cd AI_voice_agent_by_neo
python -m venv venv && venv\Scripts\activate   # Windows
# source venv/bin/activate                     # macOS/Linux

# 2. Install dependencies
pip install fastapi uvicorn twilio httpx deepgram-sdk \
    langchain-openai langchain-community duckduckgo-search \
    python-dotenv elevenlabs pydub websockets

# 3. Configure env
cp .env.sample .env   # then fill in your keys

# 4. Run
python main.py

# 5. Expose publicly
ngrok http 8000
```

Then in the [Twilio Console](https://console.twilio.com/), set your phone number's webhook to:
```
POST https://<your-ngrok-url>/voice
```

Call your Twilio number — the agent picks up.

---

## Outbound Calls

```bash
python trigger_call.py
```

Calls `TARGET_NUMBER` from your Twilio number and connects it to the same agent.

---

## Environment Variables

Copy `.env.sample` to `.env` and fill in your credentials. Required keys:

| Variable | Purpose |
|----------|---------|
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Twilio auth |
| `TWILIO_PHONE_NUMBER` | Your Twilio number |
| `NGROK_URL` | Public URL from ngrok |
| `OPENROUTER_API_KEY` | LLM access via OpenRouter |
| `DEEPGRAM_API_KEY` | Speech-to-text |
| `ELEVENLABS_API_KEY` | Text-to-speech |
| `EMAIL_SENDER` / `EMAIL_PASSWORD` | Gmail + App Password (email tool) |
| `TARGET_NUMBER` | Number to call via `trigger_call.py` |

---

## Project Files

```
main.py            ← FastAPI server (the whole agent)
trigger_call.py    ← Trigger an outbound call
.env.sample        ← Environment variable template
```

---

## Built with NEO

This project was developed using [NEO](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo), an AI assistant inside VS Code.

**Developing with NEO:**

The agent was scaffolded and iterated on by describing requirements directly to NEO in plain English. For example:

- *"Build a voice agent using Deepgram for speech-to-text, LangChain with GPT-4o-mini as the brain, and ElevenLabs for text-to-speech over a Twilio WebSocket"*
- *"Add a web_search tool using DuckDuckGo so the agent can look things up mid-call"*
- *"Add a send_email tool using smtplib so the agent can dispatch emails during a conversation"*

NEO generated the FastAPI server, the Deepgram live transcription callbacks, the LangChain tool-use loop, and the ElevenLabs TTS streaming — iterating on each piece as requirements changed.

**Running with NEO:**

You can ask NEO to run the server, expose it via ngrok, and trigger a test call without leaving VS Code:

- *"Run the voice agent server"* → NEO runs `python main.py`
- *"Expose port 8000 publicly"* → NEO runs `ngrok http 8000`
- *"Trigger an outbound test call"* → NEO runs `python trigger_call.py`

---

## License

MIT
