# OpenHands WorktreeRuntime Implementation

This document describes the `WorktreeRuntime` implementation for OpenHands, which provides Docker-like isolation without container overhead by using git worktrees.

## Files Created

```
openhands/runtime/impl/worktree/
├── __init__.py              # Package exports
├── worktree_runtime.py      # Main implementation
├── README.md                # Documentation
├── example.py               # Usage example
└── test_worktree_runtime.py # Unit tests
```

## Quick Start

### 1. Installation

Copy the `worktree` directory to your OpenHands installation:

```bash
cp -r openhands/runtime/impl/worktree /path/to/openhands/runtime/impl/
```

### 2. Basic Usage

```python
from openhands.runtime.impl.worktree import WorktreeRuntime

runtime = WorktreeRuntime(
    config=config,
    event_stream=event_stream,
    llm_registry=llm_registry,
    sid='my-session',
    base_repo_path='/path/to/repo',
)

await runtime.connect()
# ... use runtime ...
runtime.close()
```

## Architecture

### Class Hierarchy

```
Runtime (base.py)
    └── ActionExecutionClient (action_execution_client.py)
            ├── DockerRuntime (docker/docker_runtime.py)
            ├── LocalRuntime (local/local_runtime.py)
            └── WorktreeRuntime (worktree/worktree_runtime.py) [NEW]
```

### Key Components

#### WorktreeRuntime Class

The main class that extends `ActionExecutionClient` to provide worktree-based isolation.

**Key Methods:**
- `connect()` - Creates worktree and starts the action execution server
- `close()` - Stops server and removes worktree
- `pause()` - Stops server but keeps worktree
- `resume()` - Restarts server in existing worktree
- `run_action()` - Executes actions in the worktree context

**Key Properties:**
- `action_execution_server_url` - URL of the running server
- `vscode_url` - URL for VSCode access
- `web_hosts` - Dictionary of available web hosts

#### ActionExecutionServerInfo

Dataclass that holds information about a running server process:
- `process` - The subprocess.Popen instance
- `execution_server_port` - Port for the action execution server
- `vscode_port` - Port for VSCode
- `app_ports` - List of application ports
- `worktree_path` - Path to the worktree directory

## Implementation Details

### Worktree Creation

```python
def _create_worktree(self) -> str:
    """Creates a git worktree for this runtime instance."""
    # 1. Ensure base repo is a git repository
    self._init_base_repository()
    
    # 2. Create worktree using git worktree add --detach
    subprocess.run(
        ['git', 'worktree', 'add', '--detach', worktree_path],
        cwd=self.base_repo_path,
        check=True,
    )
    
    # 3. Configure git user in worktree
    # 4. Return worktree path
```

### Server Management

```python
def _start_server(self) -> ActionExecutionServerInfo:
    """Starts the action execution server in the worktree."""
    # 1. Find available ports
    execution_port, vscode_port, app_ports = self._find_available_ports()
    
    # 2. Prepare environment variables
    env = {
        'port': str(execution_port),
        'VSCODE_PORT': str(vscode_port),
        'OPENHANDS_WORKTREE_PATH': self.worktree_path,
        # ...
    }
    
    # 3. Start subprocess in worktree directory
    process = subprocess.Popen(
        command,
        cwd=self.worktree_path,
        env=env,
        # ...
    )
    
    # 4. Start log streaming thread
    # 5. Return server info
```

### Cleanup

```python
def close(self) -> None:
    """Closes the runtime and cleans up resources."""
    # 1. Stop server process
    self._stop_server()
    
    # 2. Remove worktree
    self._remove_worktree()
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENHANDS_WORKTREE_BASE_DIR` | Base directory for worktrees | `/tmp/openhands-worktrees` |
| `DISABLE_VSCODE_PLUGIN` | Disable VSCode plugin | `false` |

### Constructor Parameters

```python
WorktreeRuntime(
    config: OpenHandsConfig,          # Required: OpenHands configuration
    event_stream: EventStream,        # Required: Event stream
    llm_registry: LLMRegistry,        # Required: LLM registry
    sid: str = 'default',             # Optional: Session ID
    plugins: list[PluginRequirement], # Optional: Plugins
    env_vars: dict[str, str],         # Optional: Environment variables
    base_repo_path: str | None,       # Optional: Base repository path
    # ... other parameters from base class
)
```

## Comparison with Other Runtimes

| Aspect | DockerRuntime | LocalRuntime | WorktreeRuntime |
|--------|---------------|--------------|-----------------|
| **Isolation** | Container | None | Git worktree |
| **Startup** | Slow (image pull) | Fast | Fast |
| **Memory** | High | Low | Low |
| **Parallel** | Yes | No | Yes |
| **Git Ops** | Volume mounts | Native | Native |
| **Docker** | Required | Not needed | Not needed |
| **Overhead** | High | None | Minimal |

## Use Cases

### Best For

- Running multiple agents in parallel on a single VPS
- Environments where Docker is not available
- Scenarios requiring fast startup times
- Git-heavy workflows

### Not Ideal For

- Complete filesystem isolation (use DockerRuntime)
- Running untrusted code (no security sandbox)
- Scenarios requiring specific OS environments

## Testing

Run the unit tests:

```bash
cd openhands/runtime/impl/worktree
pytest test_worktree_runtime.py -v
```

Run the example:

```bash
cd openhands/runtime/impl/worktree
python example.py
```

## Integration with OpenHands

To integrate with OpenHands' runtime factory, add to `openhands/runtime/impl/__init__.py`:

```python
from openhands.runtime.impl.worktree import WorktreeRuntime

__all__ = [
    # ... existing exports
    'WorktreeRuntime',
]
```

And update the runtime factory to support the 'worktree' runtime type:

```python
# In runtime factory
if runtime_type == 'worktree':
    from openhands.runtime.impl.worktree import WorktreeRuntime
    return WorktreeRuntime(...)
```

## Performance Considerations

### Startup Time

- **DockerRuntime**: 30-120 seconds (image pull/build)
- **LocalRuntime**: 1-2 seconds
- **WorktreeRuntime**: 2-5 seconds (worktree creation + server start)

### Memory Usage

- **DockerRuntime**: ~500MB-2GB per container
- **LocalRuntime**: ~100-200MB per process
- **WorktreeRuntime**: ~100-200MB per process

### Disk Usage

- **DockerRuntime**: Image size + container layers
- **LocalRuntime**: Shared filesystem
- **WorktreeRuntime**: Shared git history + working directory

## Troubleshooting

### Common Issues

1. **Worktree already exists**
   - Solution: Remove existing worktree manually or use unique session IDs

2. **Port conflicts**
   - Solution: Runtime automatically finds alternative ports

3. **Git not initialized**
   - Solution: Runtime auto-initializes, or pre-initialize your repository

4. **Permission denied**
   - Solution: Ensure write permissions to worktree base directory

## Future Enhancements

Potential improvements:

1. **Overlay filesystem support** - For even more efficient disk usage
2. **Worktree pooling** - Reuse worktrees for faster startup
3. **Namespace isolation** - Linux namespace support for better isolation
4. **Resource limits** - CPU/memory limits per worktree
5. **Network isolation** - Per-worktree network namespaces

## References

- [Git Worktrees Documentation](https://git-scm.com/docs/git-worktree)
- [OpenHands Runtime Documentation](https://github.com/OpenHands/OpenHands/tree/main/openhands/runtime)
- [DockerRuntime Implementation](https://github.com/OpenHands/OpenHands/blob/main/openhands/runtime/impl/docker/docker_runtime.py)
- [LocalRuntime Implementation](https://github.com/OpenHands/OpenHands/blob/main/openhands/runtime/impl/local/local_runtime.py)
