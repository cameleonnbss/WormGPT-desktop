"""Local file tools for the agent mode — a Claude-Code-style toolset.

The model calls these tools in a silent agent loop (never in the chat
stream). They run on the user's machine — that is the point — with bounded
output, a working directory, and a hard cap on how much text goes back into
the context window.

Tool set (deliberately mirrors Claude Code's primitives):

    read_file    Read a file with line numbers (offset/limit)
    write_file   Create or overwrite a file (parent folders created)
    edit_file    Exact single replacement inside a file
    multi_edit   Several exact replacements in one call
    list_dir     List a directory (optionally recursive)
    glob         Find files by name pattern (``**/*.py``)
    grep         Search a regex inside files of a folder
    run_command  Run a shell command (see runner.py)

Nothing here executes a shell — that lives in runner.py and is confirmed
with the user unless the app is in auto mode.
"""

import fnmatch
import os
import re

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a text file from the user's machine. Returns the "
                "content with line numbers. Use offset/limit for large "
                "files instead of reading everything."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string",
                             "description": "File path (absolute or relative to the working directory)."},
                    "offset": {"type": "integer",
                               "description": "First line to read (1-based). Default 1."},
                    "limit": {"type": "integer",
                              "description": "How many lines to read. Default 400."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": ("Create or overwrite a text file with the given "
                            "content. Parent folders are created automatically."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": ("Replace an exact text snippet inside an existing "
                            "file. The snippet must match exactly once (make it "
                            "longer if it is ambiguous)."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string",
                                   "description": "Exact text to find."},
                    "new_string": {"type": "string",
                                   "description": "Replacement text."},
                    "replace_all": {"type": "boolean",
                                    "description": "Replace every occurrence instead of requiring exactly one."},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multi_edit",
            "description": ("Apply several exact replacements to one file in "
                            "a single call. Each edit runs in order; the whole "
                            "file is written once."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "edits": {
                        "type": "array",
                        "description": "List of {old_string, new_string} (optional replace_all).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_string": {"type": "string"},
                                "new_string": {"type": "string"},
                                "replace_all": {"type": "boolean"},
                            },
                            "required": ["old_string", "new_string"],
                        },
                    },
                },
                "required": ["path", "edits"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": ("List the files and folders of a directory "
                            "(optionally recursive)."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string",
                             "description": "Directory path (default: working directory)."},
                    "recursive": {"type": "boolean",
                                  "description": "Walk sub-folders too."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": ("Find files whose path matches a glob pattern "
                            "(e.g. '**/*.py', 'src/**/*.ts')."),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string",
                                "description": "Glob pattern, '**' matches any depth."},
                    "path": {"type": "string",
                             "description": "Folder to search from (default: working directory)."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": ("Search a regular expression inside the files of a "
                            "folder (recursive). Returns file:line: text hits."),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string",
                                "description": "Regular expression to look for."},
                    "path": {"type": "string",
                             "description": "Folder to search (default: working directory)."},
                    "include": {"type": "string",
                                "description": "Only files matching this glob, e.g. '*.py'."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command on the user's machine. Use it to run "
                "scripts, tests, builds, installs or inspect the system. "
                "The output is returned to you."),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string",
                                "description": "The exact command to run."},
                    "cwd": {"type": "string",
                            "description": "Directory to run it in (default: working directory)."},
                    "timeout": {"type": "integer",
                                "description": "Seconds before the command is killed (default 120)."},
                },
                "required": ["command"],
            },
        },
    },
]

#: tool names that write/modify the machine (used for the permission gate
#: and for the activity log)
WRITE_TOOLS = {"write_file", "edit_file", "multi_edit", "run_command"}

MAX_TEXT = 12000          # max characters returned by read_file
MAX_LINES = 400           # default line window
MAX_LIST = 300            # entries returned by list_dir
MAX_GLOB = 200            # entries returned by glob
MAX_MATCHES = 60          # hits returned by grep
MAX_SCAN_BYTES = 2_000_000


def _norm(path, cwd):
    p = os.path.expanduser(str(path or "").strip())
    if not os.path.isabs(p):
        p = os.path.join(cwd or os.getcwd(), p)
    return os.path.normpath(p)


def read_file(path, cwd=None, offset=1, limit=MAX_LINES):
    """Read a file and return it with 1-based line numbers."""
    p = _norm(path, cwd)
    if os.path.isdir(p):
        return f"[not a file but a directory: {p} — use list_dir]"
    if not os.path.isfile(p):
        return f"[not a file: {p}]"
    try:
        try:
            offset = max(1, int(offset))
        except (TypeError, ValueError):
            offset = 1
        try:
            limit = max(1, min(4000, int(limit)))
        except (TypeError, ValueError):
            limit = MAX_LINES
        lines, total = [], 0
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for total, line in enumerate(f, 1):
                if total < offset:
                    continue
                if len(lines) >= limit:
                    break
                lines.append(f"{total}\t{line.rstrip()}")
        if not lines:
            return f"[empty file or offset past the end: {p}]"
        head = f"{p} (lines {offset}-{offset + len(lines) - 1}):\n"
        body = "\n".join(lines)
        if len(body) > MAX_TEXT:
            body = body[:MAX_TEXT] + "\n… (truncated — read a smaller window)"
        if len(lines) >= limit:
            body += (f"\n… (more lines may follow — continue with "
                     f"offset={offset + len(lines)})")
        return head + body
    except OSError as exc:
        return f"[read error: {exc}]"


def write_file(path, content, cwd=None):
    p = _norm(path, cwd)
    data = str(content or "")
    try:
        parent = os.path.dirname(p)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(data)
        return f"[written: {p} ({len(data)} chars, {data.count(chr(10)) + 1} lines)]"
    except OSError as exc:
        return f"[write error: {exc}]"


def _apply_edit(data, old, new, replace_all):
    """Return (new_data, None) or (None, error_message)."""
    if not old:
        return None, "[old_string is empty]"
    n = data.count(old)
    if n == 0:
        return None, "[old_string not found — no change made]"
    if n > 1 and not replace_all:
        return None, (f"[old_string matches {n} times — make it longer/"
                      "more unique, or pass replace_all=true]")
    if replace_all:
        return data.replace(old, new), None
    return data.replace(old, new, 1), None


def edit_file(path, old_text, new_text, cwd=None, old_string=None,
              new_string=None, replace_all=False):
    """Exact replacement inside a file (single match by default)."""
    p = _norm(path, cwd)
    if not os.path.isfile(p):
        return f"[not a file: {p}]"
    old = old_string if old_string is not None else old_text
    new = new_string if new_string is not None else new_text
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        new_data, err = _apply_edit(data, old, new or "", bool(replace_all))
        if err:
            return err
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_data)
        return f"[edited: {p}]"
    except OSError as exc:
        return f"[edit error: {exc}]"


def multi_edit(path, edits, cwd=None):
    """Apply an ordered list of exact replacements, writing once."""
    p = _norm(path, cwd)
    if not os.path.isfile(p):
        return f"[not a file: {p}]"
    if not isinstance(edits, list) or not edits:
        return "[no edits given]"
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        applied = 0
        for i, e in enumerate(edits, 1):
            if not isinstance(e, dict):
                return f"[edit {i}: not an object]"
            old = e.get("old_string")
            new = e.get("new_string", "")
            new_data, err = _apply_edit(data, old, new,
                                        bool(e.get("replace_all")))
            if err:
                return f"[edit {i}/{len(edits)} failed: {err}]"
            data = new_data
            applied += 1
        with open(p, "w", encoding="utf-8") as f:
            f.write(data)
        return f"[edited: {p} ({applied} edit(s) applied)]"
    except OSError as exc:
        return f"[edit error: {exc}]"


def list_dir(path, cwd=None, recursive=False):
    p = _norm(path or ".", cwd)
    if not os.path.isdir(p):
        return f"[not a directory: {p}]"
    out = []
    try:
        if recursive:
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs
                           if not d.startswith(".") and d != "__pycache__"]
                rel = os.path.relpath(root, p)
                rel = "" if rel == "." else rel + os.sep
                for d in sorted(dirs):
                    out.append(f"DIR  {rel}{d}")
                for n in sorted(files):
                    out.append(f"FILE {rel}{n}")
                if len(out) >= MAX_LIST:
                    break
        else:
            for n in sorted(os.listdir(p)):
                full = os.path.join(p, n)
                tag = "DIR  " if os.path.isdir(full) else "FILE "
                out.append(tag + n)
        out = out[:MAX_LIST]
        if len(out) >= MAX_LIST:
            out.append("… (more entries truncated)")
        return "\n".join(out) or "[empty]"
    except OSError as exc:
        return f"[list error: {exc}]"


def glob(pattern, path, cwd=None):
    """Find files matching a glob pattern."""
    base = _norm(path or ".", cwd)
    if not os.path.isdir(base):
        return f"[not a directory: {base}]"
    pat = str(pattern or "").strip() or "*"
    hits = []
    try:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs
                       if not d.startswith(".") and d != "__pycache__"]
            for n in files:
                full = os.path.join(root, n)
                rel = os.path.relpath(full, base).replace(os.sep, "/")
                if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(n, pat):
                    hits.append(rel)
                    if len(hits) >= MAX_GLOB:
                        break
            if len(hits) >= MAX_GLOB:
                break
    except OSError as exc:
        return f"[glob error: {exc}]"
    return "\n".join(sorted(hits)) or f"[no file matches '{pat}']"


def grep(pattern, path, cwd=None, include=""):
    """Search a regular expression inside the files of a folder."""
    base = _norm(path or ".", cwd)
    if not os.path.isdir(base):
        return f"[not a directory: {base}]"
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return f"[invalid regex: {exc}]"
    inc = str(include or "").strip()
    hits = []
    try:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs
                       if not d.startswith(".") and d != "__pycache__"]
            for name in sorted(files):
                if name.startswith(".") or len(hits) >= MAX_MATCHES:
                    continue
                if inc and not fnmatch.fnmatch(name, inc):
                    continue
                full = os.path.join(root, name)
                try:
                    if os.path.getsize(full) > MAX_SCAN_BYTES:
                        continue
                    with open(full, "r", encoding="utf-8",
                              errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if rx.search(line):
                                hits.append(f"{full}:{i}: {line.strip()[:200]}")
                                if len(hits) >= MAX_MATCHES:
                                    break
                except OSError:
                    continue
    except OSError as exc:
        return f"[grep error: {exc}]"
    return "\n".join(hits) or "[no match]"


def search_files(path, pattern, cwd=None):
    """Ancien nom conservé pour l'API interne (alias de grep)."""
    return grep(pattern, path, cwd)
