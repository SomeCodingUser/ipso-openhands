"""Worktree runtime implementation for OpenHands.

This module provides a runtime implementation that uses git worktrees for isolation
instead of Docker containers. This enables parallel agent execution on a single VPS
without the overhead of containerization.

Example usage:
    from openhands.runtime.impl.worktree import WorktreeRuntime

    runtime = WorktreeRuntime(
        config=config,
        event_stream=event_stream,
        llm_registry=llm_registry,
        sid='my-session',
        base_repo_path='/path/to/repo',
    )
    await runtime.connect()
"""

from openhands.runtime.impl.worktree.worktree_runtime import WorktreeRuntime

__all__ = ['WorktreeRuntime']
