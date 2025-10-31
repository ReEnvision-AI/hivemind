"""
Platform-specific utilities for cross-platform compatibility.

This module provides abstractions for handling differences between operating systems,
particularly between Unix-like systems (Linux, macOS) and Windows.
"""

import os
import sys
import socket
import asyncio
import multiprocessing as mp
from typing import Optional, Union, Tuple, Any
from enum import Enum


class Platform(Enum):
    """Supported platform types."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNIX = "unix"  # Generic Unix for other Unix-like systems


def get_platform() -> Platform:
    """
    Get the current platform.

    Returns:
        Platform: Current platform enum value
    """
    if sys.platform.startswith('win'):
        return Platform.WINDOWS
    elif sys.platform.startswith('darwin'):
        return Platform.MACOS
    elif sys.platform.startswith('linux'):
        return Platform.LINUX
    else:
        # Assume Unix for other platforms
        return Platform.UNIX


def is_windows() -> bool:
    """
    Check if running on Windows.

    Returns:
        bool: True if running on Windows
    """
    return get_platform() == Platform.WINDOWS


def is_unix() -> bool:
    """
    Check if running on a Unix-like system.

    Returns:
        bool: True if running on Unix-like system
    """
    return get_platform() != Platform.WINDOWS


def supports_unix_sockets() -> bool:
    """
    Check if the platform supports Unix domain sockets.

    Returns:
        bool: True if Unix domain sockets are supported
    """
    return not is_windows()


def supports_uvloop() -> bool:
    """
    Check if uvloop is supported on this platform.

    Returns:
        bool: True if uvloop is supported and recommended
    """
    return not is_windows()


def get_multiprocessing_context() -> mp.context.BaseContext:
    """
    Get the appropriate multiprocessing context for the platform.

    Returns:
        multiprocessing context with appropriate start method
    """
    if is_windows():
        # Windows only supports 'spawn' start method
        return mp.get_context('spawn')
    else:
        # Unix systems can use 'fork' which is more efficient
        return mp.get_context('fork')


def get_default_event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """
    Get the appropriate event loop policy for the platform.

    Returns:
        Event loop policy suitable for the current platform
    """
    if is_windows():
        # Windows uses ProactorEventLoop by default in Python 3.8+
        return asyncio.WindowsProactorEventLoopPolicy()
    else:
        # Unix systems can use the default policy
        return asyncio.DefaultEventLoopPolicy()


def get_socket_address_type(address: Union[str, Tuple[str, int]]) -> str:
    """
    Determine the socket address type based on platform and address format.

    Args:
        address: Socket address (string for Unix sockets, tuple for TCP)

    Returns:
        str: 'unix' for Unix domain sockets, 'tcp' for TCP sockets
    """
    if isinstance(address, tuple):
        return 'tcp'

    if isinstance(address, str):
        if address.startswith('/') or address.startswith('\\'):
            return 'unix'
        elif address.startswith('tcp://'):
            return 'tcp'

    # Default to TCP for Windows when ambiguous
    return 'tcp' if is_windows() else 'unix'


def normalize_socket_address(address: Union[str, Tuple[str, int]],
                           default_host: str = '127.0.0.1',
                           default_port: int = 0) -> Tuple[str, Union[str, Tuple[str, int]]]:
    """
    Normalize socket address to platform-appropriate format.

    Args:
        address: Input socket address
        default_host: Default host for TCP sockets on Windows
        default_port: Default port for TCP sockets

    Returns:
        Tuple of (address_type, normalized_address)
    """
    if isinstance(address, tuple):
        # Already a TCP address
        return 'tcp', address

    if isinstance(address, str):
        if address.startswith('/') or address.startswith('\\'):
            # Unix domain socket path
            if is_windows():
                # Convert to TCP on Windows
                return 'tcp', (default_host, default_port)
            else:
                return 'unix', address
        elif address.startswith('tcp://'):
            # TCP address string
            # Parse tcp://host:port
            tcp_part = address[6:]  # Remove 'tcp://' prefix
            if ':' in tcp_part:
                host, port_str = tcp_part.rsplit(':', 1)
                try:
                    port = int(port_str)
                    return 'tcp', (host, port)
                except ValueError:
                    # Invalid port, use default
                    return 'tcp', (tcp_part, default_port)
            else:
                # No port specified
                return 'tcp', (tcp_part, default_port)
        elif address.startswith('unix://'):
            # Explicit Unix socket
            if is_windows():
                # Convert to TCP on Windows
                return 'tcp', (default_host, default_port)
            else:
                # Remove 'unix://' prefix
                return 'unix', address[7:]

    # Default handling
    if is_windows():
        return 'tcp', (default_host, default_port)
    else:
        # Assume Unix socket path for non-Windows
        return 'unix', str(address)


def get_platform_specific_defaults() -> dict:
    """
    Get platform-specific default settings.

    Returns:
        Dictionary of platform-specific defaults
    """
    platform = get_platform()

    defaults = {
        'supports_unix_sockets': supports_unix_sockets(),
        'supports_uvloop': supports_uvloop(),
        'multiprocessing_start_method': 'spawn' if is_windows() else 'fork',
        'event_loop_type': 'proactor' if is_windows() else 'default',
        'socket_address_type': 'tcp' if is_windows() else 'unix',
        'file_path_separator': '\\' if is_windows() else '/',
        'line_ending': '\r\n' if is_windows() else '\n',
    }

    # Add platform-specific configurations
    if platform == Platform.WINDOWS:
        defaults.update({
            'default_socket_host': '127.0.0.1',
            'shared_memory_backend': 'file_mapping',  # Windows shared memory
            'process_priority_class': 'NORMAL_PRIORITY_CLASS',
        })
    else:
        defaults.update({
            'default_socket_host': 'localhost',
            'shared_memory_backend': 'mmap',  # POSIX shared memory
            'process_priority_class': None,
        })

    return defaults


def get_platform_info() -> dict:
    """
    Get comprehensive platform information for debugging and logging.

    Returns:
        Dictionary with platform details
    """
    return {
        'platform': get_platform().value,
        'system': os.name,
        'machine': os.uname().machine if hasattr(os, 'uname') else 'unknown',
        'python_version': sys.version,
        'is_windows': is_windows(),
        'is_unix': is_unix(),
        'supports_unix_sockets': supports_unix_sockets(),
        'supports_uvloop': supports_uvloop(),
        'multiprocessing_start_method': mp.get_start_method(allow_none=True),
        'default_event_loop': asyncio.get_event_loop().__class__.__name__,
    }


# Module-level constants for easy access
PLATFORM = get_platform()
IS_WINDOWS = is_windows()
IS_UNIX = is_unix()
SUPPORTS_UNIX_SOCKETS = supports_unix_sockets()
SUPPORTS_UVLOOP = supports_uvloop()
MP_CONTEXT = get_multiprocessing_context()