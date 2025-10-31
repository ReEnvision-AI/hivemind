# Windows Performance Optimization Guide

This guide provides performance optimization recommendations for running Hivemind on Windows systems.

## Overview

Windows performance characteristics differ from Unix systems due to architectural differences in process management, memory handling, and I/O operations. This guide helps you optimize Hivemind performance on Windows.

## Process Management Optimization

### Understanding Windows vs Unix Process Models

**Unix (fork):**
- Fast process creation (copy-on-write memory)
- Shared memory inheritance
- Lower overhead

**Windows (spawn):**
- Slower process creation (fresh interpreter)
- No memory inheritance
- Higher startup overhead

### Optimization Strategies

#### 1. Process Reuse

```python
from hivemind.utils.processing import create_process
import multiprocessing as mp

# ❌ Bad: Creating processes frequently
def bad_example():
    for task in tasks:
        proc = create_process(target=process_task, args=(task,))
        proc.start()
        proc.join()  # Expensive on Windows

# ✅ Good: Reuse processes
def good_example():
    # Create persistent worker processes
    with mp.Pool(processes=mp.cpu_count()) as pool:
        results = pool.map(process_task, tasks)
```

#### 2. Batching Operations

```python
import asyncio
from hivemind.utils.mpfuture import MPFuture

# ❌ Bad: Individual future for each operation
async def bad_example(items):
    futures = []
    for item in items:
        future = MPFuture()
        # Process individually
        futures.append(future)
    return [f.result() for f in futures]

# ✅ Good: Batch operations
async def good_example(items):
    batch_size = min(len(items), 16)  # Optimal batch size for Windows
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        # Process batch together
        batch_result = await process_batch(batch)
        results.extend(batch_result)
    return results
```

#### 3. Optimize Process Pool Size

```python
import multiprocessing as mp
from hivemind.utils.platform import get_platform_info

def get_optimal_process_count():
    """Calculate optimal process count for Windows"""
    platform_info = get_platform_info()

    # Conservative process count for Windows (less memory overhead)
    cpu_count = mp.cpu_count()
    available_memory_gb = platform_info.get('memory', {}).get('available_system_memory', 0) / (1024**3)

    # Base process count on CPU cores
    process_count = max(2, cpu_count // 2)  # Start with half CPU cores

    # Adjust based on available memory (2GB per process minimum)
    memory_limited_count = int(available_memory_gb / 2)
    process_count = min(process_count, memory_limited_count)

    return min(process_count, 8)  # Cap at 8 for most workloads

optimal_processes = get_optimal_process_count()
```

## Memory Optimization

### Windows Memory Management

Windows handles memory differently than Unix systems:
- No copy-on-write for process memory
- Higher per-process memory overhead
- Different shared memory mechanisms

### Memory Optimization Strategies

#### 1. Shared State Optimization

```python
from hivemind.utils.mpfuture import SharedState

# ✅ Use efficient shared state on Windows
def efficient_shared_state():
    # Windows automatically uses multiprocessing.Value
    shared_value = SharedState.next()
    return shared_value

# Monitor memory usage
from hivemind.utils.limits import get_current_limits

def monitor_memory():
    limits = get_current_limits()
    memory_usage_percent = limits['memory']['percent']

    if memory_usage_percent > 80:
        print("High memory usage detected - consider optimization")
        return False
    return True
```

#### 2. Tensor Memory Management

```python
import torch

# ✅ Memory-efficient tensor operations
def memory_efficient_tensors():
    # Use CPU tensors when GPU not needed
    device = torch.device('cpu')

    # Clear gradients
    torch.cuda.empty_cache()  # If using CUDA

    # Use in-place operations where possible
    tensor = torch.randn(1000, 1000)
    tensor.add_(1.0)  # In-place operation

    return tensor

# ✅ Batch tensor operations
def batch_tensor_operations(data_list, batch_size=32):
    results = []
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i:i+batch_size]
        # Process batch together
        batch_tensor = torch.stack(batch)
        result = process_tensor_batch(batch_tensor)
        results.extend(result)
    return results
```

#### 3. Memory Monitoring

```python
import psutil
import time
from hivemind.utils.limits import check_resource_sufficiency

class MemoryMonitor:
    def __init__(self, warning_threshold=80, critical_threshold=90):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def check_memory(self):
        """Check current memory usage"""
        process = psutil.Process()
        memory_percent = process.memory_percent()

        if memory_percent > self.critical_threshold:
            raise MemoryError(f"Critical memory usage: {memory_percent:.1f}%")
        elif memory_percent > self.warning_threshold:
            print(f"Warning: High memory usage: {memory_percent:.1f}%")

        return memory_percent

    def ensure_resources(self, required_memory_mb=1024):
        """Ensure sufficient resources are available"""
        if not check_resource_sufficiency(required_memory_mb=required_memory_mb):
            raise RuntimeError("Insufficient system resources")
```

## I/O Optimization

### Windows I/O Characteristics

- TCP sockets are used instead of Unix domain sockets
- Asynchronous I/O is generally more efficient
- File I/O has different performance characteristics

### I/O Optimization Strategies

#### 1. Async I/O Patterns

```python
import asyncio
import aiofiles

# ✅ Async file operations
async def async_file_operations(file_path, data_list):
    async with aiofiles.open(file_path, 'w') as f:
        for data in data_list:
            await f.write(f"{data}\n")
            await f.flush()  # Periodic flushing

# ✅ Concurrent I/O operations
async def concurrent_io_processing(items):
    semaphore = asyncio.Semaphore(10)  # Limit concurrent I/O

    async def process_with_limit(item):
        async with semaphore:
            return await process_item_async(item)

    tasks = [process_with_limit(item) for item in items]
    return await asyncio.gather(*tasks)
```

#### 2. Socket Optimization

```python
# Windows uses TCP sockets automatically
from hivemind.p2p import P2P

async def optimized_p2p_setup():
    # Configure for Windows performance
    p2p = await P2P.create(
        startup_timeout=30,      # Increased timeout for Windows
        conn_manager=True,       # Enable connection management
        auto_nat=True,          # Enable NAT traversal
    )

    # Use larger message sizes for Windows TCP
    # (TCP handles large messages efficiently)
    return p2p
```

## Network Optimization

### Windows Network Performance

- TCP loopback is well-optimized
- Connection pooling is important
- Network I/O can benefit from async patterns

### Network Optimization Strategies

#### 1. Connection Pooling

```python
import asyncio
from contextlib import asynccontextmanager

class ConnectionPool:
    def __init__(self, max_connections=10):
        self.semaphore = asyncio.Semaphore(max_connections)
        self.connections = asyncio.Queue()

    @asynccontextmanager
    async def get_connection(self):
        async with self.semaphore:
            try:
                conn = self.connections.get_nowait()
            except asyncio.QueueEmpty:
                conn = await create_new_connection()

            try:
                yield conn
            finally:
                await self.connections.put(conn)

# Usage
async def with_connection_pool():
    pool = ConnectionPool(max_connections=5)

    async with pool.get_connection() as conn:
        result = await conn.operation()
    return result
```

#### 2. Batch Network Operations

```python
# ✅ Batch network requests
async def batch_network_requests(requests, batch_size=10):
    results = []
    for i in range(0, len(requests), batch_size):
        batch = requests[i:i+batch_size]

        # Send batch requests concurrently
        tasks = [send_request(req) for req in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        results.extend(batch_results)
    return results
```

## Concurrency Optimization

### Windows Threading Considerations

- Thread creation overhead is higher on Windows
- GIL (Global Interpreter Lock) affects performance similarly
- Async patterns often perform better

### Concurrency Optimization Strategies

#### 1. Async/Await Patterns

```python
# ✅ Prefer async over threading for I/O-bound tasks
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Separate CPU-bound and I/O-bound operations
async def hybrid_processing(data_list):
    # I/O-bound operations (async)
    async def io_processing(item):
        # Network/disk operations
        result = await fetch_data_async(item)
        return result

    # CPU-bound operations (thread pool)
    with ThreadPoolExecutor(max_workers=4) as executor:
        loop = asyncio.get_event_loop()

        # Process items with appropriate concurrency model
        tasks = []
        for item in data_list:
            if is_io_bound(item):
                tasks.append(io_processing(item))
            else:
                tasks.append(loop.run_in_executor(executor, cpu_processing, item))

        return await asyncio.gather(*tasks)
```

#### 2. Executor Configuration

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp

def get_optimal_executors():
    """Configure optimal executors for Windows"""

    # Conservative thread count for Windows
    thread_count = min(mp.cpu_count(), 4)

    # Conservative process count (considering memory)
    process_count = min(mp.cpu_count() // 2, 4)

    thread_executor = ThreadPoolExecutor(
        max_workers=thread_count,
        thread_name_prefix="hivemind-thread"
    )

    process_executor = ProcessPoolExecutor(
        max_workers=process_count
    )

    return thread_executor, process_executor
```

## Performance Monitoring

### Windows Performance Metrics

```python
import psutil
import time
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class PerformanceMetrics:
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    timestamp: float

class WindowsPerformanceMonitor:
    def __init__(self):
        self.process = psutil.Process()
        self.metrics_history: List[PerformanceMetrics] = []

    def collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics"""
        # CPU and Memory
        cpu_percent = self.process.cpu_percent()
        memory_info = self.process.memory_info()
        memory_percent = self.process.memory_percent()

        # Disk I/O
        io_counters = self.process.io_counters()
        disk_read_mb = io_counters.read_bytes / (1024**2)
        disk_write_mb = io_counters.write_bytes / (1024**2)

        # Network I/O
        network_io = psutil.net_io_counters()
        net_sent_mb = network_io.bytes_sent / (1024**2)
        net_recv_mb = network_io.bytes_recv / (1024**2)

        metrics = PerformanceMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_info.rss / (1024**2),
            disk_io_read_mb=disk_read_mb,
            disk_io_write_mb=disk_write_mb,
            network_sent_mb=net_sent_mb,
            network_recv_mb=net_recv_mb,
            timestamp=time.time()
        )

        self.metrics_history.append(metrics)
        return metrics

    def get_performance_summary(self, window_minutes=5) -> Dict:
        """Get performance summary for recent time window"""
        cutoff_time = time.time() - (window_minutes * 60)
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {}

        return {
            'avg_cpu': sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
            'avg_memory': sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
            'peak_memory': max(m.memory_percent for m in recent_metrics),
            'metrics_count': len(recent_metrics),
            'window_minutes': window_minutes
        }

# Usage
monitor = WindowsPerformanceMonitor()

# Periodic monitoring
async def periodic_monitoring():
    while True:
        metrics = monitor.collect_metrics()
        summary = monitor.get_performance_summary()

        # Alert on high resource usage
        if metrics.memory_percent > 85:
            print(f"High memory usage: {metrics.memory_percent:.1f}%")

        await asyncio.sleep(60)  # Monitor every minute
```

## Benchmarking

### Windows-Specific Benchmarks

```python
import time
import asyncio
from typing import List, Any

def benchmark_function(func, *args, **kwargs) -> dict:
    """Benchmark a function's performance"""
    start_time = time.perf_counter()

    # Run function
    result = func(*args, **kwargs)

    end_time = time.perf_counter()
    execution_time = end_time - start_time

    return {
        'result': result,
        'execution_time': execution_time,
        'throughput': len(result) / execution_time if hasattr(result, '__len__') else 0
    }

async def benchmark_async_function(coro_func, *args, **kwargs) -> dict:
    """Benchmark an async function's performance"""
    start_time = time.perf_counter()

    # Run async function
    result = await coro_func(*args, **kwargs)

    end_time = time.perf_counter()
    execution_time = end_time - start_time

    return {
        'result': result,
        'execution_time': execution_time,
        'throughput': len(result) / execution_time if hasattr(result, '__len__') else 0
    }

# Example benchmarks
async def run_windows_benchmarks():
    """Run Windows-specific performance benchmarks"""

    # Benchmark process creation
    from hivemind.utils.processing import create_process

    def dummy_function():
        return "test_result"

    process_benchmark = benchmark_function(
        lambda: [create_process(target=dummy_function) for _ in range(10)]
    )
    print(f"Process creation: {process_benchmark['execution_time']:.3f}s")

    # Benchmark MPFuture
    from hivemind.utils.mpfuture import MPFuture

    mpfuture_benchmark = await benchmark_async_function(
        lambda: [MPFuture() for _ in range(100)]
    )
    print(f"MPFuture creation: {mpfuture_benchmark['execution_time']:.3f}s")

    # Benchmark serialization
    import pickle

    futures = [MPFuture() for _ in range(50)]
    for f in futures:
        f.set_result("test_data")

    serialization_benchmark = benchmark_function(
        lambda: [pickle.dumps(f) for f in futures]
    )
    print(f"Serialization: {serialization_benchmark['execution_time']:.3f}s")
```

## Recommendations

### General Windows Performance Recommendations

1. **Process Management:**
   - Minimize process creation/recreation
   - Use process pools for CPU-bound work
   - Batch operations to reduce inter-process communication

2. **Memory Management:**
   - Monitor memory usage regularly
   - Use appropriate batch sizes
   - Clear unused objects and gradients

3. **I/O Optimization:**
   - Prefer async/await for I/O operations
   - Use connection pooling
   - Batch network requests

4. **Concurrency:**
   - Use async patterns for I/O-bound tasks
   - Use thread pools for CPU-bound tasks
   - Limit concurrent operations

5. **Monitoring:**
   - Implement performance monitoring
   - Set up alerts for resource usage
   - Regular benchmarking

### Production Deployment

For production deployments on Windows:

1. **Resource Planning:**
   - Allocate sufficient RAM (16GB+ for production)
   - Use SSD storage for better I/O performance
   - Monitor system resources continuously

2. **Configuration:**
   - Optimize process counts based on available resources
   - Configure appropriate timeouts
   - Enable connection management

3. **Monitoring:**
   - Set up automated performance monitoring
   - Configure alerts for resource thresholds
   - Regular performance benchmarking

4. **Scaling:**
   - Consider distributed deployment for large workloads
   - Use load balancing for high-throughput scenarios
   - Implement graceful degradation mechanisms

---

*For general Hivemind optimization guidance, see the main documentation. This guide focuses on Windows-specific performance considerations.*