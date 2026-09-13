"""Remove embedded Gemini keys; optionally amend the known, unpushed commit.

Run with Python 3 from the Codespaces repository, using --repair-commit.
Never prints credentials, contacts Gemini, or pushes changes.
"""
import argparse
import ast
from pathlib import Path
import re
import subprocess

BLOCKED = "e2f6f16119e1d0c2b1a4cf0c639357eec4220768"
FOLDER = "06-data-infrastructure-for-gen-ai-app"
FILES = [
    "embeddings.py",
    "llm_api_with_context_enhanced_prompts_textual.py",
    "llm_api_with_context_enhanced_prompts_transactional.py",
    "llm_api_with_standalone_prompts.py",
    "store_embeddings_in_bigquery.py",
]
KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_-]{35}")


def clean_source(source):
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "GEMINI_API_KEY"
                           for t in node.targets)]
    if len(assignments) != 1:
        raise ValueError("Expected exactly one GEMINI_API_KEY assignment; inspect this file manually.")
    node = assignments[0]
    lines[node.lineno - 1:node.end_lineno] = [
        'GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()\n',
        'if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":\n',
        '    raise SystemExit("Set GEMINI_API_KEY in this terminal before running this script.")\n',
    ]
    text = "".join(lines)
    if not any(isinstance(n, ast.Import) and any(a.name == "os" and a.asname is None
               for a in n.names) for n in tree.body):
        raise ValueError("Expected import os; inspect this file manually.")
    text = re.sub(r'^\s*#\s*(?:GEMINI_API_KEY|api_key)\s*=.*\n', '', text, flags=re.M)
    text = text.replace('genai.Client(api_key=GEMINI_API_KEY)',
                        'genai.Client(vertexai=False, api_key=GEMINI_API_KEY)')
    text = text.replace('"gemini-2.0-flash-001"',
                        'os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")')
    text = KEY_PATTERN.sub("REMOVED_API_KEY", text)
    ast.parse(text)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--repair-commit", action="store_true")
    args = parser.parse_args()

    def git(*argv):
        result = subprocess.run(["git", "-C", args.repo, *argv], capture_output=True, text=True)
        if result.returncode:
            raise SystemExit("Git command failed: " + " ".join(argv))
        return result.stdout.strip()

    root = Path(git("rev-parse", "--show-toplevel"))
    if args.repair_commit:
        if git("rev-parse", "HEAD") != BLOCKED:
            raise SystemExit("STOP: HEAD is not the blocked commit. No files changed. Share: git log --oneline origin/main..HEAD")
        if git("status", "--porcelain", "--untracked-files=no"):
            raise SystemExit("STOP: tracked files have uncommitted changes. No files changed. Review git status first.")
        if BLOCKED in git("rev-list", "--remotes").splitlines():
            raise SystemExit("STOP: commit is already on a remote branch. No history changed.")

    # Validate all files before writing any of them.
    replacements = {}
    for name in FILES:
        path = root / FOLDER / name
        try:
            replacements[path] = clean_source(path.read_text())
        except (ValueError, SyntaxError, OSError):
            raise SystemExit("STOP: could not safely transform " + name + ". No files changed.")
    for path, content in replacements.items():
        path.write_text(content)
        print("Updated:", path.name)

    if args.repair_commit:
        git("add", "--", *[str(p.relative_to(root)) for p in replacements])
        git("-c", "core.editor=true", "commit", "--amend", "--no-edit")
        print("Amended the blocked commit:", git("rev-parse", "--short", "HEAD"))
        print("Run git push in Codespaces. GitHub will check the outgoing history again.")
    else:
        print("Files updated; no commits or remote changes made.")


if __name__ == "__main__":
    main()
