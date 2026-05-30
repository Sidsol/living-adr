"""Core domain types and stable seams for LivingADR.

Re-exports the configuration and repository-identity contracts established by
feature 002 so downstream features depend on ``living_adr.core`` rather than
parsing YAML or redefining identity models.
"""

from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.repository import RepositoryIdentity

__all__ = [
    "RepositoryIdentity",
    "RepositoryConfig",
    "LivingADRConfig",
    "PublicationPolicy",
]
