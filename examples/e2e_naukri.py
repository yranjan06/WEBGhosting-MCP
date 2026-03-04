#!/usr/bin/env python3
"""Naukri Job Search — E2E Benchmark"""

import sys, time, json
sys.path.insert(0, '.')
from examples.client import *

client = GhostMCPClient()

try:
    print(f"\n{CYAN}{'='*50}\n  Naukri: Data Engineering Job Extraction\n{'='*50}{RESET}\n")

    # Direct URL search (no LLM wasted on navigation)
    target = "https://www.naukri.com/data-engineering-jobs?k=data%20engineering"
    print(f"{YELLOW}[Action] Opening: {target}{RESET}")
    client.call("browse", {"url": target})
    client.call("wait_for_load_state", {"state": "networkidle"})
    time.sleep(5)

    # Extract
    print(f"\n{YELLOW}[Action] Extracting jobs (Map-Reduce)...{RESET}")
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "job_title": {"type": "string"},
                "company_name": {"type": "string"},
                "experience_required": {"type": "string"},
                "location": {"type": "string"},
                "skills_or_requirements": {"type": "string"}
            },
            "required": ["job_title", "company_name"]
        },
        "description": "Extract all job postings visible on the page"
    }
    res = client.call("extract", {"schema": schema})
    print(f"{GREEN}{res}{RESET}")
    print(f"\n{GREEN}Naukri benchmark complete!{RESET}")

except Exception as e:
    print(f"\n{RED}Error: {e}{RESET}")
finally:
    client.close()
