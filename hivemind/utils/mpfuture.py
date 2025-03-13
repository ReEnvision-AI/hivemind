import multiprocessing as mp
import os
import threading
import uuid
from concurrent.futures import Future, InvalidStateError, CancelledError
from contextlib import nullcontext
from enum import Enum, auto
from multiprocessing import shared_memory
from typing import Any, Callable, Generic, Optional, TypeVar
from weakref import ref
import asyncio

# Type variable for generic result type
ResultType = TypeVar("ResultType")

# Define all possible states for the Future
ALL_STATES = ('PENDING', 'RUNNING', 'FINISHED', 'CANCELLED', 'CANCELLED_AND_NOTIFIED')
TERMINAL_STATES = {'FINISHED', 'CANCELLED', 'CANCELLED_AND_NOTIFIED'}

# Enum for update types sent between processes
class UpdateType(Enum):
    RESULT = auto()
    EXCEPTION = auto()
    CANCEL = auto()

class MPFuture(Future, Generic[ResultType]):
    """
    A Future implementation that supports cross-process result and exception handling
    using a shared memory pool for state management and a managed queue dictionary for updates.
    """

    # Class-level attributes for managing shared resources
    _manager = None  # Multiprocessing Manager instance
    _queue_dict = None  # Shared dictionary mapping PIDs to queues
    _shared_memory_pool = None  # Shared memory segment for all futures' states
    _next_offset = None  # Managed integer for next available offset
    _offset_lock = None  # Managed lock for offset allocation
    _initialization_lock = mp.Lock()  # Lock for initializing backend
    _update_lock = mp.Lock()  # Lock for sending updates
    _active_futures = None  # Dictionary of active futures in the origin process
    _active_pid = None  # PID of the current process for active futures
    _pipe_waiter_thread = None  # Background thread for processing updates

    def __init__(self, *, use_lock: bool = True):
        """
        Initialize an MPFuture instance.

        Args:
            use_lock (bool): Whether to use a lock when sending updates (default: True).
        """
        # Ensure the backend is initialized
        self._maybe_initialize_mpfuture_backend()

        # Store the PID of the process that created this future
        self._origin_pid = os.getpid()

        # Generate a unique identifier for this future
        self._uid = uuid.uuid4().int

        # Allocate an offset from the shared memory pool
        with MPFuture._offset_lock:
            offset = MPFuture._next_offset.value
            MPFuture._next_offset.value += 1
            if offset >= MPFuture._shared_memory_pool.size:
                raise RuntimeError("Shared memory pool exhausted")
        self._offset = offset
        self._shared_state_code = MPFuture._shared_memory_pool

        # Initialize the state to PENDING in the shared memory
        self._shared_state_code.buf[self._offset] = ALL_STATES.index('PENDING')

        # Cache for state strings to avoid repeated creation
        self._state_cache = {}

        # Initialize the base Future class
        super().__init__()

        # Whether to use a lock for updates
        self._use_lock = use_lock

        # Register this future in the active futures dictionary
        MPFuture._active_futures[self._uid] = ref(self)

        # Set up asyncio event for async support, if an event loop is available
        try:
            self._loop = asyncio.get_event_loop()
            self._aio_event = asyncio.Event()
        except RuntimeError:
            self._loop, self._aio_event = None, None

    @property
    def _state(self) -> str:
        """Get the current state of the future from the shared memory pool."""
        state_index = self._shared_state_code.buf[self._offset]
        shared_state = ALL_STATES[state_index]
        return self._state_cache.get(shared_state, shared_state)

    @_state.setter
    def _state(self, new_state: str):
        """Set the state of the future in the shared memory pool."""
        state_index = ALL_STATES.index(new_state)
        self._shared_state_code.buf[self._offset] = state_index
        # If the state is terminal and there's an event loop, set the asyncio event
        if new_state in TERMINAL_STATES and self._loop is not None and not self._aio_event.is_set():
            self._set_event_threadsafe()

    def _set_event_threadsafe(self):
        """Set the asyncio event in a thread-safe manner."""
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._aio_event.set)
        else:
            self._aio_event.set()

    @classmethod
    def _maybe_initialize_mpfuture_backend(cls):
        """
        Initialize the multiprocessing backend for the current process if not already done.
        This includes setting up the shared memory pool and manager.
        """
        pid = os.getpid()
        if cls._queue_dict is None or pid not in cls._queue_dict:
            with cls._initialization_lock:
                if cls._manager is None:
                    # Initialize the manager and shared resources
                    cls._manager = mp.Manager()
                    cls._queue_dict = cls._manager.dict()
                    cls._shared_memory_pool = shared_memory.SharedMemory(create=True, size=1000000)  # 1MB for 1M futures
                    cls._next_offset = cls._manager.Value('i', 0)
                    cls._offset_lock = cls._manager.Lock()
                if pid not in cls._queue_dict:
                    # Set up the queue and background thread for this process
                    cls._queue_dict[pid] = cls._manager.Queue()
                    cls._active_pid = pid
                    cls._active_futures = {}
                    cls._pipe_waiter_thread = threading.Thread(
                        target=cls._process_updates_in_background,
                        args=[cls._queue_dict[pid]],
                        name=f"{__name__}.BACKEND",
                        daemon=True,
                    )
                    cls._pipe_waiter_thread.start()

    @classmethod
    def _process_updates_in_background(cls, update_queue):
        """Background thread to process updates from the queue."""
        while True:
            try:
                uid, update_type, payload = update_queue.get()
                future_ref = cls._active_futures.get(uid)
                if future_ref is not None:
                    future = future_ref()
                    if future is not None:
                        if update_type == UpdateType.RESULT:
                            future.set_result(payload)
                        elif update_type == UpdateType.EXCEPTION:
                            future.set_exception(payload)
                        elif update_type == UpdateType.CANCEL:
                            future.cancel()
            except (BrokenPipeError, EOFError):
                print("Queue closed, exiting background thread.")
                break
            except Exception as e:
                print(f"Error in background thread: {e}")

    def _send_update(self, update_type: UpdateType, payload: Any = None):
        """Send an update to the origin process's queue."""
        try:
            with MPFuture._update_lock if self._use_lock else nullcontext():
                update_queue = MPFuture._queue_dict[self._origin_pid]
                update_queue.put((self._uid, update_type, payload))
        except Exception as e:
            print(f"Error sending update: {e}")

    def set_result(self, result: ResultType):
        """Set the result of the future and notify the origin process if necessary."""
        if os.getpid() == self._origin_pid:
            super().set_result(result)
            MPFuture._active_futures.pop(self._uid, None)
        elif self._state in TERMINAL_STATES:
            raise InvalidStateError(f"Can't set_result on {self._state} future ({self._uid})")
        else:
            self._state_cache[self._state] = 'FINISHED'
            self._send_update(UpdateType.RESULT, result)

    def set_exception(self, exception: Optional[BaseException]):
        """Set an exception for the future and notify the origin process if necessary."""
        if os.getpid() == self._origin_pid:
            super().set_exception(exception)
            MPFuture._active_futures.pop(self._uid, None)
        elif self._state in TERMINAL_STATES:
            raise InvalidStateError(f"Can't set_exception on {self._state} future ({self._uid})")
        else:
            self._state_cache[self._state] = 'FINISHED'
            self._send_update(UpdateType.EXCEPTION, exception)

    def cancel(self) -> bool:
        """Cancel the future if possible and notify the origin process if necessary."""
        if os.getpid() == self._origin_pid:
            MPFuture._active_futures.pop(self._uid, None)
            return super().cancel()
        elif self._state in ['RUNNING', 'FINISHED']:
            return False
        else:
            self._state_cache[self._state] = 'CANCELLED'
            self._send_update(UpdateType.CANCEL)
            return True

    def set_running_or_notify_cancel(self) -> bool:
        """Set the future to RUNNING or notify cancellation."""
        if self._state == 'PENDING':
            self._state = 'RUNNING'
            return True
        elif self._state == 'CANCELLED':
            return False
        else:
            raise InvalidStateError(f"Can't set running on {self._state} future ({self._uid})")

    def result(self, timeout: Optional[float] = None) -> ResultType:
        """Retrieve the result of the future."""
        if self._state not in TERMINAL_STATES:
            if os.getpid() != self._origin_pid:
                raise RuntimeError("Only origin process can await result")
            return super().result(timeout)
        elif self._state == 'CANCELLED':
            #raise asyncio.CancelledError()
            raise CancelledError()
        elif self._exception:
            raise self._exception
        else:
            return self._result

    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        """Retrieve the exception of the future, if any."""
        if self._state not in TERMINAL_STATES:
            if os.getpid() != self._origin_pid:
                raise RuntimeError("Only origin process can await exception")
            return super().exception(timeout)
        elif self._state == 'CANCELLED':
            #raise asyncio.CancelledError()
            raise CancelledError()
        return self._exception

    def done(self) -> bool:
        """Check if the future is done."""
        return self._state in TERMINAL_STATES

    def running(self) -> bool:
        """Check if the future is running."""
        return self._state == 'RUNNING'

    def cancelled(self) -> bool:
        """Check if the future is cancelled."""
        return self._state == 'CANCELLED'

    def add_done_callback(self, callback: Callable[["MPFuture"], None]):
        """Add a callback to be called when the future is done."""
        if os.getpid() != self._origin_pid:
            raise RuntimeError("Only origin process can set callbacks")
        return super().add_done_callback(callback)

    def close(self):
        """Deprecated method; shared memory is now managed at the class level."""
        pass

    def __await__(self):
        """Support for async/await syntax."""
        if not self._aio_event:
            raise RuntimeError("Can't await: no event loop")
        yield from self._aio_event.wait().__await__()
        try:
            return super().result()
        except asyncio.CancelledError:
            #raise asyncio.CancelledError()
            raise CancelledError()

    def __del__(self):
        """Clean up resources when the future is deleted."""
        if getattr(self, "_origin_pid", None) == os.getpid() and MPFuture._active_futures is not None:
            MPFuture._active_futures.pop(self._uid, None)
        if getattr(self, "_aio_event", None):
            self._aio_event.set()

    def __getstate__(self):
        """Prepare the state for pickling."""
        state = self.__dict__.copy()
        state.pop('_condition', None)
        state.pop('_waiters', None)
        state.pop('_done_callbacks', None)
        state.pop('_aio_event', None)
        state.pop('_loop', None)
        return state

    def __setstate__(self, state):
        """Restore the state after unpickling."""
        self.__dict__.update(state)
        self._condition = threading.Condition()
        self._waiters = []
        self._done_callbacks = []
        try:
            self._loop = asyncio.get_event_loop()
            self._aio_event = asyncio.Event()
        except RuntimeError:
            self._loop, self._aio_event = None, None