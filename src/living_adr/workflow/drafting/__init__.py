"""Drafting workflow services for feature 008 (claude-adr-drafting-capability).

Small, individually testable services composed by the feature-015 ADR draft
node: external-LLM policy gating, graph-context packaging, token budgeting,
prompt assembly, the Anthropic adapter, and the Markdown output parser. None of
these perform authoritative mutations.
"""
