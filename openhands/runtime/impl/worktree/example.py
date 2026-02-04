#!/usr/bin/env python3
"""Example usage of WorktreeRuntime for OpenHands.

This script demonstrates how to use the WorktreeRuntime to run multiple
agents in parallel on a single VPS using git worktrees for isolation.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the parent directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from openhands.core.config import OpenHandsConfig
from openhands.events import EventStream
from openhands.events.action import CmdRunAction
from openhands.llm.llm_registry import LLMRegistry
from openhands.runtime.impl.worktree import WorktreeRuntime


async def run_agent_in_worktree(
    session_id: str,
    task: str,
    base_repo_path: str,
) -> None:
    """Run an agent task in an isolated worktree.

    Args:
        session_id: Unique session identifier.
        task: The task to execute.
        base_repo_path: Path to the base git repository.
    """
    print(f"[{session_id}] Starting agent in worktree...")

    # Create configuration
    config = OpenHandsConfig()
    event_stream = EventStream()
    llm_registry = LLMRegistry()

    # Create the runtime
    runtime = WorktreeRuntime(
        config=config,
        event_stream=event_stream,
        llm_registry=llm_registry,
        sid=session_id,
        base_repo_path=base_repo_path,
        headless_mode=True,
    )

    try:
        # Connect to the runtime (creates worktree and starts server)
        await runtime.connect()
        print(f"[{session_id}] Connected to runtime at: {runtime.worktree_path}")
        print(f"[{session_id}] Server URL: {runtime.action_execution_server_url}")

        # Execute a command in the worktree
        action = CmdRunAction(command=f'echo "Running task: {task}" && pwd && git status')
        observation = runtime.run_action(action)
        print(f"[{session_id}] Result: {observation}")

        # Execute another command to show isolation
        action = CmdRunAction(command='echo "Worktree-specific file" > test.txt && cat test.txt')
        observation = runtime.run_action(action)
        print(f"[{session_id}] Result: {observation}")

        print(f"[{session_id}] Task completed successfully!")

    except Exception as e:
        print(f"[{session_id}] Error: {e}")
        raise

    finally:
        # Clean up
        runtime.close()
        print(f"[{session_id}] Runtime closed and worktree removed.")


async def main():
    """Run multiple agents in parallel using worktrees."""
    # Use current directory as base repository
    base_repo_path = os.getcwd()

    print("=" * 60)
    print("WorktreeRuntime Parallel Agent Execution Example")
    print("=" * 60)
    print(f"Base repository: {base_repo_path}")
    print()

    # Define tasks for multiple agents
    tasks = [
        ("agent-001", "Implement feature A"),
        ("agent-002", "Fix bug B"),
        ("agent-003", "Refactor module C"),
    ]

    # Run agents in parallel
    print("Starting parallel agent execution...\n")
    await asyncio.gather(
        *[
            run_agent_in_worktree(session_id, task, base_repo_path)
            for session_id, task in tasks
        ]
    )

    print("\n" + "=" * 60)
    print("All agents completed!")
    print("=" * 60)


if __name__ == '__main__':
    # Run the example
    asyncio.run(main())
