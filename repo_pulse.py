#!/usr/bin/env python3

import subprocess
import sys
import re
import argparse
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional


# ANSI colors
C = {
    "reset":      "\x1b[0m",
    "bold":       "\x1b[1m",
    "dim":        "\x1b[2m",
    "red":        "\x1b[31m",
    "yellow":     "\x1b[93m",
    "green":      "\x1b[32m",
    "light_blue": "\x1b[96m",
    "white":      "\x1b[37m",
    "gray":       "\x1b[90m",
    "cyan":       "\x1b[36m",
}


# ── data classes ──

@dataclass
class FileChurn:
    path: str
    commits: int = 0
    additions: int = 0
    deletions: int = 0

@dataclass
class ScoredFile:
    path: str
    filename: str
    directory: str
    commits: int
    additions: int
    deletions: int
    score: float

    @property
    def lines_changed(self) -> int:
        return self.additions + self.deletions

@dataclass
class DirectoryGroup:
    dir: str
    files: list['ScoredFile']
    total_commits: int
    total_lines_changed: int
    max_score: float


# ── utils ──

def colorize(text: str, color: str, no_color: bool) -> str:
    return text if no_color else f"{color}{text}{C['reset']}"

def strip_ansi(text: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

def format_number(n: int) -> str:
    return f"{n:,}"

def pluralize(n: int, word: str) -> str:
    return f"{format_number(n)} {word}{'s' if n != 1 else ''}"

def pad_end(text: str, length: int) -> str:
    visible = strip_ansi(text)
    return text + " " * max(0, length - len(visible))

def format_lines_changed(added: int, deleted: int, no_color: bool) -> str:
    a = colorize(f"+{format_number(added)}", C["green"], no_color)
    d = colorize(f"-{format_number(deleted)}", C["red"], no_color)
    return f"{a} {d}"

def is_user_ignored(path: str, ignore: list[str]) -> bool:
    return any(i in path for i in ignore)


# ── themes ──

STOP_WORDS = {
    # language keywords
    "if", "else", "elif", "for", "while", "do", "end", "def", "class", "module",
    "return", "import", "from", "export", "default", "const", "let", "var", "function",
    "true", "false", "nil", "null", "none", "self", "this", "new", "try", "catch",
    "rescue", "raise", "except", "finally", "with", "as", "in", "not", "and", "or",
    "case", "when", "switch", "break", "continue", "yield", "async", "await",
    "public", "private", "protected", "static", "void", "int", "string", "bool",
    "type", "interface", "enum", "struct", "impl", "use", "fn", "pub", "mut", "ref",
    "require", "include", "extend", "super", "begin", "ensure", "then",
    # common boilerplate
    "todo", "fixme", "note", "hack", "xxx", "spec", "test", "describe", "context",
    "expect", "assert", "should", "before", "after", "each", "all",
    "puts", "print", "log", "console", "debug", "info", "warn", "error",
    "get", "set", "has", "map", "push", "pop", "length", "size", "count",
    "attr", "reader", "writer", "accessor",
    # common generic terms
    "the", "that", "this", "these", "those", "are", "was", "were", "been", "being",
    "have", "had", "does", "did", "will", "would", "could", "shall",
    "name", "value", "data", "key", "item", "items", "list", "array", "index",
    "result", "results", "params", "args", "opts", "options", "config",
    "path", "file", "dir", "src", "lib", "tmp", "url", "str",
    "uuid", "nil", "noop", "std", "fmt", "msg", "err", "val", "obj", "num",
    "add", "update", "delete", "remove", "create", "read", "write", "find", "send",
    "can", "not", "also", "just", "only", "some", "any", "its", "but", "than",
    "types", "typeof", "instanceof", "undefined",
}

_CAMEL_RE = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')
_IDENT_RE = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*')


def split_identifier(ident: str) -> list[str]:
    parts = _CAMEL_RE.sub('_', ident).lower().split('_')
    return [p for p in parts if len(p) > 2 and p not in STOP_WORDS]


def get_themes(since: str, author: Optional[str], directory: Optional[str],
               ignore: list[str], ignore_themes: Optional[list[str]] = None,
               top: int = 10) -> list[tuple[str, int, int]]:
    ignore_themes = ignore_themes or []
    cmd = ["git", "log", f"--since={since}", "-p", "-U0", "--pretty=format:---COMMIT---"]
    if author:
        cmd.append(f"--author={author}")
    if directory:
        cmd += ["--", directory]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        return []

    term_count: dict[str, int] = defaultdict(int)
    term_files: dict[str, set] = defaultdict(set)
    current_file = None

    for line in result.stdout.splitlines():
        if line.startswith("diff --git"):
            match = re.search(r' b/(.+)$', line)
            current_file = match.group(1) if match else None
            if current_file and is_user_ignored(current_file, ignore):
                current_file = None
            continue

        if not current_file:
            continue

        if not (line.startswith("+") or line.startswith("-")):
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue

        content = line[1:]
        for ident in _IDENT_RE.findall(content):
            for token in split_identifier(ident):
                term_count[token] += 1
                term_files[token].add(current_file)

    scored = [
        (term, count, len(term_files[term]))
        for term, count in term_count.items()
        if len(term_files[term]) >= 2
        and not any(i in term for i in ignore_themes)
    ]
    scored.sort(key=lambda t: (t[2], t[1]), reverse=True)
    return scored[:top]


def render_themes(themes: list[tuple[str, int, int]], no_color: bool) -> str:
    if not themes:
        return ""

    header = colorize("  themes", C["bold"] + C["white"], no_color)
    lines = [header, ""]
    for term, count, file_count in themes:
        label = colorize(term, C["white"], no_color)
        meta = colorize(
            f"{format_number(count)} mentions across {pluralize(file_count, 'file')}",
            C["gray"], no_color,
        )
        lines.append(f"   {label}  {meta}")
    return "\n".join(lines)


# ── git ──

def get_churn_data(since: str, author: Optional[str], directory: Optional[str],
                   ignore: list[str]) -> list[FileChurn]:
    cmd = ["git", "log", f"--since={since}", "--numstat", "--pretty=format:---COMMIT---"]
    if author:
        cmd.append(f"--author={author}")
    if directory:
        cmd += ["--", directory]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        print("Error: not a git repository or git is not installed.")
        sys.exit(1)

    file_map: dict[str, FileChurn] = {}
    commit_sets: dict[str, set[int]] = defaultdict(set)
    commit_id = 0

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line == "---COMMIT---":
            commit_id += 1
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added_str, deleted_str, path = parts
        additions = 0 if added_str == "-" else int(added_str)
        deletions = 0 if deleted_str == "-" else int(deleted_str)

        if is_user_ignored(path, ignore):
            continue

        commit_sets[path].add(commit_id)

        if path in file_map:
            f = file_map[path]
            file_map[path] = FileChurn(
                path=f.path,
                commits=len(commit_sets[path]),
                additions=f.additions + additions,
                deletions=f.deletions + deletions,
            )
        else:
            file_map[path] = FileChurn(path=path, commits=1, additions=additions, deletions=deletions)

    return list(file_map.values())


# ── scoring ──

def score_and_sort(files: list[FileChurn], top: int) -> list[ScoredFile]:
    if not files:
        return []

    max_commits = max((f.commits for f in files), default=1)
    max_lines = max((f.additions + f.deletions for f in files), default=1)

    def to_scored(f: FileChurn) -> ScoredFile:
        commit_score = f.commits / max_commits
        line_score = (f.additions + f.deletions) / max_lines
        score = commit_score * 0.7 + line_score * 0.3
        parts = f.path.split("/")
        filename = parts[-1]
        directory = "/".join(parts[:-1]) if len(parts) > 1 else "."
        return ScoredFile(
            path=f.path,
            filename=filename,
            directory=directory,
            commits=f.commits,
            additions=f.additions,
            deletions=f.deletions,
            score=score,
        )

    scored = sorted([to_scored(f) for f in files], key=lambda f: f.score, reverse=True)
    return scored[:top]


# ── grouping ──

def _build_prefix_counts(files: list[ScoredFile]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for f in files:
        parts = f.path.split("/")
        for i in range(len(parts) - 1):
            counts["/".join(parts[:i+1])] += 1
    return counts


def get_group_dir(filepath: str, prefix_counts: dict[str, int]) -> str:
    parts = filepath.split("/")
    if len(parts) <= 1:
        return "(root)"

    for i in range(len(parts) - 2, -1, -1):
        parent = "/".join(parts[:i+1])
        if prefix_counts.get(parent, 0) >= 2:
            return parent

    return parts[0]

def group_by_directory(files: list[ScoredFile]) -> list[DirectoryGroup]:
    prefix_counts = _build_prefix_counts(files)
    dir_map: dict[str, list[ScoredFile]] = defaultdict(list)
    for f in files:
        dir_map[get_group_dir(f.path, prefix_counts)].append(f)

    groups = []
    for dir_name, dir_files in dir_map.items():
        sorted_files = sorted(dir_files, key=lambda f: f.score, reverse=True)
        groups.append(DirectoryGroup(
            dir=dir_name,
            files=sorted_files,
            total_commits=sum(f.commits for f in dir_files),
            total_lines_changed=sum(f.lines_changed for f in dir_files),
            max_score=max(f.score for f in dir_files),
        ))

    return sorted(groups, key=lambda g: g.max_score, reverse=True)


# ── heat ──

def compute_quartiles(files: list[ScoredFile]) -> tuple[float, float, float]:
    scores = sorted(f.score for f in files)
    n = len(scores)
    return scores[int(n * 0.25)], scores[int(n * 0.50)], scores[int(n * 0.75)]


def get_heat_indicator(score: float, quartiles: tuple[float, float, float], no_color: bool) -> str:
    q1, q2, q3 = quartiles
    if score >= q3:
        return colorize("●", C["red"], no_color)
    if score >= q2:
        return colorize("●", C["yellow"], no_color)
    if score >= q1:
        return colorize("●", C["green"], no_color)
    return colorize("●", C["light_blue"], no_color)


# ── render ──

def render_flat_line(file: ScoredFile, quartiles: tuple[float, float, float],
                     max_path_len: int, no_color: bool) -> str:
    indicator = get_heat_indicator(file.score, quartiles, no_color)
    filepath = pad_end(colorize(file.path, C["white"], no_color), max_path_len + 20)
    commits = colorize(pluralize(file.commits, "commit"), C["dim"], no_color)
    lines = format_lines_changed(file.additions, file.deletions, no_color)
    return f"   {indicator}  {filepath}  {commits}  {lines}"

def render_grouped_file(file: ScoredFile, quartiles: tuple[float, float, float],
                        max_path_len: int, no_color: bool) -> str:
    indicator = get_heat_indicator(file.score, quartiles, no_color)
    filename = colorize(file.filename, C["white"], no_color)
    commits = colorize(pluralize(file.commits, "commit"), C["gray"], no_color)
    lines = format_lines_changed(file.additions, file.deletions, no_color)
    return f"      {indicator}  {filename}  {commits}  {lines}"

def render_group(group: DirectoryGroup, top_file_paths: set,
                 quartiles: tuple[float, float, float],
                 max_path_len: int, no_color: bool) -> str:
    visible_files = [f for f in group.files if f.path in top_file_paths]
    if not visible_files:
        return ""

    indicator = get_heat_indicator(group.max_score, quartiles, no_color)
    dir_label = colorize(group.dir + "/", C["bold"] + C["white"], no_color)
    meta = colorize(
        f"  {pluralize(group.total_commits, 'commit')}  ·  {pluralize(len(visible_files), 'file')}",
        C["gray"], no_color
    )
    header = f"   {indicator}  {dir_label}{meta}"
    file_lines = "\n".join(
        render_grouped_file(f, quartiles, max_path_len, no_color) for f in visible_files
    )
    return f"{header}\n{file_lines}"

def render_flat(files: list[ScoredFile], quartiles: tuple[float, float, float],
                max_path_len: int, no_color: bool) -> str:
    return "\n".join(render_flat_line(f, quartiles, max_path_len, no_color) for f in files)

def render_grouped(files: list[ScoredFile], quartiles: tuple[float, float, float],
                   max_path_len: int, no_color: bool) -> str:
    top_file_paths = {f.path for f in files}
    groups = group_by_directory(files)
    parts = [render_group(g, top_file_paths, quartiles, max_path_len, no_color) for g in groups]
    return "\n\n".join(p for p in parts if p)

def legend(no_color: bool) -> str:
    return (
        colorize("      ●", C["red"], no_color) + colorize(" high  ", C["gray"], no_color) +
        colorize("●", C["yellow"], no_color) + colorize(" moderate  ", C["gray"], no_color) +
        colorize("●", C["green"], no_color) + colorize(" low  ", C["gray"], no_color) +
        colorize("●", C["light_blue"], no_color) + colorize(" minimal", C["gray"], no_color)
    )

def divider(no_color: bool) -> str:
    return colorize("─" * 60, C["gray"], no_color)

def render(files: list[ScoredFile], days: int, flat: bool, no_color: bool,
           themes: Optional[list[tuple[str, int, int]]] = None,
           total_files: Optional[int] = None) -> None:
    header = (
        colorize("  repo-pulse", C["bold"] + C["cyan"], no_color) +
        colorize(" | codebase activity report", C["gray"], no_color)
    )
    meta = (
        colorize(f"  {days} days ago → today", C["dim"], no_color) +
        colorize(
            f" · {pluralize(sum(f.commits for f in files), 'commit')} · {pluralize(total_files or len(files), 'file')} touched",
            C["gray"], no_color,
        )
    )

    div = divider(no_color)

    if not files:
        print(f"\n{div}\n\n{header}\n\n{meta}\n\n{colorize('  No changes found in this time range.', C['gray'], no_color)}\n\n{div}\n")
        return

    quartiles = compute_quartiles(files)
    hotspots_header = colorize("  hotspots", C["bold"] + C["white"], no_color)
    if flat:
        lengths = sorted(len(f.path) for f in files)
        median = lengths[len(lengths) // 2]
        max_path_len = min(median + 15, max(lengths)) + 2
        body = render_flat(files, quartiles, max_path_len, no_color)
    else:
        max_path_len = max(len(f.filename) for f in files) + 2
        body = render_grouped(files, quartiles, max_path_len, no_color)

    themes_section = ""
    if themes:
        themes_section = f"\n\n{render_themes(themes, no_color)}\n"

    print(f"\n{div}\n\n{header}\n\n{meta}\n\n{hotspots_header}\n\n{body}\n\n{legend(no_color)}\n{themes_section}\n{div}\n")


# ── cli ──

HELP_TEXT = """
  repo-pulse — See what's been happening in your codebase at a glance.

  Usage:  repo-pulse [options]

  Options:

    -d, --days N               Lookback window in days (default: 30)
    -t, --top N                Max files to show (default: 20)
    -a, --author NAME          Filter by author name or email
        --dir PATH             Scope to a subdirectory
        --flat                 Flat list instead of grouped by directory
        --ignore-files PATHS   Comma-separated paths to ignore
        --themes N             Number of themes to show (default: 10)
        --no-themes            Disable themes section
        --ignore-themes TERMS  Comma-separated terms to ignore
        --no-color             Disable colored output
    -h, --help                 Show this help message
"""


def parse_args():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(HELP_TEXT)
        sys.exit(0)

    parser = argparse.ArgumentParser(prog="repo-pulse", add_help=False)
    parser.add_argument("-d", "--days", type=int, default=30)
    parser.add_argument("-t", "--top", type=int, default=20)
    parser.add_argument("-a", "--author", type=str)
    parser.add_argument("--dir", type=str)
    parser.add_argument("--flat", action="store_true")
    parser.add_argument("--ignore-files", type=str, default="")
    parser.add_argument("--themes", type=int, default=10)
    parser.add_argument("--no-themes", action="store_true")
    parser.add_argument("--ignore-themes", type=str, default="")
    parser.add_argument("--no-color", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    ignore = [i.strip() for i in args.ignore_files.split(",") if i.strip()]
    ignore_themes = [i.strip().lower() for i in args.ignore_themes.split(",") if i.strip()]

    raw = get_churn_data(
        since=f"{args.days} days ago",
        author=args.author,
        directory=args.dir,
        ignore=ignore,
    )

    if not raw:
        print("\n  repo-pulse — no activity found with the given options.\n")
        sys.exit(0)

    scored = score_and_sort(raw, args.top)

    themes = None
    if not args.no_themes:
        themes = get_themes(
            since=f"{args.days} days ago",
            author=args.author,
            directory=args.dir,
            ignore=ignore,
            ignore_themes=ignore_themes,
            top=args.themes,
        )

    render(scored, args.days, args.flat, args.no_color,
           themes=themes, total_files=len(raw))


if __name__ == "__main__":
    main()
