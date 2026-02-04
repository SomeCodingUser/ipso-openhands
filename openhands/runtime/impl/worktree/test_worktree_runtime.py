"""Tests for WorktreeRuntime.

These tests verify the functionality of the WorktreeRuntime class,
including worktree creation, server management, and cleanup.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openhands.core.config import OpenHandsConfig
from openhands.core.exceptions import AgentRuntimeError
from openhands.events import EventStream
from openhands.llm.llm_registry import LLMRegistry
from openhands.runtime.impl.worktree.worktree_runtime import (
    WORKTREE_NAME_PREFIX,
    WorktreeRuntime,
)


@pytest.fixture
def temp_repo():
    """Create a temporary git repository for testing."""
    temp_dir = tempfile.mkdtemp()
    try:
        # Initialize git repository
        subprocess.run(
            ['git', 'init'],
            cwd=temp_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=temp_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=temp_dir,
            capture_output=True,
            check=True,
        )
        # Create initial commit
        Path(temp_dir, 'README.md').write_text('# Test Repo\n')
        subprocess.run(
            ['git', 'add', 'README.md'],
            cwd=temp_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ['git', 'commit', '-m', 'Initial commit'],
            cwd=temp_dir,
            capture_output=True,
            check=True,
        )
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_config():
    """Create a mock OpenHandsConfig."""
    config = MagicMock(spec=OpenHandsConfig)
    config.sandbox = MagicMock()
    config.sandbox.vscode_port = None
    config.sandbox.runtime_startup_env_vars = {}
    config.sandbox.keep_runtime_alive = False
    config.debug = False
    config.workspace_base = '/tmp'
    config.workspace_mount_path = '/tmp'
    config.workspace_mount_path_in_sandbox = '/workspace'
    return config


@pytest.fixture
def mock_event_stream():
    """Create a mock EventStream."""
    return MagicMock(spec=EventStream)


@pytest.fixture
def mock_llm_registry():
    """Create a mock LLMRegistry."""
    return MagicMock(spec=LLMRegistry)


class TestWorktreeRuntime:
    """Test cases for WorktreeRuntime."""

    def test_init(self, mock_config, mock_event_stream, mock_llm_registry, temp_repo):
        """Test WorktreeRuntime initialization."""
        runtime = WorktreeRuntime(
            config=mock_config,
            event_stream=mock_event_stream,
            llm_registry=mock_llm_registry,
            sid='test-session',
            base_repo_path=temp_repo,
        )

        assert runtime.sid == 'test-session'
        assert runtime.worktree_name == WORKTREE_NAME_PREFIX + 'test-session'
        assert runtime.base_repo_path == temp_repo
        assert runtime.worktree_path is None

    def test_is_git_repository(self, temp_repo):
        """Test _is_git_repository method."""
        runtime = WorktreeRuntime(
            config=MagicMock(),
            event_stream=MagicMock(),
            llm_registry=MagicMock(),
            base_repo_path=temp_repo,
        )

        assert runtime._is_git_repository(temp_repo) is True
        assert runtime._is_git_repository('/nonexistent/path') is False

    def test_init_base_repository(self, temp_repo):
        """Test _init_base_repository method."""
        # Create a non-git directory
        non_git_dir = tempfile.mkdtemp()
        try:
            runtime = WorktreeRuntime(
                config=MagicMock(),
                event_stream=MagicMock(),
                llm_registry=MagicMock(),
                base_repo_path=non_git_dir,
            )

            # Should initialize the repository
            runtime._init_base_repository()
            assert runtime._is_git_repository(non_git_dir) is True
        finally:
            shutil.rmtree(non_git_dir, ignore_errors=True)

    def test_create_worktree(self, temp_repo, mock_config, mock_event_stream, mock_llm_registry):
        """Test _create_worktree method."""
        runtime = WorktreeRuntime(
            config=mock_config,
            event_stream=mock_event_stream,
            llm_registry=mock_llm_registry,
            sid='test-create',
            base_repo_path=temp_repo,
        )

        worktree_path = runtime._create_worktree()

        assert worktree_path is not None
        assert os.path.exists(worktree_path)
        assert runtime.worktree_name in worktree_path

        # Verify it's a valid worktree
        result = subprocess.run(
            ['git', 'worktree', 'list'],
            cwd=temp_repo,
            capture_output=True,
            text=True,
        )
        assert worktree_path in result.stdout

        # Clean up
        runtime._remove_worktree()

    def test_remove_worktree(self, temp_repo, mock_config, mock_event_stream, mock_llm_registry):
        """Test _remove_worktree method."""
        runtime = WorktreeRuntime(
            config=mock_config,
            event_stream=mock_event_stream,
            llm_registry=mock_llm_registry,
            sid='test-remove',
            base_repo_path=temp_repo,
        )

        # Create a worktree
        worktree_path = runtime._create_worktree()
        assert os.path.exists(worktree_path)

        # Remove the worktree
        runtime._remove_worktree()
        assert not os.path.exists(worktree_path)

    def test_find_available_ports(self, mock_config, mock_event_stream, mock_llm_registry, temp_repo):
        """Test _find_available_ports method."""
        runtime = WorktreeRuntime(
            config=mock_config,
            event_stream=mock_event_stream,
            llm_registry=mock_llm_registry,
            base_repo_path=temp_repo,
        )

        execution_port, vscode_port, app_ports = runtime._find_available_ports()

        assert isinstance(execution_port, int)
        assert isinstance(vscode_port, int)
        assert isinstance(app_ports, list)
        assert len(app_ports) == 2
        assert all(isinstance(p, int) for p in app_ports)

    def test_get_worktree_base_dir(self, mock_config, mock_event_stream, mock_llm_registry, temp_repo):
        """Test _get_worktree_base_dir method."""
        runtime = WorktreeRuntime(
            config=mock_config,
            event_stream=mock_event_stream,
            llm_registry=mock_llm_registry,
            base_repo_path=temp_repo,
        )

        # Default case
        base_dir = runtime._get_worktree_base_dir()
        assert 'openhands-worktrees' in base_dir

        # With environment variable
        custom_dir = '/custom/worktree/dir'
        with patch.dict(os.environ, {'OPENHANDS_WORKTREE_BASE_DIR': custom_dir}):
            base_dir = runtime._get_worktree_base_dir()
            assert base_dir == custom_dir

    def test_vscode_url(self, mock_config, mock_event_stream, mock_llm_registry, temp_repo):
        """Test vscode_url property."""
        runtime = WorktreeRuntime(
            config=mock_config,
            event_stream=mock_event_stream,
            llm_registry=mock_llm_registry,
            sid='test-vscode',
            base_repo_path=temp_repo,
        )

        # Before server starts
        assert runtime.vscode_url is None

    def test_web_hosts(self, mock_config, mock_event_stream, mock_llm_registry, temp_repo):
        """Test web_hosts property."""
        runtime = WorktreeRuntime(
            config=mock_config,
            event_stream=mock_event_stream,
            llm_registry=mock_llm_registry,
            sid='test-web',
            base_repo_path=temp_repo,
        )

        # Before server starts
        assert runtime.web_hosts == {}

    def test_get_action_execution_server_startup_command(
        self, mock_config, mock_event_stream, mock_llm_registry, temp_repo
    ):
        """Test get_action_execution_server_startup_command method."""
        runtime = WorktreeRuntime(
            config=mock_config,
            event_stream=mock_event_stream,
            llm_registry=mock_llm_registry,
            sid='test-cmd',
            base_repo_path=temp_repo,
        )

        command = runtime.get_action_execution_server_startup_command()

        assert isinstance(command, list)
        assert len(command) > 0


class TestWorktreeRuntimeIntegration:
    """Integration tests for WorktreeRuntime."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, temp_repo, mock_config, mock_event_stream, mock_llm_registry):
        """Test the full lifecycle of a WorktreeRuntime."""
        # This test would require a full OpenHands setup
        # For now, we just verify the basic structure
        runtime = WorktreeRuntime(
            config=mock_config,
            event_stream=mock_event_stream,
            llm_registry=mock_llm_registry,
            sid='test-lifecycle',
            base_repo_path=temp_repo,
        )

        assert runtime is not None
        assert runtime.sid == 'test-lifecycle'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
