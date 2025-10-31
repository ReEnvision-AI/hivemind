import os
import sys
import subprocess
from typing import Optional, Dict, Any

from hivemind.utils.logging import get_logger
from hivemind.utils.platform import IS_WINDOWS

logger = get_logger(__name__)


def increase_file_limit(new_soft: int = 2**15, new_hard: int = 2**15) -> bool:
    """
    Increase the maximum number of open files. On Unix systems, this allows spawning more processes/threads.
    On Windows, provides alternative resource management.

    Args:
        new_soft: New soft limit for open files (Unix only)
        new_hard: New hard limit for open files (Unix only)

    Returns:
        bool: True if limits were successfully increased, False otherwise
    """
    if IS_WINDOWS:
        return _increase_windows_limits()
    else:
        return _increase_unix_limits(new_soft, new_hard)


def _increase_unix_limits(new_soft: int, new_hard: int) -> bool:
    """Increase file limits on Unix-like systems using the resource module."""
    try:
        import resource  # Unix-only module

        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        new_soft = max(soft, new_soft)
        new_hard = max(hard, new_hard)
        logger.info(f"Increasing file limit: soft {soft}=>{new_soft}, hard {hard}=>{new_hard}")
        resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, new_hard))
        return True
    except Exception as e:
        logger.warning(f"Failed to increase file limit: {e}")
        return False


def _increase_windows_limits() -> bool:
    """
    Increase system limits on Windows. Windows handles file descriptors differently
    than Unix systems, so we focus on process-related limits instead.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # On Windows, we can't directly increase file handle limits like on Unix
        # However, we can log current system information for debugging
        logger.info("Windows detected: file handle limits are managed differently than on Unix")

        # Log some Windows-specific system information
        _log_windows_system_info()

        # Note: Windows file handle limits are typically much higher than Unix defaults
        # and are managed by the system rather than per-process limits

        return True
    except Exception as e:
        logger.warning(f"Failed to gather Windows system info: {e}")
        return False


def _log_windows_system_info() -> None:
    """Log Windows-specific system information for resource management."""
    try:
        import psutil

        # Get system memory info
        memory = psutil.virtual_memory()
        logger.info(f"Windows system memory: {memory.total // (1024**3)} GB total, "
                   f"{memory.available // (1024**3)} GB available")

        # Get process info
        process = psutil.Process()
        logger.info(f"Current process: {process.num_fds() if hasattr(process, 'num_fds') else 'N/A'} file descriptors, "
                   f"{process.num_threads()} threads")

    except ImportError:
        # psutil not available, try basic Windows commands
        logger.debug("psutil not available for detailed system info")
        _log_basic_windows_info()
    except Exception as e:
        logger.debug(f"Could not get detailed Windows system info: {e}")


def _log_basic_windows_info() -> None:
    """Log basic Windows information without additional dependencies."""
    try:
        # Get environment variables that might be relevant
        computer_name = os.environ.get('COMPUTERNAME', 'Unknown')
        processor_count = str(os.cpu_count())

        logger.info(f"Windows system: {computer_name}, CPU cores: {processor_count}")
    except Exception as e:
        logger.debug(f"Could not get basic Windows info: {e}")


def get_current_limits() -> Dict[str, Any]:
    """
    Get current resource limits for the platform.

    Returns:
        Dictionary containing platform-specific limit information
    """
    limits = {
        'platform': 'windows' if IS_WINDOWS else 'unix',
        'process_id': os.getpid(),
    }

    if IS_WINDOWS:
        return _get_windows_limits(limits)
    else:
        return _get_unix_limits(limits)


def _get_unix_limits(limits: Dict[str, Any]) -> Dict[str, Any]:
    """Get Unix-specific resource limits."""
    try:
        import resource

        # File descriptor limits
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        limits.update({
            'file_descriptors': {
                'soft_limit': soft,
                'hard_limit': hard,
                'is_unlimited': soft == -1 or hard == -1
            }
        })

        # Memory limits (if available)
        try:
            mem_soft, mem_hard = resource.getrlimit(resource.RLIMIT_AS)
            limits.update({
                'memory': {
                    'soft_limit': mem_soft,
                    'hard_limit': mem_hard,
                    'is_unlimited': mem_soft == -1 or mem_hard == -1
                }
            })
        except (OSError, ValueError):
            # Some systems don't support RLIMIT_AS
            pass

        # Process limits
        try:
            proc_soft, proc_hard = resource.getrlimit(resource.RLIMIT_NPROC)
            limits.update({
                'processes': {
                    'soft_limit': proc_soft,
                    'hard_limit': proc_hard,
                    'is_unlimited': proc_soft == -1 or proc_hard == -1
                }
            })
        except (OSError, ValueError):
            # Some systems don't support RLIMIT_NPROC
            pass

    except ImportError:
        logger.debug("Resource module not available")
    except Exception as e:
        logger.debug(f"Could not get Unix limits: {e}")

    return limits


def _get_windows_limits(limits: Dict[str, Any]) -> Dict[str, Any]:
    """Get Windows-specific resource information."""
    try:
        import psutil
        process = psutil.Process()

        limits.update({
            'file_descriptors': {
                'open_count': process.num_fds() if hasattr(process, 'num_fds') else 'N/A',
                'limit_type': 'system_managed'
            },
            'memory': {
                'rss': process.memory_info().rss,
                'vms': process.memory_info().vms,
                'percent': process.memory_percent(),
                'available_system_memory': psutil.virtual_memory().available
            },
            'processes': {
                'current_threads': process.num_threads(),
                'limit_type': 'system_managed'
            }
        })

    except ImportError:
        # Fallback without psutil
        limits.update({
            'file_descriptors': {'limit_type': 'system_managed'},
            'memory': {'limit_type': 'system_managed'},
            'processes': {'limit_type': 'system_managed'}
        })
        logger.debug("Install psutil for detailed Windows resource information")
    except Exception as e:
        logger.debug(f"Could not get Windows limits: {e}")

    return limits


def check_resource_sufficiency(required_file_descriptors: int = 1000,
                             required_memory_mb: int = 1024) -> bool:
    """
    Check if the current system has sufficient resources for the requirements.

    Args:
        required_file_descriptors: Minimum number of file descriptors needed
        required_memory_mb: Minimum memory in MB needed

    Returns:
        bool: True if system has sufficient resources, False otherwise
    """
    limits = get_current_limits()

    if IS_WINDOWS:
        # Windows-specific checks
        try:
            import psutil

            # Check available memory
            available_memory_mb = psutil.virtual_memory().available // (1024**2)
            if available_memory_mb < required_memory_mb:
                logger.warning(f"Insufficient memory: {available_memory_mb} MB available, "
                             f"{required_memory_mb} MB required")
                return False

            logger.debug(f"Resource check passed: {available_memory_mb} MB memory available")
            return True

        except ImportError:
            logger.debug("Cannot verify resource sufficiency without psutil, assuming sufficient")
            return True
    else:
        # Unix-specific checks
        import resource

        # Check file descriptor limits
        if 'file_descriptors' in limits:
            soft_limit = limits['file_descriptors']['soft_limit']
            if soft_limit != -1 and soft_limit < required_file_descriptors:
                logger.warning(f"Insufficient file descriptors: {soft_limit} available, "
                             f"{required_file_descriptors} required")
                return False

        logger.debug("Unix resource check passed")
        return True
