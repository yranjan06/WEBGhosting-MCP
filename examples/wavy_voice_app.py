import os
import asyncio
import subprocess
import base64
import json
import threading
import wave
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

try:
    import pyaudio
except ImportError:
    print("Please install PyAudio: pip install pyaudio")
    exit(1)

from sarvamai import AsyncSarvamAI

app = FastAPI()

# -----------------
# PYAUDIO RECORDER
# -----------------
class AudioRecorder:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False

    def start(self):
        self.is_recording = True
        self.frames = []
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=16000,
                                  input=True,
                                  frames_per_buffer=1024)
        # Run recording loop in a background thread so it doesn't block async execution
        def record():
            while self.is_recording:
                try:
                    data = self.stream.read(1024, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception:
                    pass
        threading.Thread(target=record, daemon=True).start()

    def stop(self, output_filename="temp_command.wav"):
        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        # Save as standard 16kHz PCM WAV file
        wf = wave.open(output_filename, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        return output_filename

recorder = AudioRecorder()

# ---------
# HTML / CSS
# ---------
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WEBGhosting Voice Assistant</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #0f172a; /* Slate 900 */
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, "Open Sans", sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }

        h1 {
            font-weight: 300;
            letter-spacing: 2px;
            margin-bottom: 40px;
            text-align: center;
        }

        /* The Amoeba Wrapper */
        .blob-wrapper {
            position: relative;
            width: 250px;
            height: 250px;
            display: flex;
            justify-content: center;
            align-items: center;
            cursor: pointer;
            margin-bottom: 30px;
        }

        /* Inside mic icon */
        .mic-icon {
            position: absolute;
            z-index: 10;
            font-size: 3rem;
            transition: transform 0.3s;
            pointer-events: none;
        }

        /* The Wavy Blob */
        .blob {
            position: absolute;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #0ea5e9, #8b5cf6, #ec4899);
            border-radius: 50%;
            opacity: 0.8;
            box-shadow: 0 0 30px rgba(139, 92, 246, 0.4);
            transition: all 0.5s ease;
        }

        /* Hover effect when Idle */
        .blob-wrapper:hover .blob.idle {
            box-shadow: 0 0 50px rgba(139, 92, 246, 0.8);
            transform: scale(1.05);
        }

        /* Wavy Animation Class */
        .wavy {
            animation: ripple 1.5s infinite linear;
        }

        @keyframes ripple {
            0%   { border-radius: 40% 60% 70% 30% / 40% 50% 60% 50%; box-shadow: 0 0 30px #0ea5e9; transform: scale(1); }
            34%  { border-radius: 70% 30% 50% 50% / 30% 30% 70% 70%; box-shadow: 0 0 50px #8b5cf6; transform: scale(1.15); }
            67%  { border-radius: 100% 60% 60% 100% / 100% 100% 60% 60%; box-shadow: 0 0 40px #ec4899; transform: scale(1.1); }
            100% { border-radius: 40% 60% 70% 30% / 40% 50% 60% 50%; box-shadow: 0 0 30px #0ea5e9; transform: scale(1); }
        }

        .status {
            font-size: 1.2rem;
            opacity: 0.8;
            margin-bottom: 20px;
            height: 28px;
        }

        .terminal {
            width: 90%;
            max-width: 800px;
            height: 250px;
            background-color: #1e293b;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #334155;
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
            font-family: "Courier New", Courier, monospace;
            font-size: 0.9rem;
            color: #10b981;
            white-space: pre-wrap;
            overflow-y: auto;
        }

        /* Hidden initially */
        .hidden {
            display: none;
        }
    </style>
</head>
<body>

    <h1>WEBGhosting Agent</h1>

    <div class="blob-wrapper" id="mic-btn">
        <div class="blob idle" id="blob-bg"></div>
        <div class="mic-icon" id="mic-emoji">🎙️</div>
    </div>

    <div class="status" id="status-text">Click the orb to speak...</div>

    <div class="terminal" id="terminal">Initializing system... Waiting for command.</div>

    <script>
        const btn = document.getElementById('mic-btn');
        const blob = document.getElementById('blob-bg');
        const icon = document.getElementById('mic-emoji');
        const status = document.getElementById('status-text');
        const terminal = document.getElementById('terminal');

        let isRecording = false;

        btn.addEventListener('click', async () => {
            if (!isRecording) {
                // START RECORDING
                isRecording = true;

                // Visuals
                blob.classList.remove('idle');
                blob.classList.add('wavy');
                icon.innerText = "🛑";
                status.innerText = "Listening... Speak now, click to stop & run.";

                // Tell Python to start pyaudio
                await fetch('/start_recording', { method: 'POST' });
                terminal.innerText = ">> Microphone opened. Recording locally...\n";

            } else {
                // STOP AND EXECUTE
                isRecording = false;

                // Visuals
                blob.classList.remove('wavy');
                blob.classList.add('idle');
                icon.innerText = "⏳";
                status.innerText = "Transcribing & executing...";

                try {
                    // Tell Python to stop pyaudio and run the orchestrator
                    const response = await fetch('/stop_and_run', { method: 'POST' });

                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    terminal.innerText = "";

                    // Stream output chunks to the terminal div
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        terminal.innerText += decoder.decode(value);
                        terminal.scrollTop = terminal.scrollHeight; // Auto-scroll
                    }

                    status.innerText = "Task Finished. Click the orb to speak again.";
                    icon.innerText = "🎙️";
                } catch (e) {
                    status.innerText = "Error executing command.";
                    icon.innerText = "🎙️";
                }
            }
        });
    </script>
</body>
</html>
"""

# ---------
# ENDPOINTS
# ---------
@app.get("/")
def home():
    return HTMLResponse(content=HTML_PAGE)

@app.post("/start_recording")
def start_recording():
    recorder.start()
    return {"status": "started"}

async def transcribe(audio_path: str):
    if not os.path.exists(audio_path):
        return "No audio found."

    with open(audio_path, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode("utf-8")

    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        return "Error: SARVAM_API_KEY environment variable is not set."
    client = AsyncSarvamAI(api_subscription_key=api_key)

    final_text = ""
    try:
        async with client.speech_to_text_streaming.connect(
            model="saaras:v3",
            mode="transcribe",
            language_code="unknown",
            high_vad_sensitivity=False
        ) as ws:
            await ws.transcribe(audio=audio_data)

            while True:
                try:
                    response_json = await asyncio.wait_for(ws.recv(), timeout=2.5)
                    chunk = ""
                    if hasattr(response_json, 'data') and hasattr(response_json.data, 'transcript'):
                        chunk = response_json.data.transcript
                    else:
                        try:
                            res_dict = json.loads(response_json)
                            chunk = res_dict.get('transcript', str(response_json))
                        except Exception:
                            chunk = str(response_json)

                    if chunk and chunk != "None":
                        final_text += " " + chunk.strip()
                except asyncio.TimeoutError:
                    break
                except Exception:
                    break
    except Exception as e:
        return f"Error transcribing: {e}"

    return final_text.strip()

@app.post("/stop_and_run")
async def stop_and_run():
    async def log_generator():
        yield "Stopping microphone...\n"
        output_file = recorder.stop("temp_ui_command.wav")

        yield "Sending audio to Sarvam AI Streaming API...\n"
        text = await transcribe(output_file)

        if not text or len(text) < 2 or "Error" in text:
            yield f"Transcription failed or was empty: '{text}'."
            return

        yield f"✅ Transcribed: '{text}'\n---\n"
        yield "Launching WEBGhosting Orchestrator...\n"

        env = os.environ.copy()
        required = ["AI_API_KEY", "AI_BASE_URL", "AI_MODEL"]
        missing = [name for name in required if not env.get(name)]
        if missing:
            yield f"Missing WEBGhosting env vars: {', '.join(missing)}\n"
            return

        process = subprocess.Popen(
            ["python3", "-m", "orchestrator.orchestrator", "--run", text],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Stream the subprocess STDOUT back to the web browser
        for line in iter(process.stdout.readline, ''):
            yield line

        process.wait()
        process.stdout.close()
        yield "\n--- Execution Complete ---"

    return StreamingResponse(log_generator(), media_type="text/plain")

if __name__ == "__main__":
    import webbrowser
    print("Launching visually appealing Wavy Voice UI on http://127.0.0.1:8000")
    webbrowser.open("http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
