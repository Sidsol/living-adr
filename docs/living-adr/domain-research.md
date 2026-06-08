# Domain Research: architecture-decision-records-automation

<!-- CRISPY Project Phase: RESEARCH → produces domain-research.md -->
<!-- BLIND research. Do NOT read vision.md. Investigate the problem domain & external landscape only. -->

> ⚠️ **Blind Research:** Conducted without knowledge of the project vision or planned product.
> This ensures unbiased exploration of the domain and prior art.

**Researched:** 2026-05-25  
**Domain area:** architecture-decision-records-automation

---

## 1. Domain Overview

Architecture Decision Records (ADRs) are a lightweight architecture-knowledge management practice for preserving the context, chosen option, alternatives, status, and consequences of significant technical decisions. Michael Nygard's 2011 ADR post framed ADRs as small, modular, repository-stored text files that future developers can read to avoid "blindly accept" or "blindly change" past decisions ([Nygard 2011](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)). MADR, Y-Statements, adr-tools, Log4brains, arc42, and Backstage TechDocs represent mature docs-as-code prior art for capturing, reviewing, and publishing decision knowledge ([MADR](https://adr.github.io/madr/), [ADR templates](https://adr.github.io/adr-templates/), [adr-tools](https://github.com/npryce/adr-tools), [Log4brains](https://github.com/thomvaill/log4brains), [arc42 §9](https://docs.arc42.org/section-9/), [Backstage TechDocs](https://backstage.io/docs/features/techdocs/)).

Automation around ADRs intersects with software repository mining, code knowledge graphs, graph/RAG retrieval, LLM agents, source-control events, and human approval workflows. Existing systems extract signals from commits, pull requests, diffs, code structure, docs, issues, and reviews; represent them as relational databases, property graphs, RDF triples, vector embeddings, or hybrid GraphRAG indexes; and use agents or workflow engines to summarize, classify, propose, review, and publish artifacts. CodeQL and Joern show the precision-oriented static-analysis side of code representation, while Sourcegraph, LlamaIndex PropertyGraphIndex, and Microsoft GraphRAG show search/retrieval-oriented designs ([CodeQL](https://codeql.github.com/docs/codeql-overview/about-codeql/), [Joern CPG](https://docs.joern.io/code-property-graph/), [Sourcegraph Code Search](https://sourcegraph.com/docs/code-search), [LlamaIndex PropertyGraphIndex](https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/), [Microsoft GraphRAG](https://microsoft.github.io/graphrag/)).

The common actors in this domain are architects, developers, tech leads, maintainers, platform teams, security reviewers, compliance teams, and reviewers of AI-generated artifacts. Common workflows include proposing an ADR during design, linking ADRs to pull requests or issues, discovering decisions from existing repositories, classifying structural changes, producing summaries of PR intent, reviewing suggested documentation, publishing docs portals, and measuring documentation health. The most repeated tension in the literature and tooling is that the value is in "why" and context, while most automated signals are better at "what changed" than "why it was decided" ([Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), [GitHub Copilot PR summaries](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/copilot-on-github/copilot-for-github-tasks/create-a-pr-summary), [Buchgeher et al. ADR MSR study](https://se.jku.at/using-architecture-decision-records-in-open-source-projects-an-msr-study-on-github/)).

---

## 2. Glossary (Ubiquitous Language)

| Term | Meaning |
|---|---|
| ADR | Architecture Decision Record: a short record of one architecturally significant decision, its context, status, and consequences ([Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)). |
| Architectural Decision | A justified software design choice addressing an architecturally significant functional or non-functional requirement ([MADR](https://adr.github.io/madr/)). |
| Architecturally Significant Requirement (ASR) | A requirement that meaningfully constrains system structure, qualities, dependencies, interfaces, or construction techniques; arc42 and ADR guidance use ASRs to decide what merits architecture documentation ([arc42 §9](https://docs.arc42.org/section-9/)). |
| Nygard ADR | The original lightweight ADR shape with title, context, decision, status, and consequences ([Nygard 2011](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)). |
| MADR | Markdown Architectural Decision Records: a structured Markdown ADR template family with options, tradeoffs, status, consequences, and metadata ([MADR](https://adr.github.io/madr/)). |
| Y-Statement | A concise ADR/rationale sentence: in a context, facing a concern, decide for an option and against alternatives to achieve qualities while accepting downsides ([ADR templates](https://adr.github.io/adr-templates/), [Zimmermann](https://ozimmer.ch/practices/2020/04/27/ArchitectureDecisionMaking.html)). |
| Lightweight ADR | A small, low-ceremony ADR stored as text, commonly Markdown, intended to be easy to read, review, and update ([Nygard 2011](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)). |
| Any Decision Record | The broader use of ADR-style records for important design, product, operations, or organizational decisions, not only architecture decisions ([MADR background](https://adr.github.io/madr/)). |
| ADR status | A lifecycle marker such as proposed, accepted, deprecated, or superseded that indicates whether a decision is current ([Nygard 2011](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)). |
| Superseded ADR | An ADR retained for history but marked as replaced by a later decision ([adr-tools](https://github.com/npryce/adr-tools)). |
| Docs-as-code | A documentation workflow using version control, plain text, reviews, issue trackers, and automated tests like source code ([Write the Docs](https://www.writethedocs.org/guide/docs-as-code/)). |
| Documentation rot | Documentation becoming stale, misleading, or untrusted as code and architecture evolve; ADR adoption/staleness risk is observed in ADR and documentation studies ([Buchgeher et al.](https://se.jku.at/using-architecture-decision-records-in-open-source-projects-an-msr-study-on-github/), [Fluri et al. DOI](https://doi.org/10.1109/WCRE.2007.21)). |
| Ubiquitous language | A shared vocabulary used consistently by domain experts and implementers; this glossary is intended to seed that vocabulary for later phases. |
| Property graph | A graph of labeled nodes and directed, labeled edges with key-value properties; Joern describes CPGs as directed, edge-labeled, attributed multigraphs ([Joern CPG](https://docs.joern.io/code-property-graph/)). |
| RDF knowledge graph | A W3C-standard graph model based on subject-predicate-object triples, IRIs, literals, datasets, and RDF vocabularies ([W3C RDF 1.1](https://www.w3.org/TR/rdf11-concepts/)). |
| Knowledge graph | A structured representation of entities and relationships, often used to support traversal, reasoning, retrieval, and explanation. |
| GraphRAG | Graph-based Retrieval-Augmented Generation that extracts a knowledge graph, clusters it into communities, summarizes communities, and uses graph structures at query time ([Microsoft GraphRAG](https://microsoft.github.io/graphrag/)). |
| RAG | Retrieval-Augmented Generation: retrieving external context and supplying it to a language model to ground answers. |
| Flat RAG / Baseline RAG | A RAG pattern that retrieves top-k text chunks by vector similarity without explicit entity/relation traversal; Microsoft GraphRAG contrasts this with graph-assisted retrieval ([Microsoft GraphRAG](https://microsoft.github.io/graphrag/)). |
| RAG faithfulness | Whether generated answer claims are supported by retrieved context; Ragas defines it as supported claims divided by total claims ([Ragas faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)). |
| RAG answer relevance | Whether a response directly addresses the user input; Ragas estimates it through generated-question similarity ([Ragas answer relevancy](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/)). |
| RAG context recall | How many reference-answer claims are supported by retrieved context; Ragas uses it to detect missing context ([Ragas context recall](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/)). |
| RAG context precision | How well the retriever ranks relevant chunks ahead of irrelevant ones ([Ragas context precision](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/)). |
| Code Property Graph (CPG) | A program-analysis graph combining syntax, control-flow, and data-flow representations to query code patterns and vulnerabilities ([Joern CPG](https://docs.joern.io/code-property-graph/)). |
| CodeQL database | A relational representation of a codebase extracted by CodeQL, then queried for security and correctness patterns ([CodeQL](https://codeql.github.com/docs/codeql-overview/about-codeql/)). |
| Semantic code search | Search over code using structure, symbols, natural language, regex, embeddings, or code intelligence rather than only exact text matching ([Sourcegraph Code Search](https://sourcegraph.com/docs/code-search)). |
| Vector embedding | A numerical representation of text/code used for similarity search; often effective for fuzzy retrieval but weak at exact structural or causal reasoning. |
| Intent extraction | Automated inference of what a change does and why it was made from commits, PR descriptions, diffs, issue links, reviews, and conventions. |
| Structural change | A codebase change that alters architecture-relevant structure such as dependencies, interfaces, modules, data flow, deployment topology, or non-functional behavior. |
| Conventional Commits | A commit-message convention with typed prefixes such as `feat`, `fix`, and `BREAKING CHANGE` to expose machine-readable change intent ([Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)). |
| PR summarization | AI- or rule-assisted generation of pull request summaries from diffs and metadata; GitHub Copilot can generate PR summaries but asks users to review them carefully ([GitHub Copilot PR summaries](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/copilot-on-github/copilot-for-github-tasks/create-a-pr-summary)). |
| Agent workflow | A multi-step LLM/tool process with state, events, retries, routing, and sometimes human review. |
| LangGraph | A low-level orchestration runtime for long-running, stateful agents with durable execution, streaming, human-in-the-loop, memory, and LangSmith debugging ([LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)). |
| LlamaIndex Workflows | An event-driven, step-based execution framework where steps are triggered by events and emit events for later steps ([LlamaIndex Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/)). |
| LlamaIndex PropertyGraphIndex | A LlamaIndex abstraction for constructing and querying labeled property graphs from documents, using extractors and retrievers ([PropertyGraphIndex](https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/)). |
| MCP | Model Context Protocol: an open protocol using JSON-RPC to connect LLM applications with external data sources and tools ([MCP spec](https://modelcontextprotocol.io/specification/2025-06-18)). |
| MCP host | The LLM application that initiates connections and contains MCP clients ([MCP spec](https://modelcontextprotocol.io/specification/2025-06-18)). |
| MCP client | The connector inside a host that communicates with an MCP server ([MCP spec](https://modelcontextprotocol.io/specification/2025-06-18)). |
| MCP server | A service exposing tools, resources, and prompts to MCP clients ([MCP spec](https://modelcontextprotocol.io/specification/2025-06-18)). |
| MCP transport | The communication mechanism for MCP messages; current spec defines stdio and Streamable HTTP, with HTTP optionally using SSE ([MCP transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)). |
| Tool invocation | An LLM or agent calling an external function, API, command, or MCP tool, often requiring consent and audit. |
| Human-in-the-loop (HITL) | A workflow pattern where a human approves, edits, rejects, labels, or resumes automated work; LangGraph interrupts and GitHub reviews are examples ([LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [GitHub PR reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews)). |
| Approval queue | A UI/workflow collection of pending items awaiting approve/edit/reject actions, common in code review and labeling systems. |
| SCM event | A source-control event such as push, pull request opened/synchronized/closed, review submitted, or check completed. |
| GitHub App | A GitHub integration model with fine-grained permissions, repository installation scope, webhooks, and short-lived tokens ([GitHub Apps](https://docs.github.com/en/apps/overview)). |
| GitHub Actions workflow | A GitHub-native workflow triggered by repository events, schedules, or external events ([Actions events](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows)). |
| Webhook | An HTTP callback delivering event payloads to an external server when subscribed events occur ([GitHub webhooks](https://docs.github.com/en/webhooks/about-webhooks)). |
| Azure DevOps service hook | Azure DevOps event subscription that runs tasks or posts messages to external services when project events occur ([Azure DevOps Service Hooks](https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview?view=azure-devops)). |
| LLM observability trace | A structured record of model calls, retrieval, tool use, custom logic, latency, errors, cost, and outputs for debugging and evaluation ([Phoenix](https://arize.com/docs/phoenix), [Langfuse](https://langfuse.com/docs)). |
| OpenTelemetry GenAI semantic conventions | Development-status OpenTelemetry conventions for GenAI events, exceptions, metrics, model spans, agent spans, and MCP telemetry ([OpenTelemetry GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)). |
| Prompt injection | A GenAI security risk where crafted inputs manipulate an LLM or agent into unintended actions; OWASP lists it as an LLM Top 10 category ([OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)). |
| Excessive agency | Granting LLMs too much unchecked ability to act, causing unintended reliability, privacy, or trust consequences; OWASP lists it as an LLM risk ([OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)). |

---

## 3. External Systems & Integrations Commonly Found

| System / API | Role in domain | Notes |
|---|---|---|
| Git repositories | Source of code, docs, ADR files, commit history, ownership, and branch topology | Nygard and adr-tools place ADRs in repository paths such as `doc/adr` or `doc/arch` ([Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions), [adr-tools](https://github.com/npryce/adr-tools)). |
| GitHub / GitHub Enterprise | SCM, PRs, checks, reviews, Apps, Actions, webhooks, Copilot PR summaries | GitHub Apps are preferred over OAuth apps for fine-grained repo permissions and short-lived tokens ([GitHub Apps](https://docs.github.com/en/apps/overview)). |
| Azure DevOps | Repos, pull requests, service hooks, extensions, pipelines | Service hooks publish project events to consumers; extensions customize UI and use REST APIs ([Service Hooks](https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview?view=azure-devops), [Extensions](https://learn.microsoft.com/en-us/azure/devops/extend/overview?view=azure-devops)). |
| Webhook endpoints | Event ingestion for PR, review, push, issue, and check events | Webhooks scale better than polling but require signature validation, retry handling, idempotency, and event ordering logic ([GitHub webhooks](https://docs.github.com/en/webhooks/about-webhooks)). |
| CI/CD systems | Enforcement and publication point for docs-as-code, ADR linting, generated docs, and status checks | GitHub Actions workflows run on repository events but not every webhook event maps to a workflow trigger ([Actions events](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows)). |
| Issue trackers | Source of rationale, discussions, acceptance criteria, and linked changes | GitHub Apps and Azure DevOps service hooks both support issue/work-item event integrations ([GitHub Apps](https://docs.github.com/en/apps/overview), [Azure Service Hooks](https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview?view=azure-devops)). |
| ADR tooling | Create, number, supersede, search, publish, and lint decision records | Examples: adr-tools, MADR, YADR, Log4brains ([adr-tools](https://github.com/npryce/adr-tools), [MADR](https://adr.github.io/madr/), [YADR](https://github.com/adr/yadr/), [Log4brains](https://github.com/thomvaill/log4brains)). |
| Documentation portals | Publish docs/ADRs and connect them to service catalogs | Backstage TechDocs is a docs-like-code solution; Backstage catalog uses human-maintainable `catalog-info.yaml` descriptors ([TechDocs](https://backstage.io/docs/features/techdocs/), [Catalog descriptor](https://backstage.io/docs/features/software-catalog/descriptor-format/)). |
| Static analysis engines | Extract code structure, dependencies, call/data-flow, and security findings | Joern uses CPGs; CodeQL extracts relational databases from source; both are more precise than unstructured text retrieval for static properties ([Joern CPG](https://docs.joern.io/code-property-graph/), [CodeQL](https://codeql.github.com/docs/codeql-overview/about-codeql/)). |
| Code search / code intelligence | Discover symbols, references, diffs, commits, and cross-repo patterns | Sourcegraph provides code search, commit/diff search, and code navigation across repositories ([Sourcegraph Code Search](https://sourcegraph.com/docs/code-search)). |
| Graph databases | Store and query entities, relationships, lineage, ownership, and code/doc links | Examples: Neo4j/Cypher, JanusGraph/Gremlin, TigerGraph/GSQL, Memgraph/Cypher-like query surfaces ([Neo4j Cypher](https://neo4j.com/docs/cypher-manual/current/introduction/), [JanusGraph](https://docs.janusgraph.org/), [TigerGraph](https://docs.tigergraph.com/), [Memgraph](https://memgraph.com/docs)). |
| RDF triple stores / semantic web tooling | Interoperable knowledge graphs with W3C RDF/SPARQL semantics | RDF uses subject-predicate-object triples and datasets ([W3C RDF 1.1](https://www.w3.org/TR/rdf11-concepts/)). |
| Vector databases / embedding indexes | Similarity search over code, docs, diffs, issues, and ADR text | Useful for fuzzy recall; often combined with graph traversals in GraphRAG or PropertyGraphIndex designs ([Microsoft GraphRAG](https://microsoft.github.io/graphrag/), [PropertyGraphIndex](https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/)). |
| LLM providers / gateways | Generate summaries, classify intent, extract entities, and produce draft artifacts | Observability and gateway tools such as Helicone track cost, latency, and errors ([Helicone](https://docs.helicone.ai/getting-started/platform-overview)). |
| Agent orchestration frameworks | Coordinate multi-step LLM/tool workflows, retries, state, and human approval | LangGraph, LlamaIndex Workflows, CrewAI, AutoGen, and Semantic Kernel are representative ([LangGraph](https://docs.langchain.com/oss/python/langgraph/overview), [LlamaIndex Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/), [CrewAI](https://docs.crewai.com/introduction), [AutoGen](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/agents.html), [Semantic Kernel Agent Framework](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/)). |
| MCP hosts and servers | IDE/agent integration surface for external tools, resources, and prompts | MCP uses JSON-RPC with hosts, clients, servers, resources, prompts, and tools ([MCP spec](https://modelcontextprotocol.io/specification/2025-06-18)). |
| LLM observability platforms | Trace, evaluate, debug, and monitor LLM/RAG/agent workflows | LangSmith, Phoenix, OpenLLMetry, Langfuse, Helicone, and OpenTelemetry GenAI conventions are common references ([LangSmith](https://docs.smith.langchain.com/), [Phoenix](https://arize.com/docs/phoenix), [OpenLLMetry](https://www.traceloop.com/docs/openllmetry/introduction), [Langfuse](https://langfuse.com/docs), [Helicone](https://docs.helicone.ai/getting-started/platform-overview), [OpenTelemetry GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)). |
| Human review / labeling tools | Approve, edit, reject, annotate, and evaluate AI outputs | GitHub PR reviews, LangGraph interrupts, Label Studio, and Amazon A2I illustrate review/annotation workflows ([GitHub PR reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews), [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [Label Studio ML](https://labelstud.io/guide/ml), [Amazon A2I](https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-getting-started.html)). |
| Identity, permissions, and secrets systems | Control repository access, app installation scope, model keys, and API credentials | GitHub App permissions are explicit and should be minimum necessary; MCP/VS Code docs warn about untrusted local servers and secrets in config ([GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app), [VS Code MCP](https://code.visualstudio.com/docs/copilot/chat/mcp-servers)). |

---

## 4. Reference Architectures

### Reference A — In-repository ADR log with CLI-assisted lifecycle

- **Source:** Michael Nygard ADR pattern and `adr-tools` ([Nygard 2011](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions), [adr-tools](https://github.com/npryce/adr-tools))
- **Shape:** ADRs live as small Markdown files inside the project repository, commonly under `doc/adr`, `doc/arch`, or `docs/adr`. The CLI initializes the ADR directory, creates numbered files, and can mark earlier decisions as superseded. Review happens through the same branch/PR process as code.
- **Notable strengths:** Low tooling barrier; versioned with code; easy to diff/review; preserves history; supports supersession rather than destructive edits; aligns with docs-as-code.
- **Notable weaknesses:** Captures only what humans remember to write; weak global discoverability across many repos; numbering can cause merge friction; status drift and stale decisions are not automatically detected; rationale quality varies widely.
- **Applicability notes:** Strong baseline for ADR automation because most downstream automation can treat the repo as the source of record, but automation must not confuse file presence with accurate rationale.

### Reference B — Structured ADR template family (MADR, Y-Statement, YADR)

- **Source:** MADR, ADR templates, Y-Statement, YADR ([MADR](https://adr.github.io/madr/), [ADR templates](https://adr.github.io/adr-templates/), [Zimmermann](https://ozimmer.ch/practices/2020/04/27/ArchitectureDecisionMaking.html), [YADR](https://github.com/adr/yadr/))
- **Shape:** A template defines decision metadata, context, considered options, decision outcome, consequences, and sometimes a compact rationale sentence. MADR is Markdown-oriented; YADR ports MADR/Y-Statement concepts to YAML with schema validation examples.
- **Notable strengths:** Higher semantic consistency than free-form ADRs; options/pros/cons improve "why" quality; YAML variants are easier for automation to parse; Y-Statements force concise rationale.
- **Notable weaknesses:** More fields can become ceremony; YAML is less readable for narrative context; schema compliance cannot prove decision quality; teams may cargo-cult templates without discussing alternatives.
- **Applicability notes:** Useful prior art for machine-readable ADRs and extraction targets. A key distinction is whether automation emits human-friendly prose, schema-first records, or both.

### Reference C — ADR knowledge base and docs portal

- **Source:** Log4brains and Backstage TechDocs/catalog ([Log4brains](https://github.com/thomvaill/log4brains), [Backstage TechDocs](https://backstage.io/docs/features/techdocs/), [Backstage catalog descriptor](https://backstage.io/docs/features/software-catalog/descriptor-format/))
- **Shape:** ADRs and Markdown docs stay in Git but are rendered into a searchable static/documentation portal. Backstage connects docs to catalog entities described by YAML descriptors, while Log4brains provides ADR creation, local preview, static site generation, search, timeline, and git-derived metadata.
- **Notable strengths:** Improves discovery and onboarding; keeps authors in Git workflow; supports search and chronology; connects docs to service ownership/catalog context; portal UX can make ADRs more visible than buried files.
- **Notable weaknesses:** Publication pipelines can fail or lag; portal search does not guarantee freshness; catalog ownership metadata can drift; Log4brains explicitly trades enforced structure for flexibility, which weakens machine extraction; static sites may obscure PR review context.
- **Applicability notes:** Strong pattern for publishing and discovering ADRs, but not by itself an intent-extraction or staleness-detection architecture.

### Reference D — Code property graph / queryable static-analysis knowledge base

- **Source:** Joern CPG and CodeQL ([Joern CPG](https://docs.joern.io/code-property-graph/), [CodeQL](https://codeql.github.com/docs/codeql-overview/about-codeql/), [CodeQL CLI](https://docs.github.com/en/code-security/codeql-cli/getting-started-with-the-codeql-cli/about-the-codeql-cli))
- **Shape:** Source code is parsed into an intermediate representation. Joern merges syntax, control-flow, and data-flow into a property graph queried by a DSL; CodeQL creates a relational database extracted from code and queries it for variants, vulnerabilities, and patterns.
- **Notable strengths:** Precise structural evidence; explainable traversals/queries; strong for security, data flow, dependency analysis, and exact code patterns; reproducible from code snapshots.
- **Notable weaknesses:** Expensive to build and update; language support varies; dynamic/runtime behavior, generated code, and infrastructure context may be missed; mapping low-level code facts to high-level architectural intent is not automatic.
- **Applicability notes:** Best reference for evidence-backed "what structure changed" detection; needs augmentation from PR/issues/docs for "why".

### Reference E — Property-graph / GraphRAG retrieval layer for "why" questions

- **Source:** Microsoft GraphRAG and LlamaIndex PropertyGraphIndex ([Microsoft GraphRAG](https://microsoft.github.io/graphrag/), [LlamaIndex PropertyGraphIndex](https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/), [W3C RDF](https://www.w3.org/TR/rdf11-concepts/))
- **Shape:** Documents or code-adjacent artifacts are chunked, entities and relationships are extracted, graph communities are summarized, and query-time retrieval uses graph traversals plus text context. LlamaIndex provides extraction/retrieval abstractions over labeled property graphs; RDF provides a standardized triple-based alternative.
- **Notable strengths:** Better multi-hop and global-context retrieval than flat vector search when relationships are accurate; graph summaries help holistic questions; can combine vector and graph retrievers; graph paths provide inspectable evidence.
- **Notable weaknesses:** Entity/relation extraction can hallucinate; graph schemas can drift; graph construction can be costly; RDF interoperability may add modeling overhead; property graphs can become vendor/query-language specific; GraphRAG docs warn prompt/config tuning is often needed.
- **Applicability notes:** Relevant for connecting decisions, code structures, commits, owners, and docs, especially where "why" depends on cross-artifact relations.

### Reference F — Stateful LLM agent orchestration runtime

- **Source:** LangGraph, LlamaIndex Workflows, CrewAI, AutoGen, Semantic Kernel Agent Framework ([LangGraph](https://docs.langchain.com/oss/python/langgraph/overview), [LlamaIndex Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/), [CrewAI](https://docs.crewai.com/introduction), [AutoGen](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/agents.html), [Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/))
- **Shape:** Workflows model a task as graph nodes, event-driven steps, flows/crews, stateful agents, messages, and tool calls. LangGraph emphasizes durable execution and interrupts; LlamaIndex Workflows emphasize event-triggered steps; CrewAI separates flows from collaborative crews; AutoGen models stateful agent conversations; Semantic Kernel provides agent abstractions and orchestration.
- **Notable strengths:** Encodes multi-step processes, retries, state, branching, and human approval; supports long-running agent tasks; integrates retrieval, tools, and model calls; frameworks increasingly provide observability hooks.
- **Notable weaknesses:** Framework APIs evolve rapidly; agent behavior is nondeterministic; state persistence and idempotency are easy to get wrong; tool execution creates safety risk; multi-agent designs can obscure accountability and cost.
- **Applicability notes:** Mature enough to study for orchestration patterns, but long-lived domain systems need explicit boundaries, deterministic checkpoints, and human gates for generated artifacts.

### Reference G — MCP-based IDE/agent integration surface

- **Source:** MCP spec, VS Code MCP, GitHub Copilot MCP docs ([MCP spec](https://modelcontextprotocol.io/specification/2025-06-18), [MCP transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports), [MCP authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization), [VS Code MCP](https://code.visualstudio.com/docs/copilot/chat/mcp-servers), [GitHub Copilot MCP](https://docs.github.com/en/copilot/customizing-copilot/extending-copilot-chat-with-mcp))
- **Shape:** An IDE or agent host connects to configured MCP servers. Servers expose tools, resources, and prompts over JSON-RPC via stdio or Streamable HTTP. Users or enterprises configure servers at workspace/user/organization levels, and hosts mediate trust and tool consent.
- **Notable strengths:** Standardizes tool/resource exposure across hosts; local stdio servers are easy to package; HTTP supports remote services and auth; IDE integration makes context/action surfaces developer-native; Copilot and VS Code docs show mainstream adoption.
- **Notable weaknesses:** Authorization is optional and HTTP-focused; stdio credential handling is environment-specific; local servers can run arbitrary code; enterprise policies can disable MCP; server trust UX is still evolving; transport names changed from early HTTP+SSE patterns to Streamable HTTP in current spec.
- **Applicability notes:** Strong reference for extensibility seams, especially IDE and CLI integration; security posture and consent UI are first-class architecture concerns.

### Reference H — SCM event-driven bot / automation integration

- **Source:** GitHub Apps/webhooks/Actions, GitHub rate limits, Azure DevOps service hooks/extensions ([GitHub Apps](https://docs.github.com/en/apps/overview), [GitHub webhooks](https://docs.github.com/en/webhooks/about-webhooks), [GitHub Actions events](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows), [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), [Azure Service Hooks](https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview?view=azure-devops), [Azure Extensions](https://learn.microsoft.com/en-us/azure/devops/extend/overview?view=azure-devops))
- **Shape:** A platform integration receives SCM events, calls APIs under scoped permissions, posts comments/checks/statuses, triggers workflows, and/or updates docs. GitHub Apps provide installation-scoped tokens and webhooks; Actions run workflows inside GitHub; Azure DevOps service hooks publish events to consumers and extensions add UI/task surfaces.
- **Notable strengths:** Near-real-time triggers; mature permission/audit models; PR lifecycle events provide natural review gates; checks/comments integrate into existing developer workflows; comparable GitHub/Azure DevOps seams enable portability analysis.
- **Notable weaknesses:** Event delivery can be duplicated or missed; APIs have primary and secondary rate limits; webhooks require public/reachable endpoints or relays; Actions security differs by event type; cross-SCM abstractions leak due to different event taxonomies and permission models.
- **Applicability notes:** Reference for event ingestion and artifact proposal workflows; robust systems need idempotency, replay/backfill, rate-limit strategy, and platform-specific adapters.

---

## 5. Prior Art / Competitive Landscape

| Product / Project | Approach summary | Strength | Weakness |
|---|---|---|---|
| Michael Nygard ADR | Original lightweight ADR practice in small repo-stored text files ([source](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)) | Simple, influential, easy to adopt | Manual authoring; stale status risk; limited metadata |
| MADR | Structured Markdown ADR templates with options and consequences ([source](https://adr.github.io/madr/)) | Better tradeoff capture; active template variants | More ceremony than Nygard; quality still depends on authors |
| Y-Statement | One-sentence rationale format emphasizing context, concern, option, alternatives, benefit, downside ([source](https://ozimmer.ch/practices/2020/04/27/ArchitectureDecisionMaking.html)) | Forces concise "why" | Too compact for complex evidence; may omit operational details |
| YADR | YAML ADR templates/examples and JSON-schema validation for ADR structures ([source](https://github.com/adr/yadr/)) | Machine-readable ADR path | Less familiar/readable than Markdown; not as widely adopted as MADR |
| adr-tools | CLI for initializing ADR directories, creating numbered ADRs, and superseding old ADRs ([source](https://github.com/npryce/adr-tools)) | Low friction lifecycle automation | Focused on files/lifecycle, not semantic extraction |
| Log4brains | Docs-as-code ADR knowledge base with CLI, local preview, static site, search, timeline, git metadata ([source](https://github.com/thomvaill/log4brains)) | Improves visibility and publishing | Does not enforce structure; project appears feature-limited/stale in some areas |
| Backstage TechDocs | Docs-like-code publishing integrated into developer portal and service catalog ([source](https://backstage.io/docs/features/techdocs/)) | Enterprise discovery; catalog/service linkage | Depends on healthy catalog ownership and docs maintenance |
| Backstage Software Catalog | YAML descriptors for components, APIs, systems, owners, lifecycle, and relations ([source](https://backstage.io/docs/features/software-catalog/descriptor-format/)) | Stable metadata anchor for service ownership | Catalog drift and incomplete ownership metadata are common operational risks |
| Joern | Code property graph framework for querying code patterns and vulnerabilities ([source](https://docs.joern.io/code-property-graph/)) | Precise structural/data-flow evidence | Heavy setup; language coverage and dynamic behavior limits |
| CodeQL | Relational code database and query language for variant analysis and code scanning ([source](https://codeql.github.com/docs/codeql-overview/about-codeql/)) | Mature security ecosystem; CI integration | Query authoring expertise needed; not designed for rationale extraction |
| Sourcegraph Code Search | Cross-repo code, diff, commit, and symbol search/navigation ([source](https://sourcegraph.com/docs/code-search)) | Developer-friendly discovery and investigation | Search results still need interpretation; less precise than custom static analysis for deep data flow |
| Neo4j | Property graph database with Cypher query language ([source](https://neo4j.com/docs/cypher-manual/current/introduction/)) | Mature graph ecosystem and tooling | Vendor/query-language coupling; ontology governance required |
| JanusGraph | Distributed property graph database over storage backends, using TinkerPop/Gremlin ([source](https://docs.janusgraph.org/)) | Scales large graphs; open source | Operational complexity; tuning and backend tradeoffs |
| TigerGraph | Enterprise graph database and GSQL ecosystem ([source](https://docs.tigergraph.com/)) | High-scale analytics focus | Commercial/platform lock-in considerations |
| Memgraph | Real-time graph database with Cypher-like ecosystem ([source](https://memgraph.com/docs)) | Low-latency graph analytics | Smaller ecosystem than Neo4j; modeling still required |
| RDF / SPARQL stack | W3C-standard triple model and datasets ([source](https://www.w3.org/TR/rdf11-concepts/)) | Interoperability and semantic-web standards | Verbose modeling; can be heavier than pragmatic property graphs |
| LlamaIndex PropertyGraphIndex | Framework abstraction for extracting and querying labeled property graphs from documents ([source](https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/)) | Integrates graph and vector retrieval | LLM extraction accuracy and schema control are risks |
| Microsoft GraphRAG | Graph extraction, community detection, summaries, and graph-informed query modes ([source](https://microsoft.github.io/graphrag/)) | Strong prior art for multi-hop/global questions | Indexing cost, prompt tuning, and extracted-graph quality risks |
| Conventional Commits | Structured commit-message convention exposing type, scope, body, footer, breaking changes ([source](https://www.conventionalcommits.org/en/v1.0.0/)) | Machine-readable change signal | Only as good as author discipline; `feat/fix` rarely captures architecture rationale |
| GitHub Copilot PR summaries | AI-generated PR summaries in descriptions/comments for reviewers ([source](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/copilot-on-github/copilot-for-github-tasks/create-a-pr-summary)) | Demonstrates mainstream AI diff summarization | Must be reviewed; ignores existing PR description according to docs |
| Sweep AI | GitHub issue/PR-oriented AI coding bot prior art ([source](https://github.com/sweepai/sweep)) | Shows event-driven AI code-change workflow | Bot-oriented code generation is not equivalent to trustworthy decision rationale |
| LangGraph | Stateful agent orchestration with durable execution and human-in-the-loop ([source](https://docs.langchain.com/oss/python/langgraph/overview)) | Strong control over state and HITL | Low-level; requires careful implementation discipline |
| LlamaIndex Workflows | Event-driven step/event framework for AI apps ([source](https://docs.llamaindex.ai/en/stable/module_guides/workflow/)) | Natural for branching/looping pipelines | Less opinionated about governance and reviews |
| CrewAI | Flows plus crews of collaborating agents ([source](https://docs.crewai.com/introduction)) | Clear autonomy/control split | Multi-agent autonomy can hide accountability and increase cost |
| AutoGen AgentChat | Stateful multi-agent conversation framework with tools ([source](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/agents.html)) | Good for conversational multi-agent experiments | Kitchen-sink agent warning; statefulness can surprise users |
| Semantic Kernel Agent Framework | Microsoft agent abstractions and orchestration packages ([source](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/)) | Enterprise/.NET/Python ecosystem integration | Multiple agent types and packages add design complexity |
| MCP | Open protocol for LLM apps to access tools/resources/prompts ([source](https://modelcontextprotocol.io/specification/2025-06-18)) | Cross-host extensibility | Trust, consent, auth, and server ecosystem maturity are active concerns |
| VS Code / Copilot MCP support | IDE integration for configuring and invoking MCP servers ([source](https://code.visualstudio.com/docs/copilot/chat/mcp-servers), [source](https://docs.github.com/en/copilot/customizing-copilot/extending-copilot-chat-with-mcp)) | Developer-native tool surface | Local arbitrary-code warning; enterprise policies may gate usage |
| GitHub Apps / webhooks / Actions | SCM integration primitives for events and automation ([source](https://docs.github.com/en/apps/overview), [source](https://docs.github.com/en/webhooks/about-webhooks), [source](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows)) | Native PR/check/review workflows | Rate limits, event semantics, and permissions require robust design |
| Azure DevOps service hooks/extensions | Comparable integration model for Azure DevOps events and UI/API extension ([source](https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview?view=azure-devops), [source](https://learn.microsoft.com/en-us/azure/devops/extend/overview?view=azure-devops)) | Useful cross-platform comparison | Different event taxonomy and extension model from GitHub |
| LangSmith | Framework-agnostic tracing/evaluation/deployment platform for agents and LLM apps ([source](https://docs.smith.langchain.com/)) | Integrated agent debugging/evals | Commercial platform considerations |
| Arize Phoenix | Open-source AI observability/evaluation with OpenTelemetry/OpenInference traces ([source](https://arize.com/docs/phoenix)) | Strong tracing, eval, datasets, human annotations | Needs instrumentation and eval discipline |
| OpenLLMetry | OpenTelemetry-based LLM tracing instrumentation ([source](https://www.traceloop.com/docs/openllmetry/introduction)) | Vendor-neutral telemetry export | Observability backend/eval layer still needed |
| Langfuse | Open-source LLM engineering platform for traces, prompts, evaluation, datasets ([source](https://langfuse.com/docs)) | Self-hostable, broad integrations | Trace data can be sensitive; governance required |
| Helicone | LLM gateway and observability for costs, latency, errors, routing ([source](https://docs.helicone.ai/getting-started/platform-overview)) | Easy gateway-based monitoring | Proxy/gateway trust and provider-routing dependency |
| Label Studio | Human labeling/review platform with ML-assisted preannotations and model evaluation ([source](https://labelstud.io/guide/ml)) | Mature HITL annotation workflow | Labeling UX is not the same as developer review UX |
| Amazon Augmented AI | Managed human review workflows around ML predictions ([source](https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-getting-started.html)) | Shows enterprise HITL pattern | AWS-specific; less tailored to code artifacts |

---

## 6. Regulatory / Compliance Considerations

- **No single ADR-automation-specific regulation was found.** Compliance pressure comes from the artifacts processed: source code, repository metadata, personal data in commits/issues, secrets, LLM prompts/outputs, and audit trails.
- **Privacy / personal data:** GDPR applies to personal data, defined as information relating to an identified or identifiable natural person; repository data can include names, emails, review comments, issue content, and telemetry identifiers ([GDPR personal data](https://gdpr.eu/eu-gdpr-personal-data/)).
- **AI governance:** The EU AI Act creates risk-based obligations for AI systems and GPAI providers/deployers; ordinary developer-assistance tooling is not automatically high-risk, but deployers/providers still need classification, transparency, and governance analysis where outputs affect EU users or regulated domains ([EU AI Act official text](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689)).
- **GenAI security:** OWASP's GenAI/LLM Top 10 flags prompt injection, insecure output handling, sensitive information disclosure, insecure plugin design, excessive agency, and overreliance as domain-relevant risks for LLM agents and tool integrations ([OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)).
- **SCM permissions:** GitHub Apps have no permissions by default, and selected permissions determine both API access and webhook availability; minimum required permissions are a documented best practice ([GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)).
- **MCP trust and auth:** MCP authorization is optional and transport-level; HTTP transports should follow the spec, stdio should retrieve credentials from the environment, and hosts must implement consent/control because the protocol cannot enforce all security principles ([MCP authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization), [MCP security principles](https://modelcontextprotocol.io/specification/2025-06-18)).
- **Local tool execution:** VS Code warns that local MCP servers can run arbitrary code and should only be added from trusted sources; it also warns against hardcoding sensitive information in MCP config ([VS Code MCP](https://code.visualstudio.com/docs/copilot/chat/mcp-servers)).
- **Telemetry and trace data:** OpenTelemetry GenAI conventions include inputs/outputs, model spans, agent spans, and MCP telemetry, so observability design must treat traces as potentially sensitive source/prompt/output data ([OpenTelemetry GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)).
- **Architecture documentation standards:** ISO/IEC/IEEE 42010:2022 specifies requirements for architecture descriptions but does not mandate a recording format; arc42 and ADR templates are commonly used practical complements ([ISO 42010:2022](https://www.iso.org/standard/74393.html), [arc42 §9](https://docs.arc42.org/section-9/)).
- **Auditability:** Code review systems expose approve/comment/request-changes states and protected-branch review requirements, providing a familiar audit model for generated artifacts ([GitHub PR reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews)).

---

## 7. Common Failure Modes & Risks in This Domain

1. **ADR never created at decision time.** ADR adoption remains low in open-source repositories, and many ADR-using repositories have only one to five ADRs, suggesting trial without durable adoption ([Buchgeher et al.](https://se.jku.at/using-architecture-decision-records-in-open-source-projects-an-msr-study-on-github/)).
2. **ADR status rot.** Decisions can remain marked accepted even after context changes; Nygard's own lifecycle relies on humans marking decisions superseded/deprecated ([Nygard 2011](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)).
3. **Over-documentation and ADR fatigue.** Zimmermann warns not to document everything and notes that very large AD logs are hard to maintain and put readers to sleep ([Zimmermann](https://ozimmer.ch/practices/2020/04/27/ArchitectureDecisionMaking.html)).
4. **Pseudo-rationale and missing alternatives.** ADRs that say "everybody does it" or omit alternatives fail to answer why; Zimmermann's good/bad justification examples identify this as a recurring anti-pattern ([Zimmermann](https://ozimmer.ch/practices/2020/04/27/ArchitectureDecisionMaking.html)).
5. **Decision ownership loss.** The motivating ADR scenario is that people leave and remaining contributors no longer remember the forces behind decisions ([Nygard 2011](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)).
6. **After-the-fact hallucinated rationale.** Automated tools can infer "what changed" from diffs more reliably than "why it was decided"; Conventional Commits expose types/scopes but bodies/footers are optional and human-authored ([Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)).
7. **Static graph blind spots.** CPG/CodeQL representations depend on language frontends/extractors and may miss runtime behavior, generated code, deployment topology, and external system behavior ([Joern CPG](https://docs.joern.io/code-property-graph/), [CodeQL](https://codeql.github.com/docs/codeql-overview/about-codeql/)).
8. **Graph schema drift.** Property graph schemas and labels can evolve without governance; JanusGraph docs show operational knobs/backends and graph-level complexity rather than a universal schema ([JanusGraph](https://docs.janusgraph.org/)).
9. **Embeddings retrieve similarity, not causality.** Microsoft GraphRAG notes baseline vector RAG struggles when answers require connecting disparate information through shared attributes ([Microsoft GraphRAG](https://microsoft.github.io/graphrag/)).
10. **GraphRAG false edges and entity-resolution errors.** LlamaIndex PropertyGraphIndex relies on extractors, including LLM path extraction, so graph quality depends on extraction and validation settings ([LlamaIndex PropertyGraphIndex](https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/)).
11. **Low RAG faithfulness.** Answers may contain claims unsupported by retrieved context; faithfulness metrics explicitly check claim support ([Ragas faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)).
12. **Retriever misses relevant context.** Low context recall means important evidence was not retrieved, undermining generated rationale ([Ragas context recall](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/)).
13. **Agent excessive agency.** OWASP flags unchecked LLM autonomy as a security/reliability risk for agentic systems ([OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)).
14. **Prompt/tool injection.** OWASP prompt injection and insecure plugin/tool design risks apply directly to agents reading repository content and invoking tools ([OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)).
15. **MCP local-server trust failure.** VS Code warns local MCP servers can run arbitrary code and should be trusted before start ([VS Code MCP](https://code.visualstudio.com/docs/copilot/chat/mcp-servers)).
16. **MCP auth mismatch.** MCP authorization is optional and HTTP-specific; stdio credentials are environment-based, creating inconsistent security models across transports ([MCP authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)).
17. **SCM event duplication, gaps, and replay complexity.** Webhooks deliver near-real-time events but robust integrations must handle delivery, API access, and polling/rate-limit tradeoffs ([GitHub webhooks](https://docs.github.com/en/webhooks/about-webhooks), [GitHub rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)).
18. **Rate-limit starvation during backfill.** GitHub REST API primary limits vary by auth mode and installation; repository-scale mining can consume limits quickly ([GitHub rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)).
19. **PR summary overtrust.** GitHub Copilot PR summaries must be reviewed carefully and do not consider existing PR description content according to docs ([GitHub Copilot PR summaries](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/copilot-on-github/copilot-for-github-tasks/create-a-pr-summary)).
20. **HITL rubber-stamping and approval fatigue.** Code review systems support approve/request-changes/comment, but required approvals can become procedural if reviewers lack time or evidence ([GitHub PR reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews)).
21. **Sensitive data in traces.** Langfuse and Phoenix trace model calls, retrieval, tool use, and outputs; OpenTelemetry GenAI conventions include GenAI input/output events, so telemetry can contain code, prompts, secrets, or personal data if not redacted ([Langfuse](https://langfuse.com/docs), [Phoenix](https://arize.com/docs/phoenix), [OpenTelemetry GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)).
22. **Evaluation overfitting.** Dataset-driven evaluations improve regression detection, but metrics like faithfulness/relevance/recall only measure what is in the evaluation set and reference data ([Ragas metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/), [Phoenix evaluations](https://arize.com/docs/phoenix)).
23. **Docs-as-code without review gates.** Docs-as-code benefits assume version control, code reviews, and automated tests; merely colocating Markdown with code does not force updates ([Write the Docs](https://www.writethedocs.org/guide/docs-as-code/)).
24. **Cross-SCM abstraction leaks.** GitHub Apps/webhooks/Actions and Azure DevOps service hooks/extensions expose different event, permission, and UI models ([GitHub Apps](https://docs.github.com/en/apps/overview), [Azure Service Hooks](https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview?view=azure-devops), [Azure Extensions](https://learn.microsoft.com/en-us/azure/devops/extend/overview?view=azure-devops)).

---

## 8. Organizational Context (WorkIQ findings, if any)

- WorkIQ was not queried in this blind research run. No internal ADRs, post-mortems, or platform notes were incorporated. This avoids accidental discovery of planned-product context and keeps the artifact based on public domain/prior-art sources only.

---

## 9. Key References

| Type | Title / URL | Why relevant |
|---|---|---|
| Article | Michael Nygard, "Documenting Architecture Decisions" — https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions | Origin of lightweight ADR practice and lifecycle/status concepts. |
| Template/spec | MADR — https://adr.github.io/madr/ | Structured Markdown ADR template family. |
| Template/spec | ADR templates incl. Nygard, MADR, Y-Statement — https://adr.github.io/adr-templates/ | Comparative ADR templates and Y-Statement description. |
| Template/spec | YADR — https://github.com/adr/yadr/ | YAML ADR templates/examples and schema validation prior art. |
| Article | Olaf Zimmermann, Architectural Decision Making — https://ozimmer.ch/practices/2020/04/27/ArchitectureDecisionMaking.html | ADR history, Y-Statements, good/bad rationale, and anti-patterns. |
| Tool | adr-tools — https://github.com/npryce/adr-tools | CLI lifecycle pattern for ADR creation/supersession. |
| Tool | Log4brains — https://github.com/thomvaill/log4brains | ADR knowledge-base/static-site prior art. |
| Standard/template | arc42 Architecture Decisions — https://docs.arc42.org/section-9/ | Widely used architecture-documentation template guidance for ADRs. |
| Platform | Backstage TechDocs — https://backstage.io/docs/features/techdocs/ | Docs-like-code portal pattern. |
| Platform | Backstage catalog descriptor — https://backstage.io/docs/features/software-catalog/descriptor-format/ | Service catalog YAML model relevant to ownership/context. |
| Study | Buchgeher et al., Using ADRs in OSS Projects — https://se.jku.at/using-architecture-decision-records-in-open-source-projects-an-msr-study-on-github/ | Empirical ADR adoption study and low-adoption evidence. |
| Study | Fluri et al., Do Code and Comments Co-Evolve? DOI — https://doi.org/10.1109/WCRE.2007.21 | Documentation/code co-evolution and stale-comment research. |
| Practice | Write the Docs, Docs as Code — https://www.writethedocs.org/guide/docs-as-code/ | Docs-as-code workflow definition and benefits. |
| Code graph | Joern Code Property Graph — https://docs.joern.io/code-property-graph/ | CPG architecture and building blocks. |
| Code analysis | CodeQL overview — https://codeql.github.com/docs/codeql-overview/about-codeql/ | Relational code analysis and variant-analysis pattern. |
| Code search | Sourcegraph Code Search — https://sourcegraph.com/docs/code-search | Cross-repo code/diff/commit search prior art. |
| Graph standard | RDF 1.1 Concepts — https://www.w3.org/TR/rdf11-concepts/ | RDF/triple model comparison point. |
| Graph DB | JanusGraph docs — https://docs.janusgraph.org/ | Distributed property graph database prior art. |
| RAG/graph | LlamaIndex PropertyGraphIndex — https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/ | Graph extraction/retrieval abstraction. |
| RAG/graph | Microsoft GraphRAG — https://microsoft.github.io/graphrag/ | GraphRAG reference architecture and baseline-RAG weaknesses. |
| VCS convention | Conventional Commits — https://www.conventionalcommits.org/en/v1.0.0/ | Machine-readable commit-intent convention. |
| PR AI | GitHub Copilot PR summaries — https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/copilot-on-github/copilot-for-github-tasks/create-a-pr-summary | AI PR summary workflow and limitation notes. |
| Agent framework | LangGraph overview — https://docs.langchain.com/oss/python/langgraph/overview | Stateful orchestration, durable execution, HITL. |
| Agent framework | LlamaIndex Workflows — https://docs.llamaindex.ai/en/stable/module_guides/workflow/ | Event-driven workflow model. |
| Agent framework | CrewAI introduction — https://docs.crewai.com/introduction | Flows/crews architecture for multi-agent workflows. |
| Agent framework | AutoGen AgentChat — https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/agents.html | Stateful multi-agent conversation pattern. |
| Agent framework | Semantic Kernel Agent Framework — https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/ | Enterprise agent abstraction and orchestration pattern. |
| Protocol | MCP specification — https://modelcontextprotocol.io/specification/2025-06-18 | Host/client/server/tool/resource/prompt protocol. |
| Protocol | MCP transports — https://modelcontextprotocol.io/specification/2025-06-18/basic/transports | stdio and Streamable HTTP transport details/security warning. |
| Protocol | MCP authorization — https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization | Optional OAuth-based authorization model. |
| IDE integration | VS Code MCP servers — https://code.visualstudio.com/docs/copilot/chat/mcp-servers | IDE configuration, trust, and local-server caveats. |
| IDE integration | GitHub Copilot MCP — https://docs.github.com/en/copilot/customizing-copilot/extending-copilot-chat-with-mcp | Copilot/VS Code MCP integration and enterprise policy context. |
| SCM integration | GitHub Apps — https://docs.github.com/en/apps/overview | GitHub integration and permission model. |
| SCM integration | GitHub webhooks — https://docs.github.com/en/webhooks/about-webhooks | Event delivery pattern and polling comparison. |
| SCM integration | GitHub Actions events — https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows | Workflow-trigger event surface. |
| SCM integration | GitHub REST rate limits — https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api | API limit constraints for repository mining. |
| SCM integration | Azure DevOps Service Hooks — https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview?view=azure-devops | Comparable event integration surface. |
| SCM integration | Azure DevOps Extensions — https://learn.microsoft.com/en-us/azure/devops/extend/overview?view=azure-devops | Comparable UI/API extension surface. |
| HITL | GitHub PR reviews — https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews | Approve/comment/request-changes pattern. |
| HITL | LangGraph interrupts — https://docs.langchain.com/oss/python/langgraph/interrupts | Pause/resume human approval pattern in agent workflows. |
| HITL | Label Studio ML integration — https://labelstud.io/guide/ml | Human review of ML predictions and autolabeling. |
| HITL | Amazon Augmented AI — https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-getting-started.html | Managed human review workflow prior art. |
| Observability | LangSmith — https://docs.smith.langchain.com/ | LLM/agent tracing/evaluation platform. |
| Observability | Arize Phoenix — https://arize.com/docs/phoenix | OpenTelemetry-based AI observability/evaluation. |
| Observability | OpenLLMetry — https://www.traceloop.com/docs/openllmetry/introduction | OpenTelemetry tracing instrumentation. |
| Observability | Langfuse — https://langfuse.com/docs | Open-source traces, prompts, evaluation, datasets. |
| Observability | Helicone — https://docs.helicone.ai/getting-started/platform-overview | LLM gateway and cost/latency/error observability. |
| Observability standard | OpenTelemetry GenAI semantic conventions — https://opentelemetry.io/docs/specs/semconv/gen-ai/ | Standardized GenAI events, metrics, model/agent spans, MCP telemetry. |
| Evaluation | Ragas faithfulness — https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/ | Grounded-answer metric. |
| Evaluation | Ragas answer relevancy — https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/ | User-input relevance metric. |
| Evaluation | Ragas context recall — https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/ | Retrieval coverage metric. |
| Evaluation | Ragas context precision — https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/ | Retrieval ranking metric. |
| Security | OWASP Top 10 for LLM Applications — https://owasp.org/www-project-top-10-for-large-language-model-applications/ | Prompt injection, sensitive information disclosure, excessive agency, plugin risks. |
| Privacy | GDPR personal data — https://gdpr.eu/eu-gdpr-personal-data/ | Personal-data definition relevant to repository/user telemetry. |
| Regulation | EU AI Act official text — https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689 | Risk-based AI governance context. |
| Standard | ISO/IEC/IEEE 42010:2022 — https://www.iso.org/standard/74393.html | Architecture-description standard context. |

**Research fetch notes:** Direct fetches failed or were inaccessible for some candidate sources: OpenAI docs pages returned 403, ACM DOI pages returned 403, docs-as-co.de failed to fetch, and Increment documentation-decay returned 403. They were not relied on for factual claims; accessible substitutes are cited above.

---

## 10. Open Questions for Architecture

1. **ADR threshold:** Which prior-art definition of "architecturally significant" will bound automation: Nygard/arc42 ASR scope, MADR options, service-catalog changes, security-sensitive changes, or another observable rule?
2. **Source-of-truth hierarchy:** When code, ADRs, PR summaries, issues, and graph-derived facts conflict, which source is authoritative for current vs. historical rationale?
3. **Representation choice:** Is the domain best modeled as Markdown/YAML ADR files, a property graph, RDF triples, relational tables, vector indexes, or a hybrid graph+vector architecture?
4. **Temporal modeling:** How should decisions, supersessions, PRs, commits, releases, and code graph snapshots be related over time?
5. **Intent confidence:** What evidence threshold distinguishes a proposed decision rationale from an extracted/observed fact?
6. **SCM integration boundary:** Which integration family is the baseline comparison point: GitHub App/webhook, GitHub Actions-only, Azure DevOps service hooks/extensions, or portable adapter pattern?
7. **HITL gate semantics:** Which actions are needed for generated artifacts: approve, edit, reject, request evidence, mark stale, supersede, or defer?
8. **MCP trust model:** If MCP is used, which server trust, tool consent, credential, and transport assumptions are acceptable across local IDE and remote service contexts?
9. **Telemetry governance:** What trace fields must be redacted, retained, sampled, or excluded to avoid leaking code, secrets, personal data, or model prompts?
10. **Evaluation harness:** What gold sets, RAG metrics, human labels, and regression tests are needed to measure generated ADR quality and staleness detection?
11. **YAML ADR naming:** The citable architecture-decision YAML prior art found is YADR, not a stable architecture-decision standard named "OpenADR"; confirm whether future phases mean YADR or another OpenADR artifact.
12. **Compliance classification:** Does any deployment context make generated decision artifacts or agent actions subject to higher-risk AI, audit, retention, or regulated-industry controls?
