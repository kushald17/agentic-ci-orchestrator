# Quick Reference - Phase 2

## What's New in Phase 2

✅ **Full PR Creation Pipeline**
- Automated branch creation
- Git commits with descriptive messages
- Pull request generation with AI descriptions
- Risk assessment and approval workflows

## New Commands

```bash
# Full pipeline - creates PR
./run.sh --repo owner/repo --mode full

# Commit only, no PR
./run.sh --repo owner/repo --mode full --no-pr
```

## New Agents

1. **DiffAnalyzerAgent** - Calculates risk scores, determines approval needs
2. **GitCommitAgent** - Creates branches, commits files
3. **PRCreatorAgent** - Opens PRs with LLM-generated descriptions

## Full Pipeline Flow

```
1. Detection → Analyze repository structure
2. Generation → Create CI workflow with templates + LLM
3. Validation → Check YAML syntax, security
4. Diff Analysis → Calculate risk score
5. Git Commit → Create branch, commit workflow
6. PR Creation → Open pull request with description
```

## Example Output

```bash
./run.sh --repo kushald17/Git-demo --mode full
```

```
✓ Pull request created successfully!
  PR #1
  URL: https://github.com/kushald17/Git-demo/pull/1
  Branch: agent/ci-20251127-051652
  Confidence: 95.00%
  Risk Level: LOW

Next steps:
  - Review the PR
  - Merge when ready
```

## Risk Categories

- **Low** (< 0.3): High confidence, minimal warnings
- **Medium** (0.3-0.5): Some concerns, review recommended
- **High** (0.5-0.7): Significant issues, careful review needed
- **Critical** (>= 0.7): Security issues or very low confidence

## Testing

```bash
# Quick test on your repository
./run.sh --repo owner/repo --mode generate-only

# Full pipeline test
source venv/bin/activate && PYTHONPATH=$PWD python tests/test_phase2.py

# Test individual phases
./run.sh --repo owner/repo --mode detect-only  # Detection only
```

## What's Next (Phase 3)

- **CI Monitoring**: Track workflow runs in real-time
- **Failure Detection**: Parse logs, classify error types
- **Preparation for Healing**: State management for failure information

## Files Changed

### New Files
- `src/agents/diff_analyzer.py` (150 lines)
- `src/agents/git_commit.py` (120 lines)
- `src/agents/pr_creator.py` (180 lines)
- `tests/test_phase2.py` (130 lines)
- `PHASE2_SUMMARY.md` (comprehensive documentation)

### Modified Files
- `src/main.py` (added 3 new phases, --no-pr flag)
- `README.md` (updated status, examples, features)

### Lines Added
~1,200+ lines of production code + documentation

## Verification

Live PR created: https://github.com/kushald17/Git-demo/pull/1

All phases tested and working ✅
