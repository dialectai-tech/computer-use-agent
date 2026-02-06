Here’s a **practical, up-to-date overview (2025–early 2026)** of how to build a **computer-use agent using AWS Bedrock with Anthropic Claude models (Sonnet / Haiku / Opus)**—including architecture, current docs, examples, and real-world pitfalls.

I’ll organize this into:

1. What “computer use” on Bedrock actually is
2. Supported models and requirements (important gotcha)
3. Architecture: how a computer-use agent works end-to-end
4. Implementation steps (with concrete patterns)
5. Example flow and code structure
6. Pitfalls and gotchas people run into
7. Notes on Sonnet vs Haiku vs Opus
8. Useful repos, docs, and patterns to explore

---

# 1. What “computer use” on Bedrock actually means

On Bedrock, **computer use is not an autonomous agent running on AWS**.

Instead:

* Claude outputs **structured tool actions** (mouse, keyboard, bash, etc.)
* **Your code executes those actions**
* You send back screenshots or results
* Claude continues planning

So the loop is:

```
Prompt → Claude → tool_use JSON → your executor → screenshot/result → Claude → …
```

AWS describes this explicitly:

* Claude returns `tool_use` actions in JSON (scroll, click, screenshot, etc.).
* Your application runs the actions and sends results back. ([AWS Documentation][1])

This is important:
**Bedrock provides the brain, not the hands. You implement the hands.**

---

# 2. Supported models and requirements (critical)

This is where many people get confused.

### Models that support computer use

Recent AWS docs list support for:

* Claude 3.7 Sonnet
* Claude 3.5 Sonnet v2
* Claude Sonnet 4 / 4.5
* Claude Haiku 4.5
* Claude Opus 4 / 4.5 ([AWS Documentation][2])

But:

**Agents with computer-use tools in Bedrock Agents**

* Official agent workflow examples currently highlight **Sonnet variants primarily**. ([AWS Documentation][3])

So:

* API-level computer use: broader model support
* Bedrock Agents + computer use: Sonnet most commonly supported in docs

### Required parameter

You must enable the beta feature:

```json
"anthropic_beta": ["computer-use-2025-01-24"]
```

Otherwise tool use fails silently or errors. ([AWS Documentation][2])

This is one of the most common mistakes.

---

# 3. Architecture of a Bedrock computer-use agent

A typical architecture:

```
User
  ↓
Agent Orchestrator (your code)
  ↓
Bedrock Claude
  ↓
tool_use actions
  ↓
Tool Executor Layer
  - VM
  - container
  - browser automation
  - desktop automation
  ↓
Screenshots / outputs
  ↓
Claude continues
```

AWS explicitly recommends:

* Run in a **VM or container**
* Use minimal privileges
* Avoid sensitive credentials ([AWS Documentation][2])

---

# 4. Implementation steps (realistic workflow)

### Step 1: Get model access

In AWS console:

```
Bedrock → Model access → request Anthropic models
```

You must do this per region. ([Claude API Docs][4])

---

### Step 2: Decide architecture

Two main patterns:

#### Pattern A — Bedrock Agents

Use:

* Action Groups
* Computer tool
* Guardrails

Workflow:

1. Create agent
2. Add action group
3. Implement tool handler
4. Invoke agent and handle tool calls ([AWS Documentation][3])

This is more managed but less flexible.

---

#### Pattern B — Direct Converse API (recommended for control)

Use:

* Converse API
* Tools parameter
* Manual loop

This gives full control and is what most production systems do.

---

### Step 3: Define tools

Example tool definition:

```json
{
  "name": "computer",
  "type": "computer_20250124"
}
```

Anthropic-defined tools:

* computer
* text_editor
* bash ([AWS Documentation][3])

You do NOT provide schemas for these tools.

---

### Step 4: Build the execution loop

Pseudo-code pattern:

```python
while True:
    response = bedrock.converse(...)
    
    if response.stop_reason == "tool_use":
        actions = extract_tool_calls(response)

        results = execute_actions(actions)

        send_tool_results(results)
    else:
        break
```

This loop is the core of every computer-use agent.

---

### Step 5: Build tool executors

Common implementations:

| Tool        | Typical implementation            |
| ----------- | --------------------------------- |
| Computer    | Playwright / Selenium / PyAutoGUI |
| Bash        | subprocess in sandbox             |
| Text editor | file operations                   |

Most demos run in:

* Docker container
* headless VM
* VNC environment

---

# 5. Example flow (realistic scenario)

User:

```
Open Gmail and summarize unread emails
```

Claude loop:

1. Screenshot desktop
2. Click browser
3. Navigate
4. Screenshot inbox
5. Extract text
6. Summarize

Each step is:

```
Claude → tool_use → executor → screenshot → Claude
```

---

# 6. Pitfalls and gotchas (important)

These are the real issues teams hit.

## 6.1 Forgetting anthropic_beta header

This causes:

* tool calls not appearing
* validation errors

Very common.

---

## 6.2 Not returning tool results properly

You must:

* preserve tool_use id
* return structured results

Otherwise Claude ignores results or loops.

A frequent complaint from developers is tools being called but responses ignored—often due to payload or orchestration issues. ([Reddit][5])

---

## 6.3 Running computer use on your real machine

AWS strongly warns against this.

Use:

* disposable VM
* locked-down container ([AWS Documentation][2])

---

## 6.4 Image guardrails limitations

If extracting text from screenshots:

* you may need ApplyGuardrail manually ([AWS Documentation][3])

This catches people in regulated environments.

---

## 6.5 Model support inconsistencies

Some developers report:

* tool use errors on certain models
* throttling
* regional differences ([Reddit][6])

Not official documentation—but common field experience.

---

## 6.6 Region availability

Anthropic models vary by region. ([Claude API Docs][4])

Sometimes moving to us-east-1 fixes issues.

---

## 6.7 Latency and cost

Computer-use loops are expensive because:

* multiple screenshots
* large multimodal context
* many tool calls

Budget planning matters.

---

# 7. Sonnet vs Haiku vs Opus for agents

Practical tradeoffs:

| Model  | Use case                  |
| ------ | ------------------------- |
| Haiku  | fast UI automation, cheap |
| Sonnet | best balance for agents   |
| Opus   | complex reasoning tasks   |

In practice:

* Sonnet is most widely used for agents today
* Haiku works for simple workflows
* Opus may be slower or harder to provision in Bedrock

---

# 8. Latest patterns and ecosystem notes

These trends are emerging:

### OpenAI-compatible gateways

Some teams run a proxy layer to make Bedrock Claude work with agent frameworks. ([Reddit][7])

Reason:

* Bedrock SDK differs from common agent tooling.

---

### MCP-style tool protocols

Research shows:

* tool invocation reliability still relatively low (~36% success rates in benchmarks) ([arXiv][8])

So:

* orchestration logic matters as much as the model.

---

# 9. Reference docs worth reading

Key AWS docs:

* Tool use parameters
  [https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages-tool-use.html](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages-tool-use.html)

* Computer use with agents
  [https://docs.aws.amazon.com/bedrock/latest/userguide/agents-computer-use.html](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-computer-use.html)

* Example computer use workflow
  [https://docs.aws.amazon.com/bedrock/latest/userguide/computer-use.html](https://docs.aws.amazon.com/bedrock/latest/userguide/computer-use.html)

Anthropic quickstarts (for executor code):

* anthropic-quickstarts repo

---

# 10. Recommended architecture (what experienced teams do)

If you’re building something serious:

```
Claude (Bedrock)
   ↓
Agent loop (Python service)
   ↓
Tool router
   ↓
Executor containers
   ↓
Screenshot pipeline
   ↓
State store
```

And:

* run executor in ephemeral containers
* cap step count
* add safety filters

---

# 11. A practical mental model

Think of computer-use agents as:

```
Planner (LLM)
+
Executor (your infra)
+
State loop (orchestrator)
```

Most bugs happen in:

* the loop
* tool result formatting
* state management

Not in the model itself.

---

Sources:

[1]: https://docs.aws.amazon.com/bedrock/latest/userguide/computer-use.html?utm_source=chatgpt.com "Use a computer use tool to complete an Amazon Bedrock model response - Amazon Bedrock"
[2]: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages-tool-use.html?utm_source=chatgpt.com "Tool use - Amazon Bedrock"
[3]: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-computer-use.html?utm_source=chatgpt.com "Configure an Amazon Bedrock Agent to complete tasks with computer use tools - Amazon Bedrock"
[4]: https://docs.anthropic.com/en/api/claude-on-amazon-bedrock?utm_source=chatgpt.com "Amazon Bedrock API - Anthropic"
[5]: https://www.reddit.com/r/AI_Agents/comments/1l0ok9o?utm_source=chatgpt.com "Struggling to get agent to use a tool with aws bedrock agents"
[6]: https://www.reddit.com//r/aws/comments/1fqsdmv?utm_source=chatgpt.com "Bedrock is buggy: ValidationException: This model doesn't support tool use."
[7]: https://www.reddit.com//r/ClaudeAI/comments/1pqu9ja/use_claude_45_on_aws_bedrock_with_openwebui_cline/?utm_source=chatgpt.com "Use Claude 4.5 on AWS Bedrock with OpenWebUI, Cline, n8n, and any OpenAI-compatible tool"
[8]: https://arxiv.org/abs/2510.24563?utm_source=chatgpt.com "OSWorld-MCP: Benchmarking MCP Tool Invocation In Computer-Use Agents"
