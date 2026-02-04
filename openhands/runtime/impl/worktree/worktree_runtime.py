"""Worktree-based runtime for OpenHands using git worktrees for isolation.

This runtime provides Docker-like isolation without container overhead by using
git worktrees to create isolated working directories for each agent session.
Each worktree shares the same git history but has its own working directory,
enabling parallel agent execution on a single VPS.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import httpx
import tenacity

from openhands.core.config import OpenHandsConfig
from openhands.core.exceptions import (
    AgentRuntimeDisconnectedError,
    AgentRuntimeError,
)
from openhands.core.logger import openhands_logger as logger
from openhands.events import EventStream
from openhands.events.action import Action
from openhands.events.observation import Observation
from openhands.events.serialization import event_to_dict, observation_from_dict
from openhands.integrations.provider import PROVIDER_TOKEN_TYPE
from openhands.llm.llm_registry import LLMRegistry
from openhands.runtime.impl.action_execution.action_execution_client import (
    ActionExecutionClient,
)
from openhands.runtime.plugins import PluginRequirement
from openhands.runtime.plugins.vscode import VSCodeRequirement
from openhands.runtime.runtime_status import RuntimeStatus
from openhands.runtime.utils import find_available_tcp_port
from openhands.runtime.utils.command import (
    DEFAULT_MAIN_MODULE,
    get_action_execution_server_startup_command,
)
from openhands.utils.async_utils import call_sync_from_async
from openhands.utils.http_session import httpx_verify_option
from openhands.utils.tenacity_stop import stop_if_should_exit

DISABLE_VSCODE_PLUGIN = os.getenv('DISABLE_VSCODE_PLUGIN', 'false').lower() == 'true'

# Port ranges for the worktree runtime
EXECUTION_SERVER_PORT_RANGE = (30000, 39999)
VSCODE_PORT_RANGE = (40000, 49999)
APP_PORT_RANGE_1 = (50000, 54999)
APP_PORT_RANGE_2 = (55000, 59999)

WORKTREE_NAME_PREFIX = 'openhands-worktree-'
WORKTREE_BASE_DIR_ENV = 'OPENHANDS_WORKTREE_BASE_DIR'


@dataclass
class ActionExecutionServerInfo:
    """Information about a running server process in a worktree."""

    process: subprocess.Popen
    execution_server_port: int
    vscode_port: int
    app_ports: list[int]
    log_thread: threading.Thread
    log_thread_exit_event: threading.Event
    worktree_path: str
    worktree_name: str


class WorktreeRuntime(ActionExecutionClient):
    """Runtime that uses git worktrees for isolation instead of Docker containers.

    This runtime creates isolated working environments using git worktrees,
    allowing multiple agents to work in parallel on the same repository without
    Docker container overhead. Each worktree shares the same git history but
    has its own working directory.

    Args:
        config: The OpenHands configuration.
        event_stream: The event stream to subscribe to.
        sid: The session ID. Defaults to 'default'.
        plugins: List of plugin requirements. Defaults to None.
        env_vars: Environment variables to set. Defaults to None.
        status_callback: Callback for status updates. Defaults to None.
        attach_to_existing: Whether to attach to an existing runtime. Defaults to False.
        headless_mode: Whether to run in headless mode. Defaults to True.
        user_id: The user ID. Defaults to None.
        git_provider_tokens: Git provider tokens. Defaults to None.
        main_module: The main module to run. Defaults to DEFAULT_MAIN_MODULE.
        base_repo_path: The base repository path. Defaults to current working directory.
    """

    def __init__(
        self,
        config: OpenHandsConfig,
        event_stream: EventStream,
        llm_registry: LLMRegistry,
        sid: str = 'default',
        plugins: list[PluginRequirement] | None = None,
        env_vars: dict[str, str] | None = None,
        status_callback: Callable | None = None,
        attach_to_existing: bool = False,
        headless_mode: bool = True,
        user_id: str | None = None,
        git_provider_tokens: PROVIDER_TOKEN_TYPE | None = None,
        main_module: str = DEFAULT_MAIN_MODULE,
        base_repo_path: str | None = None,
    ):
        self.config = config
        self.status_callback = status_callback
        self.sid = sid
        self.worktree_name = WORKTREE_NAME_PREFIX + sid
        self.base_repo_path = base_repo_path or os.getcwd()
        self.worktree_path: str | None = None
        self.main_module = main_module

        # Server info
        self._server_info: ActionExecutionServerInfo | None = None
        self._vscode_port = -1
        self._app_ports: list[int] = []

        # Ensure VSCode plugin is included if not disabled
        if plugins is None:
            plugins = []
        if not DISABLE_VSCODE_PLUGIN and not any(
            isinstance(p, VSCodeRequirement) for p in plugins
        ):
            plugins = plugins + [VSCodeRequirement()]

        super().__init__(
            config,
            event_stream,
            llm_registry,
            sid,
            plugins,
            env_vars,
            status_callback,
            attach_to_existing,
            headless_mode,
            user_id,
            git_provider_tokens,
        )

    @property
    def action_execution_server_url(self) -> str:
        """Get the URL of the action execution server."""
        if self._server_info is None:
            raise RuntimeError('Server not started')
        return f'http://localhost:{self._server_info.execution_server_port}'

    def _get_worktree_base_dir(self) -> str:
        """Get the base directory for worktrees."""
        base_dir = os.environ.get(WORKTREE_BASE_DIR_ENV)
        if base_dir:
            return base_dir
        # Default to a subdirectory in the system temp directory
        return os.path.join(tempfile.gettempdir(), 'openhands-worktrees')

    def _is_git_repository(self, path: str) -> bool:
        """Check if the given path is a git repository."""
        try:
            result = subprocess.run(
                ['git', '-C', path, 'rev-parse', '--git-dir'],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _init_base_repository(self) -> None:
        """Initialize the base repository if it's not a git repository."""
        if not self._is_git_repository(self.base_repo_path):
            logger.info(
                f'Base path {self.base_repo_path} is not a git repository. Initializing...'
            )
            try:
                subprocess.run(
                    ['git', 'init'],
                    cwd=self.base_repo_path,
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    ['git', 'config', 'user.email', 'openhands@localhost'],
                    cwd=self.base_repo_path,
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    ['git', 'config', 'user.name', 'OpenHands'],
                    cwd=self.base_repo_path,
                    capture_output=True,
                    check=True,
                )
                # Create an initial commit if there are files
                subprocess.run(
                    ['git', 'add', '-A'],
                    cwd=self.base_repo_path,
                    capture_output=True,
                    check=False,
                )
                subprocess.run(
                    ['git', 'commit', '-m', 'Initial commit', '--allow-empty'],
                    cwd=self.base_repo_path,
                    capture_output=True,
                    check=False,
                )
            except subprocess.CalledProcessError as e:
                raise AgentRuntimeError(
                    f'Failed to initialize git repository: {e.stderr}'
                ) from e

    def _create_worktree(self) -> str:
        """Create a git worktree for this runtime instance.

        Returns:
            The path to the created worktree.
        """
        self._init_base_repository()

        worktree_base = self._get_worktree_base_dir()
        os.makedirs(worktree_base, exist_ok=True)

        worktree_path = os.path.join(worktree_base, self.worktree_name)

        # Remove existing worktree if it exists
        if os.path.exists(worktree_path):
            logger.warning(
                f'Worktree {worktree_path} already exists. Removing...'
            )
            self._remove_worktree()

        try:
            # Create the worktree
            subprocess.run(
                ['git', 'worktree', 'add', '--detach', worktree_path],
                cwd=self.base_repo_path,
                capture_output=True,
                check=True,
            )
            logger.info(f'Created worktree at {worktree_path}')

            # Configure the worktree
            subprocess.run(
                ['git', 'config', 'user.email', 'openhands@localhost'],
                cwd=worktree_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ['git', 'config', 'user.name', 'OpenHands'],
                cwd=worktree_path,
                capture_output=True,
                check=True,
            )

            return worktree_path

        except subprocess.CalledProcessError as e:
            raise AgentRuntimeError(
                f'Failed to create worktree: {e.stderr}'
            ) from e

    def _remove_worktree(self) -> None:
        """Remove the git worktree for this runtime instance."""
        if not self.worktree_path or not os.path.exists(self.worktree_path):
            return

        try:
            # Remove the worktree using git worktree remove
            subprocess.run(
                ['git', 'worktree', 'remove', '--force', self.worktree_path],
                cwd=self.base_repo_path,
                capture_output=True,
                check=False,
            )

            # Clean up any remaining directory
            if os.path.exists(self.worktree_path):
                shutil.rmtree(self.worktree_path, ignore_errors=True)

            logger.info(f'Removed worktree at {self.worktree_path}')

        except Exception as e:
            logger.warning(f'Error removing worktree: {e}')

    def _find_available_ports(self) -> tuple[int, int, list[int]]:
        """Find available ports for the server.

        Returns:
            Tuple of (execution_server_port, vscode_port, app_ports).
        """
        execution_port = find_available_tcp_port(
            EXECUTION_SERVER_PORT_RANGE[0],
            EXECUTION_SERVER_PORT_RANGE[1],
        )

        if self.config.sandbox.vscode_port:
            vscode_port = self.config.sandbox.vscode_port
        else:
            vscode_port = find_available_tcp_port(
                VSCODE_PORT_RANGE[0],
                VSCODE_PORT_RANGE[1],
            )

        app_port_1 = find_available_tcp_port(
            APP_PORT_RANGE_1[0],
            APP_PORT_RANGE_1[1],
        )
        app_port_2 = find_available_tcp_port(
            APP_PORT_RANGE_2[0],
            APP_PORT_RANGE_2[1],
        )

        return execution_port, vscode_port, [app_port_1, app_port_2]

    def _start_server(self) -> ActionExecutionServerInfo:
        """Start the action execution server in the worktree.

        Returns:
            Information about the started server.
        """
        if not self.worktree_path:
            raise RuntimeError('Worktree not created')

        execution_port, vscode_port, app_ports = self._find_available_ports()

        # Prepare environment variables
        env = os.environ.copy()
        env.update(self.initial_env_vars)
        env.update({
            'port': str(execution_port),
            'PYTHONUNBUFFERED': '1',
            'VSCODE_PORT': str(vscode_port),
            'APP_PORT_1': str(app_ports[0]),
            'APP_PORT_2': str(app_ports[1]),
            'OPENHANDS_SESSION_ID': str(self.sid),
            'PIP_BREAK_SYSTEM_PACKAGES': '1',
            'OPENHANDS_WORKTREE_PATH': self.worktree_path,
        })

        if self.config.debug:
            env['DEBUG'] = 'true'

        # Add runtime startup env vars
        env.update(self.config.sandbox.runtime_startup_env_vars)

        # Get the startup command
        command = self.get_action_execution_server_startup_command()

        logger.info(f'Starting server in worktree with command: {command}')
        logger.debug(f'Worktree path: {self.worktree_path}')

        # Start the server process
        try:
            process = subprocess.Popen(
                command,
                cwd=self.worktree_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            raise AgentRuntimeError(f'Failed to start server process: {e}') from e

        # Create log thread
        log_exit_event = threading.Event()
        log_thread = threading.Thread(
            target=self._stream_logs,
            args=(process, log_exit_event),
            daemon=True,
        )
        log_thread.start()

        return ActionExecutionServerInfo(
            process=process,
            execution_server_port=execution_port,
            vscode_port=vscode_port,
            app_ports=app_ports,
            log_thread=log_thread,
            log_thread_exit_event=log_exit_event,
            worktree_path=self.worktree_path,
            worktree_name=self.worktree_name,
        )

    def _stream_logs(
        self,
        process: subprocess.Popen,
        exit_event: threading.Event,
    ) -> None:
        """Stream logs from the server process."""
        if process.stdout is None or process.stderr is None:
            return

        def read_stream(stream, prefix: str):
            try:
                for line in iter(stream.readline, ''):
                    if exit_event.is_set():
                        break
                    if line:
                        logger.debug(f'[{prefix}] {line.rstrip()}')
            except Exception as e:
                logger.debug(f'Log stream error: {e}')
            finally:
                stream.close()

        stdout_thread = threading.Thread(
            target=read_stream,
            args=(process.stdout, 'SERVER'),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=read_stream,
            args=(process.stderr, 'SERVER-ERR'),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        # Wait for exit event
        exit_event.wait()

    def _stop_server(self) -> None:
        """Stop the action execution server."""
        if self._server_info is None:
            return

        # Signal log thread to exit
        self._server_info.log_thread_exit_event.set()

        # Terminate the process
        process = self._server_info.process
        if process.poll() is None:
            try:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning('Server process did not terminate, killing...')
                    process.kill()
                    process.wait()
            except Exception as e:
                logger.warning(f'Error stopping server: {e}')

        # Wait for log thread
        self._server_info.log_thread.join(timeout=2)

        logger.info('Server stopped')
        self._server_info = None

    async def connect(self) -> None:
        """Connect to the runtime by creating the worktree and starting the server."""
        self.set_runtime_status(RuntimeStatus.STARTING_RUNTIME)

        try:
            # Create the worktree
            self.worktree_path = self._create_worktree()
            logger.info(f'Worktree created at: {self.worktree_path}')

            # Start the server
            self.set_runtime_status(RuntimeStatus.STARTING_RUNTIME)
            self._server_info = self._start_server()

            logger.info(
                f'Server started on port {self._server_info.execution_server_port}'
            )

            # Wait for the server to be ready
            if not self.attach_to_existing:
                self.log(
                    'info',
                    f'Waiting for client to become ready at {self.action_execution_server_url}...',
                )
                self.set_runtime_status(RuntimeStatus.STARTING_RUNTIME)
                await call_sync_from_async(self.wait_until_alive)
                self.log('info', 'Runtime is ready.')

            # Setup initial environment
            if not self.attach_to_existing:
                await call_sync_from_async(self.setup_initial_env)

            self.log(
                'debug',
                f'Worktree initialized with plugins: {[plugin.name for plugin in self.plugins]}. VSCode URL: {self.vscode_url}',
            )

            if not self.attach_to_existing:
                self.set_runtime_status(RuntimeStatus.READY)

            self._runtime_initialized = True

        except Exception as e:
            # Cleanup on failure
            self._stop_server()
            self._remove_worktree()
            raise

    @tenacity.retry(
        stop=tenacity.stop_after_delay(120) | stop_if_should_exit(),
        retry=tenacity.retry_if_exception_type(
            (ConnectionError, httpx.ConnectError, httpx.ConnectTimeout)
        ),
        reraise=True,
        wait=tenacity.wait_fixed(2),
    )
    def wait_until_alive(self) -> None:
        """Wait until the server is alive and responding."""
        if self._server_info is None:
            raise AgentRuntimeDisconnectedError('Server not started')

        # Check if process is still running
        if self._server_info.process.poll() is not None:
            raise AgentRuntimeDisconnectedError(
                f'Server process exited with code {self._server_info.process.returncode}'
            )

        self.check_if_alive()

    def close(self) -> None:
        """Close the runtime and cleanup resources."""
        super().close()

        if self.config.sandbox.keep_runtime_alive or self.attach_to_existing:
            return

        self._stop_server()
        self._remove_worktree()

    def pause(self) -> None:
        """Pause the runtime by stopping the server process."""
        if self._server_info is None:
            raise RuntimeError('Server not started')

        self._stop_server()
        logger.debug(f'Worktree {self.worktree_name} paused')

    def resume(self) -> None:
        """Resume the runtime by restarting the server process."""
        if self.worktree_path is None:
            raise RuntimeError('Worktree not created')

        self._server_info = self._start_server()
        logger.debug(f'Worktree {self.worktree_name} resumed')

        # Wait for the server to be ready
        self.wait_until_alive()

    @classmethod
    async def delete(cls, conversation_id: str) -> None:
        """Delete a worktree runtime by conversation ID.

        Args:
            conversation_id: The conversation ID (sid) of the runtime to delete.
        """
        worktree_name = WORKTREE_NAME_PREFIX + conversation_id
        worktree_base = os.environ.get(
            WORKTREE_BASE_DIR_ENV,
            os.path.join(tempfile.gettempdir(), 'openhands-worktrees'),
        )
        worktree_path = os.path.join(worktree_base, worktree_name)

        if os.path.exists(worktree_path):
            try:
                # Try to remove using git worktree remove
                # Find the base repository
                result = subprocess.run(
                    ['git', 'worktree', 'list', '--porcelain'],
                    capture_output=True,
                    text=True,
                )
                for line in result.stdout.split('\n'):
                    if line.startswith('worktree '):
                        wt_path = line.split(' ', 1)[1]
                        if os.path.basename(wt_path) == worktree_name:
                            subprocess.run(
                                ['git', 'worktree', 'remove', '--force', wt_path],
                                capture_output=True,
                                check=False,
                            )
                            break

                # Clean up any remaining directory
                if os.path.exists(worktree_path):
                    shutil.rmtree(worktree_path, ignore_errors=True)

                logger.info(f'Deleted worktree: {worktree_path}')

            except Exception as e:
                logger.warning(f'Error deleting worktree: {e}')

    @property
    def vscode_url(self) -> str | None:
        """Get the VSCode URL for this runtime."""
        if self._server_info is None:
            return None

        token = super().get_vscode_token()
        if not token:
            return None

        return f'http://localhost:{self._server_info.vscode_port}/?tkn={token}&folder={self.worktree_path}'

    @property
    def web_hosts(self) -> dict[str, int]:
        """Get the web hosts for this runtime."""
        hosts: dict[str, int] = {}

        if self._server_info:
            for port in self._server_info.app_ports:
                hosts[f'http://localhost:{port}'] = port

        return hosts

    def get_action_execution_server_startup_command(self) -> list[str]:
        """Get the command to start the action execution server."""
        if self._server_info is None:
            # Use default port if server not started yet
            return get_action_execution_server_startup_command(
                server_port=0,  # Will be set via env var
                plugins=self.plugins,
                app_config=self.config,
                main_module=self.main_module,
            )
        return get_action_execution_server_startup_command(
            server_port=self._server_info.execution_server_port,
            plugins=self.plugins,
            app_config=self.config,
            main_module=self.main_module,
        )

    def run_action(self, action: Action) -> Observation:
        """Run an action in the worktree runtime.

        Args:
            action: The action to run.

        Returns:
            The observation result.
        """
        # Ensure we're in the correct worktree context
        if self.worktree_path:
            action.worktree_path = self.worktree_path  # type: ignore
        return super().run_action(action)
