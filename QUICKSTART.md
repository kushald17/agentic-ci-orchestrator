# Quick Reference Guide

## Installation (One-Time Setup)

```bash
# 1. Install Ollama
brew install ollama  # macOS
# OR download from https://ollama.ai

# 2. Start Ollama service
ollama serve

# 3. Pull models (in another terminal)
ollama pull llama3:70b
ollama pull llama3:13b

# 4. Setup Python environment
cd /Users/kushald/Dev-Agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure
cp config.example.yaml config.yaml
cp .env.example .env
# Edit .env and add: GITHUB_TOKEN=ghp_your_token_here
```

## Daily Usage

### Activate Environment
```bash
cd /Users/kushald/Dev-Agent
source venv/bin/activate
```

### Common Commands

```bash
# Detect repository language and configuration
python src/main.py --repo owner/repo --mode detect-only

# Generate workflow (no commits)
python src/main.py --repo owner/repo --mode generate-only

# Generate with debug logging
python src/main.py --repo owner/repo --mode generate-only --debug

# Dry run (no API writes)
python src/main.py --repo owner/repo --dry-run

# Test components
python tests/test_phase1.py
```

## Command Reference

### Main CLI Options

| Option | Description | Example |
|--------|-------------|---------|
| `--repo` | Repository (owner/name) | `--repo psf/requests` |
| `--branch` | Branch to analyze | `--branch main` |
| `--mode` | Execution mode | `--mode detect-only` |
| `--config` | Config file path | `--config custom.yaml` |
| `--debug` | Enable debug logging | `--debug` |
| `--dry-run` | No actual API calls | `--dry-run` |

### Modes

| Mode | Description | Writes Data? |
|------|-------------|--------------|
| `detect-only` | Analyze repository only | ❌ No |
| `generate-only` | Generate + validate workflow | ❌ No |
| `full` | Complete pipeline (TODO) | ⚠️ Yes |

## Output Examples

### Detect-Only Mode
```
=== Repository Detection Results ===
Language: python
Package Manager: poetry
Build Tool: poetry
Has Tests: True
Has Linter: True
Test Framework: pytest
Custom Commands: ['test', 'lint', 'build']
```

### Generate-Only Mode
```
=== Generated Workflow ===
name: CI - requests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      ...

=== Validation Results ===
Valid: True
Warnings: 1
  - Job 'ci' has no timeout configured
```

## Configuration Quick Reference

### Essential Settings (config.yaml)

```yaml
# Ollama
ollama:
  base_url: "http://localhost:11434"
  models:
    reasoning: "llama3:70b"
    lightweight: "llama3:13b"

# GitHub
github:
  token: "${GITHUB_TOKEN}"  # Set in .env file

# Safety
safety:
  confidence:
    auto_commit_threshold: 0.9
    pr_creation_threshold: 0.7
```

### Environment Variables (.env)

```bash
GITHUB_TOKEN=ghp_your_actual_token_here
# Optional: OLLAMA_BASE_URL=http://localhost:11434
```

## Supported Languages

| Language | Detected By | Package Managers | Build Tools |
|----------|-------------|------------------|-------------|
| Python | `requirements.txt`, `setup.py`, `pyproject.toml` | pip, poetry, pipenv | pip, poetry |
| Node.js | `package.json` | npm, yarn, pnpm | npm scripts |
| Java | `pom.xml`, `build.gradle` | maven, gradle | maven, gradle |
| Go | `go.mod` | go modules | go |
| Rust | `Cargo.toml` | cargo | cargo |
| Ruby | `Gemfile` | bundler | bundler |

## Troubleshooting

### Issue: "Ollama is not available"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve
```

### Issue: "GitHub token not configured"
```bash
# Check .env file exists
cat .env

# Should contain:
# GITHUB_TOKEN=ghp_...

# Verify token is loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GITHUB_TOKEN'))"
```

### Issue: "Model not found"
```bash
# List available models
ollama list

# Pull missing model
ollama pull llama3:70b
```

### Issue: Import errors
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "langgraph|pydantic|PyGithub"
```

## Testing Tips

### Start Small
Test with small, well-structured repositories:
```bash
# Good starter repos
python src/main.py --repo octocat/Hello-World --mode detect-only
python src/main.py --repo pallets/flask --mode generate-only
```

### Use Debug Mode
```bash
python src/main.py --repo owner/repo --debug --mode generate-only
```

Debug output includes:
- Agent execution times
- Ollama request/response details
- GitHub API calls
- Validation checks

### Check Logs
Structured logs in JSON format show:
```json
{
  "event": "workflow_generated",
  "size": 1234,
  "confidence": 0.95,
  "duration": 2.5,
  "timestamp": "2025-11-25T10:30:00.123Z"
}
```

## Next Steps After Phase 1

Once detection and generation are working:

1. **Test on your own repositories**
   ```bash
   python src/main.py --repo yourusername/yourrepo --mode generate-only
   ```

2. **Review generated workflows**
   - Check if commands are correct
   - Verify language detection
   - Validate security checks

3. **Provide feedback**
   - What languages/tools are missing?
   - What validation checks should be added?
   - What improvements to generated workflows?

4. **Phase 2 Development**
   - PR creation
   - Git operations
   - Diff analysis

## Performance Notes

- **Detection**: ~1-3 seconds (depends on repo size)
- **Generation**: ~5-10 seconds (llama3:70b)
- **Validation**: <1 second

To improve performance:
- Use lighter models for simple tasks
- Cache repository metadata
- Batch GitHub API calls

## Resources

- **Documentation**: See `README.md`, `SETUP.md`, `ARCHITECTURE.md`
- **Configuration**: See `config.example.yaml`
- **Tests**: See `tests/test_phase1.py`
- **Ollama Docs**: https://ollama.ai/docs
- **GitHub API**: https://docs.github.com/en/rest
- **LangGraph**: https://langchain-ai.github.io/langgraph/

## Getting Help

1. Run component tests: `python tests/test_phase1.py`
2. Check configuration: Review `config.yaml` and `.env`
3. Enable debug logging: Add `--debug` flag
4. Check Ollama: `ollama list` and `ollama serve`
5. Verify GitHub token: Test API access

## Status Checklist

Before running:
- [ ] Ollama service is running (`ollama serve`)
- [ ] Models are pulled (`ollama list`)
- [ ] Virtual environment is activated (`source venv/bin/activate`)
- [ ] Dependencies are installed (`pip list`)
- [ ] Configuration files exist (`config.yaml`, `.env`)
- [ ] GitHub token is set (check `.env`)

Ready to go! 🚀
