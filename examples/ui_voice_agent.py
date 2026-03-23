import gradio as gr
import asyncio
import base64
import os
import subprocess
import json
from sarvamai import AsyncSarvamAI
import numpy as np
import wave

async def transcribe_audio(audio_numpy):
    if audio_numpy is None:
        return ""

    try:
        sample_rate, data = audio_numpy
        # Force mono channel
        if len(data.shape) > 1:
            data = data.mean(axis=1).astype(data.dtype)

        # Convert audio array to 16-bit PCM for perfect STT compatibility
        if data.dtype in (np.float32, np.float64):
            data = np.int16(data * 32767)
        elif data.dtype == np.int32:
            data = np.int16(data >> 16)

        temp_wav = "/tmp/gradio_sarvam_audio.wav"
        with wave.open(temp_wav, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(data.tobytes())

        with open(temp_wav, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return f"Error Formatting Audio: {e}"

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

async def process_voice_command(audio_tuple):
    if audio_tuple is None:
        return "Nothing recorded."
    # Returns the transcribed string to the textbox
    transcript = await transcribe_audio(audio_tuple)
    return transcript

def execute_command(text):
    if not text or len(text.strip()) < 2 or text.startswith("Error") or text.startswith("Nothing"):
        yield "Waiting for a valid command..."
        return

    env = os.environ.copy()
    required = ["AI_API_KEY", "AI_BASE_URL", "AI_MODEL"]
    missing = [name for name in required if not env.get(name)]
    if missing:
        yield f"Missing WEBGhosting env vars: {', '.join(missing)}"
        return

    # Streaming the bash output live
    process = subprocess.Popen(
        ["python3", "-m", "orchestrator.orchestrator", "--run", text],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    output = f"Executing Command...\n---\n"
    for line in iter(process.stdout.readline, ''):
        output += line
        yield output

    process.stdout.close()
    process.wait()
    yield output + "\n✅ Finished!"


custom_css = """
body, .gradio-container {
    background-color: #171717 !important;
}

/* Hide the default Gradio audio block visually so only our custom Amoeba shows.
   We CANNOT use display:none because Safari blocks microphone clicks on hidden elements! */
#hidden-audio {
    position: absolute !important;
    opacity: 0.001 !important;
    z-index: -9999 !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
}

/* Container for our custom Amoeba Button */
.amoeba-wrapper {
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 40px auto;
    height: 150px;
    width: 150px;
}

/* The Pixel Art Red Circle Amoeba styling */
.pixel-amoeba {
    width: 100px;
    height: 100px;
    background-color: #ef4444; /* bright red */
    position: relative;
    cursor: pointer;
    box-shadow:
        inset -8px -8px 0px 0px rgba(0,0,0,0.3),
        inset 8px 8px 0px 0px rgba(255,255,255,0.4),
        0 0 0 4px #000;
    transition: all 0.3s;
    display: flex;
    justify-content: center;
    align-items: center;
}

/* Text inside the amoeba */
.pixel-amoeba span {
    font-family: monospace;
    font-size: 2rem;
    pointer-events: none;
    opacity: 0.8;
}

/* Base shape: Perfect Circle */
.pixel-circle {
    border-radius: 50%;
}

/* Wavy Amoeba shape (listening mode) */
.pixel-wavy {
    animation: pixelmorph 1s steps(6, end) infinite;
    background-color: #fsa444; /* changes a bit randomly */
    box-shadow:
        inset -4px -4px 0px 0px rgba(0,0,0,0.3),
        inset 4px 4px 0px 0px rgba(255,255,255,0.4),
        0 0 0 4px #000,
        0 0 20px 10px rgba(239, 68, 68, 0.6);
}

@keyframes pixelmorph {
    0% { border-radius: 60% 40% 50% 50%; transform: scale(1); }
    25% { border-radius: 50% 60% 40% 60%; transform: scale(1.05); }
    50% { border-radius: 40% 50% 60% 40%; transform: scale(1.1); }
    75% { border-radius: 40% 40% 60% 60%; transform: scale(1.05); }
    100% { border-radius: 60% 40% 50% 50%; transform: scale(1); }
}

.center-text {
    text-align: center;
    color: #a3a3a3;
    font-family: Courier, monospace;
    margin-top: 10px;
}
"""

js_code = """
async () => {
    let isRecording = false;
    const initInterval = setInterval(() => {
        let orb = document.getElementById('amoeba-orb');
        let icon = document.getElementById('orb-icon');
        let textStatus = document.getElementById('orb-status');
        let audioDiv = document.querySelector('#hidden-audio');
        if (!orb || !audioDiv) return; // Wait until DOM is fully injected by Gradio

        clearInterval(initInterval);
        console.log("Amoeba Orb successfully attached to Gradio DOM!");

        orb.addEventListener('click', () => {
            let recordBtn = audioDiv.querySelector('button[aria-label="Record"]');
            let stopBtn = audioDiv.querySelector('button[aria-label="Stop"]');
            // Gradio 6 sometimes just has a button without specific aria labels depending on state.
            let firstBtn = audioDiv.querySelector('button');

            if (!isRecording) {
                // START RECORDING
                if (recordBtn) recordBtn.click();
                else if (firstBtn) firstBtn.click();

                orb.classList.remove('pixel-circle');
                orb.classList.add('pixel-wavy');
                icon.innerText = "🛑";
                textStatus.innerText = "Listening... Amoeba is active!";
                isRecording = true;
            } else {
                // STOP RECORDING
                if (stopBtn) stopBtn.click();
                else if (firstBtn) firstBtn.click(); // often the single center button just toggles

                orb.classList.remove('pixel-wavy');
                orb.classList.add('pixel-circle');
                icon.innerText = "🎙️";
                textStatus.innerText = "Processing & Execution Mode... Please wait.";
                isRecording = false;
            }
        });
    }, 500);
}
"""

# --- GRADIO UI ---
with gr.Blocks() as demo:
    gr.Markdown("# 👾 Pixel Voice Agent", elem_classes=["center-text"])
    gr.Markdown("<div id='orb-status' class='center-text'>Click the red blob to start!</div>")

    # Custom HTML Amoeba (Red Pixel Art Circle)
    gr.HTML('''
        <div class="amoeba-wrapper">
            <div id="amoeba-orb" class="pixel-amoeba pixel-circle">
                <span id="orb-icon">🎙️</span>
            </div>
        </div>
    ''')

    # Hidden audio input handling natively Gradio streams!
    audio_input = gr.Audio(sources=["microphone"], type="numpy", elem_id="hidden-audio")

    transcript_box = gr.Textbox(label="Transcribed Command", interactive=True)
    logs_box = gr.Textbox(label="Agent Status", lines=15, interactive=False)

    # When audio recording is completed, transcribe FIRST
    transcription_event = audio_input.change(
        fn=process_voice_command,
        inputs=audio_input,
        outputs=transcript_box
    )

    # When transcription FINISHES (.then), it automatically executes!
    transcription_event.then(
        fn=execute_command,
        inputs=transcript_box,
        outputs=logs_box
    )

    demo.load(js=js_code) # Initialize the javascript hooks

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True, css=custom_css, theme=gr.themes.Monochrome())
