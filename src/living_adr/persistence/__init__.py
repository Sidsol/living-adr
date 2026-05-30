"""Persistence package (feature 003).

Provides the durable ingestion delivery + candidate-evidence store used for
idempotency, replay, and dead-letter recovery. Exposes a Protocol plus an
in-memory implementation (primary test seam) and a SQLite-backed implementation
for durability per architecture #data-model.
"""
