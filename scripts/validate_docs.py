#!/usr/bin/env python3
"""validate_docs.py - Documentation Structure and Link Validator for WBS 1.0."""
import os
import re
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = WORKSPACE_ROOT / "docs"

REQUIRED_DOCS = [
    DOCS_DIR / "index.md",
    DOCS_DIR / "known-issues.md",
    DOCS_DIR / "coverage.md",
    DOCS_DIR / "architecture" / "overview.md",
    DOCS_DIR / "architecture" / "backend.md",
    DOCS_DIR / "architecture" / "frontend.md",
    DOCS_DIR / "architecture" / "export-import.md",
    DOCS_DIR / "database" / "schema.md",
    DOCS_DIR / "database" / "migrations.md",
    DOCS_DIR / "database" / "backup-recovery.md",
    DOCS_DIR / "api" / "endpoints.md",
    DOCS_DIR / "api" / "authentication.md",
    DOCS_DIR / "operations" / "bootstrap.md",
    DOCS_DIR / "operations" / "cli-reference.md",
    DOCS_DIR / "operations" / "troubleshooting.md",
    DOCS_DIR / "operations" / "backup-restore.md",
    DOCS_DIR / "security" / "security-model.md",
    DOCS_DIR / "decisions" / "0001-workspace-bootstrap-standard-adoption.md",
    DOCS_DIR / "decisions" / "0002-dual-backup-recovery-contract.md",
    DOCS_DIR / "decisions" / "0003-docker-first-local-development.md",
    DOCS_DIR / "templates" / "adr-template.md",
    DOCS_DIR / "templates" / "issue-template.md",
]

LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def check_required_files():
    errors = []
    print("[1/3] Checking required documentation files...")
    for doc in REQUIRED_DOCS:
        if not doc.is_file():
            errors.append(f"Missing required documentation file: {doc.relative_to(WORKSPACE_ROOT)}")
        else:
            if doc.stat().st_size == 0:
                errors.append(f"Empty documentation file: {doc.relative_to(WORKSPACE_ROOT)}")
    return errors


def check_internal_links():
    errors = []
    print("[2/3] Checking internal markdown links...")
    markdown_files = list(DOCS_DIR.glob("**/*.md"))
    top_level_mds = [WORKSPACE_ROOT / "README.md", WORKSPACE_ROOT / "AGENTS.md", WORKSPACE_ROOT / "CHANGELOG.md"]
    for top_md in top_level_mds:
        if top_md.is_file():
            markdown_files.append(top_md)

    for md_file in markdown_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"Failed to read {md_file.relative_to(WORKSPACE_ROOT)}: {e}")
            continue

        for match in LINK_PATTERN.finditer(content):
            link_text, link_target = match.groups()

            # Ignore external web links, email, or pure anchor links
            if (
                link_target.startswith("http://")
                or link_target.startswith("https://")
                or link_target.startswith("mailto:")
                or link_target.startswith("#")
                or link_target.startswith("file://")
                or link_target.startswith("conversation://")
            ):
                continue

            # Strip in-page anchors
            target_path_str = link_target.split("#")[0]
            if not target_path_str:
                continue

            # Resolve relative link
            target_path = (md_file.parent / target_path_str).resolve()
            if not target_path.exists():
                errors.append(
                    f"Broken link in {md_file.relative_to(WORKSPACE_ROOT)}: [{link_text}]({link_target}) -> {target_path_str} not found"
                )

    return errors


def check_manifest_consistency():
    errors = []
    print("[3/3] Checking workspace manifest and root documents...")
    manifest = WORKSPACE_ROOT / "workspace-manifest.yaml"
    agents_md = WORKSPACE_ROOT / "AGENTS.md"
    setup_sh = WORKSPACE_ROOT / "setup.sh"
    cw_cli = WORKSPACE_ROOT / "cw"

    for f in [manifest, agents_md, setup_sh, cw_cli]:
        if not f.exists():
            errors.append(f"Missing core WBS artifact: {f.relative_to(WORKSPACE_ROOT)}")

    return errors


def main():
    print("============================================================")
    print(" CalWriter Documentation Validator (WBS 1.0)")
    print("============================================================")

    all_errors = []
    all_errors.extend(check_required_files())
    all_errors.extend(check_internal_links())
    all_errors.extend(check_manifest_consistency())

    print("")
    if all_errors:
        print(f"✗ Validation failed with {len(all_errors)} error(s):")
        for err in all_errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("✓ All documentation files, links, and manifests validated successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()

