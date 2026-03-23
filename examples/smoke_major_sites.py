#!/usr/bin/env python3
"""
Run prompt-driven smoke tests against major public websites.

Usage:
    python3 examples/smoke_major_sites.py
    python3 examples/smoke_major_sites.py --list
    python3 examples/smoke_major_sites.py --sites hackernews,github,wikipedia
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".smoke-logs"

SMOKE_TESTS = {
    "hackernews": {
        "description": "Extract article metadata and comments from Hacker News",
        "prompt": "Open the Hacker News homepage. Extract the title and author of the 5th article. Then open the comments page for that same 5th article and extract the text of the first 2 comments.",
    },
    "github": {
        "description": "Extract repository metadata from GitHub",
        "prompt": "Open the GitHub repository microsoft/playwright and extract the repository name, description, and star count.",
    },
    "wikipedia": {
        "description": "Extract title and intro from Wikipedia",
        "prompt": "Open the Wikipedia article for Model Context Protocol and extract the article title and the first paragraph.",
    },
    "youtube": {
        "description": "Extract first-result metadata from YouTube search",
        "prompt": "Open YouTube search results for Model Context Protocol and extract the title and channel name of the first result.",
    },
    "amazon": {
        "description": "Extract first relevant product details from Amazon",
        "prompt": "Open Amazon and find iPhone 16. Extract the title, price, and rating of the first relevant result.",
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run WEBGhosting smoke tests against major websites.")
    parser.add_argument(
        "--sites",
        help="Comma-separated site keys to run. Default: all tests.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available smoke tests and exit.",
    )
    return parser.parse_args()


def selected_sites(raw_sites):
    if not raw_sites:
        return list(SMOKE_TESTS.keys())

    sites = [site.strip().lower() for site in raw_sites.split(",") if site.strip()]
    unknown = [site for site in sites if site not in SMOKE_TESTS]
    if unknown:
        raise SystemExit(f"Unknown smoke test(s): {', '.join(unknown)}")
    return sites


def ensure_env():
    required = ["AI_API_KEY", "AI_BASE_URL", "AI_MODEL"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ".\nSet them before running this smoke suite."
        )


def list_tests():
    print("Available smoke tests:")
    for name, config in SMOKE_TESTS.items():
        print(f"- {name}: {config['description']}")


def run_test(site):
    config = SMOKE_TESTS[site]
    prompt = config["prompt"]
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{site}.log"

    cmd = [
        sys.executable,
        "-m",
        "orchestrator.orchestrator",
        "--run",
        prompt,
    ]

    started = time.time()
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    duration = time.time() - started

    combined = result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr
    log_path.write_text(combined)

    passed = result.returncode == 0 and "Recipe completed successfully." in combined
    return {
        "site": site,
        "description": config["description"],
        "passed": passed,
        "returncode": result.returncode,
        "duration": duration,
        "log_path": log_path,
    }


def main():
    args = parse_args()

    if args.list:
        list_tests()
        return

    ensure_env()
    sites = selected_sites(args.sites)

    print("Running WEBGhosting smoke tests:")
    print(f"- Sites: {', '.join(sites)}")
    print(f"- Logs: {LOG_DIR}")

    passed = 0
    results = []

    for site in sites:
        print(f"\n[{site}] {SMOKE_TESTS[site]['description']}")
        result = run_test(site)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"  {status} in {result['duration']:.1f}s"
            f"  log={result['log_path']}"
        )
        if result["passed"]:
            passed += 1

    print("\nSummary")
    print(f"- Passed: {passed}/{len(results)}")
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"- {result['site']}: {status} ({result['duration']:.1f}s)")

    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
