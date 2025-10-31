# Windows Support

Hivemind now supports native Windows execution on Windows 10 and 11. This document provides comprehensive information about Windows compatibility, installation, and usage.

## Overview

Hivemind has been enhanced to support cross-platform operation, including native Windows support alongside existing Linux and macOS compatibility. The Windows implementation uses:

- **Spawn-based multiprocessing**: Windows-compatible process creation model
- **TCP sockets**: Cross-platform inter-process communication
- **multiprocessing.Value**: Windows-compatible shared state management
- **Standard asyncio**: Windows-friendly event loop handling

## System Requirements

### Minimum Requirements
- **Windows 10** (version 1903 or later) or **Windows 11**
- **Python 3.8+** (64-bit recommended)
- **Go 1.19+** (for building p2pd daemon)
- **Visual Studio Build Tools** (for C++ extensions)
- **8GB+ RAM** (16GB+ recommended for production workloads)
- **10GB+ free disk space**

### Recommended Requirements
- **Windows 11** (latest version)
- **Python 3.10+** (64-bit)
- **Go 1.21+**
- **Visual Studio 2022** with C++ workload
- **16GB+ RAM**
- **SSD storage**

## Installation

### Option 1: Install from PyPI (Recommended)

```bash
# Install Hivemind with CPU-only PyTorch
pip install hivemind

# For GPU support (CUDA 11.8)
pip install hivemind[bitsandbytes] torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Option 2: Install from Source

1. **Install Prerequisites:**

   ```bash
   # Install Python 3.8+ from python.org or Microsoft Store
   # Install Go from https://go.dev/dl/
   # Install Visual Studio Build Tools from https://visualstudio.microsoft.com/downloads/
   ```

2. **Clone and Install:**

   ```bash
   git clone https://github.com/learning-at-home/hivemind.git
   cd hivemind

   # Install with Windows binary support (builds p2pd from source)
   pip install -e . --build-option=buildgo
   ```

### Option 3: Development Installation

```bash
git clone https://github.com/learning-at-home/hivemind.git
cd hivemind

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install with build support
pip install -e . --build-option=buildgo
```

## Windows-Specific Features

### Cross-Platform Process Management

Hivemind automatically detects the platform and uses appropriate process creation:

```python
from hivemind.utils.processing import get_process_class, create_process

# Automatically uses ForkProcess on Unix, Process on Windows
ProcessClass = get_process_class()

# Create cross-platform processes
proc = create_process(target=my_function, args=(arg1, arg2))
proc.start()
```

### Platform Detection

```python
from hivemind.utils.platform import get_platform, is_windows

if is_windows():
    print("Running on Windows")
    print(f"Platform: {get_platform()}")
```

### Event Loop Optimization

```python
from hivemind.utils.asyncio import get_optimal_event_loop

# Automatically selects best event loop for the platform
loop = get_optimal_event_loop()
```

## Usage Examples

### Basic DHT Usage

```python
import asyncio
from hivemind.dht import DHT

async def main():
    # Create DHT node (works on all platforms)
    dht = await DHT.create(start=True)

    # Store and retrieve values
    await dht.store("key", b"value")
    result = await dht.get("key")

    print(f"Retrieved: {result}")
    await dht.shutdown()

asyncio.run(main())
```

### MPFuture Usage

```python
from hivemind.utils.mpfuture import MPFuture

# Cross-process future (works on Windows and Unix)
future = MPFuture()

# Set result from any process
future.set_result("Hello from Windows!")

# Get result in original process
result = future.result()
print(result)  # "Hello from Windows!"
```

### P2P Communication

```python
import asyncio
from hivemind.p2p import P2P

async def main():
    # Automatically uses TCP sockets on Windows, Unix sockets on Unix
    p2p = await P2P.create()

    print(f"Peer ID: {p2p.peer_id}")
    print(f"Listen address: {p2p.listen_maddrs}")

    await p2p.shutdown()

asyncio.run(main())
```

## Performance Considerations

### Process Creation Overhead

Windows uses the "spawn" process model which has higher overhead than Unix "fork". To optimize performance:

1. **Reuse processes**: Create long-running worker processes instead of frequent process creation
2. **Batch operations**: Group multiple operations to minimize process communication
3. **Process pools**: Use `multiprocessing.Pool` for CPU-bound tasks

### Memory Management

Windows handles shared memory differently than Unix:

```python
# Monitor resource usage on Windows
from hivemind.utils.limits import get_current_limits, check_resource_sufficiency

limits = get_current_limits()
print(f"Current limits: {limits}")

# Check if system has sufficient resources
sufficient = check_resource_sufficiency(
    required_file_descriptors=1000,
    required_memory_mb=2048
)
```

### Network Performance

- **TCP sockets**: Windows uses TCP sockets for inter-process communication
- **Loopback optimization**: Local TCP traffic is optimized on Windows
- **Port allocation**: Dynamic port allocation may be slower on Windows

## Troubleshooting

### Common Issues

#### 1. p2pd Binary Not Found

**Problem**: `FileNotFoundError: p2pd executable not found`

**Solution**:
```bash
# Rebuild with Windows binary support
pip install -e . --build-option=buildgo

# Or install Go and build manually:
go version  # Verify Go installation
pip uninstall hivemind
pip install -e . --build-option=buildgo
```

#### 2. Process Creation Issues

**Problem**: `RuntimeError: Failed to start process`

**Solution**:
```python
import multiprocessing as mp
from hivemind.utils.processing import configure_multiprocessing

# Configure multiprocessing for Windows
configure_multiprocessing()

# Use correct start method
mp.set_start_method('spawn', force=True)
```

#### 3. Socket Connection Issues

**Problem**: `ConnectionRefusedError` or timeout errors

**Solution**:
```python
# Check firewall settings
# Windows Firewall may block local TCP connections

# Use explicit timeout
import asyncio
from hivemind.p2p import P2P

async def main():
    try:
        p2p = await P2P.create(startup_timeout=30)
        # ... use p2p
    except asyncio.TimeoutError:
        print("Startup timeout - check firewall settings")

asyncio.run(main())
```

#### 4. Memory Issues

**Problem**: OutOfMemoryError or excessive memory usage

**Solution**:
```python
# Monitor memory usage
from hivemind.utils.limits import check_resource_sufficiency

if not check_resource_sufficiency(required_memory_mb=4096):
    print("Insufficient memory available")
    # Reduce batch size or use fewer processes

# Use CPU-only PyTorch if GPU not needed
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
from hivemind.utils.logging import get_logger

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = get_logger(__name__)

# Enable platform-specific debug info
from hivemind.utils.platform import get_platform_info
print(f"Platform info: {get_platform_info()}")
```

### Performance Monitoring

Monitor Windows-specific performance metrics:

```python
import psutil
from hivemind.utils.limits import get_current_limits

# Get detailed resource information
limits = get_current_limits()
print(f"Memory usage: {limits['memory']['percent']:.1f}%")
print(f"Available memory: {limits['memory']['available_system_memory'] / 1024**3:.1f} GB")
```

## Development

### Building Windows Binaries

To build Windows p2pd binaries:

```bash
# Ensure Go is installed
go version

# Build with Windows support
python setup.py build_py --buildgo

# The binary will be created as:
# hivemind/hivemind_cli/p2pd.exe
```

### Testing on Windows

Run the test suite:

```bash
# Run all tests
pytest tests/

# Run Windows-specific tests
pytest tests/ -k "windows"

# Run with coverage
pytest tests/ --cov=hivemind --cov-report=html
```

### Cross-Platform Development

For cross-platform development:

1. **Test on multiple platforms**: Use GitHub Actions for automated testing
2. **Platform detection**: Use `hivemind.utils.platform` for conditional behavior
3. **Avoid Unix-specific code**: Use cross-platform alternatives
4. **Windows paths**: Use `pathlib.Path` or `os.path` for cross-platform paths

## Limitations

### Current Limitations

1. **Performance**: Process creation is slower on Windows due to spawn model
2. **Shared memory**: Windows uses different shared memory mechanisms
3. **Signal handling**: Limited signal support compared to Unix
4. **Unix domain sockets**: Not available on Windows, TCP sockets used instead

### Workarounds

1. **Process reuse**: Minimize process creation overhead
2. **Memory optimization**: Use process pools and efficient data structures
3. **Async alternatives**: Use asyncio for communication instead of signals
4. **TCP optimization**: Local TCP is well-optimized on Windows

## Contributing

When contributing Windows support:

1. **Test on Windows**: Ensure code works on Windows 10/11
2. **Use platform utilities**: Leverage `hivemind.utils.platform`
3. **Update tests**: Add Windows-specific test cases
4. **Documentation**: Update this document with new features

### Platform-Specific Code Guidelines

```python
# Good: Use platform abstraction
from hivemind.utils.platform import IS_WINDOWS

if IS_WINDOWS:
    # Windows-specific code
    pass
else:
    # Unix-specific code
    pass

# Avoid: Direct platform checks
import sys
if sys.platform == 'win32':
    # This is discouraged - use utilities instead
```

## Resources

- [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/) - Alternative Windows support
- [Python on Windows Documentation](https://docs.python.org/3/using/windows.html)
- [multiprocessing on Windows](https://docs.python.org/3/library/multiprocessing.html#windows)
- [Go Installation](https://go.dev/doc/install)

## Support

For Windows-specific issues:

1. **GitHub Issues**: Report bugs on the [hivemind repository](https://github.com/learning-at-home/hivemind)
2. **Discussions**: Use GitHub Discussions for questions
3. **Documentation**: Check this document first for known issues
4. **Logs**: Include debug logs when reporting issues

---

*This document covers Hivemind Windows support. For general Hivemind documentation, see the main README.md and other documentation files.*