# WorktreeRuntime for OpenHands

A lightweight runtime implementation for OpenHands that uses **git worktrees** for isolation instead of Docker containers. This enables parallel agent execution on a single VPS without the overhead of containerization.

## Overview

`WorktreeRuntime` creates isolated working environments using git worktrees, allowing multiple agents to work in parallel on the same repository. Each worktree:

- Shares the same git history with the base repository
- Has its own independent working directory
- Runs processes directly on the host (no container overhead)
- Is completely isolated from other worktrees

## Features

- **No Docker Required**: Runs directly on the host system
- **Lightweight**: Uses git worktrees for isolation (shares git history)
- **Parallel Execution**: Multiple agents can work simultaneously
- **Fast Startup**: No container image building or pulling
- **Resource Efficient**: Lower memory and CPU overhead compared to containers
- **Full Git Integration**: Native git operations within each worktree

## Installation

1. Ensure you have git installed:
```bash
git --version
```

2. Copy the `worktree` directory to your OpenHands installation:
```bash
cp -r worktree /path/to/openhands/runtime/impl/
```

3. The runtime will be automatically available through OpenHands' runtime factory.

## Usage

### Basic Usage

```python
from openhands.core.config import OpenHandsConfig
from openhands.events import EventStream
from openhands.llm.llm_registry import LLMRegistry
from openhands.runtime.impl.worktree import WorktreeRuntime

# Create configuration
config = OpenHandsConfig()
event_stream = EventStream()
llm_registry = LLMRegistry()

# Create and connect to the runtime
runtime = WorktreeRuntime(
    config=config,
    event_stream=event_stream,
    llm_registry=llm_registry,
    sid='my-session-001',
    base_repo_path='/path/to/your/repo',
)

# Connect to the runtime (creates worktree and starts server)
await runtime.connect()

# Use the runtime
# ... your agent code here ...

# Clean up
runtime.close()
```

### Configuration Options

```python
runtime = WorktreeRuntime(
    config=config,
    event_stream=event_stream,
    llm_registry=llm_registry,
    sid='unique-session-id',
    plugins=[VSCodeRequirement()],  # Optional plugins
    env_vars={'MY_VAR': 'value'},   # Environment variables
    base_repo_path='/path/to/repo', # Base repository path
    headless_mode=True,             # Run in headless mode
)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENHANDS_WORKTREE_BASE_DIR` | Base directory for all worktrees | `/tmp/openhands-worktrees` |
| `DISABLE_VSCODE_PLUGIN` | Disable VSCode plugin | `false` |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Host System                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Base Repository                        │   │
│  │         (/path/to/your/repo)                        │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐             │   │
│  │  │  .git/  │  │  src/   │  │  docs/  │             │   │
│  │  └─────────┘  └─────────┘  └─────────┘             │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│              git worktree add --detach                     │
│                           │                                 │
│              ┌────────────┼────────────┐                   │
│              ▼            ▼            ▼                   │
│  ┌─────────────────┐ ┌─────────────────┐ ┌────────────────┐│
│  │  Worktree 1     │ │  Worktree 2     │ │  Worktree 3    ││
│  │  (session-001)  │ │  (session-002)  │ │  (session-003) ││
│  │  ┌───────────┐  │ │  ┌───────────┐  │ │  ┌──────────┐  ││
│  │  │  src/     │  │ │  │  src/     │  │ │  │  src/    │  ││
│  │  │ (modified)│  │ │  │ (modified)│  │ │  │(modified)│  ││
│  │  └───────────┘  │ │  └───────────┘  │ │  └──────────┘  ││
│  │  ┌───────────┐  │ │  ┌───────────┐  │ │  ┌──────────┐  ││
│  │  │  .git     │──┘ │  │  .git     │──┘ │  │  .git    │──┘│
│  │  │ (linked)  │    │  │ (linked)  │    │  │ (linked) │   │
│  │  └───────────┘    │  └───────────┘    │  └──────────┘   │
│  └─────────────────┘ └─────────────────┘ └────────────────┘│
│                                                            │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

1. **Worktree Creation**: When `connect()` is called, the runtime creates a new git worktree using `git worktree add --detach`

2. **Process Isolation**: Each worktree runs its own action execution server process on a dedicated port

3. **Shared Git History**: All worktrees share the same `.git` directory, making git operations efficient

4. **Independent Working Directories**: Each worktree has its own working directory for file operations

5. **Cleanup**: When `close()` is called, the worktree is removed using `git worktree remove`

## Comparison with Other Runtimes

| Feature | DockerRuntime | LocalRuntime | WorktreeRuntime |
|---------|---------------|--------------|-----------------|
| Isolation | Container | None | Git worktree |
| Startup Time | Slow (image pull/build) | Fast | Fast |
| Memory Overhead | High | Low | Low |
| Parallel Execution | Yes | No | Yes |
| Git Integration | Requires volume mounts | Native | Native |
| Resource Usage | High | Low | Low |
| Docker Required | Yes | No | No |

## API Reference

### WorktreeRuntime

#### Constructor Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `config` | `OpenHandsConfig` | Yes | OpenHands configuration |
| `event_stream` | `EventStream` | Yes | Event stream for communication |
| `llm_registry` | `LLMRegistry` | Yes | LLM registry |
| `sid` | `str` | No | Session ID (default: 'default') |
| `plugins` | `list[PluginRequirement]` | No | List of plugins to load |
| `env_vars` | `dict[str, str]` | No | Environment variables |
| `status_callback` | `Callable` | No | Status update callback |
| `attach_to_existing` | `bool` | No | Attach to existing runtime |
| `headless_mode` | `bool` | No | Run in headless mode |
| `user_id` | `str` | No | User ID |
| `git_provider_tokens` | `PROVIDER_TOKEN_TYPE` | No | Git provider tokens |
| `main_module` | `str` | No | Main module to run |
| `base_repo_path` | `str` | No | Base repository path |

#### Methods

##### `async connect()`
Creates the worktree and starts the action execution server.

##### `close()`
Stops the server and removes the worktree.

##### `pause()`
Pauses the runtime by stopping the server process (worktree remains).

##### `resume()`
Resumes the runtime by restarting the server process.

##### `run_action(action: Action) -> Observation`
Executes an action in the worktree context.

##### `classmethod async delete(conversation_id: str)`
Deletes a worktree runtime by conversation ID.

#### Properties

##### `action_execution_server_url: str`
URL of the action execution server.

##### `vscode_url: str | None`
URL for VSCode access (if enabled).

##### `web_hosts: dict[str, int]`
Dictionary of web hosts and their ports.

## Examples

### Running Multiple Agents in Parallel

```python
import asyncio
from openhands.runtime.impl.worktree import WorktreeRuntime

async def run_agent(session_id: str, task: str):
    runtime = WorktreeRuntime(
        config=config,
        event_stream=event_stream,
        llm_registry=llm_registry,
        sid=session_id,
        base_repo_path='/path/to/repo',
    )
    await runtime.connect()
    
    # Run your agent logic here
    # ...
    
    runtime.close()

# Run multiple agents in parallel
await asyncio.gather(
    run_agent('agent-001', 'Task 1'),
    run_agent('agent-002', 'Task 2'),
    run_agent('agent-003', 'Task 3'),
)
```

### Custom Worktree Base Directory

```python
import os

# Set custom worktree base directory
os.environ['OPENHANDS_WORKTREE_BASE_DIR'] = '/var/openhands/worktrees'

runtime = WorktreeRuntime(
    config=config,
    event_stream=event_stream,
    llm_registry=llm_registry,
    sid='my-session',
    base_repo_path='/path/to/repo',
)
```

### With Plugins

```python
from openhands.runtime.plugins import VSCodeRequirement, JupyterRequirement

runtime = WorktreeRuntime(
    config=config,
    event_stream=event_stream,
    llm_registry=llm_registry,
    sid='my-session',
    plugins=[
        VSCodeRequirement(),
        JupyterRequirement(),
    ],
    base_repo_path='/path/to/repo',
)
```

## Troubleshooting

### Worktree Already Exists

If you see an error about a worktree already existing, you can manually remove it:

```bash
# List worktrees
git worktree list

# Remove a specific worktree
git worktree remove --force /path/to/worktree

# Or remove all worktrees
for wt in $(git worktree list --porcelain | grep worktree | cut -d' ' -f2); do
    git worktree remove --force "$wt"
done
```

### Port Conflicts

If you encounter port conflicts, the runtime will automatically find alternative ports. You can also specify custom port ranges in the configuration.

### Git Not Initialized

If the base repository path is not a git repository, the runtime will automatically initialize it. To avoid this, ensure your repository is already initialized:

```bash
cd /path/to/your/repo
git init
git add .
git commit -m "Initial commit"
```

## Contributing

Contributions are welcome! Please ensure:

1. Code follows the existing style and patterns
2. Tests are added for new functionality
3. Documentation is updated

## License

This project is part of OpenHands and follows the same license terms.
