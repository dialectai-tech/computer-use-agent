# Computer Use Automation - Implementation Plan

## Project Summary

A flexible, multi-provider computer use automation framework that enables AI agents (Claude or OpenAI) to autonomously complete web-based tasks through visual understanding and browser automation.

## Key Features

✅ **Multi-Provider Support**: Claude (Anthropic) and OpenAI with unified interface
✅ **Docker Isolation**: Safe, containerized browser environment
✅ **Real-time Monitoring**: VNC viewing and session recording
✅ **Performance Tracking**: Per-page and total session metrics
✅ **Flexible Configuration**: Easy model switching via environment variables
✅ **Generic Task Handling**: Works with any user-provided URL and instructions

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Python Application (Host)                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  CLI Interface (click)                                 │ │
│  │    └─> AgentController                                 │ │
│  │          ├─> Provider (Claude/OpenAI)                  │ │
│  │          ├─> BrowserController (Playwright)            │ │
│  │          ├─> MetricsCollector                          │ │
│  │          └─> SessionRecorder                           │ │
│  └────────────────────────────────────────────────────────┘ │
│               │ Docker API                  │               │
│               ▼                            ▼               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Docker Container (cua-browser)                        │ │
│  │  ├─ Xvfb (Virtual Display)                            │ │
│  │  ├─ Chromium Browser (Playwright)                     │ │
│  │  ├─ VNC Server (for viewing)                          │ │
│  │  └─ Supervisor (process management)                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
cua-project/
├── README.md                    # User-facing documentation
├── CLAUDE.md                    # Technical implementation guide
├── QUICKSTART.md                # 5-minute getting started
├── IMPLEMENTATION_PLAN.md       # This file
├── pyproject.toml              # Python package config
├── .env                        # Environment variables (gitignored)
├── .env.example                # Example env file
│
├── docker/
│   ├── Dockerfile              # Browser container
│   ├── docker-compose.yml      # Orchestration
│   ├── supervisord.conf        # Process management
│   └── start.sh                # Container startup
│
├── src/cua/
│   ├── __init__.py
│   ├── main.py                 # CLI entry point
│   │
│   ├── providers/              # AI Provider implementations
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract base class
│   │   ├── claude.py           # Anthropic Claude
│   │   ├── openai.py           # OpenAI
│   │   └── portkey.py          # Optional: Portkey gateway
│   │
│   ├── browser/                # Browser automation
│   │   ├── __init__.py
│   │   ├── docker_manager.py  # Docker container management
│   │   └── playwright_controller.py  # Playwright wrapper
│   │
│   ├── agent/                  # Agent logic
│   │   ├── __init__.py
│   │   ├── loop.py             # Main agent loop
│   │   ├── actions.py          # Action execution
│   │   └── completion.py       # Task completion detection
│   │
│   ├── monitoring/             # Monitoring & metrics
│   │   ├── __init__.py
│   │   ├── recorder.py         # Session video recording
│   │   └── metrics.py          # Performance tracking
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       ├── screenshot.py       # Screenshot handling
│       ├── logger.py           # Logging setup
│       └── config.py           # Configuration management
│
├── tests/                      # Unit & integration tests
│   ├── __init__.py
│   ├── test_providers.py
│   ├── test_browser.py
│   ├── test_agent.py
│   └── fixtures/
│
├── examples/                   # Example tasks
│   ├── simple_form.py
│   ├── multi_page.py
│   └── data_entry.py
│
├── recordings/                 # Session recordings (generated)
├── screenshots/                # Screenshots (generated)
└── logs/                       # Log files (generated)
```

## Implementation Phases

### Phase 1: Foundation (Week 1) ✓ READY TO IMPLEMENT

**Goal**: Basic working prototype with Claude provider

Tasks:
- [x] Project structure and documentation
- [x] Docker container setup
- [ ] Base provider interface
- [ ] Claude provider implementation
- [ ] Basic browser controller (Playwright)
- [ ] Simple agent loop
- [ ] CLI interface

**Deliverable**: Can navigate to URL and take screenshot via Claude

### Phase 2: OpenAI Integration (Week 1-2)

**Goal**: Add OpenAI support with same interface

Tasks:
- [ ] OpenAI provider implementation
- [ ] Unified action mapping (Claude ↔ OpenAI)
- [ ] Provider factory pattern
- [ ] Configuration for easy switching

**Deliverable**: Can use either Claude or OpenAI via `--provider` flag

### Phase 3: Monitoring & Metrics (Week 2)

**Goal**: Comprehensive observability

Tasks:
- [ ] VNC integration
- [ ] Session recording (ffmpeg)
- [ ] Metrics collection (timing, actions, costs)
- [ ] Pretty console output (rich)
- [ ] Logging system

**Deliverable**: Can watch agent in real-time and review recordings

### Phase 4: Advanced Features (Week 3)

**Goal**: Production-ready features

Tasks:
- [ ] Task completion detection (semantic)
- [ ] Error recovery and retries
- [ ] Multi-page workflow handling
- [ ] Form auto-fill intelligence
- [ ] Context extraction (HTML + screenshots)

**Deliverable**: Handles complex multi-step tasks reliably

### Phase 5: Testing & Optimization (Week 4)

**Goal**: Robust, tested, optimized

Tasks:
- [ ] Comprehensive test suite
- [ ] Performance benchmarks
- [ ] Cost optimization (screenshot compression)
- [ ] Documentation completion
- [ ] Example tasks library

**Deliverable**: Production-ready release

## Core Components

### 1. Provider Interface

```python
class ComputerUseProvider(ABC):
    @abstractmethod
    def create_request(self, prompt: str, screenshot: str = None) -> Any:
        """Create API request"""

    @abstractmethod
    def parse_response(self, response: Any) -> List[Action]:
        """Extract actions from response"""

    @abstractmethod
    def continue_conversation(self, screenshot: str, action_result: dict) -> Any:
        """Continue with new context"""

    @abstractmethod
    def is_task_complete(self, response: Any) -> bool:
        """Check if task is done"""
```

### 2. Action Types

```python
@dataclass
class Action:
    type: ActionType  # screenshot, click, type, key, scroll, etc.
    params: Dict[str, Any]
    id: str
    timestamp: float

class ActionType(Enum):
    SCREENSHOT = "screenshot"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TYPE = "type"
    KEY = "key"
    SCROLL = "scroll"
    WAIT = "wait"
    # ... more
```

### 3. Agent Loop

```python
class AgentLoop:
    def run_task(self, url: str, prompt: str, max_iterations: int = 30):
        # 1. Initialize browser
        # 2. Navigate to URL
        # 3. Take initial screenshot
        # 4. Send to AI provider
        # 5. Loop:
        #    a. Get actions from AI
        #    b. Execute actions
        #    c. Capture screenshot
        #    d. Send back to AI
        #    e. Check completion
        # 6. Return results
```

### 4. Metrics Collection

```python
@dataclass
class PageMetrics:
    url: str
    time_spent: float
    actions_count: int
    screenshot_count: int

@dataclass
class SessionMetrics:
    start_time: datetime
    end_time: datetime
    total_time: float
    pages: List[PageMetrics]
    total_actions: int
    total_screenshots: int
    api_calls: int
    estimated_cost: float
```

## Key Design Decisions

### 1. Provider Abstraction

**Decision**: Use abstract base class with factory pattern

**Rationale**:
- Easy to add new providers (Azure OpenAI, AWS Bedrock)
- Consistent interface across providers
- Testable with mocks
- User can switch providers without code changes

### 2. Docker for Browser

**Decision**: Run browser in Docker container, not on host

**Rationale**:
- Security isolation
- Reproducible environment
- Easy cleanup
- Works on Azure VM without desktop
- VNC accessible remotely

### 3. Playwright over Selenium

**Decision**: Use Playwright for browser automation

**Rationale**:
- Better async support
- More reliable
- Better TypeScript/Python support
- Modern API
- Used by both Claude and OpenAI reference implementations

### 4. Recording Strategy

**Decision**: Use ffmpeg to record X11 display

**Rationale**:
- Native recording of virtual display
- No browser plugin needed
- Can record full session
- Lightweight

### 5. Configuration Management

**Decision**: Use .env file with pydantic models

**Rationale**:
- Simple for users
- Type-safe with pydantic
- Easy defaults
- Secure (not in git)

## Example Usage Patterns

### Pattern 1: Simple Task

```bash
python -m cua.main \
  --url "https://example.com" \
  --prompt "Click the contact button"
```

### Pattern 2: With Configuration

```bash
python -m cua.main \
  --url "https://forms.gle/xyz" \
  --prompt "Fill the survey" \
  --provider claude \
  --model claude-opus-4-5 \
  --max-iterations 50 \
  --enable-recording
```

### Pattern 3: Programmatic

```python
from cua import ComputerUseAgent
from cua.providers import ClaudeProvider

agent = ComputerUseAgent(
    provider=ClaudeProvider(),
    enable_recording=True
)

result = agent.run_task(
    url="https://example.com",
    prompt="Complete the form"
)

print(f"Success: {result.success}")
print(f"Time: {result.total_time:.2f}s")
```

### Pattern 4: Model Comparison

```python
from cua import compare_providers

results = compare_providers(
    url="https://test-site.com",
    prompt="Complete task X",
    providers=["claude", "openai"]
)

for provider, result in results.items():
    print(f"{provider}: {result.total_time:.2f}s, ${result.cost:.2f}")
```

## Testing Strategy

### Unit Tests
- Provider implementations
- Action parsers
- Screenshot handlers
- Metrics collectors

### Integration Tests
- Docker container setup
- Playwright automation
- End-to-end agent loop

### E2E Tests
- Real tasks on test websites
- Multi-step workflows
- Error scenarios

## Performance Considerations

### Screenshot Optimization
- Compress to JPEG at 85% quality
- Resize to API limits
- Cache if unchanged
- Implement coordinate scaling

### API Cost Optimization
- Use Haiku for simple tasks
- Batch actions when possible
- Implement thinking budget
- Cache common patterns

### Container Resources
- Set memory limits (2GB)
- Use shared memory for Chromium
- Clean up old containers
- Monitor disk usage

## Security Considerations

### Container Isolation
- No host filesystem access
- Network allowlist (optional)
- Non-root user (future)
- Resource limits

### API Key Management
- Never commit .env
- Use environment variables
- Rotate keys regularly
- Monitor usage

### Task Safety
- Confirm high-risk actions
- Domain allowlist
- Timeout limits
- Human-in-loop (optional)

## Next Steps After Implementation

### Short Term
1. **Documentation**: Complete API docs and tutorials
2. **Examples**: Build library of common tasks
3. **Testing**: Comprehensive test coverage
4. **Optimization**: Performance tuning

### Medium Term
1. **Additional Providers**: Azure OpenAI, AWS Bedrock
2. **UI Dashboard**: Web interface for monitoring
3. **Task Templates**: Pre-built task definitions
4. **Parallel Execution**: Run multiple tasks concurrently

### Long Term
1. **Learning System**: Learn from successful tasks
2. **Prompt Optimization**: Auto-improve prompts
3. **Agent Collaboration**: Multiple agents on same task
4. **Cloud Deployment**: Deploy as SaaS service

## Success Metrics

**Phase 1 Success**:
- [ ] Can navigate to URL via Claude
- [ ] Can take screenshot
- [ ] Can click elements
- [ ] Can type text
- [ ] Basic metrics collected

**Full Project Success**:
- [ ] Works with both Claude and OpenAI
- [ ] Can complete multi-step forms
- [ ] VNC viewing works
- [ ] Session recording works
- [ ] Metrics and timing tracked
- [ ] Documentation complete
- [ ] Test coverage >80%
- [ ] Successfully completes 10+ example tasks

## Resources & References

### Documentation
- [README.md](./README.md) - User guide
- [CLAUDE.md](./CLAUDE.md) - Technical deep dive
- [QUICKSTART.md](./QUICKSTART.md) - Getting started

### External Resources
- [Anthropic Computer Use Docs](https://docs.anthropic.com/claude/docs/computer-use)
- [OpenAI Computer Use Guide](https://platform.openai.com/docs/guides/tools-computer-use)
- [Claude Reference Implementation](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo)
- [Playwright Documentation](https://playwright.dev/python/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

### Tools & Libraries
- **anthropic**: Claude API client
- **openai**: OpenAI API client
- **playwright**: Browser automation
- **docker-py**: Docker Python SDK
- **click**: CLI framework
- **rich**: Terminal UI
- **pydantic**: Data validation
- **python-dotenv**: Environment management

## Questions & Decisions Needed

1. **Recording Format**: MP4 or WebM? (Recommendation: MP4 for compatibility)
2. **Default Model**: Sonnet or Haiku? (Recommendation: Sonnet for balance)
3. **Max Iterations**: 30 or 50? (Recommendation: 30 with configurable override)
4. **VNC Default**: On or Off? (Recommendation: Off by default, enable via flag)
5. **Portkey Integration**: Required or optional? (Recommendation: Optional)

## Timeline Estimate

**Minimum Viable Product**: 1 week
- Basic Claude provider + Docker + Simple agent loop

**Full Feature Set**: 3-4 weeks
- Both providers + monitoring + advanced features + testing

**Production Ready**: 6-8 weeks
- Above + optimization + documentation + examples + deployment

## Conclusion

This implementation plan provides a comprehensive roadmap for building a production-ready, multi-provider computer use automation framework. The modular architecture enables incremental development while maintaining flexibility for future enhancements.

**Current Status**: ✅ Foundation complete, ready to implement Phase 1

**Next Action**: Begin coding provider interface and Claude implementation
