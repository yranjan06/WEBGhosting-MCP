import asyncio
import base64
import os
import subprocess
import wave
import json

try:
    import pyaudio
except ImportError:
    print("Please install PyAudio: pip install pyaudio")
    exit(1)

from sarvamai import AsyncSarvamAI

# Audio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 10
WAVE_OUTPUT_FILENAME = "temp_command.wav"

def record_audio():
    """Records audio from the microphone for a set duration or until stopped."""
    p = pyaudio.PyAudio()

    print(f"\nGaining microphone access. Speak your command for {RECORD_SECONDS} seconds...")

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    frames = []

    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("Recording finished.")

    stream.stop_stream()
    stream.close()
    p.terminate()

    # Save the recorded data as a WAV file
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

async def transcribe_and_execute():
    # Make sure we have the file
    if not os.path.exists(WAVE_OUTPUT_FILENAME):
        print("Audio file not found.")
        return

    # Base64 encode the audio as per Sarvam API requirements
    with open(WAVE_OUTPUT_FILENAME, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode("utf-8")

    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        print("ERROR: SARVAM_API_KEY environment variable is not set.")
        return

    print("Transcribing via Sarvam AI Streaming API...")

    # Initialize client
    client = AsyncSarvamAI(api_subscription_key=api_key)

    # Connect and transcribe
    try:
        async with client.speech_to_text_streaming.connect(
            model="saaras:v3",
            mode="transcribe",
            language_code="unknown",
            high_vad_sensitivity=False
        ) as ws:

            await ws.transcribe(audio=audio_data)

            # Read all chunks because the user might pause while speaking
            final_text = ""
            while True:
                try:
                    # Wait for up to 3 seconds for the next chunk
                    response_json = await asyncio.wait_for(ws.recv(), timeout=3.0)

                    try:
                        if hasattr(response_json, 'data') and hasattr(response_json.data, 'transcript'):
                            chunk = response_json.data.transcript
                        else:
                            chunk = str(response_json)
                    except Exception:
                        chunk = str(response_json)

                    if chunk and chunk != "None":
                        final_text += " " + chunk.strip()
                except asyncio.TimeoutError:
                    break  # No more transcripts coming
                except Exception:
                    break

            text = final_text.strip()

            print(f"\nYou said: '{text}'")

            if text and len(str(text).strip()) > 2:
                print("Passing command to WEBGhosting Orchestrator...")

                env = os.environ.copy()
                required = ["AI_API_KEY", "AI_BASE_URL", "AI_MODEL"]
                missing = [name for name in required if not env.get(name)]
                if missing:
                    print(f"ERROR: Missing WEBGhosting env vars: {', '.join(missing)}")
                    return

                subprocess.run([
                    "python3",
                    "-m",
                    "orchestrator.orchestrator",
                    "--run",
                    str(text)
                ], env=env)
            else:
                print("No valid command detected (too short or empty).")

    except Exception as e:
        print(f"Transcription failed: {e}")

    finally:
        # Cleanup temporary audio file
        if os.path.exists(WAVE_OUTPUT_FILENAME):
            os.remove(WAVE_OUTPUT_FILENAME)


if __name__ == "__main__":
    record_audio()
    asyncio.run(transcribe_and_execute())
