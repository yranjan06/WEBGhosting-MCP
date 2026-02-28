#!/usr/bin/env python3
"""LinkedIn Job Search — E2E Benchmark"""

import sys, time, json
sys.path.insert(0, '.')
from examples.client import *

client = GoWebMCPClient()

try:
    print(f"\n{CYAN}{'='*50}\n  LinkedIn: Data Engineering Job Extraction\n{'='*50}{RESET}\n")

    # Step 1: Login (manual — LinkedIn requires auth)
    print(f"{YELLOW}[Action] Opening LinkedIn Login...{RESET}")
    client.call("browse", {"url": "https://www.linkedin.com/login"})
    client.call("wait_for_load_state", {"state": "domcontentloaded"})

    print(f"\n{CYAN}  MANUAL LOGIN REQUIRED (60 seconds){RESET}")
    print(f"{DIM}  Complete Google SSO in the browser window{RESET}")
    for i in range(60, 0, -1):
        sys.stdout.write(f"\r  Waiting... {i}s ")
        sys.stdout.flush()
        time.sleep(1)
    print()

    # Step 2: Navigate to search (direct URL)
    target = "https://www.linkedin.com/jobs/search/?keywords=Data%20Engineering"
    print(f"\n{YELLOW}[Action] Opening: {target}{RESET}")
    client.call("browse", {"url": target})
    client.call("wait_for_load_state", {"state": "domcontentloaded"})
    time.sleep(8)

    # Step 3: Extract
    print(f"\n{YELLOW}[Action] Extracting jobs (Map-Reduce)...{RESET}")
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "job_title": {"type": "string"},
                "company": {"type": "string"},
                "location": {"type": "string"},
                "posted_time": {"type": "string"}
            },
            "required": ["job_title", "company"]
        },
        "description": "Extract all Data Engineering job postings"
    }
    res = client.call("extract", {"schema": schema})
    print(f"{GREEN}{res}{RESET}")
    print(f"\n{GREEN}LinkedIn benchmark complete!{RESET}")

except Exception as e:
    print(f"\n{RED}Error: {e}{RESET}")
finally:
    client.close()
