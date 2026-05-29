def _status_tag(branch):
    if branch["ahead"] and branch["behind"]:
        return f"[↑{branch['ahead']} ↓{branch['behind']}]"
    if branch["ahead"]:
        return f"[↑{branch['ahead']} ahead]"
    if branch["behind"]:
        return f"[↓{branch['behind']} behind]"
    if branch["remote"]:
        return "[up to date]"
    return ""


def render(info):
    local = info["local"]
    remote = info["remote"]

    lines = []
    lines.append("=" * 50)
    lines.append("  Git Branch Structure")
    lines.append("=" * 50)

    lines.append("\nLOCAL BRANCHES")
    for i, b in enumerate(local):
        connector = "`--" if i == len(local) - 1 else "|--"
        marker = "*" if b["current"] else " "
        tracking = f"-> {b['remote']}" if b["remote"] else "(no remote)"
        tag = _status_tag(b)
        lines.append(f"  {connector} {marker} {b['name']:<20} {tracking:<30} {tag}")

    if remote:
        remotes_by_origin = {}
        for r in remote:
            origin, _, branch = r.partition("/")
            remotes_by_origin.setdefault(origin, []).append(branch)

        for origin, branches in remotes_by_origin.items():
            lines.append(f"\nREMOTE BRANCHES ({origin})")
            for i, b in enumerate(branches):
                connector = "`--" if i == len(branches) - 1 else "|--"
                lines.append(f"  {connector}   {b}")
    else:
        lines.append("\n  (no remote branches)")

    lines.append("")
    return "\n".join(lines)
