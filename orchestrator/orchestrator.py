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

import sys, os, json, time, glob, tempfile, hashlib, requests
from datetime import datetime, timezone

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from examples.client import WEBGhostingClient, GREEN, RED, YELLOW, CYAN, DIM, BOLD, RESET

CHECKPOINT_DIR = os.path.join(tempfile.gettempdir(), "webghosting_checkpoints")

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

LOGIN_INDICATORS = [
    "sign in", "log in", "login", "signin",
    "enter your password", "authentication"
]


def detect_hil_needed(client):
    """Check if the current page has captcha or login that needs human intervention."""
    try:
        result = client.call("execute_js", {
            "script": "document.title + ' ' + document.body.innerText.substring(0, 500)"
        })
        if not result:
            return None
        text = str(result).lower()

        for indicator in CAPTCHA_INDICATORS:
            if indicator in text:
                return "captcha"
        for indicator in LOGIN_INDICATORS:
            if indicator in text:
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

EXACT action formats (use these EXACTLY):

{"id": 1, "action": "browse", "url": "https://example.com", "narrate": "Opening site..."}
{"id": 2, "action": "wait", "state": "domcontentloaded"}
{"id": 3, "action": "js", "code": "document.querySelector('h1').innerText", "save_as": "title", "narrate": "Reading title..."}
{"id": 4, "action": "scroll", "amount": 600}
{"id": 5, "action": "open_tab"}
{"id": 6, "action": "switch_tab", "index": 0}
{"id": 7, "action": "search", "selector": "textarea#APjFqb", "query": "search term", "narrate": "Searching..."}
{"id": 8, "action": "wait_selector", "selector": "textarea#area"}
{"id": 9, "action": "type_to_notepad", "selector": "textarea#area", "template": "text with {var.key}", "speed_ms": 15, "narrate": "Typing..."}
{"id": 10, "action": "sleep", "seconds": 2}
{"id": 11, "action": "hil_pause", "narrate": "Please solve the captcha"}

Pre-cached selectors you can use in JS code:
{selectors}

Variable system: save_as stores JS results as JSON. Reference via {variable.key} in later steps.
For JS code that returns data, wrap in IIFE: (() => { ... return JSON.stringify({...}); })()

Rules:
1. Output ONLY valid JSON. No markdown, no explanation, no backtick fences.
2. Top-level keys: "name" (string) and "steps" (array)
3. Every step MUST have "id" and "action". Use "narrate" for user-facing steps.
4. "browse" MUST have "url". "js" MUST have "code". "search" MUST have "query".
5. For Hacker News use tr.athing selectors. For Reddit use shreddit-comment[depth] selectors.
6. Keep recipes minimal."""


def generate_recipe(command, selectors_db):
    """Use LLM to generate a JSON recipe from a natural language command."""
    api_key = os.environ.get("AI_API_KEY")
    base_url = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("AI_MODEL", "gpt-4o")

    if not api_key:
        print(f"{RED}ERROR: AI_API_KEY not set{RESET}")
        return None

    selectors_summary = json.dumps(selectors_db, indent=2)
    system_prompt = RECIPE_SYSTEM_PROMPT.replace("{selectors}", selectors_summary)

    print(f"{CYAN}  Generating recipe for: {BOLD}\"{command}\"{RESET}")
    print(f"{DIM}  Asking LLM to create execution plan...{RESET}")

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": command}
                ],
                "temperature": 0.2,
                "max_tokens": 2000
            },
            timeout=30
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        recipe = json.loads(content)
        steps = len(recipe.get("steps", []))
        print(f"  {GREEN}Recipe generated: \"{recipe.get('name', 'Unnamed')}\" ({steps} steps){RESET}")
        return recipe

    except requests.exceptions.RequestException as e:
        print(f"{RED}  LLM API error: {e}{RESET}")
        return None
    except json.JSONDecodeError as e:
        print(f"{RED}  Failed to parse LLM response as JSON: {e}{RESET}")
        print(f"{DIM}  Raw response: {content[:300]}{RESET}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Core Orchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RecipeOrchestrator:
    """Executes JSON recipe files step-by-step via WEBGhostingClient.

    Features:
      - Selector caching + self-healing (Stagehand pattern)
      - Checkpoint/resume on crash (LangGraph pattern)
      - Human-in-the-loop for captchas (Playwright MCP pattern)
    """

    def __init__(self):
        self.client = None
        self.context = {}
        self.selectors = {}
        self.selector_cache = None

        # Load selectors from selectors/ directory
        selectors_dir = os.path.join(os.path.dirname(__file__), 'selectors')
        if os.path.isdir(selectors_dir):
            for f in sorted(glob.glob(os.path.join(selectors_dir, '*.json'))):
                with open(f) as fp:
                    data = json.load(fp)
                    self.selectors.update(data)
            self.selector_cache = SelectorCache(self.selectors, selectors_dir)

    def resolve_template(self, text):
        """Replace {variable.key} placeholders with values from context."""
        if not isinstance(text, str):
            return text
        for var_name, var_data in self.context.items():
            if isinstance(var_data, dict):
                for key, val in var_data.items():
                    placeholder = f"{{{var_name}.{key}}}"
                    text = text.replace(placeholder, str(val) if val else "")
            else:
                text = text.replace(f"{{{var_name}}}", str(var_data))
        return text

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
                # Auto-HIL: check for captcha/login after navigation
                time.sleep(1)
                hil_reason = detect_hil_needed(self.client)
                if hil_reason == "captcha":
                    hil_pause("Captcha detected! Please solve it in the browser.")
                elif hil_reason == "login":
                    hil_pause("Login page detected! Please sign in.")

            elif action == "wait":
                state = step.get("state", "domcontentloaded")
                self.client.call("wait_for_load_state", {"state": state})

            elif action == "wait_selector":
                selector = self.resolve_template(step["selector"])
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
            elif action == "js":
                code = self.resolve_template(step["code"])
                result = self.client.call("execute_js", {"script": code})

            elif action == "search":
                selector = self.resolve_template(step.get("selector", "textarea#APjFqb"))
                query = self.resolve_template(step["query"])
                self.client.call("fill_form", {
                    "fields": [{"selector": selector, "value": query, "type": "textbox"}]
                })
                time.sleep(0.5)
                self.client.call("press_key", {"key": "Enter"})

            elif action == "type_to_notepad":
                selector = self.resolve_template(step["selector"])
                text = self.resolve_template(step["template"])
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
                    print(f"  {DIM}  Saved to ${save_as}: {json.dumps(parsed)[:100]}...{RESET}")
                except (json.JSONDecodeError, TypeError):
                    self.context[save_as] = {"raw": str(result)[:500]}

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

    def run(self, recipe_path, resume_from=0):
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

        print(f"\n{CYAN}{'━'*60}")
        print(f"  Recipe: {BOLD}{name}{RESET}")
        start_label = f"  Steps: {total}" if resume_from == 0 else f"  Steps: {total} (resuming from {resume_from})"
        print(f"{CYAN}{start_label}")
        print(f"{'━'*60}{RESET}\n")

        self.client = WEBGhostingClient()

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

            print(f"\n{GREEN}{BOLD}  Recipe completed successfully.{RESET}\n")
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
        recipe = generate_recipe(command, self.selectors)
        if not recipe:
            print(f"{RED}  Failed to generate recipe.{RESET}")
            return False

        tmp_path = os.path.join(tempfile.gettempdir(), f"webghosting_recipe_{int(time.time())}.json")
        with open(tmp_path, 'w') as f:
            json.dump(recipe, f, indent=2)
        print(f"{DIM}  Temporary recipe: {tmp_path}{RESET}\n")

        try:
            return self.run(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                print(f"{DIM}  Temporary recipe cleaned up.{RESET}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def list_recipes():
    """List all available recipes."""
    recipes_dir = os.path.join(os.path.dirname(__file__), 'recipes')
    files = glob.glob(os.path.join(recipes_dir, '*.json'))
    if not files:
        print(f"{DIM}No recipes found in {recipes_dir}{RESET}")
        return
    print(f"\n{CYAN}{BOLD}Available Recipes:{RESET}\n")
    for f in sorted(files):
        with open(f) as fp:
            data = json.load(fp)
        name = data.get("name", "Unnamed")
        steps = len(data.get("steps", []))
        print(f"  {GREEN}{os.path.basename(f)}{RESET}")
        print(f"  {DIM}{name} ({steps} steps){RESET}\n")


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
