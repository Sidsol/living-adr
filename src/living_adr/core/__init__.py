"""Core domain types and stable seams for LivingADR.

Re-exports the configuration and repository-identity contracts established by
feature 002 so downstream features depend on ``living_adr.core`` rather than
parsing YAML or redefining identity models.
"""

from living_adr.core.adr import (
    SOURCE_OF_TRUTH_HIERARCHY,
    ADRRecord,
    ADRRecordRepository,
    ADRStatus,
    ProjectionConflict,
    ProjectionConflictResolution,
)
from living_adr.core.approval import (
    ApprovalError,
    ApprovalRequiredError,
    ApprovedReviewDecision,
    DecisionAlreadyConsumedError,
    DecisionRepositoryMismatchError,
    DraftContentMismatchError,
    MutationFingerprintMismatchError,
)
from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.graph import (
    ADRPath,
    ArchitectureContextQuery,
    ArchitectureGraphStore,
    ConformanceReport,
    GraphEdge,
    GraphSnapshotRef,
    MigrationResult,
    NodeId,
    ProvenancedADR,
    RelationshipType,
    SchemaVersion,
    UnsupportedRelationshipError,
)
from living_adr.core.graph.approval_bound_mutation import ApprovalBoundMutationService
from living_adr.core.ingestion import (
    DeliveryStatus,
    IngestionDelivery,
    IngestionErrorCategory,
)
from living_adr.core.observability import (
    NoOpObservability,
    Observability,
    ObservationSpan,
)
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    PullRequestMetadata,
    SCMEventEnvelope,
    SCMFetchHandle,
    SCMProvider,
    SCMProviderName,
    build_normalized_pr_key,
)

__all__ = [
    "RepositoryIdentity",
    "RepositoryConfig",
    "LivingADRConfig",
    "PublicationPolicy",
    "Observability",
    "NoOpObservability",
    "ObservationSpan",
    "DeliveryStatus",
    "IngestionDelivery",
    "IngestionErrorCategory",
    "SCMProviderName",
    "SCMEventEnvelope",
    "SCMFetchHandle",
    "SCMProvider",
    "PullRequestMetadata",
    "ChangedFileMetadata",
    "DiffEvidence",
    "CandidateEvidence",
    "build_normalized_pr_key",
    # Feature 006: graph store ports + approval seam (stable contracts).
    "ADRRecord",
    "ADRStatus",
    "ADRRecordRepository",
    "ProjectionConflict",
    "ProjectionConflictResolution",
    "SOURCE_OF_TRUTH_HIERARCHY",
    "ApprovedReviewDecision",
    "ApprovalError",
    "ApprovalRequiredError",
    "DecisionRepositoryMismatchError",
    "DraftContentMismatchError",
    "MutationFingerprintMismatchError",
    "DecisionAlreadyConsumedError",
    "ArchitectureGraphStore",
    "ArchitectureContextQuery",
    "ApprovalBoundMutationService",
    "NodeId",
    "GraphEdge",
    "RelationshipType",
    "UnsupportedRelationshipError",
    "SchemaVersion",
    "GraphSnapshotRef",
    "MigrationResult",
    "ConformanceReport",
    "ADRPath",
    "ProvenancedADR",
]
