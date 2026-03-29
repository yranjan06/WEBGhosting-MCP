#!/usr/bin/env python3
"""
WEBGhosting Recipe Orchestrator

Executes JSON recipe files through the WEBGhosting browser engine.
Features: Selector Caching + Self-Healing, Checkpoint/Resume, Human-in-the-Loop.

Usage:
    python3 -m orchestrator.orchestrator recipes/hn_reddit_linkedin.json
    python3 -m orchestrator.orchestrator --run "your command here"
    python3 -m orchestrator.orchestrator --resume
    python3 -m orchestrator.orchestrator --list
"""

import sys, os, json, time, glob, tempfile, hashlib, re
from contextlib import contextmanager
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest
from datetime import datetime, timezone

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from examples.client import WEBGhostingClient, GREEN, RED, YELLOW, CYAN, DIM, BOLD, RESET
from orchestrator.ui import Spinner, panel, table, step_header, pipeline_banner, recipe_banner, results_panel, stats_summary, info_msg, success_msg, error_msg, warn_msg, C, progress_bar

CHECKPOINT_DIR = os.path.join(tempfile.gettempdir(), "webghosting_checkpoints")


class HTTPRequestError(Exception):
    """Raised when an outbound JSON HTTP request fails."""


PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "PROXY_USERNAME",
    "PROXY_PASSWORD",
)


def post_json(url, headers, payload, timeout):
    """Send a JSON POST request using only the Python standard library."""
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=body, headers=headers, method="POST")

    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            status = getattr(resp, "status", resp.getcode())
    except urlerror.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise HTTPRequestError(f"HTTP {e.code}: {error_body[:400]}")
    except urlerror.URLError as e:
        raise HTTPRequestError(f"Network error: {e.reason}")

    try:
        data = json.loads(resp_body)
    except json.JSONDecodeError as e:
        raise HTTPRequestError(f"Invalid JSON response: {e}")

    if status < 200 or status >= 300:
        raise HTTPRequestError(f"HTTP {status}")

    return data


def _format_proxy_host(parsed):
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return host


def _build_proxy_url(scheme, host, username="", password=""):
    netloc = host
    if username:
        auth = urlparse.quote(username, safe="")
        if password:
            auth = f"{auth}:{urlparse.quote(password, safe='')}"
        netloc = f"{auth}@{netloc}"
    return urlparse.urlunsplit((scheme, netloc, "", "", ""))


def parse_proxy_config(raw_proxy):
    """Normalize one proxy entry for both local HTTP calls and the browser subprocess."""
    raw_proxy = (raw_proxy or "").strip()
    if not raw_proxy:
        return None

    parsed = urlparse.urlsplit(raw_proxy)
    if not parsed.scheme or not parsed.hostname:
        username = os.environ.get("PROXY_USERNAME", "")
        password = os.environ.get("PROXY_PASSWORD", "")
        return {
            "raw": raw_proxy,
            "server": raw_proxy,
            "env_proxy": raw_proxy,
            "username": username,
            "password": password,
        }

    host = _format_proxy_host(parsed)
    username = urlparse.unquote(parsed.username) if parsed.username else os.environ.get("PROXY_USERNAME", "")
    password = urlparse.unquote(parsed.password) if parsed.password else os.environ.get("PROXY_PASSWORD", "")
    server = _build_proxy_url(parsed.scheme, host)
    env_proxy = _build_proxy_url(parsed.scheme, host, username, password) if username else server

    return {
        "raw": raw_proxy,
        "server": server,
        "env_proxy": env_proxy,
        "username": username,
        "password": password,
    }


@contextmanager
def proxy_environment(proxy_config):
    """Temporarily apply proxy settings to the current orchestrator process."""
    previous = {key: os.environ.get(key) for key in PROXY_ENV_KEYS}
    try:
        if proxy_config:
            env_proxy = proxy_config["env_proxy"]
            for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                os.environ[key] = env_proxy

            username = proxy_config.get("username", "")
            password = proxy_config.get("password", "")
            if username:
                os.environ["PROXY_USERNAME"] = username
                os.environ["PROXY_PASSWORD"] = password
            else:
                os.environ.pop("PROXY_USERNAME", None)
                os.environ.pop("PROXY_PASSWORD", None)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Feature 1: Selector Caching + Self-Healing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SelectorCache:
    """Stagehand-style selector caching with self-healing.

    Before using a selector:
      1. Quick JS check: does it exist on the page?
      2. If yes → use directly (0 latency, no LLM)
      3. If no → try fallback → still no → use accessibility tree to heal
      4. Auto-update the selector JSON file with new data
    """

    def __init__(self, selectors, selectors_dir):
        self.selectors = selectors
        self.selectors_dir = selectors_dir
        self.healed_count = 0

    def verify_selector(self, client, selector):
        """Quick JS check: does this selector exist on the current page?"""
        try:
            result = client.call("execute_js", {
                "script": f"document.querySelector('{selector}') !== null ? 'found' : 'not_found'"
            })
            return result and "found" in str(result)
        except Exception:
            return False

    def heal_selector(self, client, selector_key, original_selector, fallback=None):
        """Try to find a working selector when the cached one breaks.

        Strategy:
          1. Try the fallback selector
          2. Use get_accessibility_tree to describe what we're looking for
          3. Return the first working selector found
        """
        # Step 1: Try fallback
        if fallback:
            print(f"  {YELLOW}  [Heal] Primary selector broken, trying fallback...{RESET}")
            if self.verify_selector(client, fallback):
                print(f"  {GREEN}  [Heal] Fallback works! Updating cache.{RESET}")
                self._update_selector_file(selector_key, fallback)
                self.healed_count += 1
                return fallback

        # Step 2: Use accessibility tree to find a match
        print(f"  {YELLOW}  [Heal] Fallback also broken. Scanning accessibility tree...{RESET}")
        try:
            tree = client.call("get_accessibility_tree", {})
            if tree:
                # Extract the element type from the selector key (e.g., "hn.top_post" → "post")
                element_hint = selector_key.split(".")[-1].replace("_", " ")
                print(f"  {DIM}  [Heal] Looking for element matching: '{element_hint}'{RESET}")
                # We can't auto-discover without LLM, but we log the failure clearly
                print(f"  {RED}  [Heal] Auto-discovery needs AI. Selector '{selector_key}' needs manual update.{RESET}")
        except Exception:
            pass

        return None  # Healing failed

    def get_verified_selector(self, client, selector_key):
        """Get a verified, working selector for the given key. Self-heals if broken."""
        entry = self.selectors.get(selector_key)
        if not entry:
            return None

        selector = entry.get("selector", "")
        fallback = entry.get("fallback")

        # Quick verify
        if self.verify_selector(client, selector):
            # Update confidence + last_verified
            self._mark_verified(selector_key)
            return selector

        # Primary broken → heal
        healed = self.heal_selector(client, selector_key, selector, fallback)
        return healed

    def _mark_verified(self, selector_key):
        """Update the selector entry with confidence and timestamp."""
        if selector_key in self.selectors:
            self.selectors[selector_key]["confidence"] = 1.0
            self.selectors[selector_key]["last_verified"] = datetime.now(timezone.utc).isoformat()

    def _update_selector_file(self, selector_key, new_selector):
        """Write the healed selector back to the appropriate JSON file."""
        if not self.selectors_dir or not os.path.isdir(self.selectors_dir):
            return

        # Find which file contains this selector key
        for f in glob.glob(os.path.join(self.selectors_dir, '*.json')):
            with open(f) as fp:
                data = json.load(fp)
            if selector_key in data:
                # Swap: old selector becomes fallback, new becomes primary
                old_selector = data[selector_key].get("selector", "")
                data[selector_key]["selector"] = new_selector
                data[selector_key]["fallback"] = old_selector
                data[selector_key]["confidence"] = 0.8
                data[selector_key]["last_verified"] = datetime.now(timezone.utc).isoformat()
                data[selector_key]["healed_at"] = datetime.now(timezone.utc).isoformat()

                with open(f, 'w') as fp:
                    json.dump(data, fp, indent=4)
                print(f"  {GREEN}  [Cache] Updated {os.path.basename(f)}: {selector_key}{RESET}")
                return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Feature 2: Checkpoint / Resume
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CheckpointManager:
    """Saves execution state after each step. Allows crash recovery.

    Checkpoint = {step_index, context, recipe_path, recipe_name, timestamp}
    Stored in /tmp/webghosting_checkpoints/<recipe_hash>.json
    """

    def __init__(self, recipe_path):
        self.recipe_path = recipe_path
        self.recipe_hash = hashlib.md5(recipe_path.encode()).hexdigest()[:10]
        os.makedirs(CHECKPOINT_DIR, exist_ok=True)
        self.checkpoint_file = os.path.join(CHECKPOINT_DIR, f"{self.recipe_hash}.json")

    def save(self, step_index, context, recipe_name=""):
        """Save checkpoint after a successful step."""
        checkpoint = {
            "step_index": step_index,
            "context": context,
            "recipe_path": self.recipe_path,
            "recipe_name": recipe_name,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def load(self):
        """Load existing checkpoint. Returns None if no checkpoint exists."""
        if not os.path.exists(self.checkpoint_file):
            return None
        try:
            with open(self.checkpoint_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def clear(self):
        """Delete checkpoint after successful completion."""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)

    @staticmethod
    def find_any():
        """Find any existing checkpoint files."""
        if not os.path.isdir(CHECKPOINT_DIR):
            return []
        checkpoints = []
        for f in glob.glob(os.path.join(CHECKPOINT_DIR, "*.json")):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                checkpoints.append(data)
            except (json.JSONDecodeError, IOError):
                pass
        return checkpoints


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Feature 3: Human-in-the-Loop (HIL)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CAPTCHA_INDICATORS = [
    "captcha", "recaptcha", "hcaptcha", "challenge",
    "verify you are human", "i'm not a robot", "cloudflare"
]

# Only match these in the page TITLE (not body text) to avoid false positives
LOGIN_TITLE_INDICATORS = [
    "sign in", "log in", "login", "signin", "authenticate",
    "enter your password", "verify your identity"
]


def detect_hil_needed(client):
    """Check if the current page IS a captcha or login page (not just has a login link).

    Strategy:
      1. Check page title for login/captcha keywords
      2. Check for actual login form elements (password input, captcha image)
      3. Do NOT scan body text — that causes false positives on normal pages
         that just have a "login" nav link (like HN, Reddit, etc.)
    """
    try:
        # Check 1: Page title (login/captcha pages have distinctive titles)
        title_result = client.call("execute_js", {
            "script": "document.title"
        })
        if title_result:
            title = str(title_result).lower()
            for indicator in CAPTCHA_INDICATORS:
                if indicator in title:
                    return "captcha"
            for indicator in LOGIN_TITLE_INDICATORS:
                if indicator in title:
                    return "login"

        # Check 2: Actual form elements (password field or captcha image)
        form_result = client.call("execute_js", {
            "script": """(() => {
                const has_password = document.querySelector('input[type="password"]') !== null;
                const has_captcha = document.querySelector('img#captchaimg, .g-recaptcha, .h-captcha, iframe[src*="captcha"]') !== null;
                const has_email_only = document.querySelector('input#identifierId, input[name="identifier"]') !== null;
                if (has_captcha) return 'captcha';
                if (has_password || has_email_only) return 'login_form';
                return 'none';
            })()"""
        })
        if form_result:
            result_str = str(form_result)
            if "captcha" in result_str:
                return "captcha"
            if "login_form" in result_str:
                return "login"
    except Exception:
        pass
    return None


def hil_pause(reason=""):
    """Pause execution, ring bell, wait for user to press Enter."""
    msg = reason or "Human intervention needed"
    print(f"\n  {BOLD}{YELLOW}[HIL] {msg}{RESET}")
    print(f"  {YELLOW}  Complete the action in the browser, then press Enter to continue...{RESET}")
    print("\a", end="", flush=True)  # Terminal bell
    try:
        input(f"  {DIM}  Press Enter when ready >> {RESET}")
    except EOFError:
        # Non-interactive mode (MCP subprocess) — wait 30s instead
        print(f"  {DIM}  Non-interactive mode. Waiting 30 seconds...{RESET}")
        time.sleep(30)
    print(f"  {GREEN}  [HIL] Resuming execution.{RESET}\n")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM Recipe Generator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECIPE_SYSTEM_PROMPT = """You are a WEBGhosting Recipe Generator. Convert user commands into JSON recipes.

10. **HACKER NEWS MASTERY & SMART INDEXING:** Hacker News has a specialized indexing system. **NEVER** use raw CSS for HN stories or comments. ALWAYS use these logical IDs:
    - `story:N` -> Targets the Nth news article title row.
    - `metadata:N` -> Targets the subtext row (Author, Points) for the Nth article.
    - `comments:N` -> Targets the "comments" link for the Nth article.
    - `comment:N` -> Targets the Nth comment in a discussion thread.
    - **Navigation Example:** To click comments of the 2nd article:
      `{"action": "click", "selector": "comments:2"}`.
    - **Extraction Example (Homepage):** To get the author of the 2nd article:
      `{"action": "extract", "selector": "metadata:2", "schema": {"user": "a.hnuser"}}`.
    - **Extraction Example (Thread):** To get the 2nd comment text:
      `{"action": "extract", "selector": "comment:2", "schema": {"text": ".commtext"}}`.
    - **SCOPED EXTRACTION:** For threads, the AI will automatically scope to the correct comment row if you use `comment:N`.

EXACT action formats (use these EXACTLY):

{"id": 1, "action": "browse", "url": "https://example.com", "narrate": "Opening site..."}
{"id": 2, "action": "wait", "state": "domcontentloaded"}
{"id": 3, "action": "wait_selector", "selector": ".post-title"}
{"id": 4, "action": "click", "selector": ".submit-btn", "narrate": "Clicking submit..."}
{"id": 5, "action": "type", "selector": "#search", "text": "AI agents", "narrate": "Typing query..."}
{"id": 6, "action": "extract", "schema": {"title": "string", "links": ["string"]}, "instruction": "Top 3 only", "selector": ".content-area", "save_as": "page_data", "narrate": "Extracting data..."}
{"id": 7, "action": "scroll", "amount": 600}
{"id": 8, "action": "open_tab"}
{"id": 9, "action": "switch_tab", "index": 0}
{"id": 10, "action": "extract", "schema": {"author": "string"}, "selector": "tr.athing:first-of-type + tr", "save_as": "top_author", "narrate": "Extracting author of first item only..."}
{"id": 11, "action": "search_reddit", "query": "AI agents", "subreddit": "LocalLLaMA", "sort": "relevance", "time": "all", "narrate": "Searching Reddit directly..."}

Pre-cached selector catalog (Use these selectors when applicable):
{selectors}

{system_examples}

Variable system: `save_as` stores results as JSON. Reference via {variable.key} in later steps (e.g., in `url`, `type` text, or `search` query).

**CRITICAL RULES FOR RELIABILITY (DO NOT VIOLATE):**
1. **NO RAW JS FOR EXTRACTION:** NEVER use `action: "js"` to write complex CSS/DOM queries or mappings. ALWAYS use `action: "extract"` with a descriptive JSON `schema` to let the backend safely extract data using AI. This prevents script crashes! Use the `instruction` property if the user asked to filter, sort, or limit (e.g., "top 3").
2. **MANDATORY WAITS:** Browsers are asynchronous. ALWAYS add a `{"action": "wait", "state": "domcontentloaded"}` step immediately after EVERY `browse` or `click` action that loads a new page. If clicking expands a menu, use `wait_selector`.
3. **ONLY output valid JSON:** No markdown, no explanation, no backtick fences.
4. Top-level keys MUST be exactly: "name" (string) and "steps" (array).
5. Use "narrate" to describe user-facing steps.
6. For data extraction tasks, the final step should usually be an `extract` action with a `save_as` key to capture results for the user. Do away with manual javascript scraping.
7. If you must use `action: "js"`, ONLY use it for interacting with specific non-standard UI elements that forms/clicks can't handle. Never for data reading. Always use `?.innerText` to prevent crashes.
8. **SCOPED EXTRACTION:** When using `action: "extract"`, ALWAYS provide a `selector` if possible to limit the AI's focus. If the user wants a LIST of items (e.g., 'top 5 comments'), the `selector` MUST be the **common container** (e.g., `table.comment-tree`) instead of an individual item row. This prevents the extraction of unrelated page elements (headers, footers).
9. **GOOGLE TO TARGET SITE NAVIGATION:** When searching Google and opening a specific site result (like Reddit, HackerNews, Wikipedia), NEVER use `action: "click"`. Google hijacks clicks. ALWAYS use `action: "extract"` with the proper `_result_link` selector to acquire the `href`, then use `action: "browse"` to safely navigate to that extracted URL!
10. **STRICT SELECTOR USAGE:** Always prioritize using exact `selector` keys from the injected catalog below (e.g., `"selector": "google.first_result"`) over generic `prompt` strings (e.g., `"prompt": "click the first result"`). Natural language prompts can cause the visual clicker to accidentally click the wrong bounding box (like a Login button).
11. **REDDIT-TOPIC DISCOVERY:** If the task is to find discussion about a topic on Reddit, prefer `action: "search_reddit"` over routing through Google. If the user mentions a subreddit, fill the `subreddit` field and search directly inside that subreddit."""


import os
import json
import re

SELECTOR_USAGE_FILE = os.path.join(os.path.dirname(__file__), "selectors", "selector_usage.json")

# ━━━ Token Usage Tracker ━━━
_token_usage = {"reframe_in": 0, "reframe_out": 0, "recipe_in": 0, "recipe_out": 0, "calls": 0}

def _track_tokens(resp_json, stage):
    """Extract and accumulate token usage from LLM API response."""
    usage = resp_json.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    _token_usage[f"{stage}_in"] += prompt_tokens
    _token_usage[f"{stage}_out"] += completion_tokens
    _token_usage["calls"] += 1
    return prompt_tokens, completion_tokens

def load_selector_usage():
    if os.path.exists(SELECTOR_USAGE_FILE):
        try:
            with open(SELECTOR_USAGE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_selector_usage(usage):
    try:
        with open(SELECTOR_USAGE_FILE, 'w') as f:
            json.dump(usage, f, indent=2)
    except Exception as e:
        print(f"{DIM}  Failed to save selector usage: {e}{RESET}")

def get_relevant_selectors(command, selectors_db):
    cmd_lower = command.lower()

    # Mapping selector prefixes to regex patterns for smart matching
    domain_map = {
        "reddit.": r"\b(reddit|r/|shreddit)\b",
        "hn.": r"\b(hacker news|hn|ycombinator|y combinator)\b",
        "twitter.": r"\b(twitter|x\.com|tweet)\b",
        "linkedin.": r"\b(linkedin|lnkd|lnkd\.in)\b",
        "github.": r"\b(github|repo|pull request)\b",
        "amazon.": r"\b(amazon|buy on|add to cart)\b",
        "youtube.": r"\b(youtube|yt|video)\b",
        "google.": r"\b(google|goolge|search)\b",
    }

    # Find matching prefixes
    prefixes = []
    for prefix, pattern in domain_map.items():
        if re.search(pattern, cmd_lower):
            prefixes.append(prefix)

    # Default Fallback
    if not prefixes:
        prefixes.append("google.") # Default router assumes generic web search

    # Map prompt keywords to semantic tags
    prompt_words = set(re.findall(r'\b\w+\b', cmd_lower))
    active_tags = set(["core"])
    if prompt_words.intersection({"search", "find", "look", "query"}): active_tags.add("search")
    if prompt_words.intersection({"login", "auth", "sign", "password", "email"}): active_tags.add("auth")
    if prompt_words.intersection({"read", "extract", "get", "scrape", "save", "capture"}): active_tags.add("read")
    if prompt_words.intersection({"post", "write", "comment", "reply", "tweet", "draft"}): active_tags.add("write")
    if prompt_words.intersection({"go", "navigate", "click", "open", "link"}): active_tags.add("navigate")

    # Get all valid selectors for matched prefixes THAT ALSO intersect with active tags
    valid_selectors = []
    for k, v in selectors_db.items():
        if any(k.startswith(p) for p in prefixes):
            sel_tags = set(v.get("tags", ["core"]))
            # If it has a matching tag, or defaults to core, include it
            if active_tags.intersection(sel_tags):
                valid_selectors.append((k, v))

    # [OPTIMIZATION] Layered Sorting
    usage_stats = load_selector_usage()
    # Sort by weight/usage descending (default weight is 1)
    valid_selectors.sort(key=lambda x: usage_stats.get(x[0], 1), reverse=True)

    MAX_SELECTORS = 150  # Increased drastically so it stops pruning required selectors
    top_selectors = valid_selectors[:MAX_SELECTORS]

    # Strip out raw JS scripts and filter to save massive amounts of tokens
    compact_selectors = {}
    for k, v in top_selectors:
        sel = {prop: v[prop] for prop in ['selector', 'notes', 'extract'] if prop in v}
        if 'script' in v:
            sel['is_script'] = True
        compact_selectors[k] = sel

    p_names = ', '.join([p.strip('.') for p in prefixes])

    return compact_selectors


def get_relevant_examples(command):
    """Load matching pre-built recipes from built-in AND user plugin directories."""
    cmd_lower = command.lower()
    examples = []

    # Extract prompt keywords
    prompt_words = set(re.findall(r'\b\w+\b', cmd_lower))

    # Scan ALL recipe directories (built-in + user plugins)
    all_recipe_dirs = _get_all_recipe_dirs()

    best_match = None
    best_score = 0
    fallback = None

    for recipes_dir in all_recipe_dirs:
        recipe_files = glob.glob(os.path.join(recipes_dir, '*.json'))
        source = "PLUGIN" if recipes_dir == USER_RECIPES_DIR else "BUILT-IN"

        for example_path in recipe_files:
            filename = os.path.basename(example_path).lower()
            file_keywords = set(re.findall(r'\b\w+\b', filename.replace('.json', '')))

            # Count how many prompt keywords match the filename
            overlap = len(prompt_words.intersection(file_keywords))

            if overlap > best_score:
                best_score = overlap
                best_match = (example_path, source)

            # Keep hn_reddit_linkedin as generic fallback
            if 'hn_reddit_linkedin' in filename and fallback is None:
                fallback = (example_path, source)

    # Use best keyword match, or fallback
    chosen = best_match if best_score > 0 else fallback

    if chosen:
        example_path, source = chosen
        try:
            with open(example_path, 'r') as f:
                recipe_data = json.load(f)
                minified = json.dumps(recipe_data, separators=(',', ':'))
                examples.append(minified)
                matched_name = recipe_data.get('name', os.path.basename(example_path))

        except:
            matched_name = None

    if not examples:
        return "", None

    return "Here is an example of a perfectly formatted complex recipe:\n" + "\n".join(examples), matched_name


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Prompt Reframer (RefAIne + CO-STAR + Stagehand inspired)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Hindi/Hinglish markers that indicate reframing is needed
_REFRAME_MARKERS = [
    "karo", "kro", "kardo", "kar do", "bhai", "yaar", "bata", "batao",
    "daba", "dabao", "press karo", "khol", "kholo", "daal", "daalo",
    "likh", "likho", "nikal", "nikalo", "dhundh", "dhundho", "jao",
    "dikhao", "dikha", "wala", "wali", "wale", "mein", " pe ", " ko ",
    "chahiye", "de do", "dedo", "kr do", "krdo", "seedha", "sidha",
    "kaise", "kya", "kaha", "kidhar", "upar", "neeche", "phir", "pehle",
]

# Cache reframed prompts in-memory to avoid redundant LLM calls
_reframe_cache = {}


def _needs_reframe(text):
    """Quick check if text needs LLM reframing (non-English or very casual)."""
    text_lower = text.lower().strip()

    # Already a URL → skip
    if text_lower.startswith(("http://", "https://")):
        return False

    # Has non-ASCII chars (likely Hindi/other script)
    if any(ord(c) > 127 for c in text):
        return True

    # Contains Hindi/Hinglish markers
    for marker in _REFRAME_MARKERS:
        if marker in text_lower:
            return True

    # Very short + vague
    if len(text.split()) <= 2:
        return True

    return False


def reframe_prompt(raw_prompt, api_key, base_url, model):
    """Reframe a casual/multilingual prompt into precise English.

    Architecture:
      - RefAIne style: single-call refinement
      - CO-STAR framework: Context/Objective/Style/Tone/Audience/Response
      - Stagehand patterns: decompose into browser primitives

    Returns the reframed English prompt, or original if no reframing needed.
    """
    raw_prompt = raw_prompt.strip()

    # Fast path: already clean English
    if not _needs_reframe(raw_prompt):
        return raw_prompt

    # Cache check
    if raw_prompt in _reframe_cache:
        cached = _reframe_cache[raw_prompt]
        print(f"  {DIM}[REFRAME] Cache hit{RESET}")
        return cached

    reframe_system = """You are a Prompt Reframer for a browser automation system called WEBGhosting.

Your job: Convert casual, multilingual, vague user prompts into precise, clear English commands.

Input: User prompt in any language (Hindi, Hinglish, Spanish, broken English, slang, etc.)
Output: ONLY the reframed English command. Nothing else. No JSON, no explanation.

Translation rules:
- "karo"/"kro"/"kar do" = do/perform
- "daba do"/"dabao" = click/press
- "likh do"/"likho" = type/write
- "khol do"/"kholo"/"jao" = open/go to/navigate
- "nikal do"/"nikalo"/"bata do" = extract/get/show
- "dhundh do"/"dhundho" = search/find
- "bhai"/"yaar" = strip (filler words)
- "wo wala" = that/the specific one
- "upar/neeche" = scroll up/down

Site aliases:
- "HN" = Hacker News (https://news.ycombinator.com)
- "reddit" = Reddit (https://www.reddit.com)
- "flipkart" = Flipkart (https://www.flipkart.com)
- "amazon" = Amazon (https://www.amazon.in)

Rules:
1. Output ONLY the reframed English text
2. Keep it concise and action-oriented
3. Resolve vagueness where possible
4. Expand abbreviated site names to full names
5. IMPORTANT: DO NOT aggressively split or rewrite search queries. Keep search entities intact. If the user says "search X Y Z", do NOT rewrite it as "search X and navigate to Y and Z". Preserve the exact semantic search term!
6. NO quotes, NO JSON, NO explanation — just the clean command"""

    reframe_model = os.environ.get("REFRAME_MODEL", model)

    try:
        resp_data = post_json(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            payload={
                "model": reframe_model,
                "messages": [
                    {"role": "system", "content": reframe_system},
                    {"role": "user", "content": raw_prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 256
            },
            timeout=30,
        )
        _track_tokens(resp_data, "reframe")
        reframed = resp_data["choices"][0]["message"]["content"].strip()
        # Strip any quotes the LLM might have added
        reframed = reframed.strip('"\'')
        if reframed and len(reframed) > 3:
            _reframe_cache[raw_prompt] = reframed
            return reframed
    except Exception as e:
        print(f"  {DIM}[REFRAME] LLM call failed, using original: {e}{RESET}")

    return raw_prompt


def generate_recipe(command, selectors_db):
    """Use LLM to generate a JSON recipe from a natural language command."""
    api_key = os.environ.get("AI_API_KEY")
    base_url = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("AI_MODEL", "gpt-4o")

    if not api_key:
        print(f"{RED}ERROR: AI_API_KEY not set{RESET}")
        return None

    # [REFRAME] Reframe casual/multilingual prompt before recipe generation
    original_prompt = command
    reframed_command = reframe_prompt(command, api_key, base_url, model)
    if reframed_command != command:
        command = reframed_command

    # [GUARD] Reject incomplete / cut-off prompts (e.g. voice STT truncation)
    _trailing_conjunctions = {"and", "then", "or", "aur", "kar", "karo", "fir", "phir", "but"}
    cmd_words = command.strip().split()
    if len(cmd_words) < 3:
        print(f"\n  {RED}✗ Command too short: \"{command}\"{RESET}")
        print(f"  {DIM}  Please provide a more detailed command (at least 3 words).{RESET}\n")
        return None
    if cmd_words[-1].lower().rstrip(".,!?") in _trailing_conjunctions:
        print(f"\n  {RED}✗ Command appears incomplete (ends with \"{cmd_words[-1]}\"):{RESET}")
        print(f"  {DIM}  \"{command}\"{RESET}")
        print(f"  {DIM}  Please complete your command and try again.{RESET}\n")
        return None


    # Use BOTH the raw and reframed prompt for routing/examples.
    # Reframing can occasionally simplify away destination hints like "on reddit",
    # which makes selector injection too narrow for cross-site workflows.
    routing_context = original_prompt if original_prompt == command else f"{original_prompt}\n{command}"

    # [OPTIMIZATION] Token-Efficient Smart Router
    compact_selectors = get_relevant_selectors(routing_context, selectors_db)
    selectors_summary = json.dumps(compact_selectors, indent=2)

    # [OPTIMIZATION] Few-Shot Example Injection (RAG)
    system_examples, example_name = get_relevant_examples(routing_context)

    # Show the pipeline banner
    domains = ', '.join(sorted(set(k.split('.')[0] for k in compact_selectors.keys()))) or 'general'
    pipeline_banner(original_prompt, command, domains, example_name, len(compact_selectors))

    system_prompt = RECIPE_SYSTEM_PROMPT.replace("{selectors}", selectors_summary).replace("{system_examples}", system_examples)

    spinner = Spinner("Generating recipe via LLM...", color=C.CYAN)
    spinner.start()

    try:
        user_prompt = command if original_prompt == command else f"Original user prompt:\n{original_prompt}\n\nNormalized task:\n{command}"

        resp_data = post_json(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            payload={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 2000
            },
            timeout=90,
        )
        _track_tokens(resp_data, "recipe")
        content = resp_data["choices"][0]["message"]["content"].strip()

        # Extract JSON block between first '{' or '[' and last '}' or ']'
        start_idx = content.find('{')
        arr_start = content.find('[')
        if arr_start != -1 and (start_idx == -1 or arr_start < start_idx):
            start_idx = arr_start
        end_idx = max(content.rfind('}'), content.rfind(']'))

        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            content = content[start_idx:end_idx+1]
        else:
            spinner.fail("No JSON found in LLM response")
            return None

        # Pre-process content to fix common LLM JSON escaping bugs (like invalid \')
        content = content.replace(r"\'", "'")

        # Try parsing as-is first
        recipe = None
        try:
            recipe = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: LLM returned comma-separated objects like {step1}, {step2}
            # Wrap them in an array and try again
            try:
                recipe = json.loads(f"[{content}]")
            except json.JSONDecodeError as e2:
                spinner.fail(f"JSON parse error: {e2}")
                info_msg(f"Raw: {content[:200]}")
                return None

        # Normalise: wrap bare arrays or step objects into a recipe
        if isinstance(recipe, list):
            # LLM returned a bare array of steps — wrap it
            recipe = {"name": "Unnamed", "steps": recipe}
        elif isinstance(recipe, dict) and "steps" not in recipe and "action" in recipe:
            # LLM returned a single step object — wrap it
            recipe = {"name": "Unnamed", "steps": [recipe]}

        steps = len(recipe.get("steps", []))
        spinner.stop(f"Recipe ready: \"{recipe.get('name', 'Unnamed')}\" ({steps} steps)")
        recipe_banner(recipe.get('name', 'Unnamed'), steps)
        return recipe

    except HTTPRequestError as e:
        spinner.fail(f"LLM API error: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Plugin System
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# User plugin directory: ~/.webghosting/plugins/
USER_PLUGIN_DIR = os.path.join(os.path.expanduser("~"), ".webghosting", "plugins")
USER_SELECTORS_DIR = os.path.join(USER_PLUGIN_DIR, "selectors")
USER_RECIPES_DIR = os.path.join(USER_PLUGIN_DIR, "recipes")

def _ensure_plugin_dirs():
    """Create the user plugin directories if they don't exist."""
    for d in [USER_SELECTORS_DIR, USER_RECIPES_DIR]:
        try:
            os.makedirs(d, exist_ok=True)
        except (PermissionError, OSError) as e:
            print(f"{DIM}  [PLUGIN] Cannot create {d}: {e} (user plugins disabled){RESET}")

def _load_selectors_from_dir(directory, selectors_dict):
    """Load all .json selector files from a directory into selectors_dict."""
    if not os.path.isdir(directory):
        return 0
    count = 0
    for f in sorted(glob.glob(os.path.join(directory, '*.json'))):
        if os.path.basename(f) == "selector_usage.json":
            continue
        try:
            with open(f) as fp:
                data = json.load(fp)
                selectors_dict.update(data)
                count += len(data)
        except Exception as e:
            print(f"{DIM}  [PLUGIN] Skipping invalid selector file {os.path.basename(f)}: {e}{RESET}")
    return count

def _get_all_recipe_dirs():
    """Return list of recipe directories: built-in first, then user plugins."""
    dirs = []
    builtin = os.path.join(os.path.dirname(__file__), 'recipes')
    if os.path.isdir(builtin):
        dirs.append(builtin)
    if os.path.isdir(USER_RECIPES_DIR):
        dirs.append(USER_RECIPES_DIR)
    return dirs


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Core Orchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RecipeOrchestrator:
    """Executes JSON recipe files step-by-step via WEBGhostingClient.

    Features:
      - Selector caching + self-healing (Stagehand pattern)
      - Checkpoint/resume on crash (LangGraph pattern)
      - Human-in-the-loop for captchas (Playwright MCP pattern)
      - Plugin system for user-supplied selectors & recipes
    """

    def __init__(self):
        self.client = None
        self.context = {}
        self.selectors = {}
        self.selector_cache = None

        # Ensure user plugin directories exist
        _ensure_plugin_dirs()

        # Load built-in selectors from orchestrator/selectors/
        builtin_dir = os.path.join(os.path.dirname(__file__), 'selectors')
        builtin_count = _load_selectors_from_dir(builtin_dir, self.selectors)

        # Load user plugin selectors from ~/.webghosting/plugins/selectors/
        user_count = _load_selectors_from_dir(USER_SELECTORS_DIR, self.selectors)
        if user_count > 0:
            print(f"{GREEN}  [PLUGIN] Loaded {user_count} user selector(s) from {USER_SELECTORS_DIR}{RESET}")

        if builtin_dir and os.path.isdir(builtin_dir):
            self.selector_cache = SelectorCache(self.selectors, builtin_dir)

    def get_page_snapshot(self):
        """Return a small JSON snapshot of the current page for health checks."""
        if not self.client:
            return {}

        try:
            result = self.client.call("execute_js", {
                "script": """(() => JSON.stringify({
                    url: window.location.href,
                    title: document.title || "",
                    text: (document.body ? document.body.innerText : "").replace(/\\s+/g, " ").trim().slice(0, 2500)
                }))()"""
            })
            if isinstance(result, str):
                return json.loads(result)
        except Exception:
            pass
        return {}

    def detect_page_issue(self):
        """Detect obvious block or interstitial pages that should not be extracted."""
        snapshot = self.get_page_snapshot()
        url = str(snapshot.get("url", "")).lower()
        title = str(snapshot.get("title", "")).lower()
        text = str(snapshot.get("text", "")).lower()

        reddit_block_markers = [
            "blocked by mistake",
            "request has been blocked",
            "you've been blocked by network security",
            "whoa there, pardner",
            "for some reason reddit can't be reached",
            "for some reason reddit cannot be reached",
        ]

        if "reddit.com" in url:
            for marker in reddit_block_markers:
                if marker in title or marker in text:
                    return "reddit_block"

        return None

    def build_reddit_search_url(self, query, subreddit="", sort="relevance", time_filter="all"):
        """Build a canonical Reddit search URL for global or subreddit-scoped topic discovery."""
        query = (query or "").strip()
        subreddit = (subreddit or "").strip().lstrip("r/").strip("/")
        sort = (sort or "relevance").strip()
        time_filter = (time_filter or "all").strip()

        encoded_query = urlparse.quote_plus(query)
        encoded_subreddit = urlparse.quote(subreddit)

        if encoded_subreddit:
            return (
                f"https://www.reddit.com/r/{encoded_subreddit}/search/"
                f"?q={encoded_query}&restrict_sr=on&sort={urlparse.quote(sort)}&t={urlparse.quote(time_filter)}"
            )

        return (
            f"https://www.reddit.com/search/"
            f"?q={encoded_query}&sort={urlparse.quote(sort)}&t={urlparse.quote(time_filter)}"
        )

    def run_navigation_checks(self, intended_url=""):
        """Run lightweight checks after navigation and stop on obvious bad pages."""
        time.sleep(1)
        hil_reason = detect_hil_needed(self.client)

        snapshot = self.get_page_snapshot()
        current_url = str(snapshot.get("url", "")).lower()

        if current_url and ("login" in current_url or "signin" in current_url):
            if "login" not in intended_url.lower() and "signin" not in intended_url.lower():
                hil_reason = "login"

        if hil_reason == "captcha":
            hil_pause("Captcha detected! Please solve it in the browser.")
        elif hil_reason == "login":
            hil_pause("Login page detected! Please sign in.")

        page_issue = self.detect_page_issue()
        if page_issue == "reddit_block":
            raise RuntimeError(
                "Reddit returned a block/interstitial page instead of the discussion thread. "
                "Try again with a persistent browser profile, proxy rotation, or headed mode."
            )

    def resolve_template(self, text):
        """Replace {variable.key} placeholders with values from context."""
        if not isinstance(text, str):
            return text
        for var_name, var_data in self.context.items():
            if isinstance(var_data, list) and len(var_data) > 0 and isinstance(var_data[0], dict):
                # Data is array of dicts (typical for LLM extraction list results). Safely map {var.key} to first item.
                for key, val in var_data[0].items():
                    placeholder = f"{{{var_name}.{key}}}"
                    text = text.replace(placeholder, str(val) if val else "")
                text = text.replace(f"{{{var_name}}}", str(var_data))
            elif isinstance(var_data, dict):
                for key, val in var_data.items():
                    placeholder = f"{{{var_name}.{key}}}"
                    text = text.replace(placeholder, str(val) if val else "")
            else:
                text = text.replace(f"{{{var_name}}}", str(var_data))
        return text

    def resolve_selector_reference(self, selector):
        """Resolve selector catalog keys like 'reddit.post_title' into real selectors."""
        if not isinstance(selector, str):
            return selector

        selector = selector.strip()
        if selector in self.selectors:
            if self.selector_cache:
                verified = self.selector_cache.get_verified_selector(self.client, selector)
                if verified:
                    return verified

            entry = self.selectors.get(selector, {})
            resolved = entry.get("selector")
            if resolved:
                return resolved

        return self.resolve_logical_selector(selector)

    def resolve_logical_selector(self, selector):
        """Translate logical IDs like 'story:N' into bulletproof XPath/CSS."""
        if not isinstance(selector, str):
            return selector

        # Hacker News Adapter (XPath based for precision indexing)
        # story:N -> The Nth article title row
        story_match = re.match(r"^story:(\d+)$", selector)
        if story_match:
            n = story_match.group(1)
            return f"xpath=(//tr[contains(@class, 'athing')])[{n}]"

        # metadata:N -> The subtext row for the Nth article
        meta_match = re.match(r"^metadata:(\d+)$", selector)
        if meta_match:
            n = meta_match.group(1)
            return f"xpath=(//tr[contains(@class, 'athing')])[{n}]/following-sibling::tr[1]"

        # comments:N -> The comments link for the Nth article
        comments_match = re.match(r"^comments:(\d+)$", selector)
        if comments_match:
            n = comments_match.group(1)
            # HN Specific: Target the link that actually goes to the discussion thread
            return f"xpath=(//tr[contains(@class, 'athing')])[{n}]/following-sibling::tr[1]//a[contains(@href, 'item?id=') and (contains(text(), 'comment') or contains(text(), 'discuss'))]"

        # comment:N -> The Nth comment in a thread
        comment_match = re.match(r"^comment:(\d+)$", selector)
        if comment_match:
            n = comment_match.group(1)
            return f"xpath=(//table[contains(@class, 'comment-tree')]//tr[contains(@class, 'comtr')])[{n}]"

        # SELF-HEALING: If LLM hallucinates literal catalog keys into the 'prompt' field
        if selector == "google.first_result": return "h3.LC20lb"
        if selector == "google.reddit_result_link": return "a[jsname='UWckNb'][href*='reddit.com']"
        if selector == "google.hn_result_link": return "a[jsname='UWckNb'][href*='news.ycombinator.com']"

        return selector

    def execute_step(self, step):
        """Execute a single recipe step. Returns True on success."""
        action = step["action"]
        step_id = step.get("id", "?")
        narrate = step.get("narrate")
        save_as = step.get("save_as")

        if narrate:
            resolved_narrate = self.resolve_template(narrate)
            print(f"  {YELLOW}[Step {step_id}] {resolved_narrate}{RESET}")

        try:
            result = None

            # ─── HIL: Manual pause ───
            if action == "hil_pause":
                hil_pause(narrate or "Human intervention needed")
                return True

            # ─── Navigation ───
            elif action == "browse":
                url = self.resolve_template(step["url"])
                self.client.call("browse", {"url": url})
                self.run_navigation_checks(url)

            elif action == "wait":
                state = step.get("state", "domcontentloaded")
                self.client.call("wait_for_load_state", {"state": state})

            elif action == "wait_selector":
                selector = self.resolve_selector_reference(self.resolve_template(step["selector"]))
                # Use selector cache if available
                if self.selector_cache:
                    verified = self.selector_cache.verify_selector(self.client, selector)
                    if not verified:
                        print(f"  {YELLOW}  [Cache] Selector not found, trying heal...{RESET}")
                        # Try to find the selector key for healing
                        for key, entry in self.selectors.items():
                            if entry.get("selector") == selector:
                                healed = self.selector_cache.heal_selector(
                                    self.client, key, selector, entry.get("fallback")
                                )
                                if healed:
                                    selector = healed
                                break
                self.client.call("wait_for_selector", {"selector": selector, "state": "visible"})

            elif action == "scroll":
                amount = step.get("amount", 600)
                self.client.call("scroll", {"amount": amount})

            elif action == "open_tab":
                self.client.call("open_tab", {})

            elif action == "switch_tab":
                self.client.call("switch_tab", {"index": step["index"]})

            # ─── Execution ───
            elif action == "js_from_selector":
                selector_id = step.get("selector_id")
                if not selector_id or selector_id not in self.selectors:
                    print(f"  {RED}[Step {step_id}] Error: selector_id '{selector_id}' not found in registry.{RESET}")
                    return False

                sel_data = self.selectors[selector_id]
                script = sel_data.get("script")

                if not script:
                    # Auto-map simple selectors to JS based on extract attributes
                    sel_str = sel_data.get("selector")
                    if sel_str:
                        extracts = sel_data.get("extract", ["innerText"])
                        if "href" in extracts and "innerText" not in extracts:
                            script = f"(() => {{ const el = document.querySelector(\"{sel_str}\"); return JSON.stringify(el ? el.href : null); }})()"
                        elif "href" in extracts and "innerText" in extracts:
                            script = f"(() => {{ const el = document.querySelector(\"{sel_str}\"); return JSON.stringify(el ? {{text: el.innerText.trim(), href: el.href}} : null); }})()"
                        else:
                            script = f"(() => {{ const el = document.querySelector(\"{sel_str}\"); return JSON.stringify(el ? el.innerText.trim() : null); }})()"
                    else:
                        print(f"  {RED}[Step {step_id}] Error: '{selector_id}' has no script or selector.{RESET}")
                        return False

                script = self.resolve_template(script)
                result = self.client.call("execute_js", {"script": script})

            elif action == "js":
                code = self.resolve_template(step["code"])
                result = self.client.call("execute_js", {"script": code})

            elif action == "search":
                selector = self.resolve_selector_reference(self.resolve_template(step.get("selector", "textarea#APjFqb")))
                query = self.resolve_template(step["query"])
                self.client.call("fill_form", {
                    "fields": [{"selector": selector, "value": query, "type": "textbox"}]
                })
                time.sleep(0.5)
                self.client.call("press_key", {"key": "Enter"})

            elif action == "search_reddit":
                query = self.resolve_template(step["query"])
                subreddit = self.resolve_template(step.get("subreddit", ""))
                sort = self.resolve_template(step.get("sort", "relevance"))
                time_filter = self.resolve_template(step.get("time", "all"))
                search_url = self.build_reddit_search_url(query, subreddit, sort, time_filter)
                self.client.call("browse", {"url": search_url})
                self.run_navigation_checks(search_url)
                result = json.dumps({
                    "url": search_url,
                    "query": query,
                    "subreddit": subreddit,
                    "sort": sort,
                    "time": time_filter,
                })

            elif action == "click":
                selector_str = self.resolve_template(step.get("selector") or step.get("prompt"))
                selector_str = self.resolve_selector_reference(selector_str)
                # Hacker News and Reddit Navigation Optimization: "Ghost Click" Fix
                # If we are clicking on a result link, prefer extracting href and direct goto
                is_hn_link = "item?id=" in selector_str and ("news.ycombinator.com" in selector_str or "item?id=" in selector_str)
                is_reddit_link = "reddit.com" in selector_str or "reddit_result_link" in selector_str
                is_google_result = "LC20lb" in selector_str or "google.first_result" in selector_str or "h3" in selector_str

                if is_hn_link or is_reddit_link or is_google_result:
                    try:
                        current_url = self.client.call("execute_js", {"script": "window.location.href"})
                        if current_url and isinstance(current_url, str):
                            selector_json = json.dumps(selector_str)
                            href = self.client.call("execute_js", {"script": f"""(() => {{
                                const sel = {selector_json};
                                let el = null;
                                if (sel.startsWith("xpath=")) {{
                                    const xpath = sel.substring(6);
                                    el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                }} else {{
                                    el = document.querySelector(sel);
                                }}

                                if (!el) return "";
                                // If inside a Google result, climb to the anchor tag
                                if (el.tagName !== 'A') el = el.closest('a') || el;
                                let h = el.getAttribute("href") || "";

                                // Clean Google tracking URLs if present
                                if (h.includes("/url?q=")) {{
                                    try {{
                                        const u = new URL(h.startsWith("/") ? `https://www.google.com${{h}}` : h);
                                        h = decodeURIComponent(u.searchParams.get("q") || "");
                                        h = h.split("&")[0];
                                    }} catch(e) {{ const m = h.match(/q=([^&]+)/); h = m ? decodeURIComponent(m[1]) : h; }}
                                }}
                                return h;
                            }})()"""})
                            if href and len(href) > 2:
                                if is_hn_link:
                                    target_url = href if href.startswith("http") else f"https://news.ycombinator.com/{href}"
                                elif is_reddit_link:
                                    # Keep Reddit URLs on the canonical host. Forcing old.reddit can land on
                                    # block/interstitial pages and poison downstream extraction.
                                    target_url = href if href.startswith("http") else f"https://www.reddit.com{href}"
                                    target_url = target_url.replace("://old.reddit.com", "://www.reddit.com")
                                    target_url = target_url.replace("://reddit.com", "://www.reddit.com")
                                else:
                                    # Generic Google click fallback (fixes hijacking universally)
                                    target_url = href if href.startswith("http") else f"https://www.google.com{href}"

                                print(f"  {CYAN}  [AI] Bulletproof Navigation: Direct GOTO {target_url}{RESET}")
                                self.client.call("browse", {"url": target_url})
                                self.run_navigation_checks(target_url)
                                result = {"status": "success", "action": "goto", "url": target_url}
                            else:
                                result = self.client.call("click", {"prompt": selector_str})
                        else:
                            result = self.client.call("click", {"prompt": selector_str})
                    except Exception as e:
                        print(f"  {DIM}  [AI] Fallback to raw click: {e}{RESET}")
                        result = self.client.call("click", {"prompt": selector_str})
                else:
                    result = self.client.call("click", {"prompt": selector_str})
                time.sleep(1)

            elif action == "type":
                selector_str = self.resolve_template(step.get("selector") or step.get("prompt"))
                selector_str = self.resolve_selector_reference(selector_str)
                text = self.resolve_template(step.get("text", ""))

                result = self.client.call("type", {"prompt": selector_str, "text": text})
                time.sleep(1)

            elif action == "extract":
                schema = step.get("schema", {})
                instruction = step.get("instruction", "")
                if not schema:
                     print(f"  {RED}[Step {step_id}] Error: 'extract' requires a 'schema' object.{RESET}")
                     return False

                page_issue = self.detect_page_issue()
                if page_issue == "reddit_block":
                    raise RuntimeError(
                        "Current Reddit page is a block/interstitial page, so extraction would be unreliable."
                    )

                # Extract uses AI, give it a spinner
                ext_spinner = Spinner("Extracting data via LLM Map-Reduce...", color=C.MAGENTA)
                ext_spinner.start()
                try:
                    payload = {"schema": schema}
                    if instruction:
                        payload["instruction"] = instruction
                    if "selector" in step:
                        payload["selector"] = self.resolve_selector_reference(self.resolve_template(step["selector"]))

                    result = self.client.call("extract", payload)
                    ext_spinner.stop("Data extracted successfully")
                except Exception as e:
                    ext_spinner.fail(f"Extraction failed: {e}")
                    raise e

            elif action == "type_to_notepad":
                if "selector" not in step:
                    print(f"  {DIM}  [Step {step_id}] Skipping type_to_notepad — no selector provided.{RESET}")
                    return True
                selector = self.resolve_template(step["selector"])
                selector = self.resolve_selector_reference(selector)
                text = self.resolve_template(step.get("template", step.get("text", "")))
                speed = step.get("speed_ms", 15)

                self.client.call("execute_js", {
                    "script": f"document.querySelector('{selector}').value = '';"
                })

                safe_text = text.replace("`", "\\`")
                typing_js = f"""
                    const ta = document.querySelector('{selector}');
                    const text = `{safe_text}`;
                    let i = 0;
                    function typeChar() {{
                        if (i < text.length) {{
                            ta.value += text.charAt(i);
                            ta.scrollTop = ta.scrollHeight;
                            i++;
                            setTimeout(typeChar, {speed});
                        }}
                    }}
                    typeChar();
                """
                self.client.call("execute_js", {"script": typing_js})
                typing_wait = (len(text) * speed / 1000) + 2
                time.sleep(typing_wait)

            elif action == "sleep":
                time.sleep(step.get("seconds", 1))

            else:
                print(f"  {RED}[Step {step_id}] Unknown action: {action}{RESET}")
                return True

            # Save result to context
            if save_as and result:
                try:
                    parsed = json.loads(result)
                    self.context[save_as] = parsed
                    print(f"  {DIM}  Saved to ${save_as}: {json.dumps(parsed, indent=2)[:500]}{RESET}")
                except (json.JSONDecodeError, TypeError):
                    self.context[save_as] = {"raw": str(result)[:500]}
                    print(f"  {DIM}  Saved to ${save_as}: {str(result)[:300]}{RESET}")
            elif result and action == "js":
                # Print JS results even without save_as so user can see the output
                result_str = str(result)
                if len(result_str) > 20:  # Skip trivial results like 'found', 'null'
                    print(f"  {GREEN}  Result: {result_str[:500]}{RESET}")

            pace = step.get("pace", 1.5)
            time.sleep(pace)
            return True

        except Exception as e:
            print(f"  {RED}[Step {step_id}] Error: {e}{RESET}")
            retries = step.get("retries", 1)
            if retries > 0:
                print(f"  {DIM}  Retrying step {step_id}...{RESET}")
                step["retries"] = retries - 1
                time.sleep(2)
                return self.execute_step(step)
            return False

    def run(self, recipe_path, resume_from=0, proxy=None):
        """Load and execute a JSON recipe file, with checkpoint support."""
        with open(recipe_path) as f:
            recipe = json.load(f)

        name = recipe.get("name", "Unnamed Task")
        steps = recipe.get("steps", [])
        total = len(steps)

        # Checkpoint manager
        checkpoint = CheckpointManager(recipe_path)

        # Check for existing checkpoint
        if resume_from == 0:
            existing = checkpoint.load()
            if existing:
                saved_step = existing["step_index"]
                saved_name = existing.get("recipe_name", "")
                print(f"\n{YELLOW}  Found checkpoint for \"{saved_name}\" at step {saved_step + 1}/{total}.{RESET}")
                try:
                    answer = input(f"  {YELLOW}  Resume from step {saved_step + 1}? [Y/n]: {RESET}").strip().lower()
                    if answer != 'n':
                        resume_from = saved_step + 1
                        self.context = existing.get("context", {})
                        print(f"  {GREEN}  Resuming from step {resume_from}...{RESET}\n")
                except EOFError:
                    resume_from = saved_step + 1
                    self.context = existing.get("context", {})

        print()
        if resume_from > 0:
            info_msg(f"Resuming from step {resume_from}")

        # Inject proxy if provided
        env_vars = {}
        if proxy:
            env_vars["HTTP_PROXY"] = proxy["server"]
            env_vars["HTTPS_PROXY"] = proxy["server"]
            env_vars["http_proxy"] = proxy["server"]
            env_vars["https_proxy"] = proxy["server"]
            if proxy.get("username"):
                env_vars["PROXY_USERNAME"] = proxy["username"]
                env_vars["PROXY_PASSWORD"] = proxy.get("password", "")
            print(f"{DIM}  [NETWORK] Using IP/Proxy: {proxy['server']}{RESET}")

        from examples.client import WEBGhostingClient
        self.client = WEBGhostingClient(env_overrides=env_vars)

        try:
            for i, step in enumerate(steps):
                # Skip already-completed steps (resume)
                if i < resume_from:
                    continue

                success = self.execute_step(step)
                if not success:
                    # Save checkpoint at failure point
                    checkpoint.save(i, self.context, name)
                    print(f"\n{RED}  Recipe aborted at step {step.get('id', i+1)}.{RESET}")
                    print(f"{DIM}  Checkpoint saved. Run with --resume to continue.{RESET}")
                    return False

                # Save checkpoint after each successful step
                checkpoint.save(i + 1, self.context, name)

            # Success — clear checkpoint
            checkpoint.clear()

            # Report selector healing stats
            if self.selector_cache and self.selector_cache.healed_count > 0:
                print(f"  {GREEN}[Cache] {self.selector_cache.healed_count} selector(s) self-healed and updated.{RESET}")

            # Print final results summary
            if self.context:
                results_panel(self.context)

            success_msg("Recipe completed successfully.")
            return True

        except KeyboardInterrupt:
            # Save checkpoint on Ctrl+C
            checkpoint.save(i if 'i' in dir() else 0, self.context, name)
            print(f"\n{YELLOW}  Recipe paused by user. Checkpoint saved.{RESET}")
            print(f"{DIM}  Run with --resume to continue from step {i+1 if 'i' in dir() else 1}.{RESET}")
            return False
        finally:
            self.client.close()

    def run_command(self, command):
        """Generate a recipe from natural language and execute it."""
        run_start = time.time()
        print()

        # Load and ROTATE proxy (random pick for IP rotation)
        proxy = None
        try:
            import random
            if os.environ.get("PROXY_LIST"):
                proxies = [p.strip() for p in os.environ.get("PROXY_LIST").split(',') if p.strip()]
                if proxies:
                    proxy = parse_proxy_config(random.choice(proxies))
                    info_msg(f"Rotating IP: {proxy['server']}")
            elif os.path.exists("proxies.txt"):
                with open("proxies.txt", "r") as pf:
                    proxies = [l.strip() for l in pf if l.strip()]
                if proxies:
                    proxy = parse_proxy_config(random.choice(proxies))
                    info_msg(f"Rotating IP: {proxy['server']}")
        except Exception:
            pass

        with proxy_environment(proxy):
            recipe = generate_recipe(command, self.selectors)
            if not recipe:
                error_msg("Failed to generate recipe.")
                return False

            tmp_path = os.path.join(tempfile.gettempdir(), f"webghosting_recipe_{int(time.time())}.json")
            with open(tmp_path, 'w') as f:
                json.dump(recipe, f, indent=2)

            try:
                success = self.run(tmp_path, proxy=proxy)

                # [OPTIMIZATION] Self-Improving Usage Feedback Loop
                if success and recipe:
                    usage_stats = load_selector_usage()
                    updated = False
                    for step in recipe.get('steps', []):
                        action = step.get('action')
                        sel_id = step.get('selector_id')
                        # Log explicit JS selector usage
                        if action == 'js_from_selector' and sel_id:
                            usage_stats[sel_id] = usage_stats.get(sel_id, 1) + 1
                            updated = True
                        # Also log if the LLM hallucinated a search input for search/type tools
                        elif action in ['type', 'search'] and sel_id:
                             usage_stats[sel_id] = usage_stats.get(sel_id, 1) + 1
                             updated = True

                    if updated:
                        save_selector_usage(usage_stats)

                # Show run statistics
                elapsed = time.time() - run_start
                steps_count = len(recipe.get('steps', []))
                stats_summary(_token_usage, elapsed, steps_count, recipe.get('name', 'Unknown'))

                return success
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def list_recipes():
    """List all available recipes (built-in + user plugins)."""
    for recipes_dir in _get_all_recipe_dirs():
        source = "User Plugins" if recipes_dir == USER_RECIPES_DIR else "Built-in"
        files = glob.glob(os.path.join(recipes_dir, '*.json'))
        if not files:
            continue
        print(f"\n{CYAN}{BOLD}Available Recipes ({source}):{RESET}\n")
        for f in sorted(files):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                name = data.get("name", "Unnamed")
                steps = len(data.get("steps", []))
                print(f"  {GREEN}{os.path.basename(f)}{RESET}")
                print(f"  {DIM}{name} ({steps} steps){RESET}\n")
            except:
                print(f"  {RED}{os.path.basename(f)} (invalid JSON){RESET}\n")
    print(f"\n{DIM}  Plugin directory: {USER_PLUGIN_DIR}{RESET}")
    print(f"{DIM}  Drop .json files into selectors/ or recipes/ to extend.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        list_recipes()
        print(f"\n{DIM}Usage:")
        print(f"  python3 -m orchestrator.orchestrator <recipe.json>")
        print(f"  python3 -m orchestrator.orchestrator --run \"your command\"")
        print(f"  python3 -m orchestrator.orchestrator --resume{RESET}\n")
        sys.exit(0)

    # --resume: find and resume from last checkpoint
    if sys.argv[1] == "--resume":
        checkpoints = CheckpointManager.find_any()
        if not checkpoints:
            print(f"{DIM}No checkpoints found.{RESET}")
            sys.exit(0)
        # Use the most recent checkpoint
        latest = max(checkpoints, key=lambda c: c.get("timestamp", ""))
        recipe_path = latest["recipe_path"]
        step_idx = latest["step_index"]
        print(f"{CYAN}  Resuming \"{latest.get('recipe_name', 'Unnamed')}\" from step {step_idx + 1}...{RESET}")
        orchestrator = RecipeOrchestrator()
        orchestrator.context = latest.get("context", {})
        success = orchestrator.run(recipe_path, resume_from=step_idx)
        sys.exit(0 if success else 1)

    # --run: natural language → auto-generate → execute → cleanup
    if sys.argv[1] == "--run":
        if len(sys.argv) < 3:
            print(f"{RED}Usage: --run \"Go to HN and find top story\"{RESET}")
            sys.exit(1)
        command = " ".join(sys.argv[2:])
        orchestrator = RecipeOrchestrator()
        success = orchestrator.run_command(command)
        sys.exit(0 if success else 1)

    # Recipe file mode
    recipe_file = sys.argv[1]
    if not os.path.isabs(recipe_file):
        candidate = os.path.join(os.path.dirname(__file__), recipe_file)
        if os.path.exists(candidate):
            recipe_file = candidate
        else:
            candidate2 = os.path.join(os.path.dirname(__file__), 'recipes', recipe_file)
            if os.path.exists(candidate2):
                recipe_file = candidate2

    if not os.path.exists(recipe_file):
        print(f"{RED}Recipe not found: {recipe_file}{RESET}")
        sys.exit(1)

    orchestrator = RecipeOrchestrator()
    success = orchestrator.run(recipe_file)
    sys.exit(0 if success else 1)
