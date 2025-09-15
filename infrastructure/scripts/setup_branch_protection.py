#!/usr/bin/env python3
"""
Setup required branch protection rules for this repository.

This script uses the GitHub REST API to configure required status checks and
review rules for branches like `main` and `develop`, matching the exact
workflow/job names present in this repo:

Required checks (contexts):
  - "Tests / Backend Unit/Smoke (cov gate)"
  - "Tests / Frontend CI"
  - "Integration Tests / integration"
  - "Type Check / mypy"
  - "📁 文件管理质量检查 / 🔍 文件质量检查"

Usage:
  export GITHUB_TOKEN=...  # repo admin token
  # Option A: Provide owner/repo explicitly
  python infrastructure/scripts/setup_branch_protection.py --owner <OWNER> --repo <REPO>
  # Option B: Auto-detect from local git remote
  python infrastructure/scripts/setup_branch_protection.py

Options:
  --branches "main,develop"        Comma-separated list of branch names
  --require-approvals N             Required approving review count (default: main=2, others=1)
  --admins-enforce/--no-admins-enforce  Enforce rules for admins (default: true on main, false on others)

Notes:
  - Requires the token to have: repo -> admin:repo_hook & repo:status permissions
  - Safe to run multiple times (idempotent PUT)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List

import json
import urllib.request


API_BASE = "https://api.github.com"


def _git_remote() -> str | None:
    try:
        url = (
            subprocess.check_output(["git", "remote", "get-url", "origin"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
        return url
    except Exception:
        return None


def _parse_remote(url: str) -> tuple[str, str] | None:
    # Support https and ssh formats
    # https://github.com/OWNER/REPO.git
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", url)
    if m:
        return m.group("owner"), m.group("repo")
    return None


def _http(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict | str]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.getcode()
            body = resp.read()
            try:
                return status, json.loads(body.decode("utf-8"))
            except Exception:
                return status, body.decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


def _required_contexts() -> List[str]:
    # Must match the exact workflow name and job name shown by GitHub Actions
    return [
        "Tests / Backend Unit/Smoke (cov gate)",
        "Tests / Frontend CI",
        "Integration Tests / integration",
        "Type Check / mypy",
        "📁 文件管理质量检查 / 🔍 文件质量检查",
    ]


@dataclass
class BranchRule:
    name: str
    approvals: int
    enforce_admins: bool


def build_payload(contexts: List[str], approvals: int, enforce_admins: bool) -> Dict:
    # See: https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection
    return {
        "required_status_checks": {
            "strict": True,
            "contexts": contexts,
        },
        "enforce_admins": enforce_admins,
        "required_pull_request_reviews": {
            "required_approving_review_count": approvals,
            "require_code_owner_reviews": True,
            "dismiss_stale_reviews": True,
        },
        "restrictions": None,  # no push restrictions
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure branch protection via GitHub API")
    parser.add_argument("--owner", help="Repository owner (org or user)")
    parser.add_argument("--repo", help="Repository name")
    parser.add_argument(
        "--branches",
        default="main,develop",
        help="Comma-separated branch names (default: main,develop)",
    )
    parser.add_argument(
        "--require-approvals",
        type=int,
        default=None,
        help="Override required approvals for all branches (default: main=2, others=1)",
    )
    parser.add_argument(
        "--admins-enforce",
        dest="admins_enforce",
        action="store_true",
        help="Enforce for admins (default true for main)",
    )
    parser.add_argument(
        "--no-admins-enforce",
        dest="admins_enforce",
        action="store_false",
        help="Do not enforce for admins",
    )
    parser.set_defaults(admins_enforce=None)

    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN is required (repo admin permissions)")
        return 2

    owner = args.owner
    repo = args.repo
    if not (owner and repo):
        remote = _git_remote()
        if not remote:
            print("❌ Could not auto-detect repo. Provide --owner and --repo.")
            return 2
        parsed = _parse_remote(remote)
        if not parsed:
            print(f"❌ Unsupported remote URL format: {remote}")
            return 2
        owner, repo = parsed

    contexts = _required_contexts()
    branches = [b.strip() for b in args.branches.split(",") if b.strip()]

    # Determine per-branch rules
    rules: List[BranchRule] = []
    for b in branches:
        if args.require_approvals is not None:
            approvals = args.require_approvals
        else:
            approvals = 2 if b == "main" else 1
        if args.admins_enforce is not None:
            admins_enforce = args.admins_enforce
        else:
            admins_enforce = True if b == "main" else False
        rules.append(BranchRule(name=b, approvals=approvals, enforce_admins=admins_enforce))

    # Apply protection
    errors = 0
    for rule in rules:
        url = f"{API_BASE}/repos/{owner}/{repo}/branches/{rule.name}/protection"
        payload = build_payload(contexts, rule.approvals, rule.enforce_admins)
        status, body = _http("PUT", url, token, payload)
        if 200 <= status < 300:
            print(f"✅ Protected {owner}/{repo}@{rule.name} (approvals={rule.approvals}, admins_enforce={rule.enforce_admins})")
        else:
            errors += 1
            print(f"❌ Failed to protect {owner}/{repo}@{rule.name}: HTTP {status}")
            print(json.dumps(body, ensure_ascii=False, indent=2) if isinstance(body, dict) else body)

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

