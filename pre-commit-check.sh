#!/opt/homebrew/bin/bash
# Pre-commit check: Ensure no API keys are in staged files
# Run before committing: ./pre-commit-check.sh

set -e

echo "Checking for API keys in staged files..."

# Check for Anthropic API key patterns in staged files
if git diff --cached --name-only | xargs grep -l "sk-ant-" 2>/dev/null; then
    echo ""
    echo "ERROR: Found Anthropic API key in staged files!"
    echo "Remove the key before committing."
    echo ""
    echo "Files containing keys:"
    git diff --cached --name-only | xargs grep -l "sk-ant-" 2>/dev/null
    exit 1
fi

# Check for generic API key patterns
if git diff --cached --name-only | xargs grep -lE "ANTHROPIC_API_KEY\s*=\s*['\"]?sk-" 2>/dev/null; then
    echo ""
    echo "ERROR: Found hardcoded ANTHROPIC_API_KEY in staged files!"
    echo "Use environment variables instead."
    exit 1
fi

# Verify .env is not staged
if git diff --cached --name-only | grep -q "^\.env$"; then
    echo ""
    echo "ERROR: .env file is staged for commit!"
    echo "Run: git reset HEAD .env"
    exit 1
fi

echo "✓ No API keys found in staged files"
echo "✓ Safe to commit"
