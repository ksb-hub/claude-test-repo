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
        line = line[2:]
        match = re.match(r"(\S+)\s+[0-9a-f]+\s*(\[.*?\])?\s*(.*)", line)
        if not match:
            continue
        name, tracking_raw, _ = match.groups()
        remote, ahead, behind = None, 0, 0
        if tracking_raw:
            inner = tracking_raw[1:-1]
            parts = inner.split(":")
            remote = parts[0].strip()
            if len(parts) > 1:
                m_a = re.search(r"ahead (\d+)", parts[1])
                m_b = re.search(r"behind (\d+)", parts[1])
                if m_a:
                    ahead = int(m_a.group(1))
                if m_b:
                    behind = int(m_b.group(1))
        branches.append({"name": name, "current": current,
                         "remote": remote, "ahead": ahead, "behind": behind})
    return branches


def get_remote_branches(repo_path="."):
    try:
        output = _run(["branch", "-r"], cwd=repo_path)
    except RuntimeError:
        return []
    return [line.strip() for line in output.splitlines()
            if line.strip() and "HEAD" not in line]


def get_branch_info(repo_path="."):
    return {"local": get_local_branches(repo_path),
            "remote": get_remote_branches(repo_path)}


def get_commit_graph_data(repo_path, n=80):
    fmt = "%H\x1f%P\x1f%D\x1f%s\x1f%an\x1f%ar"
    output = _run(["log", "--all", f"--format={fmt}", f"-{n}", "--topo-order"],
                  cwd=repo_path)
    commits = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) < 6:
            continue
        parents = parts[1].split() if parts[1].strip() else []
        refs = []
        if parts[2].strip():
            for r in parts[2].split(","):
                r = r.strip()
                if r:
                    refs.append(r)
        commits.append({
            "hash": parts[0], "short": parts[0][:7],
            "parents": parents, "refs": refs,
            "message": parts[3], "author": parts[4], "date": parts[5],
        })
    return commits


def get_commit_history(repo_path, branch, n=30):
    fmt = "%h\x1f%s\x1f%an\x1f%ar"
    output = _run(["log", branch, f"--format={fmt}", f"-{n}"], cwd=repo_path)
    commits = []
    for line in output.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            commits.append({"hash": parts[0], "message": parts[1],
                             "author": parts[2], "date": parts[3]})
    return commits


def get_remotes(repo_path):
    try:
        output = _run(["remote", "-v"], cwd=repo_path)
    except RuntimeError:
        return {}
    remotes = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and "(fetch)" in line:
            remotes[parts[0]] = parts[1]
    return remotes


def add_remote(repo_path, name, url):
    _run(["remote", "add", name, url], cwd=repo_path)


def set_remote_url(repo_path, name, url):
    _run(["remote", "set-url", name, url], cwd=repo_path)


def remove_remote(repo_path, name):
    _run(["remote", "remove", name], cwd=repo_path)


STATUS_LABELS = {
    "M": "modified", "A": "added", "D": "deleted",
    "R": "renamed",  "C": "copied", "?": "untracked",
}

def get_status(repo_path):
    output = _run(["status", "--porcelain"], cwd=repo_path)
    staged, unstaged = [], []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        x, y, filepath = line[0], line[1], line[3:]
        if x not in (" ", "?"):
            staged.append({"file": filepath, "code": x,
                           "label": STATUS_LABELS.get(x, x)})
        if y != " ":
            unstaged.append({"file": filepath, "code": y,
                             "label": STATUS_LABELS.get(y, y)})
    return {"staged": staged, "unstaged": unstaged}


def stage_file(repo_path, filepath):
    _run(["add", filepath], cwd=repo_path)


def stage_all(repo_path):
    _run(["add", "-A"], cwd=repo_path)


def unstage_file(repo_path, filepath):
    try:
        _run(["restore", "--staged", filepath], cwd=repo_path)
    except RuntimeError as e:
        # 한 번도 커밋된 적 없는 새 파일은 restore가 안 됨 → rm --cached 사용
        if "pathspec" in str(e).lower() or "did not match" in str(e).lower():
            _run(["rm", "--cached", filepath], cwd=repo_path)
        else:
            raise


def unstage_all(repo_path):
    try:
        _run(["restore", "--staged", "."], cwd=repo_path)
    except RuntimeError as e:
        if "pathspec" in str(e).lower() or "did not match" in str(e).lower():
            _run(["rm", "--cached", "-r", "."], cwd=repo_path)
        else:
            raise


def commit(repo_path, message):
    if not message.strip():
        raise RuntimeError("Commit message cannot be empty.")
    _run(["commit", "-m", message], cwd=repo_path)


def get_graph(repo_path):
    return _run(["log", "--graph", "--oneline", "--all", "--decorate", "-50"],
                cwd=repo_path)


def checkout_branch(repo_path, branch):
    _run(["checkout", branch], cwd=repo_path)


def merge_branch(repo_path, branch, strategy="no-ff"):
    args = ["merge"]
    if strategy == "no-ff":
        args.append("--no-ff")
    elif strategy == "squash":
        args.append("--squash")
    args.append(branch)
    _run(args, cwd=repo_path)


def set_upstream(repo_path, local_branch, remote_branch):
    _run(["branch", f"--set-upstream-to={remote_branch}", local_branch], cwd=repo_path)


def push_and_track(repo_path, local_branch, remote_name):
    _run(["push", "-u", remote_name, local_branch], cwd=repo_path)


def create_branch(repo_path, name):
    _run(["branch", name], cwd=repo_path)


def delete_branch(repo_path, name):
    _run(["branch", "-d", name], cwd=repo_path)


def fetch(repo_path):
    _run(["fetch", "--all"], cwd=repo_path)


def pull(repo_path):
    _run(["pull"], cwd=repo_path)


def push(repo_path):
    _run(["push"], cwd=repo_path)
