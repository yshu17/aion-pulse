"""Scan every added line in all git history for secrets (tokens, keys, passwords).

Read-only. Prints only masked values (first 4 characters and the length), never a secret.
Use before the first push and before every release: python tools/secret_scan.py
Exit code 0: no matches, 1: matches found.
"""
import re, subprocess, sys
patterns = {
    "telegram-bot-token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "openai-style-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "anthropic-style-key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "private-key-block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "bearer-token": re.compile(r"[Bb]earer\s+[A-Za-z0-9._-]{25,}"),
    "assigned-secret": re.compile(r"(?i)\b(api[_-]?key|secret|token|passwd|password|authorization)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
}
proc = subprocess.Popen(["git", "log", "--all", "-p", "--no-color", "--pretty=format:@@COMMIT %h"],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
commit = file = None
hits = {}
added = 0
for raw in proc.stdout:
    line = raw.decode("utf-8", "replace").rstrip("\n")
    if line.startswith("@@COMMIT "):
        commit = line.split()[1]; continue
    if line.startswith("diff --git "):
        file = line.split(" b/", 1)[-1]; continue
    if not line.startswith("+") or line.startswith("+++"):
        continue
    added += 1
    for name, rx in patterns.items():
        m = rx.search(line)
        if m:
            val = m.group(0)
            masked = val[:4] + "…" + str(len(val)) + "ch"
            hits.setdefault((name, file), []).append((commit, masked))
print("added lines scanned:", added)
if not hits:
    print("no matches for any pattern")
    sys.exit(0)
for (name, file), lst in sorted(hits.items()):
    print(f"{name:20s} {file}  x{len(lst)}  first {lst[0][0]} {lst[0][1]}")
sys.exit(1)
