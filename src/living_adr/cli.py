"""Operator CLI for repository onboarding validation (feature 014, slice 4).

Thin wrapper over :class:`~living_adr.onboarding.validation.OnboardingValidator`.
It performs **no** YAML parsing and **no** GitHub API calls itself — config is
loaded through the feature 002 loader inside the validator, and installation
checks go through the feature 003 provider seam. The command only parses args,
runs the validator, prints the secret-safe report, and maps the result to an
exit code (0 pass, non-zero on any blocking diagnostic).

Spelling: ``living-adr onboard validate [--config PATH]`` (the plan's preferred
operator ergonomics). This is PoC single-repo onboarding validation; it does not
perform multi-repo governance automation, repository discovery, or hot reload.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from typing import TextIO

from living_adr.onboarding.diagnostics import format_result
from living_adr.onboarding.validation import (
    InstallationVerifier,
    OnboardingValidator,
)

_POC_LABEL = (
    "PoC single-repo onboarding validation — no multi-repo governance "
    "automation, repository discovery, or hot reload."
)
_NEXT_STEP = (
    "Start living-adr-workflow and send a webhook delivery (or replay a "
    "fixture) to begin ingestion."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="living-adr",
        description="LivingADR operator commands.",
    )
    commands = parser.add_subparsers(dest="command")
    onboard = commands.add_parser(
        "onboard", help="repository onboarding commands"
    )
    onboard_commands = onboard.add_subparsers(dest="onboard_command")
    validate = onboard_commands.add_parser(
        "validate",
        help="validate the configured repository's onboarding readiness",
    )
    validate.add_argument(
        "--config",
        default=None,
        help="path to living-adr.config.yaml (else LIVING_ADR_CONFIG / default)",
    )
    return parser


def run_onboard_validate(
    *,
    config_path: str | None = None,
    env: Mapping[str, str] | None = None,
    installation_verifier: InstallationVerifier | None = None,
    validator: OnboardingValidator | None = None,
    stream: TextIO | None = None,
) -> int:
    """Run onboarding validation and print a secret-safe operator report."""

    out = stream if stream is not None else sys.stdout
    resolved_env = env if env is not None else os.environ
    if validator is None:
        validator = OnboardingValidator(
            env=resolved_env,
            config_path=config_path,
            installation_verifier=installation_verifier,
        )
    result = validator.validate()

    print(format_result(result), file=out)
    print("", file=out)
    print(_POC_LABEL, file=out)
    if result.passed:
        print(f"Next step: {_NEXT_STEP}", file=out)
    return result.exit_code


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    installation_verifier: InstallationVerifier | None = None,
    validator: OnboardingValidator | None = None,
    stream: TextIO | None = None,
) -> int:
    """Entry point. Returns a process exit code."""

    out = stream if stream is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "onboard" and getattr(args, "onboard_command", None) == (
        "validate"
    ):
        return run_onboard_validate(
            config_path=args.config,
            env=env,
            installation_verifier=installation_verifier,
            validator=validator,
            stream=out,
        )

    parser.print_help(out)
    return 2


__all__ = ["build_parser", "run_onboard_validate", "main"]
