from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .exceptions import EnvGuardError, ParseError
from .parser import parse_env_file
from .syncer import compare_env_files, generate_example_template, sync_env_files
from .validator import EnvValidator, is_placeholder

# Terminal ANSI color helpers
USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def green(text: str) -> str:
    return _color(text, "32")


def red(text: str) -> str:
    return _color(text, "31")


def yellow(text: str) -> str:
    return _color(text, "33")


def cyan(text: str) -> str:
    return _color(text, "36")


def bold(text: str) -> str:
    return _color(text, "1")


def dim(text: str) -> str:
    return _color(text, "2")


def cmd_check(args: argparse.Namespace) -> int:
    env_path = Path(args.env)
    example_path = Path(args.example)

    if not example_path.exists():
        print(red(f"Error: Template file '{example_path}' not found."))
        return 2

    if not env_path.exists():
        print(red(f"Error: Target env file '{env_path}' not found."))
        print(yellow(f"Run 'envguard sync --example {example_path} --env {env_path}' to generate it."))
        return 1

    try:
        tmpl = parse_env_file(example_path)
        target = parse_env_file(env_path)
    except ParseError as err:
        print(red(f"Syntax error: {err} (Line {err.line_number})"))
        return 2

    diff = compare_env_files(tmpl, target)
    has_errors = False

    print(f"\n{bold('EnvGuard Audit Report')}")
    print(f"Comparing: {cyan(str(env_path))} vs template {cyan(str(example_path))}\n")

    if diff.missing_in_target:
        has_errors = True
        print(red(f"[X] Missing Variables ({len(diff.missing_in_target)}):"))
        for k in diff.missing_in_target:
            line_no = tmpl.entries[k].line_number
            print(f"  {red('-')} {bold(k)} {dim(f'(defined in {example_path}:{line_no})')}")
        print()

    if diff.empty_in_target:
        has_errors = True
        print(yellow(f"[!] Empty or Unresolved Placeholders ({len(diff.empty_in_target)}):"))
        for k in diff.empty_in_target:
            val = target.entries[k].value
            line_no = target.entries[k].line_number
            desc = "empty" if not val else f"placeholder '{val}'"
            print(f"  {yellow('!')} {bold(k)}: {desc} {dim(f'({env_path}:{line_no})')}")
        print()

    if diff.extra_in_target:
        if args.strict:
            has_errors = True
            print(red(f"[X] Undocumented Variables (--strict mode) ({len(diff.extra_in_target)}):"))
        else:
            print(dim(f"[i] Extra Variables (not in template) ({len(diff.extra_in_target)}):"))
        for k in diff.extra_in_target:
            line_no = target.entries[k].line_number
            print(f"  + {k} {dim(f'({env_path}:{line_no})')}")
        print()

    if diff.matching_keys:
        print(green(f"[+] {len(diff.matching_keys)} variables valid and populated."))

    if has_errors:
        print(red("\n[X] Environment check failed. Fix issues above before proceeding.\n"))
        return 1

    print(green("\n[OK] Environment configuration is in sync and healthy!\n"))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    env_path = Path(args.env)
    example_path = Path(args.example)

    try:
        tmpl = parse_env_file(example_path)
        target = parse_env_file(env_path)
    except FileNotFoundError as err:
        print(red(f"Error: {err}"))
        return 2

    diff = compare_env_files(tmpl, target)

    print(f"\n{bold('Environment Diff')}: {example_path} -> {env_path}\n")
    print(f"  {green('Matching:')} {len(diff.matching_keys)}")
    print(f"  {red('Missing in target:')} {len(diff.missing_in_target)}")
    print(f"  {yellow('Empty/Placeholder:')} {len(diff.empty_in_target)}")
    print(f"  {cyan('Extra in target:')} {len(diff.extra_in_target)}\n")

    return 0 if not diff.missing_in_target and not diff.empty_in_target else 1


def cmd_sync(args: argparse.Namespace) -> int:
    template_path = Path(args.example)
    target_path = Path(args.env)

    if not template_path.exists():
        print(red(f"Error: Template '{template_path}' not found."))
        return 2

    if args.dry_run:
        tmpl = parse_env_file(template_path)
        target = parse_env_file(target_path) if target_path.exists() else None
        missing = [k for k in tmpl.entries if not target or k not in target.entries]
        print(f"Dry run: {len(missing)} keys would be added to {target_path}:")
        for k in missing:
            print(f"  + {k}")
        return 0

    updated, added = sync_env_files(template_path, target_path, fill_defaults=not args.empty)
    if not updated:
        print(green(f"[OK] '{target_path}' is already up to date with '{template_path}'."))
        return 0

    print(green(f"[OK] Successfully added {len(added)} missing keys to '{target_path}':"))
    for k in added:
        print(f"  + {k}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    src_path = Path(args.env)
    out_path = Path(args.out)

    if not src_path.exists():
        print(red(f"Error: Source file '{src_path}' does not exist."))
        return 2

    if out_path.exists() and not args.force:
        print(yellow(f"Warning: '{out_path}' already exists. Use --force to overwrite."))
        return 1

    generate_example_template(src_path, out_path, mask_secrets=not args.no_mask)
    print(green(f"[OK] Generated example template at '{out_path}' (secrets safely masked)."))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="envguard",
        description="A lightweight CLI to audit, diff, and synchronize environment variables.",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colored output")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # check command
    check_p = subparsers.add_parser("check", help="Validate .env against .env.example")
    check_p.add_argument("-e", "--env", default=".env", help="Target env file (default: .env)")
    check_p.add_argument("-x", "--example", default=".env.example", help="Template file (default: .env.example)")
    check_p.add_argument("--strict", action="store_true", help="Fail if target contains extra unlisted keys")

    # diff command
    diff_p = subparsers.add_parser("diff", help="Show differences between two env files")
    diff_p.add_argument("-e", "--env", default=".env", help="Target env file (default: .env)")
    diff_p.add_argument("-x", "--example", default=".env.example", help="Template file (default: .env.example)")

    # sync command
    sync_p = subparsers.add_parser("sync", help="Synchronize missing variables from template into .env")
    sync_p.add_argument("-e", "--env", default=".env", help="Target env file (default: .env)")
    sync_p.add_argument("-x", "--example", default=".env.example", help="Template file (default: .env.example)")
    sync_p.add_argument("--empty", action="store_true", help="Leave added keys empty instead of copying defaults")
    sync_p.add_argument("--dry-run", action="store_true", help="Preview keys to add without writing")

    # init command
    init_p = subparsers.add_parser("init", help="Generate a sanitized .env.example from an existing .env")
    init_p.add_argument("-e", "--env", default=".env", help="Source env file (default: .env)")
    init_p.add_argument("-o", "--out", default=".env.example", help="Output template file (default: .env.example)")
    init_p.add_argument("-f", "--force", action="store_true", help="Overwrite output file if it exists")
    init_p.add_argument("--no-mask", action="store_true", help="Do not mask sensitive keys with placeholders")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.no_color:
        global USE_COLOR
        USE_COLOR = False

    if not args.command:
        # Default action: run check
        args.command = "check"
        args.env = ".env"
        args.example = ".env.example"
        args.strict = False

    handler_map = {
        "check": cmd_check,
        "diff": cmd_diff,
        "sync": cmd_sync,
        "init": cmd_init,
    }

    handler = handler_map.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
