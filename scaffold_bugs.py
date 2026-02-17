import os
import re

REPORT_FILE = "tests/REPORTS/current/emilia_daily_2026-02-15.md"
BUG_BASE_DIR = ".emiliabedilia/bugs"
REPO_PATH = "/home/vmlinux/srcwpsg/pim/pre"


def scaffold():
    if not os.path.exists(BUG_BASE_DIR):
        os.makedirs(BUG_BASE_DIR)

    with open(REPORT_FILE, "r") as f:
        content = f.read()

    # Find P0 section
    p0_start = content.find("### P0")
    p1_start = content.find("### P1")

    if p0_start == -1:
        print("No P0 section found")
        return

    p0_content = content[p0_start:p1_start] if p1_start != -1 else content[p0_start:]

    lines = p0_content.splitlines()
    bug_idx = 1

    bugs = [l for l in lines if l.strip().startswith("-")]
    print(f"BUGS_FOUND: {len(bugs)}")
    print(f"P0: {len(bugs)}, P1: 0, P2: 0")

    for line in lines:
        line = line.strip()
        if not line.startswith("-"):
            continue

        # Format: - **[testing]** CLI entry point broken - calls main() instead of app(), TypeError on all invocations
        match = re.match(r"- \*\*\[(.*?)\]\*\* (.*)", line)
        if match:
            demon = match.group(1)
            rest = match.group(2)

            title = rest
            description = rest
            file_ref = "Unknown"

            bug_dir = os.path.join(BUG_BASE_DIR, f"BUG_{bug_idx:03d}")
            os.makedirs(bug_dir, exist_ok=True)

            bug_report_content = f"""# BUG_{bug_idx:03d}: {title}
**Severity:** P0
**Source Demon:** {demon}
**File:** {file_ref}
**Description:** {description}
**Repository:** {REPO_PATH}
"""
            with open(os.path.join(bug_dir, "BUG_REPORT.md"), "w") as f:
                f.write(bug_report_content)

            print(f"BUG_{bug_idx:03d}|P0|{demon}|{title}|{file_ref}")
            bug_idx += 1


if __name__ == "__main__":
    scaffold()
