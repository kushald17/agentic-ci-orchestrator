# Agentic CI Orchestrator

Autonomous CI pipeline generation, monitoring, and healing using LangGraph + Ollama.

> **Current Status**: Phase 4 Complete ✅  
> Detection, generation, PR creation, monitoring, and self-healing working. Sandbox validation coming in Phase 5.

## Overview

The Agentic CI Orchestrator uses local LLMs (Ollama) to automatically analyze repositories, generate GitHub Actions workflows, validate them for security and correctness, and (in future phases) monitor and heal failing CI pipelines.

## Architecture

```
GitHub Trigger → LangGraph Controller → CI Agents → PR + Workflow Execution
                                            ↓
                                      Monitor + Healer
                                            ↓
                                    Human Approval (optional)
                                            ↓
                                     Audit & Logs Layer
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

## Features

### ✅ Implemented (Phase 1-4)
- **Autonomous Detection**: Analyzes repository structure to identify language, package manager, build tools
- **Smart Generation**: Creates complete CI workflows using templates + LLM enhancement
- **Security Validation**: YAML syntax, structure, and security checks (no inline secrets, forbidden actions)
- **Risk Analysis**: Calculates risk scores and determines approval requirements
- **Git Operations**: Automatic branch creation and file commits
- **PR Creation**: Generates pull requests with LLM-powered descriptions
- **Workflow Monitoring**: Polls GitHub Actions API to track run status
- **Failure Detection**: Classifies failures (dependency, test, build errors) and determines healability
- **Self-Healing**: Automatically generates and applies patches for common CI failures
- **Multi-Language Support**: Python, Node.js, Java, Go, Rust, Ruby + generic fallback
- **Template System**: Composable, inheritance-based templates with caching and matrix builds
- **Local LLMs**: Ollama integration with health checks and retry logic
- **Structured Logging**: JSON logs for observability

### 🚧 Coming Soon (Phase 5)
- **Sandbox Validation**: Tests fixes in isolated Docker environments before applying
- **Auto-Commit**: Low-risk changes committed directly without PR

## Quick Start

### 1. Prerequisites

- **Python 3.11+**
- **Ollama** - Install from [ollama.ai](https://ollama.ai)
- **GitHub Token** - [Create here](https://github.com/settings/tokens)

### 2. Installation

```bash
# Clone/navigate to project
cd /Users/kushald/Dev-Agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp config.example.yaml config.yaml
cp .env.example .env
# Edit .env with your GitHub token
```

### 3. Pull Ollama Models

```bash
# Start Ollama
ollama serve

# Pull required models (in another terminal)
ollama pull llama3:70b    # Primary reasoning model
ollama pull llama3:13b    # Lightweight model (optional)
```

### 4. Usage

```bash
# Detection only (read-only, no API writes)
./run.sh --repo psf/requests --mode detect-only

# Generate workflow (validation only, no commits)
./run.sh --repo psf/requests --mode generate-only

# Full mode - Create PR with workflow
./run.sh --repo owner/repo --mode full

# Full mode with monitoring - Track workflow execution
./run.sh --repo owner/repo --mode full --monitor

# Commit only (no PR creation)
./run.sh --repo owner/repo --mode full --no-pr

# With debug logging
./run.sh --repo expressjs/express --mode full --debug
```

See [SETUP.md](SETUP.md) for detailed setup instructions and troubleshooting.

## Project Structure

```
├── src/
│   ├── agents/          # Agent implementations
│   │   ├── detector.py      # Repository analysis
│   │   ├── generator.py     # Workflow generation
│   │   ├── validator.py     # YAML validation
│   │   ├── diff_analyzer.py # Risk assessment
│   │   ├── git_commit.py    # Branch creation & commits
│   │   ├── pr_creator.py    # Pull request generation
│   │   ├── monitor.py       # Workflow run tracking
│   │   ├── failure_detector.py # Failure classification
│   │   └── healer.py        # Self-healing patches
│   ├── models/          # State management
│   │   └── state.py         # Pydantic models
│   ├── templates/       # Workflow templates
│   │   └── workflow_templates.py
│   ├── integrations/    # External services
│   │   ├── ollama_client.py
│   │   └── github_client.py
│   ├── config.py        # Configuration loader
│   ├── logging_config.py # Structured logging
│   └── main.py          # Entry point & orchestrator
├── tests/
│   ├── test_phase1.py   # Detection/generation tests
│   ├── test_phase2.py   # Full pipeline test
│   ├── test_phase3.py   # Monitoring & failure detection
│   └── test_phase4.py   # Self-healing test
├── config.example.yaml  # Configuration template
├── .env.example         # Environment variables
├── requirements.txt     # Python dependencies
└── run.sh               # Wrapper script
```

## Configuration

Key configuration in `config.yaml`:

```yaml
ollama:
  models:
    reasoning: "llama3:70b"      # Complex tasks
    lightweight: "llama3:13b"    # Simple tasks
  temperature:
    patch_generation: 0.0        # Deterministic
    workflow_generation: 0.0
    
safety:
  confidence:
    auto_commit_threshold: 0.9   # High confidence only
    pr_creation_threshold: 0.7
  rate_limits:
    max_healing_attempts_per_run: 3
    max_daily_auto_fixes_per_repo: 2
```

## Usage Examples

### Detect Repository Type
```bash
./run.sh --repo tensorflow/tensorflow --mode detect-only
```

Output:
```
=== Repository Detection Results ===
Language: python
Package Manager: pip
Has Tests: True
Has Linter: True
```

### Generate Workflow
```bash
./run.sh --repo vercel/next.js --branch canary --mode generate-only
```

Output:
```
=== Generated Workflow ===
name: CI - next.js
on:
  push:
    branches: [canary]
...

=== Validation Results ===
Valid: True
Warnings: 0
```

## Testing

```bash
# Run component tests
python tests/test_phase1.py

# Test with debug logging
python src/main.py --repo owner/repo --debug --dry-run
```

## Development Phases

| Phase | Status | Features |
|-------|--------|----------|
| **Phase 1** | ✅ Complete | Detection, Generation, Validation |
| **Phase 2** | ✅ Complete | PR Creation, Git Operations, Risk Analysis |
| **Phase 3** | ✅ Complete | Monitoring, Failure Detection |
| **Phase 4** | ✅ Complete | Self-Healing, Patch Generation |
| **Phase 5** | 📋 Planned | Sandbox Validation, Auto-commit |

## Design Improvements Implemented

Based on design review feedback:

✅ **State Management**: Comprehensive Pydantic models with clear schema  
✅ **Confidence Scoring**: Built into `WorkflowContent` and validation  
✅ **Safety First**: Secret scanning, forbidden action detection, size limits  
✅ **Ollama Strategy**: Health checks, model pulling, structured responses  
✅ **Template Inheritance**: Composable templates with language-specific logic  
✅ **Configuration Management**: YAML-based with environment variable substitution  
✅ **Structured Logging**: JSON format with contextual information  
✅ **Error Handling**: Graceful degradation and retry logic  

## 🤝 Team Collaboration & Contributing

### Development Workflow

We use a feature branch workflow for team development:

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Dev-Agent
   ```

2. **Set up your development environment**:
   ```bash
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Copy configuration templates
   cp config.example.yaml config.yaml
   cp .env.example .env
   # Edit .env with your GitHub token
   ```

3. **Create feature branches**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Make your changes and test**:
   ```bash
   # Run tests before committing
   python tests/test_phase1.py
   python tests/test_phase2.py
   python tests/test_phase3.py
   python tests/test_phase4.py
   ```

5. **Submit Pull Request**:
   - Write clear commit messages
   - Include test coverage for new features
   - Add documentation for new functionality
   - Request review from team members

### Code Standards

- **Python Style**: Follow PEP 8 guidelines
- **Type Hints**: Add type annotations to all functions
- **Documentation**: Include docstrings for classes and methods
- **Testing**: Write tests for new functionality
- **Logging**: Use structured logging for debugging

### Team Development Guidelines

- **Phase-based Development**: We follow incremental rollout (Phases 1-4 complete, Phase 5 planned)
- **Configuration Management**: Use `config.yaml` and `.env` for local settings
- **Testing Strategy**: Component tests for each phase + integration tests
- **Code Review**: All changes require review before merging
- **Documentation**: Update README and architecture docs for significant changes

See [ARCHITECTURE.md](ARCHITECTURE.md) for extension points and system design.

## Troubleshooting

Common issues and solutions in [SETUP.md](SETUP.md#troubleshooting).

Quick checks:
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check configuration
python tests/test_phase1.py

# Test GitHub token
echo $GITHUB_TOKEN
```

## License

MIT

## Acknowledgments

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [Ollama](https://ollama.ai) - Local LLM inference
- [PyGithub](https://github.com/PyGithub/PyGithub) - GitHub API
- [Pydantic](https://docs.pydantic.dev/) - Data validation
