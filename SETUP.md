# Setup Instructions

## Prerequisites

1. **Python 3.11+**
   ```bash
   python3 --version
   ```

2. **Ollama** - Install from https://ollama.ai
   ```bash
   # On macOS
   brew install ollama
   
   # Start Ollama service
   ollama serve
   ```

3. **Pull required models**
   ```bash
   # Primary reasoning model (large)
   ollama pull llama3:70b
   
   # Lightweight model (optional but recommended)
   ollama pull llama3:13b
   ```

4. **GitHub Token**
   - Go to https://github.com/settings/tokens
   - Create a new token with:
     - `repo` (full control)
     - `workflow` (if you want to dispatch workflows)
   - Save the token securely

## Installation

1. **Clone or navigate to the project**
   ```bash
   cd /Users/kushald/Dev-Agent
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the application**
   ```bash
   # Copy example config
   cp config.example.yaml config.yaml
   
   # Copy example env
   cp .env.example .env
   
   # Edit .env with your GitHub token
   nano .env  # or use any editor
   ```

   Add your GitHub token to `.env`:
   ```
   GITHUB_TOKEN=ghp_your_actual_token_here
   ```

## Quick Test

### Phase 1: Detection Only (Read-only mode)

Test repository detection without generating anything:

```bash
# Test with a public Python repository
python src/main.py --repo octocat/Hello-World --mode detect-only

# Test with a Node.js repository
python src/main.py --repo vercel/next.js --mode detect-only --branch canary
```

### Phase 2: Generate and Validate

Generate a workflow and validate it (no commits):

```bash
# Generate workflow for a Python project
python src/main.py --repo psf/requests --mode generate-only

# With debug logging
python src/main.py --repo psf/requests --mode generate-only --debug
```

### Expected Output

For detect-only mode:
```
=== Repository Detection Results ===
Language: python
Package Manager: pip
Build Tool: pip
Has Tests: True
Has Linter: True
```

For generate-only mode:
```
=== Generated Workflow ===
name: CI - your-repo
on:
  push:
    branches: [main]
...

=== Validation Results ===
Valid: True
Warnings: 0
```

## Troubleshooting

### Issue: "Ollama is not available"

**Solution:**
```bash
# Start Ollama service
ollama serve

# In another terminal, test
curl http://localhost:11434/api/tags
```

### Issue: "GitHub token not configured"

**Solution:**
- Ensure `.env` file exists
- Check that `GITHUB_TOKEN=ghp_...` is set
- Verify token has correct permissions

### Issue: "Import could not be resolved"

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "Model not found"

**Solution:**
```bash
# List available models
ollama list

# Pull required model
ollama pull llama3:70b
```

## Development Mode

To work on the code with auto-reload:

```bash
# Enable debug mode in config.yaml
development:
  debug: true
  dry_run: true  # Prevents actual API calls

# Run with debug logging
python src/main.py --repo owner/repo --debug --dry-run
```

## Next Steps

Once Phase 1 (detect + generate) is working:

1. **Phase 2**: Implement PR creation
   - Git commit agent
   - PR creation agent
   - Test with `--mode full`

2. **Phase 3**: Add monitoring
   - Workflow dispatcher
   - Run monitoring
   - Failure detection

3. **Phase 4**: Add healing
   - Diagnosis agent
   - Healer agent
   - Sandbox validation

4. **Phase 5**: Production hardening
   - Rate limiting
   - Circuit breakers
   - Comprehensive error handling

## Testing Recommendations

Good test repositories:

- **Python**: `psf/requests`, `pallets/flask`
- **Node.js**: `expressjs/express`, `microsoft/TypeScript`
- **Java**: `spring-projects/spring-boot`
- **Generic**: Any small personal repository

Start with small, simple repositories before testing on large projects.
