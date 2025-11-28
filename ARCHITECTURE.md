# Agentic CI Orchestrator - Architecture

## Overview

The Agentic CI Orchestrator is a fully autonomous system that uses LangGraph and Ollama to generate, validate, monitor, and heal CI/CD pipelines in GitHub Actions.

## Core Principles

1. **Safety First**: PR-first policy, no inline secrets, sandbox validation
2. **Deterministic & Reproducible**: All operations are traceable and repeatable
3. **Local LLMs**: Uses Ollama exclusively (no external API dependencies)
4. **Autonomous with Guardrails**: Self-healing with human approval checkpoints

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Trigger                            │
│                   (manual / failure / schedule)                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph Controller                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Agent State                            │   │
│  │  • Repository metadata                                    │   │
│  │  • Workflow content                                       │   │
│  │  • Validation results                                     │   │
│  │  • Failure information                                    │   │
│  │  • Healing attempts                                       │   │
│  │  • Audit trail                                            │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Pipeline                            │
│                                                                   │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐                │
│  │ Detector │────▶│Generator │────▶│Validator │                 │
│  └──────────┘     └──────────┘     └──────────┘                 │
│        │                                  │                      │
│        │              ┌───────────────────┘                      │
│        │              │ (if invalid)                             │
│        │              ▼                                          │
│        │     ┌──────────────┐                                   │
│        │     │ Regenerate   │                                   │
│        │     └──────────────┘                                   │
│        │              │                                          │
│        └──────────────┴────────────┐                            │
│                                     ▼                            │
│                          ┌──────────────┐                        │
│                          │ Diff Analyzer│                        │
│                          └──────┬───────┘                        │
│                                 │                                │
│                                 ▼                                │
│                      ┌─────────────────┐                         │
│                      │   Git Commit    │                         │
│                      │   & PR Agent    │                         │
│                      └────────┬────────┘                         │
│                               │                                  │
│                               ▼                                  │
│                      ┌─────────────────┐                         │
│                      │   Dispatcher    │                         │
│                      └────────┬────────┘                         │
│                               │                                  │
│                               ▼                                  │
│                      ┌─────────────────┐                         │
│                      │    Monitor      │◀────┐                   │
│                      └────────┬────────┘     │                   │
│                               │              │                   │
│                               ▼              │ (poll)            │
│                      ┌─────────────────┐     │                   │
│                      │    Diagnosis    │     │                   │
│                      └────────┬────────┘     │                   │
│                               │              │                   │
│                               ▼              │                   │
│                      ┌─────────────────┐     │                   │
│                      │     Healer      │     │                   │
│                      └────────┬────────┘     │                   │
│                               │              │                   │
│                               ▼              │                   │
│                      ┌─────────────────┐     │                   │
│                      │Sandbox Validator│     │                   │
│                      └────────┬────────┘     │                   │
│                               │              │                   │
│                    ┌──────────┴──────────┐   │                   │
│                    │                     │   │                   │
│                    ▼                     ▼   │                   │
│           ┌──────────────┐      ┌────────────┴──┐               │
│           │ Auto-Commit  │      │ Create PR     │               │
│           │ (safe only)  │      │ (human review)│               │
│           └──────────────┘      └───────────────┘               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Safety & Audit Layer                         │
│  • Secret scanning                                               │
│  • Rate limiting                                                 │
│  • Circuit breakers                                              │
│  • Structured logging                                            │
│  • Metrics export                                                │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. State Management (`src/models/state.py`)

**Purpose**: Maintains complete context across all agent operations

**Key Models**:
- `AgentState`: Complete orchestration state
- `RepositoryMetadata`: Repository language, tools, configuration
- `WorkflowContent`: Generated workflow with metadata
- `ValidationResult`: YAML validation results
- `FailureInfo`: CI failure diagnosis
- `HealingAttempt`: Self-healing attempt records
- `DiffAnalysis`: Code change risk assessment

**Features**:
- Pydantic validation for type safety
- Audit trail tracking
- Error accumulation
- Confidence scoring

### 2. Integrations

#### Ollama Client (`src/integrations/ollama_client.py`)

**Purpose**: Interface with local Ollama models

**Features**:
- Health checks before operations
- Automatic model pulling
- Retry logic with exponential backoff
- Structured JSON response parsing
- Token/duration tracking
- Support for streaming responses

**Model Usage Strategy**:
- **llama3:70b** - Complex reasoning (workflow generation, healing)
- **llama3:13b** - Lightweight tasks (monitoring, classification)
- **llama3:7b** - Simple classification (optional)

#### GitHub Client (`src/integrations/github_client.py`)

**Purpose**: GitHub API operations

**Features**:
- Repository inspection
- File operations (read, commit)
- Branch management
- PR creation
- Workflow dispatch
- Run monitoring
- Rate limit tracking

### 3. Workflow Templates (`src/templates/`)

**Purpose**: Composable, inheritance-based workflow generation

**Templates**:
- `PythonTemplate`: pip/poetry/pipenv support, pytest, ruff, black
- `NodeTemplate`: npm/yarn/pnpm support, standard test/lint/build
- `JavaTemplate`: Maven/Gradle support, checkstyle, JUnit
- `GenericTemplate`: Fallback for unknown languages

**Features**:
- Matrix build configuration
- Dependency caching
- Customizable steps
- Version-specific setup

### 4. Agent Implementations

#### Repository Detector (`src/agents/detector.py`)

**Purpose**: Analyze repository structure using deterministic heuristics

**Detection Logic**:
1. List root files
2. Identify language (Python/Node/Java/Go/Rust/Ruby/Generic)
3. Detect package manager (pip/poetry/npm/yarn/maven/gradle)
4. Find dependency files
5. Check for tests and linters
6. Parse configuration files (package.json, pyproject.toml, etc.)

**Output**: `RepositoryMetadata` with complete context

#### Workflow Generator (`src/agents/generator.py`)

**Purpose**: Generate CI workflows using templates + LLM enhancement

**Process**:
1. Select appropriate template based on language
2. Configure template with detected parameters
3. Generate base workflow
4. (Optional) Enhance with LLM for custom commands
5. Create `WorkflowContent` with confidence score

**LLM Usage**: Only for complex customization, with strict safety prompts

#### YAML Validator (`src/agents/validator.py`)

**Purpose**: Validate workflow for syntax, structure, and security

**Validation Checks**:

**Syntax**:
- Valid YAML parsing
- Correct structure (name, on, jobs, steps)
- Required fields present

**Security**:
- No inline secrets (regex patterns)
- No forbidden actions (configurable blacklist)
- No dangerous shell commands (`curl | bash`, etc.)
- Appropriate permissions

**Best Practices**:
- Caching configured
- Timeouts set
- Matrix size limits
- File size limits

**Output**: `ValidationResult` with errors/warnings/security issues

### 5. Configuration (`src/config.py`)

**Purpose**: Centralized configuration with environment variable substitution

**Features**:
- YAML-based configuration
- Environment variable expansion (`${GITHUB_TOKEN}`)
- Type-safe property access
- Sensible defaults

**Key Configuration Sections**:
- Ollama models and temperatures
- GitHub authentication
- Agent timeouts and retries
- Safety thresholds and rate limits
- Workflow generation rules
- Monitoring and logging

### 6. Logging (`src/logging_config.py`)

**Purpose**: Structured JSON logging for observability

**Features**:
- Structured logs (JSON format)
- Contextual information
- Performance tracking
- Error tracing

## Data Flow

### Phase 1: Detection & Generation (Implemented)

```
Input: owner/repo, branch
  │
  ▼
┌────────────────┐
│    Detector    │  ← GitHub API (read files)
└────────┬───────┘
         │ RepositoryMetadata
         ▼
┌────────────────┐
│   Generator    │  ← Template + Ollama (optional)
└────────┬───────┘
         │ WorkflowContent
         ▼
┌────────────────┐
│   Validator    │  ← YAML parsing + security checks
└────────┬───────┘
         │ ValidationResult
         ▼
Output: Generated workflow YAML
```

### Phase 2: Commit & PR (TODO)

```
WorkflowContent + ValidationResult
  │
  ▼
┌────────────────┐
│ Diff Analyzer  │  ← Calculate risk score
└────────┬───────┘
         │ DiffAnalysis
         ▼
┌────────────────┐
│  Git Commit    │  ← Create branch, commit file
└────────┬───────┘
         │ GitOperation
         ▼
┌────────────────┐
│   PR Creator   │  ← Open PR with summary
└────────┬───────┘
         │
         ▼
Output: PR URL
```

### Phase 3: Monitor & Heal (TODO)

```
WorkflowRun
  │
  ▼
┌────────────────┐
│    Monitor     │  ← Poll run status (30s interval)
└────────┬───────┘
         │ Run completed?
         ▼
┌────────────────┐
│   Diagnosis    │  ← Ollama + log analysis
└────────┬───────┘
         │ FailureInfo
         ▼
┌────────────────┐
│     Healer     │  ← Strategy selection
└────────┬───────┘
         │ HealingAttempt
         ▼
┌────────────────┐
│Sandbox Validate│  ← Docker test environment
└────────┬───────┘
         │
         ▼
  ┌─────────────┐
  │ Confidence? │
  └──┬────────┬─┘
     │        │
   High      Low
     │        │
     ▼        ▼
Auto-commit  Create PR
```

## Safety Mechanisms

### 1. PR-First Policy

**Rule**: All changes go through PRs by default

**Exceptions** (require high confidence + safe category):
- Transient failure retries
- Flaky test wrappers
- Dependency pinning

### 2. Secret Protection

**Mechanisms**:
- Regex scanning for common secret patterns
- GitHub token pattern detection
- No execution of untrusted code
- Environment variable validation

### 3. Rate Limiting

**Limits**:
- Max 3 healing attempts per run
- Max 2 auto-fixes per repo per day
- Max 5 concurrent repositories
- GitHub API rate limit tracking

### 4. Circuit Breakers

**Triggers**:
- 5 consecutive failures → pause for 1 hour
- Ollama unavailable → fail fast
- GitHub rate limit → exponential backoff

### 5. Confidence Scoring

**Thresholds**:
- ≥ 0.9: Auto-commit eligible
- ≥ 0.7: PR creation allowed
- ≥ 0.6: Requires human approval
- < 0.6: Reject operation

**Factors**:
- Template vs LLM-generated
- Validation pass/fail
- Complexity of changes
- Historical success rate

## Implementation Status

### ✅ Completed (Phase 1)

- [x] Project structure and configuration
- [x] State management (Pydantic models)
- [x] Ollama client with retry logic
- [x] GitHub client wrapper
- [x] Workflow templates (Python, Node, Java, Generic)
- [x] Repository detector agent
- [x] Workflow generator agent
- [x] YAML validator agent
- [x] Configuration loader
- [x] Structured logging
- [x] Main entry point (detect-only, generate-only modes)

### 🚧 In Progress

- [ ] Unit tests for core components

### 📋 TODO (Phase 2)

- [ ] Diff analyzer agent
- [ ] Git commit agent
- [ ] PR creator agent
- [ ] LangGraph orchestrator integration

### 📋 TODO (Phase 3)

- [ ] Workflow dispatcher agent
- [ ] CI monitor agent
- [ ] Failure diagnosis agent
- [ ] Healer agent strategies
- [ ] Sandbox validator (Docker)
- [ ] Rollback agent

### 📋 TODO (Phase 4+)

- [ ] Human approval workflow
- [ ] Notification system (Slack, email)
- [ ] Metrics and telemetry
- [ ] Web UI for monitoring
- [ ] Multi-repository orchestration

## Development Workflow

1. **Start with small repos**: Test on simple, well-structured repositories
2. **Iterate on phases**: Complete each phase before moving to the next
3. **Monitor confidence scores**: Adjust thresholds based on real-world results
4. **Collect feedback**: Learn from failed generations and validations
5. **Refine prompts**: Improve LLM prompts based on output quality

## Extension Points

### Adding New Language Support

1. Create new template class in `src/templates/workflow_templates.py`
2. Implement detection logic in `src/agents/detector.py`
3. Add language-specific configuration to `config.yaml`
4. Test with representative repositories

### Adding New Healing Strategies

1. Add strategy to `src/agents/healer.py`
2. Define failure type classification
3. Implement sandbox validation logic
4. Set appropriate confidence thresholds

### Custom Agents

1. Create agent class in `src/agents/`
2. Define input/output state transformations
3. Add to LangGraph orchestrator
4. Configure timeouts and retries

## Performance Considerations

- **Model Selection**: Use lightweight models for frequent operations
- **Caching**: Cache repository metadata and workflow templates
- **Batching**: Group API calls when possible
- **Streaming**: Use streaming for long-running LLM calls
- **Parallelization**: Future LangGraph implementation will support parallel agents

## Security Considerations

- **Token Scoping**: Use GitHub Apps instead of PATs for production
- **Secret Management**: Never log secrets or include in state
- **Sandbox Isolation**: Docker with resource limits
- **Code Review**: All generated code must be reviewable
- **Audit Trail**: Complete logging of all operations
