import argparse
import asyncio
import base64
import glob
import json
import math
import os
import re
import struct
import sys
import tempfile
import threading
import time
import wave
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib import error as urlerror
from urllib.parse import quote, urlparse
from urllib import request as urlrequest

# Lazy imports — only needed in voice mode
pyaudio = None  # type: ignore
AsyncSarvamAI = None  # type: ignore

from client import WEBGhostingClient

# Ensure orchestrator path is resolvable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from orchestrator.ui import C, panel, _term_width

# Audio configuration (values set after pyaudio import in voice mode)
CHANNELS = 1
RATE = 16000
CHUNK = 512
SAMPLE_WIDTH = 2

# Voice activity detection settings
MAX_UTTERANCE_SECONDS = 12.0
MIN_COMMAND_SECONDS = 0.6
PRE_ROLL_SECONDS = 0.35
CALIBRATION_SECONDS = 1.0
MIN_START_THRESHOLD = 85.0
MIN_END_THRESHOLD = 55.0
START_THRESHOLD_MULTIPLIER = 2.2
END_THRESHOLD_MULTIPLIER = 1.8
SPEECH_CONFIRM_CHUNKS = 2
SILENCE_HOLD_SECONDS = 0.75
MODERATE_SPEECH_MARGIN = 35.0
SUSTAINED_SPEECH_MARGIN = 28.0
SUSTAINED_SPEECH_CHUNKS = 5
TRANSCRIBE_INITIAL_TIMEOUT_SECONDS = 4.0
TRANSCRIBE_INITIAL_RETRY_TIMEOUT_SECONDS = 1.5
TRANSCRIBE_IDLE_TIMEOUT_SECONDS = 0.8

# LLM planning settings
PLANNER_TIMEOUT = 45
MAX_HISTORY_ITEMS = 6

BUILTIN_SELECTOR_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "orchestrator", "selectors")
)
USER_SELECTOR_DIR = os.path.join(
    os.path.expanduser("~"),
    ".webghosting",
    "plugins",
    "selectors",
)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SARVAM_PROGRAM_PATH = os.path.join(REPO_ROOT, "sarvam_program.md")
SARVAM_EVAL_CASES_PATH = os.path.join(REPO_ROOT, "sarvam_eval_cases.json")
DEFAULT_RESULTS_TSV_PATH = os.environ.get(
    "SARVAM_RESULTS_TSV",
    os.path.join(REPO_ROOT, "sarvam_results.tsv"),
)

RESULTS_COLUMNS = [
    "ts_utc",
    "session_id",
    "turn_index",
    "raw_command",
    "normalized_command",
    "reframed_command",
    "plan_source",
    "plan_mode",
    "steps_json",
    "selector_path",
    "selector_used",
    "llm_used",
    "reframer_used",
    "validation_status",
    "validation_reason",
    "latency_ms",
    "active_url_before",
    "active_url_after",
    "active_title_after",
    "error",
    "assistant_reply",
]

SITE_ALIASES = {
    "google": "https://www.google.com",
    "reddit": "https://www.reddit.com",
    "hacker news": "https://news.ycombinator.com",
    "hn": "https://news.ycombinator.com",
    "github": "https://github.com",
    "youtube": "https://www.youtube.com",
    "wikipedia": "https://www.wikipedia.org",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "linkedin": "https://www.linkedin.com",
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
}

ALLOWED_TOOLS = {
    "browse",
    "click",
    "type",
    "press_key",
    "open_tab",
    "close_tab",
    "switch_tab",
    "go_back",
    "go_forward",
    "scroll",
    "scroll_to_bottom",
    "wait_for_load_state",
    "wait_for_selector",
    "get_status",
    "get_page_context",
    "list_tabs",
    "extract",
}

AUTO_WAIT_TOOLS = {"browse", "click", "press_key", "go_back", "go_forward"}

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

UI_FRAME_INTERVAL = 1.0 / 30.0

SITE_HOST_ALIASES = {
    "google.": ["google"],
    "reddit.com": ["reddit"],
    "news.ycombinator.com": ["hn"],
    "github.com": ["github"],
    "linkedin.com": ["linkedin"],
    "youtube.com": ["youtube"],
    "wikipedia.org": ["wikipedia"],
    "x.com": ["x"],
    "twitter.com": ["x", "twitter"],
    "amazon.": ["amazon"],
    "flipkart.com": ["flipkart"],
    "stackoverflow.com": ["stackoverflow"],
    "naukri.com": ["naukri"],
}


class HTTPRequestError(RuntimeError):
    pass


class SelectorRegistry:
    def __init__(self):
        self.entries: Dict[str, Dict[str, Any]] = {}
        self.by_site: Dict[str, List[tuple[str, Dict[str, Any]]]] = {}
        self._load_dir(BUILTIN_SELECTOR_DIR)
        self._load_dir(USER_SELECTOR_DIR)

    def _load_dir(self, directory: str):
        if not os.path.isdir(directory):
            return
        for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
            if os.path.basename(path) == "selector_usage.json":
                continue
            try:
                with open(path) as fh:
                    data = json.load(fh)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for key, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                self.entries[key] = entry
                site = key.split(".", 1)[0]
                self.by_site.setdefault(site, []).append((key, entry))

    def site_keys_for_host(self, host: str) -> List[str]:
        host = (host or "").lower()
        results: List[str] = []
        for token, aliases in SITE_HOST_ALIASES.items():
            if token in host:
                for alias in aliases:
                    if alias not in results:
                        results.append(alias)
        return results

    def _selector_values(self, entry: Dict[str, Any]) -> List[str]:
        selectors: List[str] = []
        primary = entry.get("selector")
        fallback = entry.get("fallback")
        if isinstance(primary, str) and primary.strip():
            selectors.append(primary.strip())
        if isinstance(fallback, str) and fallback.strip():
            selectors.append(fallback.strip())
        return selectors

    def selectors_for_intent(self, host: str, intent: str) -> List[str]:
        sites = self.site_keys_for_host(host)
        candidates: List[str] = []

        preferred_suffixes: List[str]
        if intent == "search_input":
            preferred_suffixes = ["search_box", "search_input", "textarea"]
        elif intent == "search_button":
            preferred_suffixes = ["search_button"]
        elif intent == "first_result":
            preferred_suffixes = [
                "first_result",
                "first_search_result",
                "result_link",
                "title_link",
                "top_post",
            ]
        else:
            preferred_suffixes = []

        for site in sites:
            for key, entry in self.by_site.get(site, []):
                key_tail = key.split(".", 1)[1] if "." in key else key
                tags = entry.get("tags", []) if isinstance(entry.get("tags"), list) else []
                use_entry = False

                if preferred_suffixes and any(key_tail == suffix for suffix in preferred_suffixes):
                    use_entry = True
                elif intent == "search_input" and ("search" in key_tail or ("search" in tags and "query" in tags)):
                    use_entry = True
                elif intent == "first_result" and ("first" in key_tail or "result" in key_tail):
                    use_entry = True

                if use_entry:
                    candidates.extend(self._selector_values(entry))

        deduped: List[str] = []
        seen = set()
        for selector in candidates:
            if selector not in seen:
                seen.add(selector)
                deduped.append(selector)
        return deduped


def post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=body, headers=headers, method="POST")

    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            status = getattr(resp, "status", resp.getcode())
    except urlerror.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise HTTPRequestError(f"HTTP {exc.code}: {error_body[:400]}") from exc
    except urlerror.URLError as exc:
        raise HTTPRequestError(f"Network error: {exc.reason}") from exc

    try:
        data = json.loads(resp_body)
    except json.JSONDecodeError as exc:
        raise HTTPRequestError(f"Invalid JSON response: {exc}") from exc

    if status < 200 or status >= 300:
        raise HTTPRequestError(f"HTTP {status}")

    return data


def compute_rms(data: bytes) -> float:
    count = len(data) // 2
    if count <= 0:
        return 0.0
    shorts = struct.unpack(f"<{count}h", data)
    sum_squares = sum(sample * sample for sample in shorts)
    return math.sqrt(sum_squares / count)


def estimate_ambient_rms(levels: deque) -> float:
    if not levels:
        return 0.0
    ordered = sorted(levels)
    return ordered[len(ordered) // 2]


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```")
    return cleaned.strip()


def truncate(text: str, limit: int = 280) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def normalize_spoken_command(command: str) -> str:
    text = re.sub(r"\s+", " ", command.strip())

    replacements = [
        (
            r"^(right|rite|write)\s+(.+?)\s*$",
            r"type \2",
        ),
        (
            r"^(right|rite|write)\s+(.+?)\s+(on it|in it|there)\.?$",
            r"type \2",
        ),
        (
            r"^(right|rite|write)\s+(.+?)\s+(and search|and search it)\.?$",
            r"type \2 and search",
        ),
        (
            r"^(enter|put)\s+(.+?)\s+(on it|in it|there)\.?$",
            r"type \2",
        ),
    ]

    for pattern, replacement in replacements:
        if re.match(pattern, text, flags=re.IGNORECASE):
            return re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def read_text_file(path: str, default: str = "") -> str:
    try:
        with open(path) as fh:
            return fh.read()
    except Exception:
        return default


def compact_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(value)


def tsv_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " \\n ")


def ensure_tsv_header(path: str, columns: List[str]):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\t".join(columns) + "\n")


def append_tsv_row(path: str, columns: List[str], row: Dict[str, Any]):
    ensure_tsv_header(path, columns)
    values = [tsv_cell(row.get(column, "")) for column in columns]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\t".join(values) + "\n")


class PixelMic:
    def __init__(self, cell_width: int = 2):
        self.matrix = MIC_MATRIX
        self.height = len(self.matrix)
        self.width = len(self.matrix[0])
        self.cell_width = cell_width
        self.target_energy = 0.0
        self.current_energy = 0.0

    def set_energy(self, value: float):
        self.target_energy = max(0.0, min(1.0, value))

    def render_width(self) -> int:
        return self.width * self.cell_width if self.width else 0

    def _color_for(self, px: int, state: str, row_index: int, time_t: float) -> str:
        pulse = 0.5 + (math.sin(time_t * 7.0 + row_index * 0.55) * 0.5)
        if state == "LISTENING" and px == 1 and self.current_energy > 0.45 and pulse > 0.72:
            return MIC_COLORS[2]
        if state == "TRANSCRIBING" and px == 1:
            return MIC_COLORS[2]
        return MIC_COLORS[px]

    def render(self, time_t: float, state: str) -> List[str]:
        idle_energy = 0.10 if state == "STARTUP" else 0.08 if state == "WAITING" else 0.18 if state == "TRANSCRIBING" else self.target_energy
        target = self.target_energy if state in {"WAITING", "LISTENING"} else idle_energy
        ease = 0.55 if target > self.current_energy else 0.18
        self.current_energy += (target - self.current_energy) * ease

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
            elif state == "WAITING":
                wobble = int(round(math.sin(time_t * 1.7 + row_index * 0.4) * 0.15))

            line = [" " * max(0, center_pad + wobble)]
            for px in row:
                if px == 0:
                    line.append(" " * self.cell_width)
                else:
                    line.extend([self._color_for(px, state, row_index, time_t), "█" * self.cell_width, C.RESET])
            lines.append("".join(line))

        return lines


class VoiceUI:
    def __init__(self):
        self.mic = PixelMic(cell_width=2)
        self.running = False
        self.frame_thread: Optional[threading.Thread] = None
        self.state = "STARTUP"
        self.listen_started_at: Optional[float] = None

    def set_state(self, state: str):
        self.state = state
        if state != "LISTENING":
            self.listen_started_at = None
        if state in {"WAITING", "STARTUP"}:
            self.mic.set_energy(0.0)

    def begin_listening(self):
        self.state = "LISTENING"
        self.listen_started_at = time.time()

    def feed_audio(self, data: bytes, ambient_rms: float = 0.0, boost: float = 1.0):
        rms = compute_rms(data)
        floor = max(110.0, ambient_rms * 1.15)
        span = max(450.0, ambient_rms * 4.5)
        norm = min(max((rms - floor) / span, 0.0), 1.0)
        self.mic.set_energy(norm * boost)

    def start_animation(self):
        if self.running:
            return
        self.running = True
        self.frame_thread = threading.Thread(target=self._animate_loop, daemon=True)
        self.frame_thread.start()

    def clear_animation_area(self):
        lines = self.mic.height + 1
        sys.stdout.write(f"\033[{lines}A")
        for _ in range(lines):
            sys.stdout.write("\033[2K\r\n")
        sys.stdout.write(f"\033[{lines}A")
        sys.stdout.flush()

    def stop_animation(self, clear_frame: bool = False):
        if not self.running:
            if clear_frame:
                self.clear_animation_area()
            return
        self.running = False
        if self.frame_thread:
            self.frame_thread.join()
            self.frame_thread = None
        if clear_frame:
            self.clear_animation_area()

    def _header(self, time_t: float) -> str:
        if self.state == "WAITING":
            return f"  {C.BCYAN}● READY{C.RESET} (Say your next command. Say 'discard browser' to exit.)"
        if self.state == "LISTENING":
            elapsed = 0.0 if not self.listen_started_at else time.time() - self.listen_started_at
            return f"  {C.BCYAN}● LISTENING ({elapsed:.1f}s){C.RESET} (Keep speaking...)"
        if self.state == "TRANSCRIBING":
            return f"  {C.BMAGENTA}○ TRANSCRIBING{C.RESET} (Computing...)"
        if self.state == "EXECUTING":
            return f"  {C.YELLOW}◆ EXECUTING{C.RESET} (Working in browser...)"
        return f"  {C.WHITE}STARTUP{C.RESET}"

    def _animate_loop(self):
        sys.stdout.write("\n" * (self.mic.height + 1))
        start_time = time.time()

        while self.running:
            time_t = time.time() - start_time
            frame_lines = self.mic.render(time_t, self.state)

            sys.stdout.write(f"\033[{self.mic.height + 1}A")
            sys.stdout.write(f"\033[2K\r{self._header(time_t)}\n")
            for line in frame_lines:
                sys.stdout.write(f"\033[2K\r{line}\n")
            sys.stdout.flush()
            time.sleep(UI_FRAME_INTERVAL)


class VoiceBrowserSession:
    def __init__(self):
        self.client = WEBGhostingClient(show_server_logs=False)
        self.history: List[Dict[str, Any]] = []
        self.last_error: Optional[str] = None
        self.selector_registry = SelectorRegistry()
        self.runtime_selector_cache: Dict[str, str] = {}
        self.program_policy = read_text_file(SARVAM_PROGRAM_PATH).strip()
        self.results_tsv_path = DEFAULT_RESULTS_TSV_PATH
        self.session_id = datetime.now(timezone.utc).strftime("sarvam-%Y%m%dT%H%M%SZ")
        self.turn_index = 0

        try:
            ensure_tsv_header(self.results_tsv_path, RESULTS_COLUMNS)
        except Exception:
            pass

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass

    def _remember(self, user_command: str, reply: str, steps: Optional[List[Dict[str, Any]]] = None):
        self.history.append({
            "user": user_command,
            "assistant": truncate(reply, 240),
            "steps": steps or [],
        })
        if len(self.history) > MAX_HISTORY_ITEMS:
            self.history = self.history[-MAX_HISTORY_ITEMS:]

    def _new_turn_trace(self, raw_command: str) -> Dict[str, Any]:
        self.turn_index += 1
        return {
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "turn_index": self.turn_index,
            "raw_command": raw_command,
            "normalized_command": "",
            "reframed_command": "",
            "plan_source": "",
            "plan_mode": "",
            "steps_json": "[]",
            "selector_path": "",
            "selector_used": "",
            "llm_used": False,
            "reframer_used": False,
            "validation_status": "",
            "validation_reason": "",
            "latency_ms": 0,
            "active_url_before": "",
            "active_url_after": "",
            "active_title_after": "",
            "error": "",
            "assistant_reply": "",
        }

    def _log_turn(self, trace: Dict[str, Any]):
        try:
            append_tsv_row(self.results_tsv_path, RESULTS_COLUMNS, trace)
        except Exception:
            pass

    def _call_tool(self, tool: str, args: Dict[str, Any]) -> str:
        result = self.client.call(tool, args)
        if result is None:
            raise RuntimeError(f"Tool '{tool}' returned no response.")
        if isinstance(result, str) and result.startswith("ERROR:"):
            raise RuntimeError(result)
        return result

    def _call_tool_json(self, tool: str, args: Dict[str, Any]) -> Optional[Any]:
        try:
            raw = self._call_tool(tool, args)
            return json.loads(raw)
        except Exception:
            return None

    def snapshot(self) -> Dict[str, Any]:
        return {
            "status": self._call_tool_json("get_status", {}) or {},
            "page_context": self._call_tool_json("get_page_context", {}) or {},
            "tabs": self._call_tool_json("list_tabs", {}) or [],
        }

    def _status_snapshot(self) -> Dict[str, Any]:
        return {
            "status": self._call_tool_json("get_status", {}) or {},
            "page_context": {},
            "tabs": [],
        }

    def _enrich_snapshot(
        self,
        snapshot: Dict[str, Any],
        *,
        include_page_context: bool = False,
        include_tabs: bool = False,
    ) -> Dict[str, Any]:
        if include_page_context and not snapshot.get("page_context"):
            snapshot["page_context"] = self._call_tool_json("get_page_context", {}) or {}
        if include_tabs and not snapshot.get("tabs"):
            snapshot["tabs"] = self._call_tool_json("list_tabs", {}) or []
        return snapshot

    def _reframe_command(self, command: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        page_context = snapshot.get("page_context") or {}
        page_hint = json.dumps(page_context, ensure_ascii=False) if page_context else ""

        try:
            reframed = self._call_tool_json(
                "reframe_user_prompt",
                {"prompt": command, "page_context": page_hint},
            )
            if isinstance(reframed, dict):
                clear_task = str(reframed.get("clear_task", "")).strip()
                if clear_task:
                    reframed["clear_task"] = clear_task
                    return reframed
        except Exception:
            pass

        return {
            "clear_task": command,
            "intent": "",
            "required_steps": [],
            "target_element": "",
            "target_url": "",
            "language": "unknown",
            "confidence": 0.0,
            "was_reframed": False,
        }

    def _active_tab_index(self, snapshot: Dict[str, Any]) -> Optional[int]:
        status = snapshot.get("status") or {}
        tabs = snapshot.get("tabs") or []
        active_url = status.get("active_tab_url")
        active_title = status.get("active_tab_title")
        for tab in tabs:
            if tab.get("url") == active_url and tab.get("title") == active_title:
                return tab.get("index")
        for tab in tabs:
            if tab.get("url") == active_url:
                return tab.get("index")
        return None

    def _current_url(self, snapshot: Dict[str, Any]) -> str:
        status = snapshot.get("status") or {}
        page = snapshot.get("page_context") or {}
        return str(status.get("active_tab_url") or page.get("url") or "")

    def _is_blank_page(self, snapshot: Dict[str, Any]) -> bool:
        current_url = self._current_url(snapshot).strip().lower()
        return current_url in {"", "about:blank"}

    def _command_mentions_tabs(self, command: str) -> bool:
        normalized = re.sub(r"\s+", " ", command.lower()).strip()
        return "tab" in normalized

    def _selector_cache_key(self, snapshot: Dict[str, Any], intent: str) -> str:
        current_url = self._current_url(snapshot)
        try:
            host = (urlparse(current_url).hostname or "").lower()
        except Exception:
            host = "unknown"
        return f"{host}|{intent}"

    def _remember_working_selector(self, snapshot: Dict[str, Any], intent: str, selector: str):
        if not selector:
            return
        self.runtime_selector_cache[self._selector_cache_key(snapshot, intent)] = selector

    def _snapshot_title(self, snapshot: Dict[str, Any]) -> str:
        status = snapshot.get("status") or {}
        page = snapshot.get("page_context") or {}
        return str(status.get("active_tab_title") or page.get("title") or "")

    def _cached_selector_candidates(self, snapshot: Dict[str, Any], intent: str) -> List[str]:
        cached = self.runtime_selector_cache.get(self._selector_cache_key(snapshot, intent))
        return [cached] if cached else []

    def _supports_inline_search(self, snapshot: Dict[str, Any]) -> bool:
        page = snapshot.get("page_context") or {}
        if page.get("has_search"):
            return True

        current_url = self._current_url(snapshot)
        try:
            host = (urlparse(current_url).hostname or "").lower()
        except Exception:
            host = ""

        searchable_hosts = (
            "google.",
            "reddit.com",
            "youtube.com",
            "linkedin.com",
            "x.com",
            "twitter.com",
            "wikipedia.org",
            "amazon.",
            "flipkart.com",
        )
        return any(token in host for token in searchable_hosts)

    def _typing_selector_candidates(self, snapshot: Dict[str, Any], prefer_search: bool = False) -> List[str]:
        page = snapshot.get("page_context") or {}
        current_url = self._current_url(snapshot)
        host = ""
        try:
            host = (urlparse(current_url).hostname or "").lower()
        except Exception:
            host = ""

        intent = "search_input" if (prefer_search or page.get("has_search") or self._supports_inline_search(snapshot)) else "input_field"
        candidates: List[str] = []
        candidates.extend(self._cached_selector_candidates(snapshot, intent))
        if intent == "search_input":
            candidates.extend(self.selector_registry.selectors_for_intent(host, "search_input"))

        if "google." in host:
            candidates.extend([
                "textarea#APjFqb",
                "textarea[name='q']",
                "input[name='q']",
            ])
        elif "reddit.com" in host:
            candidates.extend([
                "input[name='q']",
                "input[placeholder*='Search']",
            ])
        elif "linkedin.com" in host:
            candidates.extend([
                "input[placeholder*='Search']",
                "input[aria-label*='Search']",
            ])
        elif "x.com" in host or "twitter.com" in host:
            candidates.extend([
                "input[data-testid='SearchBox_Search_Input']",
            ])
        elif "youtube.com" in host:
            candidates.extend([
                "input#search",
                "input[name='search_query']",
            ])

        if prefer_search or page.get("has_search"):
            candidates.extend([
                "input[type='search']",
                "input[role='searchbox']",
                "textarea[aria-label*='Search' i]",
                "input[aria-label*='Search' i]",
                "input[placeholder*='Search' i]",
            ])

        candidates.extend([
            "textarea:focus",
            "input:focus",
            "[contenteditable='true']:focus",
            "textarea",
            "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='checkbox']):not([type='radio'])",
            "[contenteditable='true']",
        ])

        seen = set()
        ordered: List[str] = []
        for selector in candidates:
            if selector not in seen:
                seen.add(selector)
                ordered.append(selector)
        return ordered

    def _typing_args(self, snapshot: Dict[str, Any], text: str, prefer_search: bool = False) -> Dict[str, Any]:
        page = snapshot.get("page_context") or {}
        intent = "search_input" if (prefer_search or page.get("has_search") or self._supports_inline_search(snapshot)) else "input_field"
        prompt = "the main search box" if prefer_search else "the page search box" if intent == "search_input" else "the active input field"
        return {
            "prompt": prompt,
            "text": text,
            "_selector_intent": intent,
            "_selector_candidates": self._typing_selector_candidates(snapshot, prefer_search=prefer_search),
        }

    def _click_selector_candidates(self, snapshot: Dict[str, Any], intent: str) -> List[str]:
        current_url = self._current_url(snapshot)
        host = ""
        try:
            host = (urlparse(current_url).hostname or "").lower()
        except Exception:
            host = ""

        candidates: List[str] = []
        candidates.extend(self._cached_selector_candidates(snapshot, intent))
        candidates.extend(self.selector_registry.selectors_for_intent(host, intent))

        deduped: List[str] = []
        seen = set()
        for selector in candidates:
            if selector not in seen:
                seen.add(selector)
                deduped.append(selector)
        return deduped

    def _click_args(self, snapshot: Dict[str, Any], prompt: str, intent: Optional[str] = None) -> Dict[str, Any]:
        args: Dict[str, Any] = {"prompt": prompt}
        if intent:
            args["_selector_intent"] = intent
            args["_selector_candidates"] = self._click_selector_candidates(snapshot, intent)
        return args

    def _fast_fill_with_js(self, selector_candidates: List[str], text: str) -> Optional[Dict[str, Any]]:
        if not selector_candidates:
            return None

        script = f"""
(() => {{
  const selectors = {json.dumps(selector_candidates)};
  const text = {json.dumps(text)};
  const isVisible = (el) => {{
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 &&
      rect.height > 0 &&
      style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      !el.disabled;
  }};

  for (const sel of selectors) {{
    const el = document.querySelector(sel);
    if (!isVisible(el)) continue;
    try {{
      el.focus();
      if (typeof el.select === 'function') el.select();

      if ('value' in el) {{
        el.value = '';
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.value = text;
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
      }} else if (el.isContentEditable) {{
        el.textContent = text;
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
      }} else {{
        continue;
      }}

      return JSON.stringify({{ ok: true, selector: sel, tag: el.tagName.toLowerCase() }});
    }} catch (err) {{}}
  }}

  return JSON.stringify({{ ok: false }});
}})()
""".strip()

        try:
            raw = self._call_tool("execute_js", {"script": script})
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("ok"):
                return parsed
        except Exception:
            return None
        return None

    # Ordinal word → number mapping
    _ORDINAL_MAP = {
        "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
        "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "sixth": 6, "6th": 6,
        "seventh": 7, "7th": 7, "eighth": 8, "8th": 8, "ninth": 9, "9th": 9,
        "tenth": 10, "10th": 10, "top": 1,
    }

    # Selector templates for lists of target items, keyed by host token → target type → CSS
    _NTH_LIST_SELECTORS: Dict[str, Dict[str, str]] = {
        "news.ycombinator.com": {
            "article": "tr.athing span.titleline > a",
            "story": "tr.athing span.titleline > a",
            "post": "tr.athing span.titleline > a",
            "result": "tr.athing span.titleline > a",
            "link": "tr.athing span.titleline > a",
            "item": "tr.athing span.titleline > a",
            "comment": "tr.athing + tr .subtext a[href^='item?id=']:last-child",
        },
        "reddit.com": {
            "post": "article a[data-click-id='body']",
            "article": "article a[data-click-id='body']",
            "result": "article a[data-click-id='body']",
            "comment": "article a[data-click-id='comments']",
        },
        "github.com": {
            "result": "li.repo-list-item a",
            "repo": "li.repo-list-item a",
        },
    }

    def _click_nth_with_js(self, snapshot: Dict[str, Any], n: int, target_type: str) -> Optional[Dict[str, Any]]:
        """Click the Nth article/comment/post using cached selectors via JS."""
        current_url = self._current_url(snapshot)
        try:
            host = (urlparse(current_url).hostname or "").lower()
        except Exception:
            return None

        # Find matching host
        site_selectors = None
        for host_key, selectors in self._NTH_LIST_SELECTORS.items():
            if host_key in host:
                site_selectors = selectors
                break

        if not site_selectors:
            return None

        css_selector = site_selectors.get(target_type)
        if not css_selector:
            return None

        script = f"""
(() => {{
  const elements = document.querySelectorAll({json.dumps(css_selector)});
  const el = elements[{n} - 1];
  if (!el) return JSON.stringify({{ ok: false, reason: "not found" }});
  const text = el.innerText || el.textContent || "";
  const href = el.href || "";
  el.click();
  return JSON.stringify({{ ok: true, text: text.trim().substring(0, 120), href: href, selector: {json.dumps(css_selector)} }});
}})()
""".strip()

        try:
            raw = self._call_tool("execute_js", {"script": script})
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("ok"):
                return parsed
        except Exception:
            return None
        return None

    # Sites where JS fast-fill triggers bot detection — use stealth MCP type instead
    _BOT_DETECTION_HOSTS = (
        "google.", "reddit.com", "linkedin.com", "x.com", "twitter.com",
        "amazon.", "flipkart.com", "facebook.com", "instagram.com",
    )

    def _is_bot_protected_site(self, snapshot: Dict[str, Any]) -> bool:
        """Check if the current site is known to aggressively detect bots."""
        current_url = self._current_url(snapshot)
        try:
            host = (urlparse(current_url).hostname or "").lower()
        except Exception:
            return False
        return any(token in host for token in self._BOT_DETECTION_HOSTS)

    def _execute_type_step(self, args: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
        intent = args.pop("_selector_intent", "input_field")
        selector_candidates = args.pop("_selector_candidates", [])
        prompt = args.get("prompt", "")
        text = args.get("text", "")

        # Try JS fast-fill first (instant, uses our cached selectors)
        fast_fill = self._fast_fill_with_js(selector_candidates, text)
        if fast_fill:
            selector = fast_fill.get("selector", "the active input")
            self._remember_working_selector(snapshot, intent, selector)
            return {
                "result": f"Typed '{text}' into {selector}",
                "selector_used": selector,
                "selector_path": "selector_fast_fill",
            }

        # Fallback to MCP stealth type tool
        try:
            return {
                "result": self._call_tool("type", {"prompt": prompt, "text": text}),
                "selector_used": "",
                "selector_path": "mcp_type",
            }
        except Exception:
            raise

    def _execute_click_step(self, args: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
        intent = args.pop("_selector_intent", "")
        selector_candidates = args.pop("_selector_candidates", [])
        prompt = args.get("prompt", "")
        last_exc: Optional[Exception] = None

        for selector in selector_candidates:
            try:
                result = self._call_tool("click", {"prompt": selector})
                if intent:
                    self._remember_working_selector(snapshot, intent, selector)
                return {
                    "result": result,
                    "selector_used": selector,
                    "selector_path": "selector_click",
                }
            except Exception as exc:
                last_exc = exc

        try:
            return {
                "result": self._call_tool("click", {"prompt": prompt}),
                "selector_used": "",
                "selector_path": "mcp_click",
            }
        except Exception:
            if last_exc is not None:
                raise last_exc
            raise

    def _prepare_step_for_execution(self, step: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
        tool = step.get("tool")
        args = dict(step.get("args", {}))

        if tool == "type" and "text" in args and "_selector_candidates" not in args:
            prompt = str(args.get("prompt", "")).lower()
            text = str(args.get("text", ""))
            prefer_search = bool(
                "search" in prompt
                or "query" in prompt
                or self._supports_inline_search(snapshot)
            )
            args = self._typing_args(snapshot, text, prefer_search=prefer_search)
        elif tool == "click" and "_selector_candidates" not in args:
            prompt = str(args.get("prompt", ""))
            lower_prompt = prompt.lower()
            first_item_pattern = re.search(r"(first|1st|top)\s+(result|article|story|post|link|item)", lower_prompt)
            if first_item_pattern or lower_prompt in {"first", "1st"}:
                args = self._click_args(snapshot, prompt or "the first result", intent="first_result")

        return {"tool": tool, "args": args}

    def _local_intent(self, command: str, snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        normalized = re.sub(r"\s+", " ", command.lower()).strip()

        end_markers = (
            "discard browser",
            "close browser",
            "close the browser",
            "end session",
            "stop session",
            "quit",
            "exit",
            "band kar do browser",
            "browser band kar do",
            "browser close kar do",
        )
        if any(marker in normalized for marker in end_markers):
            return {"mode": "end", "message": "Closing the browser session now.", "steps": []}

        browser_launch_markers = (
            "open browser",
            "open the browser",
            "start browser",
            "start the browser",
            "launch browser",
            "launch the browser",
            "open chrome",
            "start chrome",
            "launch chrome",
            "browser kholo",
            "browser open karo",
        )
        if any(marker in normalized for marker in browser_launch_markers):
            status = snapshot.get("status") or {}
            if status.get("initialized"):
                title = status.get("active_tab_title") or "the current tab"
                url = status.get("active_tab_url") or "about:blank"
                return {
                    "mode": "ask",
                    "message": f"Browser is already open on {title}. URL: {url}. What should I do next?",
                    "steps": [],
                }
            return {
                "mode": "execute",
                "message": "Opening the browser on Google now.",
                "steps": [{"tool": "browse", "args": {"url": "https://www.google.com"}}],
            }

        if normalized in {"status", "where am i", "what page is this", "current page", "what's open"}:
            status = snapshot.get("status") or {}
            page = snapshot.get("page_context") or {}
            title = status.get("active_tab_title") or page.get("title") or "the current tab"
            url = status.get("active_tab_url") or page.get("url") or "about:blank"
            return {
                "mode": "ask",
                "message": f"You are on {title}. URL: {url}. Browser is still open. What next?",
                "steps": [],
            }

        # Only match pure "open/new tab" commands, not "open X in new tab"
        open_in_new_tab_match = re.search(r"(?:open|go to|navigate to|come back to|go back to|return to|switch to)\s+(.+?)\s+in\s+(?:a\s+)?new\s+tab", normalized)
        if open_in_new_tab_match:
            site_name = open_in_new_tab_match.group(1).strip()
            target_url = SITE_ALIASES.get(site_name)
            if target_url:
                return {
                    "mode": "execute",
                    "message": f"Opening {site_name} in a new tab.",
                    "steps": [
                        {"tool": "open_tab", "args": {}},
                        {"tool": "browse", "args": {"url": target_url}},
                    ],
                }
            # If not a known alias, try as a URL or fall through to LLM

        if re.fullmatch(r"(open|new)\s+(a\s+)?new\s+tab|open\s+tab", normalized):
            return {
                "mode": "execute",
                "message": "Opening a new tab.",
                "steps": [{"tool": "open_tab", "args": {}}],
            }

        match = re.search(r"(switch|go) to tab (\d+)", normalized)
        if match:
            tab_num = max(1, int(match.group(2)))
            return {
                "mode": "execute",
                "message": f"Switching to tab {tab_num}.",
                "steps": [{"tool": "switch_tab", "args": {"index": tab_num - 1}}],
            }

        match = re.search(r"close tab (\d+)", normalized)
        if match:
            tab_num = max(1, int(match.group(1)))
            return {
                "mode": "execute",
                "message": f"Closing tab {tab_num}.",
                "steps": [{"tool": "close_tab", "args": {"index": tab_num - 1}}],
            }

        if "close current tab" in normalized or normalized == "close tab":
            current_index = self._active_tab_index(snapshot)
            if current_index is None:
                return {"mode": "ask", "message": "I cannot tell which tab is active right now. Say 'list tabs' or 'close tab 2'.", "steps": []}
            return {
                "mode": "execute",
                "message": "Closing the current tab.",
                "steps": [{"tool": "close_tab", "args": {"index": current_index}}],
            }

        if normalized in {"go back", "back"}:
            return {"mode": "execute", "message": "Going back.", "steps": [{"tool": "go_back", "args": {}}]}

        if normalized in {"go forward", "forward"}:
            return {"mode": "execute", "message": "Going forward.", "steps": [{"tool": "go_forward", "args": {}}]}

        if "scroll to bottom" in normalized or "bottom of page" in normalized:
            return {"mode": "execute", "message": "Scrolling to the bottom.", "steps": [{"tool": "scroll_to_bottom", "args": {}}]}

        if "scroll down" in normalized:
            return {
                "mode": "execute",
                "message": "Scrolling down.",
                "steps": [{"tool": "scroll", "args": {"direction": "down", "amount": 900}}],
            }

        if "scroll up" in normalized:
            return {
                "mode": "execute",
                "message": "Scrolling up.",
                "steps": [{"tool": "scroll", "args": {"direction": "up", "amount": 700}}],
            }

        if normalized in {"list tabs", "show tabs"}:
            tabs = snapshot.get("tabs") or []
            if not tabs:
                return {"mode": "ask", "message": "I do not see any tabs yet. What should I open?", "steps": []}
            tab_lines = [f"Tab {tab.get('index', 0) + 1}: {tab.get('title') or '(untitled)'} - {tab.get('url')}" for tab in tabs]
            return {"mode": "ask", "message": "\n".join(tab_lines), "steps": []}

        return None

    def _fallback_plan(self, command: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        normalized = re.sub(r"\s+", " ", command.lower()).strip()
        page = snapshot.get("page_context") or {}

        url_match = re.search(r"https?://\S+", command)
        if url_match:
            return {
                "mode": "execute",
                "message": f"Opening {url_match.group(0)}.",
                "steps": [{"tool": "browse", "args": {"url": url_match.group(0)}}],
            }

        for alias, url in SITE_ALIASES.items():
            if re.search(rf"\b(open|go to|navigate to|come back to|go back to|return to|switch to)\s+{re.escape(alias)}\b", normalized):
                return {
                    "mode": "execute",
                    "message": f"Opening {alias}.",
                    "steps": [{"tool": "browse", "args": {"url": url}}],
                }

        type_search = re.search(r"type (.+?) and search", normalized)
        if type_search:
            query = type_search.group(1).strip(" .")
            if self._is_blank_page(snapshot):
                return {
                    "mode": "execute",
                    "message": f"Opening Google and searching for {query}.",
                    "steps": [{"tool": "browse", "args": {"url": f"https://www.google.com/search?q={quote(query)}"}}],
                }
            return {
                "mode": "execute",
                "message": f"Typing {query} and submitting the search.",
                "steps": [
                    {"tool": "type", "args": self._typing_args(snapshot, query, prefer_search=True)},
                    {"tool": "press_key", "args": {"key": "Enter"}},
                ],
            }

        write_search = re.search(r"(write|enter|put)\s+(.+?)\s+(and\s+)?search", normalized)
        if write_search:
            query = write_search.group(2).strip(" .")
            if self._is_blank_page(snapshot):
                return {
                    "mode": "execute",
                    "message": f"Opening Google and searching for {query}.",
                    "steps": [{"tool": "browse", "args": {"url": f"https://www.google.com/search?q={quote(query)}"}}],
                }
            return {
                "mode": "execute",
                "message": f"Typing {query} and submitting the search.",
                "steps": [
                    {"tool": "type", "args": self._typing_args(snapshot, query, prefer_search=True)},
                    {"tool": "press_key", "args": {"key": "Enter"}},
                ],
            }

        search_match = re.search(r"(search|find)\s+(for\s+)?(.+)", normalized)
        if search_match:
            query = search_match.group(3).strip(" .")
            if self._supports_inline_search(snapshot):
                return {
                    "mode": "execute",
                    "message": f"Searching for {query}.",
                    "steps": [
                        {"tool": "type", "args": self._typing_args(snapshot, query, prefer_search=True)},
                        {"tool": "press_key", "args": {"key": "Enter"}},
                    ],
                }
            return {
                "mode": "execute",
                "message": f"Searching Google for {query}.",
                "steps": [{"tool": "browse", "args": {"url": f"https://www.google.com/search?q={quote(query)}"}}],
            }

        click_match = re.search(r"click (.+)", normalized)

        # Match "open/click [the] Nth article/story/comment/post/result/link/item"
        nth_match = re.search(
            r"(click|open)\s+(the\s+)?(\w+)\s+(result|article|story|post|link|item|comment)",
            normalized,
        )
        if nth_match:
            ordinal_word = nth_match.group(3)
            target_type = nth_match.group(4)
            n = self._ORDINAL_MAP.get(ordinal_word)

            # Also try bare digits: "open 3 article" or "click 5 story"
            if n is None and ordinal_word.isdigit():
                n = int(ordinal_word)

            if n is not None and 1 <= n <= 30:
                # Try instant JS click using cached selectors
                js_result = self._click_nth_with_js(snapshot, n, target_type)
                if js_result:
                    title = js_result.get("text", f"item #{n}")
                    return {
                        "mode": "execute",
                        "message": f"Opened {ordinal_word} {target_type}: {title}",
                        "steps": [],  # Already executed via JS
                        "_already_executed": True,
                        "_js_result": js_result,
                    }

                # Fallback: use MCP click with selector candidates
                if n == 1:
                    first_result_candidates = self._click_selector_candidates(snapshot, "first_result")
                    if first_result_candidates:
                        return {
                            "mode": "execute",
                            "message": f"Opening the first {target_type}.",
                            "steps": [{"tool": "click", "args": self._click_args(snapshot, f"the first {target_type}", intent="first_result")}],
                        }

                # Generic MCP click fallback
                return {
                    "mode": "execute",
                    "message": f"Clicking the {ordinal_word} {target_type}.",
                    "steps": [{"tool": "click", "args": {"prompt": f"the {ordinal_word} {target_type}"}}],
                }

        if click_match:
            target = click_match.group(1).strip(" .")
            return {
                "mode": "execute",
                "message": f"Trying to click {target}.",
                "steps": [{"tool": "click", "args": {"prompt": target}}],
            }

        type_match = re.search(r"type (.+)", normalized)
        if type_match:
            text = type_match.group(1).strip(" .")
            if self._is_blank_page(snapshot):
                return {
                    "mode": "execute",
                    "message": f"Opening Google and searching for {text}.",
                    "steps": [{"tool": "browse", "args": {"url": f"https://www.google.com/search?q={quote(text)}"}}],
                }
            # On a search page, auto-submit after typing
            if self._supports_inline_search(snapshot):
                return {
                    "mode": "execute",
                    "message": f"Typing {text} and searching.",
                    "steps": [
                        {"tool": "type", "args": self._typing_args(snapshot, text, prefer_search=True)},
                        {"tool": "press_key", "args": {"key": "Enter"}},
                    ],
                }
            return {
                "mode": "execute",
                "message": f"Typing {text}.",
                "steps": [{"tool": "type", "args": self._typing_args(snapshot, text)}],
            }

        write_match = re.search(r"(write|enter|put)\s+(.+)", normalized)
        if write_match:
            text = write_match.group(2).strip(" .")
            if self._is_blank_page(snapshot):
                return {
                    "mode": "execute",
                    "message": f"Opening Google and searching for {text}.",
                    "steps": [{"tool": "browse", "args": {"url": f"https://www.google.com/search?q={quote(text)}"}}],
                }
            return {
                "mode": "execute",
                "message": f"Typing {text}.",
                "steps": [{"tool": "type", "args": self._typing_args(snapshot, text)}],
            }

        on_it_match = re.search(r"(type|write|right|rite|enter|put)\s+(.+?)\s+(on it|in it|there)$", normalized)
        if on_it_match:
            text = on_it_match.group(2).strip(" .")
            if self._is_blank_page(snapshot):
                return {
                    "mode": "execute",
                    "message": f"Opening Google and searching for {text}.",
                    "steps": [{"tool": "browse", "args": {"url": f"https://www.google.com/search?q={quote(text)}"}}],
                }
            return {
                "mode": "execute",
                "message": f"Typing {text}.",
                "steps": [{"tool": "type", "args": self._typing_args(snapshot, text)}],
            }

        return {
            "mode": "ask",
            "message": "I am not fully sure what you want on this page. Tell me one direct action, like 'open google', 'click the first result', 'type Hacker News and search', or 'discard browser'.",
            "steps": [],
        }

    def _plan_with_llm(self, command: str, snapshot: Dict[str, Any], reframed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        api_key = os.environ.get("AI_API_KEY")
        base_url = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
        model = os.environ.get("AI_MODEL", "gpt-4o")

        if not api_key:
            return self._fallback_plan(command, snapshot)

        planner_system = """You are WEBGhosting's conversational browser planner.

Turn one spoken browser command into a very small JSON plan for an already-running browser session.
The browser is already open and must stay open unless the user explicitly wants to end the session.

Return ONLY valid JSON with this exact shape:
{
  "mode": "execute" | "ask" | "end",
  "message": "Short natural reply for the user",
  "steps": [
    {"tool": "browse", "args": {"url": "https://www.google.com"}}
  ]
}

Allowed tools:
- browse {url}
- click {prompt}
- type {prompt, text}
- press_key {key}
- open_tab {}
- close_tab {index}
- switch_tab {index}
- go_back {}
- go_forward {}
- scroll {direction, amount}
- scroll_to_bottom {}
- wait_for_load_state {state}
- wait_for_selector {selector, state}
- get_status {}
- get_page_context {}
- list_tabs {}
- extract {schema, instruction?, selector?}

Rules:
- Never use run_task, run_recipe, or list_recipes.
- Prefer 1 to 3 steps.
- Use the current page context and recent history to resolve references like "search it", "click the first one", or "type Hacker News and search it".
- If the request is ambiguous or the page context is not enough, use mode "ask" with one short clarifying question.
- If the user wants to end the conversation or close/discard the browser, use mode "end".
- For search, prefer type into a search box and then press Enter.
- For extraction, keep the schema small and practical.
- Keep message short and helpful.
- Output JSON only."""

        if self.program_policy:
            planner_system = f"{planner_system}\n\nFollow this operating policy:\n{self.program_policy}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": planner_system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_command": command,
                            "reframed_command": (reframed or {}).get("clear_task", command),
                            "reframe_metadata": reframed or {},
                            "current_status": snapshot.get("status"),
                            "page_context": snapshot.get("page_context"),
                            "tabs": snapshot.get("tabs"),
                            "recent_history": self.history[-MAX_HISTORY_ITEMS:],
                            "last_error": self.last_error,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 700,
        }

        try:
            response = post_json(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                payload=payload,
                timeout=PLANNER_TIMEOUT,
            )
            content = response["choices"][0]["message"]["content"]
            plan = json.loads(strip_code_fences(content))
            return self._validate_plan(plan)
        except Exception:
            return self._fallback_plan(command, snapshot)

    def _validate_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(plan, dict):
            raise ValueError("Planner response was not an object.")

        mode = plan.get("mode", "ask")
        message = str(plan.get("message", "")).strip() or "What do you want to do next?"
        raw_steps = plan.get("steps", [])

        if mode not in {"execute", "ask", "end"}:
            mode = "ask"

        steps: List[Dict[str, Any]] = []
        if isinstance(raw_steps, list):
            for step in raw_steps[:4]:
                if not isinstance(step, dict):
                    continue
                tool = step.get("tool")
                args = step.get("args", {})
                if tool not in ALLOWED_TOOLS or not isinstance(args, dict):
                    continue
                steps.append({"tool": tool, "args": args})

        if mode == "execute" and not steps and not plan.get("_already_executed"):
            mode = "ask"
            message = "I need a little more guidance for that command. Tell me the next action more directly."

        validated_plan = {"mode": mode, "message": message, "steps": steps}
        if plan.get("_already_executed"):
            validated_plan["_already_executed"] = True
            if "_js_result" in plan:
                validated_plan["_js_result"] = plan["_js_result"]

        return validated_plan

    def _auto_wait_if_needed(self, tool: str):
        if tool not in AUTO_WAIT_TOOLS:
            return
        try:
            self._call_tool("wait_for_load_state", {"state": "domcontentloaded"})
        except Exception:
            pass

    def _format_follow_up(self, snapshot: Dict[str, Any]) -> str:
        status = snapshot.get("status") or {}
        title = status.get("active_tab_title") or "the current page"
        url = status.get("active_tab_url") or ""
        if url:
            return f"Browser is still open on {title}. URL: {url}. What next?"
        return f"Browser is still open on {title}. What next?"

    def _print_reply(self, title: str, lines: List[str], color: str):
        panel(title, lines, color=color)

    def _validate_execution(
        self,
        plan: Dict[str, Any],
        snapshot_before: Dict[str, Any],
        snapshot_after: Dict[str, Any],
        results: List[Dict[str, Any]],
        error: Optional[Exception] = None,
    ) -> Dict[str, str]:
        if error is not None:
            return {"status": "crash", "reason": truncate(str(error), 260)}

        mode = plan.get("mode", "ask")
        if mode == "ask":
            return {"status": "recover", "reason": "Asked the user for clarification."}
        if mode == "end":
            return {"status": "keep", "reason": "Session ended on user request."}

        steps = plan.get("steps") or []
        if not steps and not plan.get("_already_executed"):
            return {"status": "discard", "reason": "Planner returned no executable steps."}
        if plan.get("_already_executed"):
            return {"status": "keep", "reason": "Executed via JS click on cached selector."}

        before_url = self._current_url(snapshot_before)
        after_url = self._current_url(snapshot_after)
        before_title = self._snapshot_title(snapshot_before)
        after_title = self._snapshot_title(snapshot_after)
        first_tool = steps[0].get("tool", "")
        selector_used = any(item.get("selector_used") for item in results)
        extract_result = next(
            (str(item.get("result", "")).strip() for item in results if item.get("tool") == "extract"),
            "",
        )

        if first_tool == "browse":
            if after_url and after_url != "about:blank":
                return {"status": "keep", "reason": "Navigation completed successfully."}
            return {"status": "recover", "reason": "Navigation finished but the active URL is still blank."}

        if first_tool in {"click", "press_key", "go_back", "go_forward", "open_tab", "close_tab", "switch_tab"}:
            if after_url != before_url or after_title != before_title:
                return {"status": "keep", "reason": "Page state changed after the interaction."}
            return {"status": "keep", "reason": "Interaction completed without tool errors."}

        if first_tool == "type":
            if len(steps) >= 2 and steps[1].get("tool") == "press_key" and after_url == before_url:
                return {"status": "recover", "reason": "Typed and submitted, but the page did not navigate."}
            if selector_used:
                return {"status": "keep", "reason": "Typed using the selector fast path."}
            return {"status": "keep", "reason": "Typed without any tool errors."}

        if first_tool == "extract":
            if extract_result:
                return {"status": "keep", "reason": "Extraction returned data."}
            return {"status": "recover", "reason": "Extraction completed but returned empty output."}

        return {"status": "keep", "reason": "Execution completed without tool errors."}

    def handle_command(self, command: str, ui: Optional[VoiceUI] = None) -> bool:
        def flush_ui():
            if ui is not None:
                ui.stop_animation(clear_frame=True)

        turn_started_at = time.time()
        trace = self._new_turn_trace(command)
        raw_resolved_command = normalize_spoken_command(command)
        trace["normalized_command"] = raw_resolved_command

        snapshot_before = self._status_snapshot()
        trace["active_url_before"] = self._current_url(snapshot_before)
        if self._command_mentions_tabs(raw_resolved_command):
            snapshot_before = self._enrich_snapshot(snapshot_before, include_tabs=True)

        local = self._local_intent(raw_resolved_command, snapshot_before)
        if local:
            plan = self._validate_plan(local)
            resolved_command = raw_resolved_command
            trace["plan_source"] = "rule_fast_path"
        else:
            heuristic = self._fallback_plan(raw_resolved_command, snapshot_before)
            if heuristic.get("mode") == "execute" and (heuristic.get("steps") or heuristic.get("_already_executed")):
                plan = self._validate_plan(heuristic)
                resolved_command = raw_resolved_command
                trace["plan_source"] = "selector_fast_path"
            else:
                snapshot_before = self._enrich_snapshot(
                    snapshot_before,
                    include_page_context=True,
                    include_tabs=self._command_mentions_tabs(command),
                )
                reframed = self._reframe_command(command, snapshot_before)
                confidence = float(reframed.get("confidence", 1.0))
                resolved_command = normalize_spoken_command(reframed.get("clear_task") or command)
                trace["reframed_command"] = resolved_command
                trace["reframer_used"] = bool(reframed.get("was_reframed") or resolved_command != raw_resolved_command)

                # If reframer has very low confidence, don't execute garbage
                if confidence < 0.4 and reframed.get("was_reframed"):
                    plan = {
                        "mode": "ask",
                        "message": "I didn't quite understand that. Could you say it again more clearly?",
                        "steps": [],
                    }
                    trace["plan_source"] = "low_confidence_reject"
                    trace["plan_mode"] = "ask"
                    trace["steps_json"] = "[]"
                    trace["assistant_reply"] = plan["message"]
                    trace["latency_ms"] = int((time.time() - turn_started_at) * 1000)
                    self._log_turn(trace)
                    self._remember(command, plan["message"])
                    flush_ui()
                    self._print_reply("Assistant", [plan["message"]], C.YELLOW)
                    return True

                local = self._local_intent(resolved_command, snapshot_before)
                if local:
                    plan = self._validate_plan(local)
                    trace["plan_source"] = "reframed_rule_fast_path"
                else:
                    heuristic = self._fallback_plan(resolved_command, snapshot_before)
                    if heuristic.get("mode") == "execute" and (heuristic.get("steps") or heuristic.get("_already_executed")):
                        plan = self._validate_plan(heuristic)
                        trace["plan_source"] = "reframed_selector_fast_path"
                    else:
                        plan = self._plan_with_llm(resolved_command, snapshot_before, reframed)
                        trace["plan_source"] = "planner_fallback"
                        trace["llm_used"] = True

        trace["plan_mode"] = plan.get("mode", "ask")
        trace["steps_json"] = compact_json(plan.get("steps", []))

        if plan["mode"] == "end":
            validation = self._validate_execution(plan, snapshot_before, snapshot_before, [], None)
            trace["validation_status"] = validation["status"]
            trace["validation_reason"] = validation["reason"]
            trace["assistant_reply"] = plan["message"]
            trace["latency_ms"] = int((time.time() - turn_started_at) * 1000)
            self._log_turn(trace)
            self._remember(command, plan["message"])
            flush_ui()
            self._print_reply("Assistant", [plan["message"]], C.YELLOW)
            return False

        if plan["mode"] == "ask":
            self.last_error = None
            reply = plan["message"]
            validation = self._validate_execution(plan, snapshot_before, snapshot_before, [], None)
            trace["validation_status"] = validation["status"]
            trace["validation_reason"] = validation["reason"]
            trace["assistant_reply"] = reply
            trace["latency_ms"] = int((time.time() - turn_started_at) * 1000)
            self._log_turn(trace)
            self._remember(command, reply)
            flush_ui()
            self._print_reply("Assistant", [reply], C.CYAN)
            return True

        # Handle plans already executed via JS (e.g., Nth item clicks)
        if plan.get("_already_executed"):
            self._auto_wait_if_needed("click")
            status_after = self._call_tool_json("get_status", {}) or {}
            snapshot_after = {"status": status_after}
            follow_up = self._format_follow_up(snapshot_after)
            lines = [plan["message"], follow_up]

            validation = self._validate_execution(plan, snapshot_before, snapshot_after, [], None)
            trace["validation_status"] = validation["status"]
            trace["validation_reason"] = validation["reason"]
            trace["selector_path"] = "js_nth_click"
            trace["selector_used"] = (plan.get("_js_result") or {}).get("selector", "")
            trace["active_url_after"] = self._current_url(snapshot_after)
            trace["active_title_after"] = self._snapshot_title(snapshot_after)
            trace["assistant_reply"] = " ".join(lines)
            trace["latency_ms"] = int((time.time() - turn_started_at) * 1000)

            self.last_error = None
            self._log_turn(trace)
            self._remember(command, lines[0])
            flush_ui()
            self._print_reply("Assistant", lines, C.GREEN)
            return True

        results = []
        try:
            prepared_steps = [self._prepare_step_for_execution(step, snapshot_before) for step in plan["steps"]]
            trace["steps_json"] = compact_json(prepared_steps)
            for step in prepared_steps:
                tool = step["tool"]
                args = dict(step["args"])
                if tool == "type":
                    result_meta = self._execute_type_step(args, snapshot_before)
                    result_text = result_meta["result"]
                elif tool == "click" and "_selector_candidates" in args:
                    result_meta = self._execute_click_step(args, snapshot_before)
                    result_text = result_meta["result"]
                else:
                    result_text = self._call_tool(tool, args)
                    result_meta = {
                        "result": result_text,
                        "selector_used": "",
                        "selector_path": "tool_call",
                    }
                results.append(
                    {
                        "tool": tool,
                        "args": args,
                        "result": truncate(result_text, 500),
                        "selector_used": result_meta.get("selector_used", ""),
                        "selector_path": result_meta.get("selector_path", ""),
                    }
                )
                # Human-like pause before Enter after typing (avoids bot detection)
                if tool == "type" and self._is_bot_protected_site(snapshot_before):
                    time.sleep(0.4)
                self._auto_wait_if_needed(tool)

            status_after = self._call_tool_json("get_status", {}) or {}
            snapshot_after = {"status": status_after}
            follow_up = self._format_follow_up(snapshot_after)
            lines = [plan["message"], follow_up]

            for item in results:
                if item["tool"] == "extract":
                    lines.insert(1, f"Extracted data:\n{item['result']}")
                    break

            executed_plan = {"mode": plan.get("mode"), "message": plan.get("message"), "steps": prepared_steps}
            validation = self._validate_execution(executed_plan, snapshot_before, snapshot_after, results, None)
            if (
                validation["status"] == "recover"
                and prepared_steps
                and prepared_steps[0].get("tool") == "type"
                and len(prepared_steps) >= 2
                and prepared_steps[1].get("tool") == "press_key"
            ):
                after_url = self._current_url(snapshot_after).lower()
                search_text = str(prepared_steps[0].get("args", {}).get("text", "")).strip()
                if search_text and ("google." in after_url or after_url in {"", "about:blank"}):
                    self._call_tool("browse", {"url": f"https://www.google.com/search?q={quote(search_text)}"})
                    self._auto_wait_if_needed("browse")
                    status_after = self._call_tool_json("get_status", {}) or {}
                    snapshot_after = {"status": status_after}
                    follow_up = self._format_follow_up(snapshot_after)
                    lines = [
                        f"{plan['message']} I retried it directly as a Google search.",
                        follow_up,
                    ]
                    validation = {"status": "keep", "reason": "Recovered by navigating directly to the Google search URL."}

            trace["validation_status"] = validation["status"]
            trace["validation_reason"] = validation["reason"]
            trace["selector_path"] = ",".join(
                sorted({item["selector_path"] for item in results if item.get("selector_path") and item["selector_path"] != "tool_call"})
            )
            trace["selector_used"] = " | ".join(item["selector_used"] for item in results if item.get("selector_used"))
            trace["active_url_after"] = self._current_url(snapshot_after)
            trace["active_title_after"] = self._snapshot_title(snapshot_after)
            trace["assistant_reply"] = " ".join(lines)
            trace["latency_ms"] = int((time.time() - turn_started_at) * 1000)

            self.last_error = None
            self._log_turn(trace)
            self._remember(command, lines[0], prepared_steps)
            flush_ui()
            self._print_reply("Assistant", lines, C.GREEN)
            return True
        except Exception as exc:
            self.last_error = str(exc)
            validation = self._validate_execution(
                {"mode": plan.get("mode"), "message": plan.get("message"), "steps": prepared_steps if 'prepared_steps' in locals() else plan.get("steps", [])},
                snapshot_before,
                snapshot_before,
                results,
                exc,
            )
            trace["validation_status"] = validation["status"]
            trace["validation_reason"] = validation["reason"]
            trace["selector_path"] = ",".join(
                sorted({item["selector_path"] for item in results if item.get("selector_path") and item["selector_path"] != "tool_call"})
            )
            trace["selector_used"] = " | ".join(item["selector_used"] for item in results if item.get("selector_used"))
            trace["error"] = truncate(str(exc), 260)
            trace["latency_ms"] = int((time.time() - turn_started_at) * 1000)
            stuck_message = (
                f"I got stuck while trying to handle: {resolved_command}\n"
                f"Error: {truncate(str(exc), 260)}\n"
                "Please guide me with the next direct step, or say 'discard browser'."
            )
            trace["assistant_reply"] = stuck_message
            self._log_turn(trace)
            self._remember(command, stuck_message, prepared_steps if 'prepared_steps' in locals() else plan.get("steps", []))
            flush_ui()
            self._print_reply("Need Help", [stuck_message], C.YELLOW)
            return True


async def transcribe_audio_file(audio_path: str) -> str:
    with open(audio_path, "rb") as audio_file:
        audio_data = base64.b64encode(audio_file.read()).decode("utf-8")

    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY environment variable is not set.")

    client = AsyncSarvamAI(api_subscription_key=api_key)

    async with client.speech_to_text_streaming.connect(
        model="saaras:v3",
        mode="transcribe",
        language_code="unknown",
        high_vad_sensitivity=False,
    ) as ws:
        await ws.transcribe(audio=audio_data)

        final_text = ""
        received_any_chunk = False
        initial_timeout_retried = False
        while True:
            try:
                if received_any_chunk:
                    timeout = TRANSCRIBE_IDLE_TIMEOUT_SECONDS
                elif initial_timeout_retried:
                    timeout = TRANSCRIBE_INITIAL_RETRY_TIMEOUT_SECONDS
                else:
                    timeout = TRANSCRIBE_INITIAL_TIMEOUT_SECONDS
                response_json = await asyncio.wait_for(ws.recv(), timeout=timeout)
                if hasattr(response_json, "data") and hasattr(response_json.data, "transcript"):
                    chunk = response_json.data.transcript
                else:
                    try:
                        res_dict = json.loads(response_json)
                        chunk = res_dict.get("transcript", str(response_json))
                    except Exception:
                        chunk = str(response_json)
                if chunk and chunk != "None":
                    received_any_chunk = True
                    final_text += " " + chunk.strip()
            except asyncio.TimeoutError:
                if not received_any_chunk and not initial_timeout_retried:
                    initial_timeout_retried = True
                    continue
                break
            except Exception:
                break

    return final_text.strip()


def record_until_silence(ui: VoiceUI) -> str:
    stream_owner = pyaudio.PyAudio()
    stream = stream_owner.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    pre_buffer = deque(maxlen=max(1, int(PRE_ROLL_SECONDS * RATE / CHUNK)))
    ambient_levels = deque(maxlen=max(4, int(CALIBRATION_SECONDS * RATE / CHUNK)))
    frames: List[bytes] = []
    silence_chunks = 0
    silence_chunks_needed = max(1, int(SILENCE_HOLD_SECONDS * RATE / CHUNK))
    speech_started = False
    speech_candidate_chunks = 0
    sustained_speech_chunks = 0
    dynamic_end_threshold = MIN_END_THRESHOLD

    ui.set_state("WAITING")
    ui.start_animation()

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = compute_rms(data)

            if not speech_started:
                pre_buffer.append(data)
                ambient_levels.append(rms)
                ambient_rms = estimate_ambient_rms(ambient_levels)
                dynamic_start_threshold = max(MIN_START_THRESHOLD, ambient_rms * START_THRESHOLD_MULTIPLIER)
                dynamic_end_threshold = max(MIN_END_THRESHOLD, ambient_rms * END_THRESHOLD_MULTIPLIER)
                moderate_start_threshold = max(MIN_START_THRESHOLD * 0.78, ambient_rms + MODERATE_SPEECH_MARGIN)
                sustained_start_threshold = max(MIN_START_THRESHOLD * 0.55, ambient_rms + SUSTAINED_SPEECH_MARGIN)
                ui.feed_audio(data, ambient_rms=ambient_rms, boost=0.85)

                if rms >= dynamic_start_threshold:
                    speech_candidate_chunks = min(SPEECH_CONFIRM_CHUNKS, speech_candidate_chunks + 2)
                    sustained_speech_chunks = min(SUSTAINED_SPEECH_CHUNKS, sustained_speech_chunks + 2)
                elif rms >= moderate_start_threshold:
                    speech_candidate_chunks += 1
                    sustained_speech_chunks += 1
                elif rms >= sustained_start_threshold:
                    sustained_speech_chunks += 1
                    speech_candidate_chunks = max(0, speech_candidate_chunks)
                else:
                    speech_candidate_chunks = max(0, speech_candidate_chunks - 1)
                    sustained_speech_chunks = max(0, sustained_speech_chunks - 1)

                if (
                    speech_candidate_chunks >= SPEECH_CONFIRM_CHUNKS
                    or sustained_speech_chunks >= SUSTAINED_SPEECH_CHUNKS
                ):
                    speech_started = True
                    ui.begin_listening()
                    frames.extend(pre_buffer)
                    ui.feed_audio(data, ambient_rms=ambient_rms, boost=1.0)
            else:
                frames.append(data)
                ambient_rms = estimate_ambient_rms(ambient_levels)
                ui.feed_audio(data, ambient_rms=ambient_rms, boost=1.0)

                heard_seconds = 0.0 if ui.listen_started_at is None else time.time() - ui.listen_started_at
                if rms < dynamic_end_threshold:
                    silence_chunks += 1
                else:
                    silence_chunks = 0

                if heard_seconds >= MAX_UTTERANCE_SECONDS:
                    break
                if heard_seconds >= MIN_COMMAND_SECONDS and silence_chunks >= silence_chunks_needed:
                    break
    finally:
        stream.stop_stream()
        stream.close()
        stream_owner.terminate()

    ui.set_state("TRANSCRIBING")

    fd, audio_path = tempfile.mkstemp(prefix="webghosting_voice_", suffix=".wav")
    os.close(fd)
    with wave.open(audio_path, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(RATE)
        wav_file.writeframes(b"".join(frames))

    return audio_path


def _ensure_voice_deps():
    """Import pyaudio and sarvamai at runtime — only needed for voice mode."""
    global pyaudio, AsyncSarvamAI, FORMAT
    if pyaudio is not None:
        return
    try:
        import pyaudio as _pa
        pyaudio = _pa
    except ImportError:
        print(f"  {C.RED}PyAudio is required for voice mode: pip install pyaudio{C.RESET}")
        raise SystemExit(1)
    try:
        from sarvamai import AsyncSarvamAI as _sarvam
        globals()["AsyncSarvamAI"] = _sarvam
    except ImportError:
        print(f"  {C.RED}Sarvam AI SDK is required for voice mode: pip install sarvamai{C.RESET}")
        raise SystemExit(1)
    FORMAT = pyaudio.paInt16


def print_welcome(text_mode: bool = False):
    os.system("clear")
    mode_label = "Text" if text_mode else "Voice"
    print(f"\n  {C.BOLD}WEBGhosting Persistent {mode_label} Browser{C.RESET}")
    if text_mode:
        print(f"  {C.DIM}Type one command at a time. The browser stays open until you type 'discard browser'.{C.RESET}")
        print(f"  {C.DIM}Demo Mode — no microphone needed.{C.RESET}\n")
    else:
        print(f"  {C.DIM}Speak one command at a time. The browser stays open until you say 'discard browser'.{C.RESET}\n")


def _text_input_prompt() -> str:
    """Read a command from the keyboard with a styled prompt."""
    try:
        return input(f"  {C.BCYAN}❯{C.RESET} ").strip()
    except EOFError:
        return "discard browser"


def main():
    parser = argparse.ArgumentParser(
        description="WEBGhosting Persistent Browser Agent",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Demo mode: type commands instead of speaking (no mic/Sarvam needed)",
    )
    args = parser.parse_args()
    text_mode = args.text

    print_welcome(text_mode=text_mode)

    if text_mode:
        required = ["AI_API_KEY"]
    else:
        _ensure_voice_deps()
        required = ["SARVAM_API_KEY", "AI_API_KEY"]

    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        print(f"  {C.RED}Missing environment variables: {', '.join(missing)}{C.RESET}")
        raise SystemExit(1)

    ui = VoiceUI()
    session = None

    try:
        session = VoiceBrowserSession()

        if text_mode:
            panel(
                "Demo Session Ready",
                [
                    "Browser session is live. Type commands below.",
                    "Examples: 'open google', 'type Hacker News and search', 'click the first result'",
                    "Type 'discard browser' to end the session.",
                    f"Log: {os.path.basename(DEFAULT_RESULTS_TSV_PATH)}",
                ],
                color=C.CYAN,
            )

            while True:
                command = _text_input_prompt()
                if not command:
                    continue
                panel("Command", [f'"{command}"'], color=C.CYAN)
                if not session.handle_command(command):
                    break
        else:
            panel(
                "Session Ready",
                [
                    "Browser session is live and will stay open across voice commands.",
                    "Say things like 'open Google', 'type Hacker News and search it', or 'click the first result'.",
                    "Say 'discard browser' whenever you want to end the session.",
                    f"Policy: {os.path.basename(SARVAM_PROGRAM_PATH)}  |  Log: {os.path.basename(DEFAULT_RESULTS_TSV_PATH)}",
                ],
                color=C.CYAN,
            )

            while True:
                audio_path = record_until_silence(ui)
                transcript = ""
                try:
                    transcript = asyncio.run(transcribe_audio_file(audio_path))
                except Exception as stt_err:
                    ui.stop_animation(clear_frame=True)
                    panel(
                        "Transcription Error",
                        [
                            f"Sarvam STT failed: {truncate(str(stt_err), 200)}",
                            "Check your SARVAM_API_KEY. Retrying on next utterance...",
                        ],
                        color=C.YELLOW,
                    )
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                    continue
                finally:
                    ui.stop_animation(clear_frame=True)
                    if os.path.exists(audio_path):
                        os.remove(audio_path)

                if not transcript or len(transcript.strip()) < 2:
                    panel("Assistant", ["I did not catch that clearly. Please try again."], color=C.YELLOW)
                    continue

                panel("Voice Command", [f'"{transcript}"'], color=C.CYAN)
                ui.set_state("EXECUTING")
                ui.start_animation()
                try:
                    if not session.handle_command(transcript, ui=ui):
                        break
                finally:
                    ui.stop_animation()

    except KeyboardInterrupt:
        ui.stop_animation(clear_frame=True)
        print(f"\n  {C.YELLOW}Session canceled by user.{C.RESET}")
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    main()
