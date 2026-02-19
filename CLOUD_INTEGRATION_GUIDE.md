# Cloud-Integrated Voice Agent: 3-Model Architecture

This document describes the upgraded architecture of the Voice Agent, utilizing dedicated cloud-based services for a high-performance 3-model pipeline.

## 1. Architecture Overview
The agent uses a real-time streaming architecture via Twilio Media Streams (WebSockets), replacing the basic `<Gather>` mechanism.

| Component | Model / Service | Purpose |
|-----------|-----------------|---------|
| **Speech-to-Text (STT)** | Deepgram (Nova-2) | Real-time audio-to-text transcription |
| **Logic (LLM)** | OpenRouter (GPT-4o-mini) | Natural language processing and response generation |
| **Text-to-Speech (TTS)**| ElevenLabs / Deepgram Speak | Converting text responses back to voice audio |

## 2. Infrastructure Flow
1. **Inbound/Outbound Call**: Twilio initiates or receives a call.
2. **WebSocket Connection**: Twilio connects to the FastAPI `/media-stream` endpoint via WSS.
3. **STT (Streaming)**: Audio chunks in `mulaw` (8kHz) are forked to Deepgram for real-time transcription.
4. **LLM Execution**: Upon detecting a final transcript, the text is sent to OpenRouter (`openai/gpt-4o-mini`).
5. **TTS Generation**: The generated response is sent to the TTS provider (ElevenLabs).
6. **Audio Playback**: Synthesized audio is streamed back to Twilio via the same WebSocket connection and played to the caller.

## 3. Environment Configuration
The following environment variables are required:

```env
# Telephony
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=...

# Brain (LLM)
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o-mini

# Speech-to-Text
DEEPGRAM_API_KEY=...

# Text-to-Speech
ELEVENLABS_API_KEY=...

# Backend
NGROK_URL=...
MOCK_MODE=false # Set to true to simulate STT/TTS if keys are missing
```

## 4. Key Improvements
- **Lowest Latency**: Real-time streaming reduces the "wait time" between speaker turns.
- **Superior Quality**: Dedicated STT/TTS providers offer much more natural voices and robust transcription than basic telephony defaults.
- **Infinite Flexibility**: Each part of the 3-model pipeline can be swapped or tuned independently.
