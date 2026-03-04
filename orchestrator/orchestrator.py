#!/usr/bin/env python3
"""
GhostMCP Recipe Orchestrator

Executes JSON recipe files through the GhostMCP browser engine.
Replaces the need to write custom Python scripts for each task.

Usage:
    python3 -m orchestrator.orchestrator recipes/hn_reddit_linkedin.json
    python3 -m orchestrator.orchestrator --list
"""

import sys, os, json, time, glob, tempfile, requests

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from examples.client import GhostMCPClient, GREEN, RED, YELLOW, CYAN, DIM, BOLD, RESET


RECIPE_SYSTEM_PROMPT = """You are a GhostMCP Recipe Generator. Convert user commands into JSON recipes.

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

    # Build the prompt with available selectors
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

        # Clean up: remove markdown fences if LLM added them
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


class RecipeOrchestrator:
    """Executes JSON recipe files step-by-step via GhostMCPClient."""

    def __init__(self, selectors_path=None):
        self.client = None
        self.context = {}
        self.selectors = {}

        # Load selectors from selectors/ directory (merge all JSON files)
        selectors_dir = os.path.join(os.path.dirname(__file__), 'selectors')
        if os.path.isdir(selectors_dir):
            for f in sorted(glob.glob(os.path.join(selectors_dir, '*.json'))):
                with open(f) as fp:
                    data = json.load(fp)
                    self.selectors.update(data)
        elif selectors_path and os.path.exists(selectors_path):
            # Fallback: single selectors_db.json
            with open(selectors_path) as f:
                self.selectors = json.load(f)

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

            if action == "browse":
                url = self.resolve_template(step["url"])
                self.client.call("browse", {"url": url})

            elif action == "wait":
                state = step.get("state", "domcontentloaded")
                self.client.call("wait_for_load_state", {"state": state})

            elif action == "wait_selector":
                selector = self.resolve_template(step["selector"])
                self.client.call("wait_for_selector", {"selector": selector, "state": "visible"})

            elif action == "scroll":
                amount = step.get("amount", 600)
                self.client.call("scroll", {"amount": amount})

            elif action == "open_tab":
                self.client.call("open_tab", {})

            elif action == "switch_tab":
                self.client.call("switch_tab", {"index": step["index"]})

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

    def run(self, recipe_path):
        """Load and execute a JSON recipe file."""
        with open(recipe_path) as f:
            recipe = json.load(f)

        name = recipe.get("name", "Unnamed Task")
        steps = recipe.get("steps", [])
        total = len(steps)

        print(f"\n{CYAN}{'━'*60}")
        print(f"  Recipe: {BOLD}{name}{RESET}")
        print(f"{CYAN}  Steps: {total}")
        print(f"{'━'*60}{RESET}\n")

        self.client = GhostMCPClient()

        try:
            for i, step in enumerate(steps):
                success = self.execute_step(step)
                if not success:
                    print(f"\n{RED}  Recipe aborted at step {step.get('id', i+1)}.{RESET}")
                    return False

            print(f"\n{GREEN}{BOLD}  Recipe completed successfully.{RESET}\n")
            return True

        except KeyboardInterrupt:
            print(f"\n{YELLOW}  Recipe cancelled by user.{RESET}")
            return False
        finally:
            self.client.close()

    def run_command(self, command):
        """Generate a recipe from natural language and execute it."""
        recipe = generate_recipe(command, self.selectors)
        if not recipe:
            print(f"{RED}  Failed to generate recipe.{RESET}")
            return False

        # Save as temporary recipe
        tmp_path = os.path.join(tempfile.gettempdir(), f"ghostmcp_recipe_{int(time.time())}.json")
        with open(tmp_path, 'w') as f:
            json.dump(recipe, f, indent=2)
        print(f"{DIM}  Temporary recipe: {tmp_path}{RESET}\n")

        try:
            return self.run(tmp_path)
        finally:
            # Cleanup temporary recipe
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                print(f"{DIM}  Temporary recipe cleaned up.{RESET}")


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
        print(f"  python3 -m orchestrator.orchestrator --run \"your command here\"{RESET}\n")
        sys.exit(0)

    # --run mode: natural language command → auto-generate recipe → execute → cleanup
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

