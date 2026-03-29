import gradio as gr
import asyncio
import base64
import os
import subprocess
import json
from sarvamai import AsyncSarvamAI
import numpy as np
import wave

MIC_MATRIX = [
    [0, 0, 1, 1, 1, 0, 0],
    [0, 0, 1, 2, 1, 0, 0],
    [0, 0, 1, 2, 1, 0, 0],
    [0, 0, 1, 2, 1, 0, 0],
    [0, 1, 1, 2, 1, 1, 0],
    [0, 1, 1, 2, 1, 1, 0],
    [0, 1, 1, 2, 1, 1, 0],
    [0, 0, 1, 1, 1, 0, 0],
    [0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 1, 0, 0, 0],
    [0, 1, 1, 1, 1, 1, 0],
]


def render_mic_html():
    rows = []
    for row in MIC_MATRIX:
        cells = []
        for px in row:
            klass = "mic-off" if px == 0 else f"mic-on m{px}"
            cells.append(f'<div class="mic-px {klass}"></div>')
        rows.append(f'<div class="mic-row">{"".join(cells)}</div>')
    return f'<div class="mic-grid" aria-hidden="true">{"".join(rows)}</div>'


MIC_HTML = render_mic_html()

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
    background-color: #0d0a0f !important;
    color: #fcebeb !important;
}

/* Hide the default Gradio audio block visually so only our custom mic button shows.
   We CANNOT use display:none because Safari blocks microphone clicks on hidden elements! */
#hidden-audio {
    position: absolute !important;
    opacity: 0.001 !important;
    z-index: -9999 !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
}

.mic-wrapper {
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 28px auto 18px;
    min-height: 220px;
}

.mic-shell {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 24px 30px;
    cursor: pointer;
    transition: transform 0.18s ease, filter 0.25s ease;
    user-select: none;
}

.mic-shell:hover {
    transform: translateY(-2px);
}

.mic-shell::before {
    content: "";
    position: absolute;
    inset: 12px;
    border-radius: 28px;
    background: radial-gradient(circle, rgba(226,75,74,0.22) 0%, rgba(240,149,149,0.12) 35%, rgba(13,10,15,0) 72%);
    opacity: 0.55;
    filter: blur(12px);
    transition: opacity 0.2s ease;
}

.mic-grid {
    display: flex;
    flex-direction: column;
    gap: 2px;
    justify-content: center;
    align-items: center;
    position: relative;
    z-index: 1;
    filter: drop-shadow(0 10px 18px rgba(0,0,0,0.45));
    transform-origin: center center;
}

.mic-row {
    display: flex;
    gap: 2px;
}

.mic-px {
    width: 16px;
    height: 16px;
    border-radius: 1px;
}

.mic-off {
    background: transparent;
}

.mic-on {
    box-shadow: inset 0 0 0 1px #2a0808;
}

.m1 { background: #791F1F; }
.m2 { background: #E24B4A; }

.mic-shell.is-idle .mic-grid {
    animation: mic-idle 2.6s ease-in-out infinite;
}

.mic-shell.is-listening::before {
    opacity: 0.95;
    animation: mic-halo 1s ease-in-out infinite;
}

.mic-shell.is-listening .mic-grid {
    animation: mic-listen-bob 1s ease-in-out infinite;
    filter: drop-shadow(0 0 12px rgba(226,75,74,0.45)) drop-shadow(0 0 26px rgba(240,149,149,0.18));
}

.mic-shell.is-listening .mic-row:nth-child(odd) {
    animation: mic-row-left 0.7s ease-in-out infinite;
}

.mic-shell.is-listening .mic-row:nth-child(even) {
    animation: mic-row-right 0.7s ease-in-out infinite;
}

.mic-shell.is-processing::before {
    opacity: 0.85;
}

.mic-shell.is-processing .mic-grid {
    animation: mic-processing 1.2s ease-in-out infinite;
    filter: drop-shadow(0 0 10px rgba(252,235,235,0.25));
}

@keyframes mic-idle {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-3px); }
}

@keyframes mic-listen-bob {
    0%, 100% { transform: translateY(0) scale(1); }
    50% { transform: translateY(-5px) scale(1.06); }
}

@keyframes mic-row-left {
    0%, 100% { transform: translateX(0); }
    50% { transform: translateX(-1px); }
}

@keyframes mic-row-right {
    0%, 100% { transform: translateX(0); }
    50% { transform: translateX(1px); }
}

@keyframes mic-processing {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(0.96); }
}

@keyframes mic-halo {
    0%, 100% { transform: scale(0.94); }
    50% { transform: scale(1.08); }
}

.center-text {
    text-align: center;
    color: #f7c1c1;
    font-family: Courier, monospace;
    margin-top: 10px;
}
"""

js_code = """
async () => {
    let isRecording = false;
    const initInterval = setInterval(() => {
        let mic = document.getElementById('mic-shell');
        let textStatus = document.getElementById('orb-status');
        let audioDiv = document.querySelector('#hidden-audio');
        if (!mic || !audioDiv) return; // Wait until DOM is fully injected by Gradio

        clearInterval(initInterval);
        mic.classList.add('is-idle');
        console.log("Pixel microphone successfully attached to Gradio DOM!");

        const toggleRecording = () => {
            let recordBtn = audioDiv.querySelector('button[aria-label="Record"]');
            let stopBtn = audioDiv.querySelector('button[aria-label="Stop"]');
            // Gradio 6 sometimes just has a button without specific aria labels depending on state.
            let firstBtn = audioDiv.querySelector('button');

            if (!isRecording) {
                // START RECORDING
                if (recordBtn) recordBtn.click();
                else if (firstBtn) firstBtn.click();

                mic.classList.remove('is-idle', 'is-processing');
                mic.classList.add('is-listening');
                textStatus.innerText = "Listening... microphone is live.";
                isRecording = true;
            } else {
                // STOP RECORDING
                if (stopBtn) stopBtn.click();
                else if (firstBtn) firstBtn.click(); // often the single center button just toggles

                mic.classList.remove('is-listening');
                mic.classList.add('is-processing');
                textStatus.innerText = "Processing your command...";
                isRecording = false;
            }
        };

        mic.addEventListener('click', toggleRecording);
        mic.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                toggleRecording();
            }
        });
    }, 500);
}
"""

# --- GRADIO UI ---
with gr.Blocks() as demo:
    gr.Markdown("# WEBGhosting Voice Agent", elem_classes=["center-text"])
    gr.Markdown("<div id='orb-status' class='center-text'>Click the mic to start recording.</div>")

    gr.HTML(f'''
        <div class="mic-wrapper">
            <div id="mic-shell" class="mic-shell" role="button" tabindex="0" aria-label="Start or stop voice recording">
                {MIC_HTML}
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
