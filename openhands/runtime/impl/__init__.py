"""Runtime implementations for OpenHands."""

from openhands.runtime.impl.action_execution.action_execution_client import (
    ActionExecutionClient,
)
from openhands.runtime.impl.docker.docker_runtime import DockerRuntime
from openhands.runtime.impl.local.local_runtime import LocalRuntime
from openhands.runtime.impl.remote.remote_runtime import RemoteRuntime
from openhands.runtime.impl.worktree import WorktreeRuntime

__all__ = [
    'ActionExecutionClient',
    'DockerRuntime',
    'LocalRuntime',
    'RemoteRuntime',
    'WorktreeRuntime',
]

# Lazy import for CLI runtime due to Windows .NET SDK dependency
try:
    from openhands.runtime.impl.cli import CLIRuntime
    __all__.append('CLIRuntime')
except ImportError:
    pass
