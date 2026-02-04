"""Worktree-based sandbox service for OpenHands V1.

import logging

This service creates sandboxes using WorktreeRuntime instead of the agent server,
providing git worktree isolation without requiring a separate agent server process.
This allows V1 conversations to work on Windows without fcntl dependency.
"""

import asyncio
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator

import httpx
from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from openhands.agent_server.utils import utc_now
from openhands.app_server.errors import SandboxError
from openhands.app_server.sandbox.sandbox_models import (
    AGENT_SERVER,
    ExposedUrl,
    SandboxInfo,
    SandboxPage,
    SandboxStatus,
)
from openhands.app_server.sandbox.sandbox_service import (
    SandboxService,
    SandboxServiceInjector,
)
from openhands.app_server.sandbox.sandbox_spec_models import SandboxSpecInfo
from openhands.app_server.sandbox.sandbox_spec_service import SandboxSpecService
from openhands.app_server.services.injector import InjectorState

_logger = logging.getLogger(__name__)


class WorktreeInfo(BaseModel):
    """Information about a running worktree sandbox."""

    pid: int
    port: int
    worktree_path: str
    user_id: str | None
    session_api_key: str
    created_at: datetime
    sandbox_spec_id: str

    model_config = ConfigDict(frozen=True)


# Global store
_worktrees: dict[str, WorktreeInfo] = {}


@dataclass
class WorktreeSandboxService(SandboxService):
    """Sandbox service that uses WorktreeRuntime for isolation.
    
    This is an alternative to ProcessSandboxService that doesn't require
    the agent server (which needs fcntl on Unix). It runs the action
    execution server directly in a git worktree.
    """

    user_id: str | None
    sandbox_spec_service: SandboxSpecService
    base_working_dir: str
    base_port: int
    python_executable: str
    httpx_client: httpx.AsyncClient

    def __post_init__(self):
        """Initialize the service after dataclass creation."""
        os.makedirs(self.base_working_dir, exist_ok=True)

    def _find_unused_port(self) -> int:
        """Find an unused port starting from base_port."""
        import socket
        
        port = self.base_port
        while port < self.base_port + 10000:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    return port
            except OSError:
                port += 1
        raise SandboxError('No available ports found')

    def _create_worktree_directory(self, sandbox_id: str) -> str:
        """Create a dedicated directory for the worktree."""
        worktree_dir = os.path.join(self.base_working_dir, sandbox_id)
        os.makedirs(worktree_dir, exist_ok=True)
        
        # Initialize git repo if not exists
        git_dir = os.path.join(worktree_dir, '.git')
        if not os.path.exists(git_dir):
            subprocess.run(
                ['git', 'init'],
                cwd=worktree_dir,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ['git', 'config', 'user.email', 'openhands@localhost'],
                cwd=worktree_dir,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ['git', 'config', 'user.name', 'OpenHands'],
                cwd=worktree_dir,
                capture_output=True,
                check=False,
            )
        
        return worktree_dir

    async def _start_worktree_process(
        self,
        sandbox_id: str,
        port: int,
        worktree_path: str,
        session_api_key: str,
        sandbox_spec: SandboxSpecInfo,
    ) -> subprocess.Popen:
        """Start the action execution server in the worktree."""
        
        # Prepare environment
        env = os.environ.copy()
        env.update(sandbox_spec.initial_env)
        env['SESSION_API_KEY'] = session_api_key
        env['RUNTIME'] = 'worktree'
        env['OPENHANDS_WORKTREE_PATH'] = worktree_path
        env['port'] = str(port)
        env['PYTHONUNBUFFERED'] = '1'

        # Start action execution server directly
        cmd = [
            self.python_executable,
            '-m',
            'openhands.runtime.action_execution_server',
            '--port',
            str(port),
        ]

        _logger.info(
            f'Starting worktree sandbox {sandbox_id} on port {port}: {" ".join(cmd)}'
        )

        try:
            process = subprocess.Popen(
                cmd,
                env=env,
                cwd=worktree_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            await asyncio.sleep(2)

            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise SandboxError(f'Worktree process failed: {stderr.decode()}')

            return process

        except Exception as e:
            raise SandboxError(f'Failed to start worktree process: {e}')

    async def _wait_for_server_ready(self, port: int, timeout: int = 30) -> bool:
        """Wait for the action execution server to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = await self.httpx_client.get(
                    f'http://localhost:{port}/alive',
                    timeout=2.0
                )
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    async def list_sandboxes(
        self, page_id: str | None = None
    ) -> SandboxPage:
        """List all sandboxes."""
        items = []
        for sandbox_id, info in _worktrees.items():
            items.append(
                SandboxInfo(
                    id=sandbox_id,
                    status=self._get_sandbox_status(info),
                    created_at=info.created_at,
                    user_id=info.user_id,
                    sandbox_spec_id=info.sandbox_spec_id,
                )
            )
        return SandboxPage(items=items, next_page_id=None)

    async def get_sandbox(self, sandbox_id: str) -> SandboxInfo | None:
        """Get a sandbox by ID."""
        info = _worktrees.get(sandbox_id)
        if info is None:
            return None
        return SandboxInfo(
            id=sandbox_id,
            status=self._get_sandbox_status(info),
            created_at=info.created_at,
            user_id=info.user_id,
            sandbox_spec_id=info.sandbox_spec_id,
        )

    def _get_sandbox_status(self, info: WorktreeInfo) -> SandboxStatus:
        """Get the status of a worktree."""
        try:
            import psutil
            process = psutil.Process(info.pid)
            if process.is_running():
                return SandboxStatus.RUNNING
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return SandboxStatus.STOPPED

    async def find_sandbox_by_session_api_key(
        self, session_api_key: str
    ) -> SandboxInfo | None:
        """Find a sandbox by session API key."""
        for sandbox_id, info in _worktrees.items():
            if info.session_api_key == session_api_key:
                return await self.get_sandbox(sandbox_id)
        return None

    async def start_sandbox(
        self,
        sandbox_id: str,
        sandbox_spec_id: str,
        session_api_key: str,
    ) -> SandboxInfo:
        """Start a new worktree sandbox."""
        # Get sandbox spec
        sandbox_spec = await self.sandbox_spec_service.get_sandbox_spec(
            sandbox_spec_id
        )
        if sandbox_spec is None:
            raise SandboxError(f'Sandbox spec not found: {sandbox_spec_id}')

        # Find port
        port = self._find_unused_port()

        # Create worktree directory
        worktree_path = self._create_worktree_directory(sandbox_id)

        # Start worktree process
        process = await self._start_worktree_process(
            sandbox_id=sandbox_id,
            port=port,
            worktree_path=worktree_path,
            session_api_key=session_api_key,
            sandbox_spec=sandbox_spec,
        )

        # Store info
        worktree_info = WorktreeInfo(
            pid=process.pid,
            port=port,
            worktree_path=worktree_path,
            user_id=self.user_id,
            session_api_key=session_api_key,
            created_at=utc_now(),
            sandbox_spec_id=sandbox_spec_id,
        )
        _worktrees[sandbox_id] = worktree_info

        # Wait for server
        if not await self._wait_for_server_ready(port):
            await self.delete_sandbox(sandbox_id)
            raise SandboxError('Worktree sandbox failed to start')

        return await self._worktree_to_sandbox_info(sandbox_id, worktree_info)

    async def _worktree_to_sandbox_info(
        self, sandbox_id: str, info: WorktreeInfo
    ) -> SandboxInfo:
        """Convert WorktreeInfo to SandboxInfo."""
        return SandboxInfo(
            id=sandbox_id,
            status=self._get_sandbox_status(info),
            created_at=info.created_at,
            user_id=info.user_id,
            sandbox_spec_id=info.sandbox_spec_id,
            exposed_urls=[
                ExposedUrl(
                    name=AGENT_SERVER,
                    url=f'http://localhost:{info.port}',
                    port=info.port,
                )
            ],
        )

    async def resume_sandbox(self, sandbox_id: str) -> bool:
        """Resume a paused sandbox."""
        # Worktree sandboxes don't support pause/resume
        return False

    async def pause_sandbox(self, sandbox_id: str) -> bool:
        """Pause a running sandbox."""
        # Worktree sandboxes don't support pause/resume
        return False

    async def delete_sandbox(self, sandbox_id: str) -> bool:
        """Delete a worktree sandbox."""
        info = _worktrees.get(sandbox_id)
        if info is None:
            return True

        try:
            # Kill process
            import psutil
            try:
                process = psutil.Process(info.pid)
                process.terminate()
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            except psutil.NoSuchProcess:
                pass

            # Clean up directory
            import shutil
            if os.path.exists(info.worktree_path):
                shutil.rmtree(info.worktree_path, ignore_errors=True)

            del _worktrees[sandbox_id]
            return True

        except Exception as e:
            _logger.warning(f'Error deleting worktree {sandbox_id}: {e}')
            if sandbox_id in _worktrees:
                del _worktrees[sandbox_id]
            return True

    async def get_sandbox_logs(
        self, sandbox_id: str
    ) -> AsyncGenerator[bytes, None]:
        """Get logs for a sandbox."""
        # TODO: Implement log streaming
        yield b'Logs not implemented for worktree sandbox'

    async def execute_command(
        self,
        sandbox_id: str,
        command: str,
        timeout: int | None = None,
    ) -> str:
        """Execute a command in a sandbox."""
        raise SandboxError('Command execution not supported for worktree sandboxes')

    async def read_file(
        self, sandbox_id: str, path: str
    ) -> bytes:
        """Read a file from a sandbox."""
        info = _worktrees.get(sandbox_id)
        if info is None:
            raise SandboxError(f'Sandbox not found: {sandbox_id}')
        
        file_path = os.path.join(info.worktree_path, path)
        with open(file_path, 'rb') as f:
            return f.read()

    async def write_file(
        self, sandbox_id: str, path: str, content: bytes
    ) -> None:
        """Write a file to a sandbox."""
        info = _worktrees.get(sandbox_id)
        if info is None:
            raise SandboxError(f'Sandbox not found: {sandbox_id}')
        
        file_path = os.path.join(info.worktree_path, path)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(content)


class WorktreeSandboxServiceInjector(SandboxServiceInjector):
    """Dependency injector for worktree sandbox services."""

    base_working_dir: str = Field(
        default='/tmp/openhands-worktrees',
        description='Base directory for worktree sandboxes',
    )
    base_port: int = Field(
        default=8000, description='Base port number for worktree sandboxes'
    )
    python_executable: str = Field(
        default='python',
        description='Python executable to use',
    )

    async def inject(
        self, state: InjectorState, request: Request | None = None
    ) -> AsyncGenerator[SandboxService, None]:
        from openhands.app_server.config import (
            get_httpx_client,
            get_sandbox_spec_service,
            get_user_context,
        )

        async with (
            get_httpx_client(state, request) as httpx_client,
            get_sandbox_spec_service(state, request) as sandbox_spec_service,
            get_user_context(state, request) as user_context,
        ):
            user_id = await user_context.get_user_id()
            yield WorktreeSandboxService(
                user_id=user_id,
                sandbox_spec_service=sandbox_spec_service,
                base_working_dir=self.base_working_dir,
                base_port=self.base_port,
                python_executable=self.python_executable,
                httpx_client=httpx_client,
            )
