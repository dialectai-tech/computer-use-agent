# Usage Guide - Generic Prompts and Logging

## Quick Start

### Basic Usage (Simple Prompt)

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "YOUR_CHALLENGE_URL" \
  --prompt "$(cat test_prompt_simple.txt)"
```

### With Two-Phase Workflow (Recommended)

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "YOUR_CHALLENGE_URL" \
  --two-phase-workflow \
  --prompt "$(cat test_prompt_simple.txt)"
```

### With Extended Thinking (For Complex Tasks)

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "YOUR_CHALLENGE_URL" \
  --two-phase-workflow \
  --extended-thinking \
  --thinking-budget 15000 \
  --prompt "$(cat test_prompt_simple.txt)"
```

### Full Featured (All Enhancements)

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "YOUR_CHALLENGE_URL" \
  --two-phase-workflow \
  --extended-thinking \
  --thinking-budget 15000 \
  --max-iterations 25 \
  --prompt "$(cat test_prompt_simple.txt)"
```

## Different Models

### Use Haiku (Fast, Cheap)

```bash
python -m cua --provider bedrock --model haiku-4.5 \
  --url "YOUR_CHALLENGE_URL" \
  --two-phase-workflow \
  --prompt "$(cat test_prompt_simple.txt)"
```

### Use Opus (Highest Quality)

```bash
python -m cua --provider bedrock --model opus-4.5 \
  --url "YOUR_CHALLENGE_URL" \
  --two-phase-workflow \
  --extended-thinking \
  --thinking-budget 20000 \
  --prompt "$(cat test_prompt_simple.txt)"
```

### Use Sonnet 3.7 (Latest 3.x)

```bash
python -m cua --provider bedrock --model sonnet-3.7 \
  --url "YOUR_CHALLENGE_URL" \
  --two-phase-workflow \
  --prompt "$(cat test_prompt_simple.txt)"
```

## Different Providers

### Anthropic Direct API

```bash
export ANTHROPIC_API_KEY="your-api-key"

python -m cua --provider claude --model claude-sonnet-4-5 \
  --url "YOUR_CHALLENGE_URL" \
  --two-phase-workflow \
  --prompt "$(cat test_prompt_simple.txt)"
```

### OpenAI

```bash
export OPENAI_API_KEY="your-api-key"

python -m cua --provider openai --model computer-use-preview \
  --url "YOUR_CHALLENGE_URL" \
  --prompt "$(cat test_prompt_simple.txt)"
```

## Custom Prompts

### Short Custom Prompt

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "YOUR_CHALLENGE_URL" \
  --two-phase-workflow \
  --prompt "Complete all tasks on this webpage efficiently."
```

### Task-Specific Prompt

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "https://example.com/form" \
  --prompt "Fill out the registration form with test data. Use realistic values for name, email, and phone number. Submit the form when complete."
```

### Data Extraction Prompt

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "https://example.com/products" \
  --prompt "Extract all product names and prices from this page. Search for product elements in the accessibility tree. Output the data in a structured format."
```

## Viewing Logs

### Check Latest Log

```bash
# List all log files (newest last)
ls -lht logs/

# View latest log
cat logs/session_*.log | tail -n 100

# View specific log
cat logs/session_20260207_143022.log
```

### Follow Log in Real-Time

```bash
# In terminal 1, start the agent
python -m cua --provider bedrock --url "..." --prompt "..."

# In terminal 2, follow the log
tail -f logs/session_$(date +%Y%m%d)_*.log
```

### Search Logs

```bash
# Find all iterations that had errors
grep -n "ERROR" logs/session_*.log

# Find search actions
grep -n "SEARCH" logs/session_*.log

# Find phase transitions
grep -n "PHASE TRANSITION" logs/session_*.log

# See token usage per iteration
grep -n "input_tokens" logs/session_*.log
```

## Log Analysis

### Extract Summary

```bash
# Get session summary
grep -A 50 "SESSION SUMMARY" logs/session_*.log
```

### Check Token Usage

```bash
# Total tokens used
grep "input_tokens\|output_tokens" logs/session_*.log | \
  awk '{sum+=$2} END {print "Total tokens:", sum}'
```

### Count Iterations

```bash
grep "^ITERATION" logs/session_*.log | wc -l
```

## Configuration Options

### Available Flags

- `--provider`: bedrock, claude, or openai
- `--model`: Model name (depends on provider)
- `--url`: Target webpage URL
- `--prompt`: Task description
- `--two-phase-workflow`: Enable search-first workflow
- `--extended-thinking`: Enable deep reasoning
- `--thinking-budget`: Token budget for thinking (default: 10000)
- `--max-iterations`: Maximum iterations (default: 30)
- `--display-width`: Browser width (default: 1024)
- `--display-height`: Browser height (default: 768)
- `--zoom`: Browser zoom percentage (default: 85)
- `--headless`: Run browser in headless mode (default: true)
- `--record-video`: Record video of session
- `--enable-caching`: Enable prompt caching (default: true)

### Example with All Options

```bash
python -m cua \
  --provider bedrock \
  --model sonnet-4.5 \
  --url "YOUR_URL" \
  --prompt "$(cat test_prompt_simple.txt)" \
  --two-phase-workflow \
  --extended-thinking \
  --thinking-budget 15000 \
  --max-iterations 25 \
  --display-width 1280 \
  --display-height 720 \
  --zoom 100 \
  --headless \
  --record-video \
  --enable-caching
```

## Troubleshooting

### Issue: Agent is scrolling too much

**Solution:** Use `--two-phase-workflow` flag to force search-first behavior:

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "YOUR_URL" \
  --two-phase-workflow \
  --prompt "$(cat test_prompt_simple.txt)"
```

### Issue: Agent is making wrong decisions

**Solution:** Enable extended thinking and check logs:

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "YOUR_URL" \
  --two-phase-workflow \
  --extended-thinking \
  --thinking-budget 15000 \
  --prompt "$(cat test_prompt_simple.txt)"

# Then check the logs
cat logs/session_*.log | grep "RESPONSE RECEIVED" -A 20
```

### Issue: Running out of iterations

**Solution:** Increase max iterations or optimize prompt:

```bash
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "YOUR_URL" \
  --max-iterations 50 \
  --two-phase-workflow \
  --prompt "$(cat test_prompt_simple.txt)"
```

### Issue: Token costs too high

**Solutions:**
1. Use Haiku model (cheaper):
   ```bash
   python -m cua --provider bedrock --model haiku-4.5 ...
   ```

2. Reduce thinking budget:
   ```bash
   --thinking-budget 5000
   ```

3. Enable caching (default, but ensure it's on):
   ```bash
   --enable-caching
   ```

### Issue: Can't find codes

**Solution:** Check if search tool is being used by examining logs:

```bash
grep -n "search_page_content" logs/session_*.log
```

If not used enough, make prompt more explicit about search usage.

## Best Practices

1. **Always use `--two-phase-workflow`** for challenges requiring search
2. **Use extended thinking** for complex multi-step tasks
3. **Check logs** after each run to understand behavior
4. **Start with simple prompts** and add detail if needed
5. **Use Haiku for testing**, Sonnet for production, Opus for complex tasks
6. **Monitor token usage** via logs to optimize costs
7. **Mark transient content** in prompts if you know what's transient
8. **Use specific prompts** for better results

## Performance Monitoring

### Create a test script

```bash
#!/bin/bash
# test_agent.sh

URL="YOUR_CHALLENGE_URL"
LOG_DIR="./test_results"

mkdir -p "$LOG_DIR"

echo "Testing Haiku..."
python -m cua --provider bedrock --model haiku-4.5 \
  --url "$URL" --two-phase-workflow \
  --prompt "$(cat test_prompt_simple.txt)" \
  2>&1 | tee "$LOG_DIR/haiku_$(date +%s).log"

echo "Testing Sonnet..."
python -m cua --provider bedrock --model sonnet-4.5 \
  --url "$URL" --two-phase-workflow --extended-thinking \
  --prompt "$(cat test_prompt_simple.txt)" \
  2>&1 | tee "$LOG_DIR/sonnet_$(date +%s).log"

echo "Analyzing results..."
grep "Task completed\|Max iterations" "$LOG_DIR"/*.log
```

## Advanced Usage

### Batch Testing

```bash
# Test multiple URLs
for url in url1 url2 url3; do
  echo "Testing $url"
  python -m cua --provider bedrock --model sonnet-4.5 \
    --url "$url" --two-phase-workflow \
    --prompt "Complete all tasks" \
    2>&1 | tee "results_${url//\//_}.log"
done
```

### Compare Providers

```bash
# Test same task with different providers
TASK="Complete the form"
URL="https://example.com/form"

echo "Testing Bedrock..."
python -m cua --provider bedrock --model sonnet-4.5 --url "$URL" --prompt "$TASK"

echo "Testing Claude Direct..."
python -m cua --provider claude --model claude-sonnet-4-5 --url "$URL" --prompt "$TASK"

echo "Testing OpenAI..."
python -m cua --provider openai --model computer-use-preview --url "$URL" --prompt "$TASK"
```

## Getting Help

Check the documentation:
- `CLAUDE.md` - Provider details and architecture
- `TWO_PHASE_WORKFLOW_GUIDE.md` - Two-phase workflow explanation
- `SEARCH_TOOL_GUIDE.md` - Search tool usage
- `TEST_PROMPT.md` - Detailed test prompt documentation
- `CHANGES.md` - Recent changes and improvements

Check logs for debugging:
```bash
ls -lh logs/
cat logs/session_*.log
```
