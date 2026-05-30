"""Slice 1 tests: secret-safe onboarding diagnostic models + formatter.

Covers TASK-001 (aggregation/status/exit-code), TASK-003 (safe-metadata-only),
TASK-004 (redaction), and TASK-006 (category coverage). Pure deterministic logic;
no config, network, or environment dependency.
"""

from __future__ import annotations

from living_adr.onboarding.diagnostics import (
    CATEGORY_ORDER,
    REDACTED,
    DiagnosticCategory,
    DiagnosticSeverity,
    OnboardingDiagnostic,
    OnboardingValidationResult,
    format_result,
    redact_metadata,
    redact_value,
    safe_result_metadata,
)


def _diag(**kwargs) -> OnboardingDiagnostic:
    base = dict(
        category=DiagnosticCategory.CONFIG,
        severity=DiagnosticSeverity.INFO,
        message="ok",
    )
    base.update(kwargs)
    return OnboardingDiagnostic(**base)


# --- TASK-006: categories ---------------------------------------------------


def test_all_required_categories_exist() -> None:
    names = {c.value for c in DiagnosticCategory}
    assert names == {
        "config",
        "environment",
        "github_app",
        "permissions",
        "webhook_or_replay",
        "lifecycle",
    }


def test_category_order_is_complete_and_deterministic() -> None:
    assert tuple(CATEGORY_ORDER) == (
        DiagnosticCategory.CONFIG,
        DiagnosticCategory.ENVIRONMENT,
        DiagnosticCategory.GITHUB_APP,
        DiagnosticCategory.PERMISSIONS,
        DiagnosticCategory.WEBHOOK_OR_REPLAY,
        DiagnosticCategory.LIFECYCLE,
    )


def test_severities_exist() -> None:
    assert {s.value for s in DiagnosticSeverity} == {"info", "warning", "blocking"}


# --- TASK-001: aggregation, pass/fail status, exit-code mapping -------------


def test_result_passes_when_no_blocking_diagnostics() -> None:
    result = OnboardingValidationResult.from_diagnostics(
        [
            _diag(severity=DiagnosticSeverity.INFO),
            _diag(severity=DiagnosticSeverity.WARNING),
        ]
    )
    assert result.passed is True
    assert result.exit_code == 0


def test_result_fails_when_any_blocking_diagnostic_present() -> None:
    result = OnboardingValidationResult.from_diagnostics(
        [
            _diag(severity=DiagnosticSeverity.INFO),
            _diag(
                category=DiagnosticCategory.GITHUB_APP,
                severity=DiagnosticSeverity.BLOCKING,
                message="installation not found",
            ),
        ]
    )
    assert result.passed is False
    assert result.exit_code != 0
    assert [d.severity for d in result.blocking()] == [DiagnosticSeverity.BLOCKING]


def test_empty_result_passes_with_exit_zero() -> None:
    result = OnboardingValidationResult.from_diagnostics([])
    assert result.passed is True
    assert result.exit_code == 0


def test_by_category_groups_and_preserves_insertion_order() -> None:
    result = OnboardingValidationResult.from_diagnostics(
        [
            _diag(category=DiagnosticCategory.CONFIG, message="c1"),
            _diag(category=DiagnosticCategory.ENVIRONMENT, message="e1"),
            _diag(category=DiagnosticCategory.CONFIG, message="c2"),
        ]
    )
    grouped = result.by_category()
    assert [d.message for d in grouped[DiagnosticCategory.CONFIG]] == ["c1", "c2"]
    assert [d.message for d in grouped[DiagnosticCategory.ENVIRONMENT]] == ["e1"]


# --- TASK-001: formatter grouping + remediation -----------------------------


def test_formatter_groups_by_category_and_includes_remediation() -> None:
    result = OnboardingValidationResult.from_diagnostics(
        [
            _diag(
                category=DiagnosticCategory.ENVIRONMENT,
                severity=DiagnosticSeverity.BLOCKING,
                message="missing GITHUB_APP_ID",
                remediation="set GITHUB_APP_ID in your environment",
            ),
            _diag(
                category=DiagnosticCategory.CONFIG,
                severity=DiagnosticSeverity.BLOCKING,
                message="config file not found",
                remediation="create living-adr.config.yaml",
            ),
        ]
    )
    text = format_result(result)
    # Status line present and reflects failure.
    assert "FAIL" in text
    # Categories rendered in canonical order: config before environment.
    assert text.index("config") < text.index("environment")
    # Remediation text surfaced.
    assert "create living-adr.config.yaml" in text
    assert "set GITHUB_APP_ID in your environment" in text


def test_formatter_reports_pass_status() -> None:
    result = OnboardingValidationResult.from_diagnostics(
        [_diag(severity=DiagnosticSeverity.INFO, message="all good")],
        metadata={"repository_key": "github.com/acme/widgets"},
    )
    text = format_result(result)
    assert "PASS" in text
    assert "github.com/acme/widgets" in text


# --- TASK-003: safe metadata only -------------------------------------------


def test_safe_result_metadata_allowlist_drops_unknown_and_sensitive_keys() -> None:
    raw = {
        "repository_key": "github.com/acme/widgets",
        "config_path": "/etc/living-adr.config.yaml",
        "publication_policy": "livingadr_only",
        "installation_id": "inst-555",
        "default_branch": "main",
        "required_permissions": "contents:read",
        "next_step": "start workflow service",
        # Disallowed / sensitive — must not survive.
        "github_webhook_secret": "whsec_supersecret",
        "anthropic_api_key": "sk-ant-abc123",
        "raw_payload": {"action": "closed"},
        "arbitrary_field": "nope",
    }
    safe = safe_result_metadata(raw)
    assert safe["repository_key"] == "github.com/acme/widgets"
    assert safe["installation_id"] == "inst-555"
    assert "github_webhook_secret" not in safe
    assert "anthropic_api_key" not in safe
    assert "raw_payload" not in safe
    assert "arbitrary_field" not in safe


def test_success_output_contains_only_safe_metadata() -> None:
    result = OnboardingValidationResult.from_diagnostics(
        [_diag(severity=DiagnosticSeverity.INFO)],
        metadata=safe_result_metadata(
            {
                "repository_key": "github.com/acme/widgets",
                "installation_id": "inst-555",
                "github_app_private_key": "-----BEGIN PRIVATE KEY-----abc",
            }
        ),
    )
    text = format_result(result)
    assert "inst-555" in text
    assert "PRIVATE KEY" not in text
    assert "github_app_private_key" not in text


# --- TASK-004: redaction ----------------------------------------------------


def test_redact_metadata_masks_sensitive_keys() -> None:
    redacted = redact_metadata(
        {
            "repository_key": "github.com/acme/widgets",
            "github_webhook_secret": "whsec_abc",
            "anthropic_api_key": "sk-ant-xyz",
            "langsmith_api_key": "lsv2_pt_abc",
            "ui_token": "tok_abc",
            "private_key_path": "/keys/app.pem",
            "raw_payload": "{...}",
            "diff": "diff --git a/x b/x",
            "prompt": "system prompt text",
            "draft": "provisional ADR draft",
            "reviewer_comment": "looks good",
        }
    )
    assert redacted["repository_key"] == "github.com/acme/widgets"
    for sensitive in (
        "github_webhook_secret",
        "anthropic_api_key",
        "langsmith_api_key",
        "ui_token",
        "private_key_path",
        "raw_payload",
        "diff",
        "prompt",
        "draft",
        "reviewer_comment",
    ):
        assert redacted[sensitive] == REDACTED


def test_redact_value_masks_secret_signatures_in_strings() -> None:
    assert redact_value("-----BEGIN PRIVATE KEY-----\nMIIE...") == REDACTED
    assert redact_value("ghp_1234567890abcdef") == REDACTED
    assert redact_value("github_pat_11ABC") == REDACTED
    assert redact_value("sk-ant-api03-xyz") == REDACTED
    assert redact_value("lsv2_pt_secret") == REDACTED
    # Non-secret strings pass through unchanged.
    assert redact_value("github.com/acme/widgets") == "github.com/acme/widgets"
    assert redact_value("main") == "main"


def test_diagnostic_message_with_embedded_secret_is_redacted_in_output() -> None:
    result = OnboardingValidationResult.from_diagnostics(
        [
            _diag(
                category=DiagnosticCategory.GITHUB_APP,
                severity=DiagnosticSeverity.BLOCKING,
                message="auth failed using key -----BEGIN PRIVATE KEY-----leak",
            )
        ]
    )
    text = format_result(result)
    assert "PRIVATE KEY" not in text
    assert REDACTED in text


def test_diagnostic_safe_metadata_redacts_sensitive_fields() -> None:
    diag = _diag(
        metadata={
            "repository_key": "github.com/acme/widgets",
            "webhook_secret": "whsec_leak",
        }
    )
    safe = diag.safe_metadata()
    assert safe["repository_key"] == "github.com/acme/widgets"
    assert safe["webhook_secret"] == REDACTED
