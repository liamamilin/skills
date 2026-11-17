#!/usr/bin/env python3
"""扫描 skills/*/SKILL.md 与示例，生成 site/skills.json。缺少 name 或 description 时失败。"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
OUT_PATH = ROOT / "site" / "skills.json"


class SkillError(Exception):
    pass


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_frontmatter_block(block: str) -> dict[str, str]:
    lines = block.splitlines()
    data: dict[str, str] = {}
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in " \t":
            raise SkillError("frontmatter 缩进无效")
        if ":" not in line:
            raise SkillError(f"frontmatter 无法解析：{line}")
        key, rest = line.split(":", 1)
        key = key.strip()
        if not key:
            raise SkillError("frontmatter 键为空")
        rest = rest.strip()
        if rest in {">", ">-", ">+", "|", "|-", "|+"}:
            folded = rest.startswith(">")
            i += 1
            chunks: list[str] = []
            while i < total:
                nxt = lines[i]
                if nxt.strip() == "":
                    if i + 1 < total and lines[i + 1][:1] in " \t":
                        chunks.append("")
                        i += 1
                        continue
                    break
                if nxt[:1] not in " \t":
                    break
                chunks.append(nxt.strip())
                i += 1
            if folded:
                parts: list[str] = []
                acc: list[str] = []
                for item in chunks:
                    if item == "":
                        if acc:
                            parts.append(" ".join(acc))
                            acc = []
                        parts.append("\n")
                    else:
                        acc.append(item)
                if acc:
                    parts.append(" ".join(acc))
                data[key] = "".join(parts).strip()
            else:
                data[key] = "\n".join(chunks).strip()
            continue
        data[key] = unquote(rest)
        i += 1
    return data


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillError("缺少 frontmatter")
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise SkillError("frontmatter 未闭合")
    data = parse_frontmatter_block("\n".join(lines[1:end]))
    body = "\n".join(lines[end + 1 :])
    if text.endswith(("\n", "\r\n")):
        body += "\n"
    return data, body


def require_field(data: dict[str, str], key: str, where: str) -> str:
    value = data.get(key)
    if value is None or not str(value).strip():
        raise SkillError(f"{where}：缺少 {key}")
    return str(value).strip()


def first_heading(markdown: str) -> str | None:
    for line in markdown.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}[ \t]+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        text = re.sub(r"[*_`]", "", match.group(1)).strip()
        if text:
            return text
    return None


def read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeError as exc:
        raise SkillError(f"{path.relative_to(ROOT).as_posix()}：不是 UTF-8") from exc


def github_repo() -> str:
    env = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if env.count("/") == 1 and ":" not in env:
        return env
    try:
        url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "liamamilin/skills"
    url = re.sub(r"\.git$", "", url)
    match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+)$", url)
    if not match:
        return "liamamilin/skills"
    owner, repo = match.group(1), match.group(2)
    if ":" in owner or owner == "x-access-token":
        return "liamamilin/skills"
    return f"{owner}/{repo}"


def commit_sha() -> str:
    env = os.environ.get("GITHUB_SHA", "").strip()
    if env:
        return env
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "main"


def quote_path(path: str) -> str:
    return "/".join(quote(part, safe="") for part in path.split("/") if part != "")


def load_skill(folder: Path, repo: str, sha: str) -> dict:
    skill_path = folder / "SKILL.md"
    rel = skill_path.relative_to(ROOT).as_posix()
    raw = read_text(skill_path)
    try:
        data, body = split_frontmatter(raw)
    except SkillError as exc:
        raise SkillError(f"{rel}：{exc}") from exc
    name = require_field(data, "name", rel)
    description = require_field(data, "description", rel)
    examples_dir = folder / "examples"
    examples: list[dict] = []
    if examples_dir.exists() and not examples_dir.is_dir():
        raise SkillError(f"{rel}：examples 不是目录")
    if examples_dir.is_dir():
        for example_path in sorted(examples_dir.glob("*.md")):
            if not example_path.is_file() or example_path.name.startswith("."):
                continue
            example_rel = example_path.relative_to(ROOT).as_posix()
            example_raw = read_text(example_path)
            title = first_heading(example_raw) or example_path.stem
            examples.append(
                {
                    "slug": example_path.stem,
                    "title": title,
                    "body": example_raw,
                    "path": example_rel,
                    "url": f"https://github.com/{repo}/blob/{sha}/{quote_path(example_rel)}",
                }
            )
    return {
        "slug": folder.name,
        "name": name,
        "description": description,
        "body": body,
        "raw": raw,
        "path": rel,
        "url": f"https://github.com/{repo}/blob/{sha}/{quote_path(rel)}",
        "examples": examples,
    }


def build() -> dict:
    if not SKILLS_DIR.is_dir():
        raise SkillError("缺少 skills 目录")
    repo = github_repo()
    sha = commit_sha()
    skills: list[dict] = []
    errors: list[str] = []
    for folder in sorted(SKILLS_DIR.iterdir(), key=lambda item: item.name):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if not (folder / "SKILL.md").is_file():
            continue
        try:
            skills.append(load_skill(folder, repo, sha))
        except SkillError as exc:
            errors.append(str(exc))
    if errors:
        raise SkillError("校验失败：\n" + "\n".join(f"- {item}" for item in errors))
    return {
        "repo": repo,
        "commit": sha,
        "blobBase": f"https://github.com/{repo}/blob/{sha}/",
        "rawBase": f"https://raw.githubusercontent.com/{repo}/{sha}/",
        "skills": skills,
    }


def main() -> int:
    try:
        payload = build()
    except SkillError as exc:
        print(exc, file=sys.stderr)
        return 1
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(OUT_PATH)
    print(f"校验通过，写入 {OUT_PATH.relative_to(ROOT).as_posix()}（{len(payload['skills'])} 个技能）")
    for skill in payload["skills"]:
        print(f"- {skill['name']}（{len(skill['examples'])} 个示例）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
