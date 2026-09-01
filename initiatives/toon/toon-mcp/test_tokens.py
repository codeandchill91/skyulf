#!/usr/bin/env python3
"""Token savings benchmark and test verification for TOON MCP Server."""

import json
import tiktoken
from toon_py import encode

def run_token_benchmark():
    enc = tiktoken.get_encoding("cl100k_base")

    benchmarks = {
        "1. Security Scan Findings (50 items)": {
            "repository": "dxdl-development-cleanup",
            "scanner": "Codacy-SRM",
            "findings": [
                {
                    "id": f"SEC-{i:03d}",
                    "rule": "SQL_INJECTION" if i % 2 == 0 else "XSS_VULNERABILITY",
                    "severity": "CRITICAL" if i % 3 == 0 else "HIGH",
                    "file": f"src/services/handler_{i}.py",
                    "line": 10 + i * 4,
                    "status": "OPEN",
                }
                for i in range(1, 51)
            ],
        },
        "2. GitHub PR Commits (30 items)": {
            "pull_request": 42,
            "title": "Refactor data ingestion pipeline",
            "commits": [
                {
                    "sha": f"a{i:06x}f92b",
                    "author": "developer@company.com",
                    "message": f"feat(core): update step {i} data processing",
                    "additions": 15 + i,
                    "deletions": 3 + (i % 5),
                }
                for i in range(1, 31)
            ],
        },
        "3. Jira/ServiceNow Records (25 items)": {
            "project": "INFRA",
            "tickets": [
                {
                    "key": f"INFRA-{1000 + i}",
                    "summary": f"Upgrade node worker pool {i}",
                    "priority": "P2",
                    "status": "In Progress" if i % 2 == 0 else "Done",
                    "assignee": f"user{i}@corp.net",
                }
                for i in range(1, 26)
            ],
        },
    }

    header = f"{'Dataset':<38} | {'JSON (Pretty)':<14} | {'JSON (Min)':<12} | {'TOON':<8} | {'Savings vs Pretty':<18} | {'Savings vs Min':<15}"
    print("\n" + "=" * len(header))
    print("  TOON Token Savings Benchmark (cl100k_base tokenizer)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for name, data in benchmarks.items():
        json_pretty = json.dumps(data, indent=2)
        json_min = json.dumps(data, separators=(",", ":"))
        toon_text = encode(data)

        tok_pretty = len(enc.encode(json_pretty))
        tok_min = len(enc.encode(json_min))
        tok_toon = len(enc.encode(toon_text))

        saving_pretty = ((tok_pretty - tok_toon) / tok_pretty) * 100
        saving_min = ((tok_min - tok_toon) / tok_min) * 100

        print(
            f"{name:<38} | {tok_pretty:<14} | {tok_min:<12} | {tok_toon:<8} | {saving_pretty:>16.1f}% | {saving_min:>13.1f}%"
        )
    print("=" * len(header) + "\n")

if __name__ == "__main__":
    run_token_benchmark()
