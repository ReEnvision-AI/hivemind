"""
Cross-platform process creation utilities.

This module provides platform-agnostic process base classes that work with both
fork (Unix) and spawn (Windows) process models.
"""

import multiprocessing as mp
from typing import Any, Optional

from hivemind.utils.platform import get_multiprocessing_context, IS_WINDOWS


class CrossPlatformProcess:
    """
    Cross-platform process base that works with both fork and spawn process models.

    On Unix systems, uses ForkProcess for optimal performance with shared memory inheritance.
    On Windows, uses regular Process with spawn model.
    """

    def __new__(cls, *args, **kwargs):
        """
        Create the appropriate process class based on the platform.
        """
        if IS_WINDOWS:
            # On Windows, use regular Process with spawn context
            mp_context = get_multiprocessing_context()
            return mp_context.Process(*args, **kwargs)
        else:
            # On Unix, use ForkProcess for optimal performance
            return mp.context.ForkProcess(*args, **kwargs)


def get_process_class():
    """
    Get the appropriate process class for the current platform.

    Returns:
        Process class suitable for the current platform
    """
    if IS_WINDOWS:
        return get_multiprocessing_context().Process
    else:
        return mp.context.ForkProcess


class CrossPlatformProcessMixin:
    """
    Mixin class that provides cross-platform process compatibility.

    Classes can inherit from this mixin along with their desired functionality
    to automatically gain cross-platform process support.
    """

    def __init_subclass__(cls, **kwargs):
        """
        Automatically set the appropriate base class when subclassing.
        """
        super().__init_subclass__(**kwargs)

        # Replace the base class with the appropriate process class
        if IS_WINDOWS:
            # On Windows, we need to use Process with spawn context
            mp_context = get_multiprocessing_context()

            # Find the current base classes
            bases = list(cls.__bases__)

            # Replace ForkProcess with the appropriate Process class
            for i, base in enumerate(bases):
                if base is mp.context.ForkProcess:
                    bases[i] = mp_context.Process
                    break

            # Update the bases
            cls.__bases__ = tuple(bases)


def create_process(target, args=(), kwargs=None, **process_kwargs):
    """
    Create a cross-platform process with the specified target and arguments.

    Args:
        target: Function to run in the subprocess
        args: Positional arguments for the target function
        kwargs: Keyword arguments for the target function
        **process_kwargs: Additional keyword arguments for Process constructor

    Returns:
        Process instance suitable for the current platform
    """
    if kwargs is None:
        kwargs = {}

    if IS_WINDOWS:
        # On Windows, use the spawn context
        mp_context = get_multiprocessing_context()
        return mp_context.Process(
            target=target,
            args=args,
            kwargs=kwargs,
            **process_kwargs
        )
    else:
        # On Unix, use ForkProcess for optimal performance
        return mp.context.ForkProcess(
            target=target,
            args=args,
            kwargs=kwargs,
            **process_kwargs
        )


def get_optimal_start_method():
    """
    Get the optimal process start method for the current platform.

    Returns:
        str: Best start method for the current platform ('fork' or 'spawn')
    """
    if IS_WINDOWS:
        return 'spawn'
    else:
        return 'fork'


def configure_multiprocessing():
    """
    Configure multiprocessing settings for optimal cross-platform performance.

    This function should be called early in the application startup to ensure
    proper multiprocessing behavior across platforms.
    """
    if IS_WINDOWS:
        # On Windows, ensure we're using spawn method
        mp.set_start_method('spawn', force=True)
    else:
        # On Unix, prefer fork for performance and shared memory inheritance
        try:
            mp.set_start_method('fork', force=True)
        except RuntimeError:
            # Method might already be set, which is fine
            pass


# Module-level configuration
configure_multiprocessing()