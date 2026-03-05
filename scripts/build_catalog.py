#!/usr/bin/env python3
"""
Build NII-cloud-operation public repository catalog and lightweight tree index.

Outputs:
- <out-dir>/repos.jsonl
- <out-dir>/tree.jsonl
- <out-dir>/bootstrap.md
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse

API_BASE = "https://api.github.com"


class CommandError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stdout: str, stderr: str):
        joined = " ".join(cmd)
        super().__init__(f"Command failed ({returncode}): {joined}\n{stderr.strip()}")
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_json_cmd(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise CommandError(cmd, proc.returncode, proc.stdout, proc.stderr)
    return json.loads(proc.stdout)


def gh_repo_list(org: str, limit: int) -> list[dict[str, Any]]:
    cmd = [
        "gh",
        "repo",
        "list",
        org,
        "--limit",
        str(limit),
        "--visibility",
        "public",
        "--json",
        "name,description,isArchived,visibility,updatedAt,defaultBranchRef,primaryLanguage,url,homepageUrl,repositoryTopics",
    ]
    return run_json_cmd(cmd)


def gh_repo_tree(org: str, repo: str, ref: str) -> list[dict[str, Any]]:
    endpoint = (
        f"repos/{parse.quote(org)}/{parse.quote(repo)}/git/trees/{parse.quote(ref)}?recursive=1"
    )
    try:
        data = run_json_cmd(["gh", "api", endpoint])
    except CommandError as exc:
        if "HTTP 409" in exc.stderr or "HTTP 404" in exc.stderr:
            return []
        raise
    if not isinstance(data, dict):
        raise TypeError(f"Unexpected tree payload type for {repo}: {type(data).__name__}")
    tree = data.get("tree")
    if not isinstance(tree, list):
        raise TypeError(f"Unexpected tree field type for {repo}: {type(tree).__name__}")
    return tree


def gh_repo_readme_summary(org: str, repo: str, ref: str) -> tuple[str, str]:
    endpoint = f"repos/{parse.quote(org)}/{parse.quote(repo)}/readme?ref={parse.quote(ref)}"
    try:
        data = run_json_cmd(["gh", "api", endpoint])
    except CommandError as exc:
        if "HTTP 404" in exc.stderr:
            return "", "missing"
        raise
    if not isinstance(data, dict):
        raise TypeError(f"Unexpected README payload type for {repo}: {type(data).__name__}")
    encoded = data.get("content")
    if not isinstance(encoded, str) or not encoded:
        return "", "missing"
    try:
        raw = base64.b64decode(encoded, validate=False).decode("utf-8", errors="replace")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError(f"Failed to decode README content for {repo}") from exc
    return summarize_markdown(raw), "present"


def summarize_markdown(text: str) -> str:
    command_prefixes = (
        "pip ",
        "python ",
        "python3 ",
        "npm ",
        "yarn ",
        "pnpm ",
        "docker ",
        "git ",
        "make ",
        "pandoc ",
    )
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        if s.startswith("![") or s.startswith("[!["):
            continue
        if s.startswith("```"):
            continue
        if s.startswith(">"):
            continue
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
        s = re.sub(r"`([^`]+)`", r"\1", s)
        s = re.sub(r"\s+", " ", s).strip()
        low = s.lower()
        if low.startswith(command_prefixes):
            continue
        if " -o " in low and (" --" in low or " -" in low):
            continue
        if len(s) < 20:
            continue
        lines.append(s)
        if len(lines) >= 3:
            break
    if not lines:
        return ""
    summary = " ".join(lines)
    return summary[:220].strip()


def safe_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def to_public_repo_records(raw: list[dict[str, Any]], org: str) -> list[dict[str, Any]]:
    public: list[dict[str, Any]] = []
    for item in raw:
        if item["visibility"] != "PUBLIC":
            continue

        default_branch_ref = item["defaultBranchRef"]
        if default_branch_ref is None:
            raise ValueError(f"defaultBranchRef is missing for repo={item['name']}")
        default_branch = default_branch_ref["name"]

        primary_language = item["primaryLanguage"]
        language = "" if primary_language is None else primary_language["name"]

        repository_topics = item["repositoryTopics"]
        topics_raw = [] if repository_topics is None else repository_topics
        topics: list[str] = []
        for t in topics_raw:
            if "name" in t:
                topics.append(t["name"])
            elif "topic" in t and "name" in t["topic"]:
                topics.append(t["topic"]["name"])
            else:
                raise ValueError(f"Unexpected topic shape for repo={item['name']}: {t}")

        repo_name = item["name"]
        public.append(
            {
                "repo": repo_name,
                "url": item["url"],
                "description": item["description"] or "",
                "default_branch": default_branch,
                "language": language,
                "updated_at": item["updatedAt"],
                "is_archived": bool(item["isArchived"]),
                "homepage": item["homepageUrl"] or "",
                "topics": topics,
                "readme_api_url": (
                    f"{API_BASE}/repos/{parse.quote(org)}/"
                    f"{parse.quote(repo_name)}/readme"
                    f"?ref={parse.quote(default_branch)}"
                ),
            }
        )
    public.sort(key=lambda x: x["updated_at"], reverse=True)
    return public


def build_tree_record_from_entries(
    repo_record: dict[str, Any],
    max_dirs: int,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    top_dirs: set[str] = set()
    top_files: set[str] = set()
    second_level: dict[str, set[str]] = {}

    for e in entries:
        path = e.get("path")
        etype = e.get("type")
        if not isinstance(path, str) or etype not in {"blob", "tree"}:
            continue
        parts = path.split("/")
        if len(parts) == 1:
            if etype == "tree":
                top_dirs.add(parts[0])
            else:
                top_files.add(parts[0])
            continue
        top = parts[0]
        child = parts[1]
        top_dirs.add(top)
        second_level.setdefault(top, set()).add(child)

    limited_top_dirs = sorted(top_dirs, key=str.lower)[:max_dirs]
    second_level_limited: dict[str, list[str]] = {}
    for d in limited_top_dirs:
        second_level_limited[d] = sorted(second_level.get(d, set()), key=str.lower)

    return {
        "repo": repo_record["repo"],
        "default_branch": repo_record["default_branch"],
        "top_dirs": limited_top_dirs,
        "top_files": sorted(top_files, key=str.lower),
        "second_level": second_level_limited,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def write_bootstrap(path: Path, org: str, repos: list[dict[str, Any]]) -> None:
    generated_at = safe_iso_now()
    total = len(repos)
    active = repos[:20]
    lang_count: dict[str, int] = {}
    for r in repos:
        lang = r["language"] or "N/A"
        lang_count[lang] = lang_count.get(lang, 0) + 1
    top_langs = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)[:10]

    lines: list[str] = []
    lines.append("# Bootstrap Context")
    lines.append("")
    lines.append(f"- generated_at: {generated_at}")
    lines.append(f"- organization: {org}")
    lines.append(f"- public_repo_count: {total}")
    lines.append("")
    lines.append("## Top Languages")
    for lang, cnt in top_langs:
        lines.append(f"- {lang}: {cnt}")
    lines.append("")
    lines.append("## Recently Updated Repositories")
    for r in active:
        lines.append(f"- {r['updated_at']}  {r['repo']}  ({r['language'] or 'N/A'})")
    lines.append("")
    lines.append("## Retrieval Rules")
    lines.append("- Use catalog first to select candidate repositories.")
    lines.append("- Do not clone all repositories.")
    lines.append("- Clone only required repositories with shallow clone.")
    lines.append("- Include evidence paths in answers.")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=os.environ.get("NII-cloud-operation_ORG", "NII-cloud-operation"))
    parser.add_argument("--out-dir", default="catalog")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--max-dirs", type=int, default=8)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    repos_path = out_dir / "repos.jsonl"
    tree_path = out_dir / "tree.jsonl"
    bootstrap_path = out_dir / "bootstrap.md"

    raw = gh_repo_list(args.org, args.limit)
    repos = to_public_repo_records(raw, args.org)

    for repo in repos:
        summary, status = gh_repo_readme_summary(args.org, repo["repo"], repo["default_branch"])
        repo["readme_summary"] = summary
        repo["readme_status"] = status
        if not repo["description"] and summary:
            repo["description"] = summary
    write_jsonl(repos_path, repos)

    tree_rows: list[dict[str, Any]] = []
    for repo in repos:
        entries = gh_repo_tree(args.org, repo["repo"], repo["default_branch"])
        tree_rows.append(build_tree_record_from_entries(repo, args.max_dirs, entries))
    write_jsonl(tree_path, tree_rows)

    write_bootstrap(bootstrap_path, args.org, repos)

    print(f"Wrote {repos_path} ({len(repos)} rows)")
    print(f"Wrote {tree_path} ({len(tree_rows)} rows)")
    print(f"Wrote {bootstrap_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
