import asyncio
import base64
import os
import subprocess
import wave
import sys
import time
import math
import struct
import threading
from typing import List

try:
    import pyaudio
except ImportError:
    print("Please install PyAudio: pip install pyaudio")
    exit(1)

from sarvamai import AsyncSarvamAI

# Ensure orchestrator path is resolvable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from orchestrator.ui import C, panel, _term_width

# Audio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 10
WAVE_OUTPUT_FILENAME = "temp_command.wav"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEBGhosting Pixel Mic Visualization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

MIC_COLORS = {
    1: "\033[38;5;88m",
    2: "\033[38;5;203m",
}


class PixelMic:
    """
    Renders the WEBGhosting pixel mic as terminal art with a subtle
    audio-reactive pulse while listening.
    """

    def __init__(self, cell_width=2):
        self.matrix = MIC_MATRIX
        self.height = len(self.matrix)
        self.width = len(self.matrix[0])
        self.cell_width = cell_width
        self.target_energy = 0.0
        self.current_energy = 0.0

    def set_energy(self, value: float):
        self.target_energy = max(0.0, min(1.0, value))

    def render_width(self) -> int:
        if self.width == 0:
            return 0
        return self.width * self.cell_width

    def _color_for(self, px: int, state: str, row_index: int, time_t: float) -> str:
        pulse = 0.5 + (math.sin(time_t * 7.0 + row_index * 0.55) * 0.5)
        if state == "LISTENING" and px == 1 and self.current_energy > 0.45 and pulse > 0.72:
            return MIC_COLORS[2]
        if state == "TRANSCRIBING" and px == 1:
            return MIC_COLORS[2]
        return MIC_COLORS[px]

    def render(self, time_t: float, state: str) -> List[str]:
        idle_energy = 0.12 if state == "STARTUP" else 0.22 if state == "TRANSCRIBING" else self.target_energy
        self.current_energy += (idle_energy - self.current_energy) * 0.25

        term_width = _term_width()
        art_width = self.render_width()
        center_pad = max(2, (term_width - art_width) // 2)
        lines = []

        for row_index, row in enumerate(self.matrix):
            wobble = 0
            if state == "LISTENING":
                wobble = int(round(math.sin(time_t * 8.0 + row_index * 0.8) * (0.25 + self.current_energy * 0.9)))
            elif state == "TRANSCRIBING":
                wobble = int(round(math.sin(time_t * 3.0 + row_index * 0.35) * 0.35))

            line = [" " * max(0, center_pad + wobble)]
            for px in row:
                if px == 0:
                    line.append(" " * self.cell_width)
                else:
                    line.extend([self._color_for(px, state, row_index, time_t), "█" * self.cell_width, C.RESET])
            lines.append("".join(line))

        return lines


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Voice UI Manager
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class VoiceUI:
    def __init__(self):
        self.mic = PixelMic(cell_width=2)
        self.running = False
        self.frame_thread = None
        self.rms_value = 0.0
        self.state = "STARTUP" # STARTUP, LISTENING, TRANSCRIBING, EXECUTING

    def _compute_rms(self, data: bytes) -> float:
        """Calculate Root Mean Square of audio chunk to get volume amplitude."""
        count = len(data) // 2
        format_string = f"<{count}h"
        shorts = struct.unpack(format_string, data)
        sum_squares = sum(s * s for s in shorts)
        return math.sqrt(sum_squares / count) if count > 0 else 0

    def feed_audio(self, data: bytes):
        """Feed audio chunk to update visualization intensity."""
        rms = self._compute_rms(data)
        self.rms_value = rms

        # Normalize RMS (approximate baseline for normal voice)
        norm = min(max((rms - 200) / 2000.0, 0.0), 1.0)
        self.mic.set_energy(norm)

    def start_animation(self):
        self.running = True
        self.frame_thread = threading.Thread(target=self._animate_loop, daemon=True)
        self.frame_thread.start()

    def stop_animation(self):
        self.running = False
        if self.frame_thread:
            self.frame_thread.join()

    def _animate_loop(self):
        # Clear screen area
        sys.stdout.write("\n" * (self.mic.height + 3))

        start_time = time.time()
        while self.running:
            t = time.time() - start_time

            frame_lines = self.mic.render(t, self.state)

            # Move cursor up and draw
            sys.stdout.write(f"\033[{self.mic.height + 2}A")

            # Draw header
            if self.state == "LISTENING":
                remaining = max(0.0, RECORD_SECONDS - t)
                header = f"  {C.BCYAN}● LISTENING ({remaining:.1f}s){C.RESET} (Speak your command...)"
            elif self.state == "TRANSCRIBING":
                header = f"  {C.BMAGENTA}○ TRANSCRIBING{C.RESET} (Computing...)"
            else:
                header = f"  {C.WHITE}{self.state}{C.RESET}"

            sys.stdout.write(f"\033[2K\r{header}\n")
            for line in frame_lines:
                sys.stdout.write(f"\033[2K\r{line}\n")
            sys.stdout.flush()
            time.sleep(0.05) # ~20 fps


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main Flow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def record_audio(ui: VoiceUI):
    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    frames = []

    ui.state = "LISTENING"
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        ui.feed_audio(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    # Save to WAV
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

async def transcribe_and_execute(ui: VoiceUI):
    if not os.path.exists(WAVE_OUTPUT_FILENAME):
        print("Audio file not found.")
        return

    with open(WAVE_OUTPUT_FILENAME, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode("utf-8")

    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        ui.stop_animation()
        print(f"\n  {C.RED}ERROR: SARVAM_API_KEY environment variable is not set.{C.RESET}")
        return

    ui.state = "TRANSCRIBING"
    client = AsyncSarvamAI(api_subscription_key=api_key)

    try:
        async with client.speech_to_text_streaming.connect(
            model="saaras:v3",
            mode="transcribe",
            language_code="unknown",
            high_vad_sensitivity=False
        ) as ws:

            await ws.transcribe(audio=audio_data)

            final_text = ""
            while True:
                try:
                    response_json = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    chunk = ""
                    if hasattr(response_json, 'data') and hasattr(response_json.data, 'transcript'):
                        chunk = response_json.data.transcript
                    else:
                        chunk = str(response_json)

                    if chunk and chunk != "None":
                        final_text += " " + chunk.strip()
                except asyncio.TimeoutError:
                    break
                except Exception:
                    break

            text = final_text.strip()

            # Stop UI before passing to orchestrator so it prints cleanly
            ui.stop_animation()

            # Print space to clear the blob area
            sys.stdout.write(f"\033[{ui.mic.height + 2}B\n")

            panel("Voice Command", [f"\"{text}\""], color=C.CYAN)

            if text and len(str(text).strip()) > 2:
                env = os.environ.copy()
                required = ["AI_API_KEY", "AI_BASE_URL", "AI_MODEL"]
                missing = [name for name in required if not env.get(name)]
                if missing:
                    print(f"\n  {C.RED}ERROR: Missing WEBGhosting env vars: {', '.join(missing)}{C.RESET}")
                    return

                # Hand off to Orchestrator natively, inheriting its UI
                subprocess.run([
                    "python3",
                    "-m",
                    "orchestrator.orchestrator",
                    "--run",
                    str(text)
                ], env=env)
            else:
                print(f"\n  {C.YELLOW}⚠ No valid command detected (too short or empty).{C.RESET}")

    except Exception as e:
        ui.stop_animation()
        print(f"\n  {C.RED}Transcription failed: {e}{C.RESET}")

    finally:
        if os.path.exists(WAVE_OUTPUT_FILENAME):
            os.remove(WAVE_OUTPUT_FILENAME)


if __name__ == "__main__":
    os.system('clear') # Clear screen for a clean UI launch
    print(f"\n  {C.BOLD}WEBGhosting Agentic Voice Interface{C.RESET}")
    print(f"  {C.DIM}Initializing audio stream...{C.RESET}")
    time.sleep(0.5)

    ui = VoiceUI()
    ui.start_animation()

    try:
        record_audio(ui)
        asyncio.run(transcribe_and_execute(ui))
    except KeyboardInterrupt:
        ui.stop_animation()
        print(f"\n  {C.YELLOW}Canceled.{C.RESET}")
        if os.path.exists(WAVE_OUTPUT_FILENAME):
            os.remove(WAVE_OUTPUT_FILENAME)
