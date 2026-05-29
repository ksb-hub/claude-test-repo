import subprocess
import re


def _run(args, cwd):
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def get_local_branches(repo_path="."):
    output = _run(["branch", "-vv"], cwd=repo_path)
    branches = []
    for line in output.splitlines():
        current = line.startswith("*")
        line = line[2:]  # strip "* " or "  "

        # name  hash  [remote: ahead N, behind N]  message
        match = re.match(r"(\S+)\s+[0-9a-f]+\s*(\[.*?\])?\s*(.*)", line)
        if not match:
            continue

        name, tracking_raw, _ = match.groups()
        remote = None
        ahead = 0
        behind = 0

        if tracking_raw:
            inner = tracking_raw[1:-1]  # strip [ ]
            parts = inner.split(":")
            remote = parts[0].strip()
            if len(parts) > 1:
                status = parts[1]
                m_ahead = re.search(r"ahead (\d+)", status)
                m_behind = re.search(r"behind (\d+)", status)
                if m_ahead:
                    ahead = int(m_ahead.group(1))
                if m_behind:
                    behind = int(m_behind.group(1))

        branches.append({
            "name": name,
            "current": current,
            "remote": remote,
            "ahead": ahead,
            "behind": behind,
        })
    return branches


def get_remote_branches(repo_path="."):
    try:
        output = _run(["branch", "-r"], cwd=repo_path)
    except RuntimeError:
        return []
    branches = []
    for line in output.splitlines():
        name = line.strip()
        if "HEAD" in name:
            continue
        branches.append(name)
    return branches


def get_branch_info(repo_path="."):
    return {
        "local": get_local_branches(repo_path),
        "remote": get_remote_branches(repo_path),
    }
