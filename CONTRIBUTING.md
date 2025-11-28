# Contributing to Agentic CI Orchestrator

Welcome to the team! This guide will help you get started contributing to our autonomous CI/CD pipeline orchestrator.

## 🚀 Getting Started

### 1. Repository Setup

```bash
# Clone the repository
git clone <repository-url>
cd Dev-Agent

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy configuration templates
cp config.example.yaml config.yaml
cp .env.example .env

# Edit .env with your GitHub token
export GITHUB_TOKEN="your_github_token_here"

# Set up Ollama
ollama serve
ollama pull llama3:70b
ollama pull llama3:13b
```

### 3. Verify Setup

```bash
# Run tests to verify everything works
python tests/test_phase1.py
python tests/test_phase2.py
python tests/test_phase3.py
python tests/test_phase4.py

# Test the main orchestrator
./run.sh --repo octocat/Hello-World --mode detect-only --debug
```

## 🔄 Development Workflow

### Branch Strategy

We use **feature branches** for all development:

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Work on your changes
git add .
git commit -m "feat: add new healing strategy for Docker failures"

# Push to remote
git push origin feature/your-feature-name

# Create pull request on GitHub
```

### Branch Naming Convention

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test improvements

## 📝 Code Standards

### Python Style Guide

- Follow **PEP 8** style guidelines
- Use **type hints** for all function parameters and returns
- Maximum line length: **88 characters** (Black formatter)
- Use **descriptive variable names**

### Documentation Requirements

```python
class NewAgent:
    """Agent for handling X functionality.
    
    This agent implements Y strategy to solve Z problems
    in CI pipelines.
    
    Attributes:
        client: GitHub API client instance
        config: Configuration object
    """
    
    def process_failure(self, failure_type: str) -> HealingResult:
        """Process a specific type of CI failure.
        
        Args:
            failure_type: Type of failure to heal (e.g., 'gradle_permission')
            
        Returns:
            HealingResult containing patch and confidence score
            
        Raises:
            HealingError: If healing strategy fails
        """
        pass
```

### Testing Requirements

Every new feature must include:

1. **Unit tests** for individual functions
2. **Integration tests** for agent interactions
3. **Error case testing** for failure scenarios
4. **Test data** in `tests/fixtures/` if needed

```python
# Example test structure
def test_new_healing_strategy():
    """Test new Docker healing strategy."""
    # Arrange
    healer = HealerAgent(mock_config)
    failure = DockerFailure("permission denied")
    
    # Act
    result = healer.heal_docker_permission(failure)
    
    # Assert
    assert result.success is True
    assert result.confidence > 0.8
    assert "chmod +x" in result.patch
```

## 🏗️ Architecture Guidelines

### Agent Design Principles

1. **Single Responsibility**: Each agent handles one phase
2. **State Management**: Use Pydantic models for data validation
3. **Error Handling**: Graceful degradation with retry logic
4. **Logging**: Structured JSON logging for observability

### Adding New Agents

1. Create agent class in `src/agents/`
2. Inherit from appropriate base class
3. Implement required methods
4. Add to orchestrator in `src/main.py`
5. Write comprehensive tests
6. Update documentation

### Example Agent Structure

```python
from src.models.state import PipelineState
from src.integrations.ollama_client import OllamaClient

class YourAgent:
    """Agent description."""
    
    def __init__(self, config: Config):
        self.config = config
        self.ollama = OllamaClient(config.ollama)
        self.logger = logging.getLogger(__name__)
    
    def process(self, state: PipelineState) -> PipelineState:
        """Process the pipeline state."""
        try:
            # Your logic here
            return state
        except Exception as e:
            self.logger.error(f"Agent failed: {e}")
            raise
```

## 🧪 Testing Strategy

### Test Categories

1. **Unit Tests** (`tests/test_*.py`)
   - Test individual functions and classes
   - Mock external dependencies
   - Fast execution (< 1 second each)

2. **Integration Tests** (`tests/integration/`)
   - Test agent interactions
   - Use real GitHub API (rate-limited)
   - Test complete workflows

3. **Performance Tests** (`tests/performance/`)
   - Test with large repositories
   - Measure execution times
   - Memory usage validation

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific phase
pytest tests/test_phase4.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run integration tests (requires GitHub token)
pytest tests/integration/ -v
```

### Mock Data

Use fixtures for consistent test data:

```python
# tests/fixtures/sample_workflows.py
GRADLE_WORKFLOW = """
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./gradlew build
"""
```

## 📊 Project Structure

### Current Implementation Status

| Phase | Status | Lead Developer | Features |
|-------|--------|---------------|----------|
| **Phase 1** | ✅ Complete | - | Detection, Generation, Validation |
| **Phase 2** | ✅ Complete | - | PR Creation, Git Operations |
| **Phase 3** | ✅ Complete | - | Monitoring, Failure Detection |
| **Phase 4** | ✅ Complete | - | Self-Healing, Patch Generation |
| **Phase 5** | 📋 Planned | *Assignable* | Sandbox Validation |

### Development Areas

**High Priority:**
- Phase 5 sandbox validation
- Additional healing strategies
- Performance optimizations
- Enhanced monitoring

**Medium Priority:**
- Web dashboard UI
- Webhook integrations
- Multi-cloud support
- Advanced ML models

**Low Priority:**
- Mobile notifications
- Slack integrations
- Custom plugins

## 🐛 Debugging & Troubleshooting

### Common Development Issues

1. **Ollama Connection Errors**
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   
   # Restart if needed
   pkill ollama && ollama serve
   ```

2. **GitHub API Rate Limits**
   ```bash
   # Check rate limit status
   curl -H "Authorization: token $GITHUB_TOKEN" \
        https://api.github.com/rate_limit
   ```

3. **Model Loading Issues**
   ```bash
   # Verify models are available
   ollama list
   
   # Pull if missing
   ollama pull llama3:70b
   ```

### Debugging Tools

```bash
# Enable debug logging
./run.sh --repo owner/repo --mode detect-only --debug

# Test specific components
python -c "from src.agents.healer import HealerAgent; print('Healer loaded')"

# Validate configuration
python -c "from src.config import load_config; print(load_config())"
```

## 🚀 Deployment & Release

### Pre-merge Checklist

- [ ] All tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No secrets in code
- [ ] Performance impact assessed
- [ ] Backward compatibility maintained

### Release Process

1. **Feature Complete**: All features tested and documented
2. **Code Review**: At least one team member approval
3. **Integration Testing**: Full pipeline tested
4. **Documentation**: README and architecture docs updated
5. **Merge to Main**: Squash merge with clear commit message

## 📞 Getting Help

### Team Communication

- **GitHub Issues**: Bug reports and feature requests
- **Pull Request Reviews**: Code discussion and feedback
- **Documentation**: Check README.md and ARCHITECTURE.md first

### Code Review Guidelines

**As a Reviewer:**
- Focus on architecture and design
- Check for security issues
- Verify test coverage
- Suggest improvements kindly

**As a Developer:**
- Provide context in PR descriptions
- Respond to feedback constructively
- Update code based on reviews
- Thank reviewers for their time

## 🎯 Contribution Opportunities

### Good First Issues
- Add new healing strategies for common failures
- Improve error messages and logging
- Add support for new project types
- Enhance documentation with examples

### Advanced Contributions
- Implement Phase 5 sandbox validation
- Add ML-based failure prediction
- Build web dashboard UI
- Optimize performance for large repositories

---

**Welcome to the team! Let's build something amazing together! 🚀**