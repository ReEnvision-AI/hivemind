# Windows Compatibility Matrix

This document provides a detailed analysis of Hivemind's dependency compatibility with Windows operating systems.

## Overview

Hivemind has been enhanced to support Windows 10+ through cross-platform architectural changes. Most dependencies are Windows-compatible, but some require special handling or alternatives.

## Dependency Compatibility Matrix

| Dependency | Version | Windows Status | Issues | Solutions |
|------------|---------|----------------|--------|-----------|
| **uvloop** | >=0.14.0 | ❌ Not Available | Unix-only event loop | ✅ Automatic fallback to asyncio |
| **pytest-forked** | - | ❌ Not Available | Unix fork() system call | ⚠️ Use pytest-windows or default isolation |
| **PyYAML** | - | ✅ Compatible | None | N/A |
| **torch** | >=1.9.0 | ✅ Compatible | None | Use official PyTorch Windows wheels |
| **numpy** | >=1.17 | ✅ Compatible | None | Use official NumPy Windows wheels |
| **scipy** | >=1.2.1 | ✅ Compatible | None | Use official SciPy Windows wheels |
| **grpcio-tools** | ==1.71.0 | ✅ Compatible | May need Visual Studio Build Tools | Use precompiled wheels |
| **cryptography** | >=3.4.6 | ✅ Compatible | May need Microsoft Visual C++ Redistributable | Use precompiled wheels |
| **psutil** | - | ✅ Compatible | None | N/A |

## Critical Dependencies Requiring Changes

### 1. uvloop ❌
**Status**: Already handled in code

**Issue**: uvloop is a Unix-only high-performance event loop implementation.

**Solution**: The code automatically detects Windows and falls back to standard asyncio:

```python
from hivemind.utils.asyncio import get_optimal_event_loop

# Automatically uses uvloop on Unix, asyncio on Windows
loop = get_optimal_event_loop()
```

### 2. pytest-forked ❌
**Status**: Requires attention for test infrastructure

**Issue**: Uses Unix fork() system call for process isolation.

**Solution**: Update test requirements to use Windows-compatible alternatives:

```bash
# Instead of: pip install pytest-forked
# Use: pip install pytest-windows
```

## Development Environment Setup

### Windows System Requirements

**Minimum Requirements:**
- **Windows 10** (version 1903+) or **Windows 11**
- **Python 3.8+** (64-bit recommended)
- **Visual Studio Build Tools** (for C extensions)
- **Microsoft Visual C++ Redistributable** (for cryptography)

**Recommended:**
- **Windows 11** (latest version)
- **Python 3.10+**
- **Visual Studio 2022** with C++ workload

### Installation Commands

```bash
# Core installation
pip install -r requirements-windows.txt

# Development installation
pip install -r requirements-dev-windows.txt

# For CPU-only PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# For GPU PyTorch (CUDA 11.8)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Testing Considerations

### Windows vs Unix Testing Differences

| Aspect | Unix Behavior | Windows Behavior |
|--------|---------------|------------------|
| **Process Isolation** | Uses fork() for efficient process creation | Uses spawn() for process creation |
| **Event Loop** | uvloop for high performance | Standard asyncio |
| **Signal Handling** | Unix signals available | Limited signal support |
| **File Paths** | Forward slashes `/` | Backslashes `\` or forward slashes |
| **Permissions** | Unix-style permissions | Windows ACL permissions |

### Test Configuration

```python
# pytest.ini or pyproject.toml
[tool:pytest]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
    # Remove Windows-incompatible options
    # "-p no:forked"  # Uncomment on Windows
]

# Windows-specific test marks
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "windows_only: marks tests that only run on Windows",
    "unix_only: marks tests that only run on Unix systems"
]
```

## Performance Considerations

### Expected Performance Differences

| Metric | Unix | Windows | Impact |
|--------|------|--------|--------|
| **Process Creation** | Fast (fork) | Slower (spawn) | Higher startup overhead |
| **Event Loop** | High (uvloop) | Standard (asyncio) | Lower I/O performance |
| **Inter-process Comm** | Shared memory inheritance | Explicit serialization | Higher communication overhead |
| **Memory Usage** | Copy-on-write optimization | Full memory copy | Higher memory usage |

### Mitigation Strategies

1. **Process Reuse**: Create long-running processes instead of frequent creation
2. **Batching**: Group operations to minimize inter-process communication
3. **Connection Pooling**: Reuse connections where possible
4. **Async Patterns**: Use asyncio for I/O-bound operations

## Known Limitations

### Current Limitations

1. **Performance**: Windows processes have higher creation overhead than Unix fork
2. **Memory**: No copy-on-write optimization for shared memory
3. **Signal Handling**: Limited signal support compared to Unix
4. **Unix Sockets**: TCP sockets used instead of Unix domain sockets

### Workarounds

1. **Process Pools**: Reuse processes to minimize creation overhead
2. **Memory Management**: Monitor and optimize memory usage
3. **Alternative Communication**: Use asyncio patterns instead of signals
4. **TCP Optimization**: Use localhost TCP for efficient local communication

## Troubleshooting

### Common Installation Issues

#### 1. Visual Studio Build Tools
```bash
# Install Visual Studio Build Tools
wing install Microsoft.VisualStudio.2022.BuildTools

# Or install via Visual Studio Installer
# Select: C++ build tools
# Select: Windows 10 SDK
# Select: MSVC v143 build tools
```

#### 2. Cryptography Issues
```bash
# Try installing from precompiled wheels first
pip install --upgrade pip setuptools wheel

# If compilation is needed, ensure Visual Studio is installed
pip install cryptography --verbose
```

#### 3. torch Installation
```bash
# CPU-only version
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# GPU version (check CUDA version compatibility)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Common Runtime Issues

#### 1. Process Creation Errors
- **Symptom**: "cannot pickle 'weakref.ReferenceType' object"
- **Cause**: Using spawn with objects that contain weakrefs
- **Solution**: Code automatically forces fork method on Unix

#### 2. Event Loop Issues
- **Symptom**: Performance warnings or errors
- **Cause**: uvloop not available on Windows
- **Solution**: Code automatically falls back to asyncio

#### 3. Socket Connection Issues
- **Symptom**: Connection refused or timeout errors
- **Cause**: Windows Firewall blocking local TCP connections
- **Solution**: Configure Windows Firewall to allow Python.exe connections

## Migration Guide

### From Unix to Windows

1. **Install Prerequisites**: Install Visual Studio Build Tools
2. **Use Windows Requirements**: Use `requirements-windows.txt`
3. **Update Test Configuration**: Remove Unix-specific pytest plugins
4. **Test Incrementally**: Start with basic functionality
5. **Monitor Performance**: Expect 10-30% performance difference

### Development Environment Setup

```bash
# 1. Set up virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-windows.txt
pip install -r requirements-dev-windows.txt

# 3. Install Hivemind with Windows binary support
pip install -e . --build-option=buildgo

# 4. Run tests
python -m pytest tests/ -v
```

## Support Status

### ✅ Fully Supported
- Core functionality (DHT, P2P, MPFuture)
- Process management with cross-platform compatibility
- Network communication with TCP sockets
- Development and testing infrastructure
- Documentation and examples

### ⚠️ With Limitations
- Performance (10-30% slower than Unix)
- Signal handling limitations
- No Unix domain sockets (TCP replacement)

### ❌ Not Supported
- Windows versions older than 10
- uvloop performance optimizations
- Unix-specific testing tools

---

*This document is part of Hivemind's Windows support initiative. For the latest compatibility information, see the [Windows Support Guide](windows_support.md).*