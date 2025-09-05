# aiodav - Python Async WebDAV Client

aiodav is a Python asynchronous WebDAV client library built on aiohttp, designed to provide async/await support for WebDAV operations like upload, download, listing, and managing remote files and directories.

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

### Bootstrap and Setup
- **Python Version**: Requires Python 3.6+ (tested with Python 3.12.3)
- **Install in development mode**: `pip3 install -e .` -- takes 15-30 seconds when dependencies are cached, up to 5 minutes on first install. NEVER CANCEL. Set timeout to 10+ minutes.
- **Dependencies**: Installs automatically: aiohttp, aiofiles, faust-cchardet, aiodns, lxml

### Build and Package
- **Package Build**: `python3 -m build` -- **NETWORK DEPENDENT**: May fail due to timeout issues accessing PyPI. If it fails, use `pip3 install -e .` instead for development.
- **Direct Installation**: The package installs successfully with `pip3 install -e .` for development purposes.

### Testing and Validation
- **Quick Import Test**: `python3 -c "import aiodav; print(f'Version: {aiodav.__version__}')"` -- takes <1 second
- **Comprehensive Validation Script**: Create and run this validation script after making changes:

```python
#!/usr/bin/env python3
import asyncio
from aiodav import Client
from aiodav.exceptions import *

async def validate_aiodav():
    print("Testing aiodav functionality...")
    
    # Test import and version
    import aiodav
    print(f"✓ Version: {aiodav.__version__}")
    
    # Test client creation
    async with Client('https://test.example.com', login='test', password='test') as client:
        print("✓ Client created successfully")
        
        # Test essential methods exist
        methods = ['upload', 'download', 'list', 'exists', 'delete', 'copy', 'move']
        for method in methods:
            if hasattr(client, method):
                print(f"✓ Method '{method}' available")
    
    # Test exceptions import
    print("✓ Exception classes imported")
    print("All validation tests passed!")

asyncio.run(validate_aiodav())
```

Save this as `validate_aiodav.py` and run with: `python3 validate_aiodav.py` -- takes <1 second

### Development Workflow
- **Code Compilation Check**: `python3 -m py_compile aiodav/*.py` -- validates syntax, will show SyntaxWarning in urn.py (known issue with escape sequence)
- **Manual Testing**: Always test async context manager usage since the Client requires an event loop

## Validation Scenarios

### CRITICAL: Always Validate After Changes
After making ANY changes to the aiodav code, **ALWAYS** run these validation scenarios in order:

1. **Syntax Check**: `python3 -m py_compile aiodav/*.py` 
   - Should complete without errors (SyntaxWarning in urn.py is expected)

2. **Quick Import Test**: 
   ```bash
   python3 -c "import aiodav; print('Import successful, version:', aiodav.__version__)"
   ```

3. **Full Functionality Validation**: Run the comprehensive validation script (from Testing section above)
   - Should show "All validation tests passed!"

4. **Manual Scenario Testing**: Test actual WebDAV-like usage patterns:
   ```python
   import asyncio
   from aiodav import Client
   
   async def manual_test():
       # Test different client configurations
       clients = [
           Client('https://test1.example.com', login='user', password='pass'),
           Client('https://test2.example.com', token='test-token'),
       ]
       
       for i, client in enumerate(clients):
           async with client:
               print(f"✓ Client {i+1} instantiated successfully")
               # Verify no immediate exceptions when accessing properties
               print(f"✓ Client {i+1} base URL: {client._base_url if hasattr(client, '_base_url') else 'N/A'}")
   
   asyncio.run(manual_test())
   ```

### Expected Results
- **Syntax check**: No errors, only SyntaxWarning in urn.py
- **Import test**: Shows current version (0.1.14)
- **Validation script**: All checkmarks, "All validation tests passed!"
- **Manual test**: Both clients instantiate without errors
- **Method count**: Client should have 28+ available methods

## Common Tasks

### Repository Structure
```
/
├── .github/
│   ├── workflows/python-publish.yml
│   └── dependabot.yml
├── aiodav/
│   ├── __init__.py      # Main package file, defines version
│   ├── client.py        # Main Client class with WebDAV operations
│   ├── exceptions.py    # Custom exception classes
│   ├── urn.py          # URN handling utilities (has SyntaxWarning)
│   └── utils.py        # XML parsing utilities
├── LICENSE             # MIT license
├── README.md           # Package documentation
├── pyproject.toml      # Package configuration
├── requirements.txt    # Dependencies list
└── setup.py           # Simple setuptools setup
```

### Key Files to Know
- **aiodav/client.py**: Contains the main `Client` class with all WebDAV operations (upload, download, list, etc.)
- **aiodav/exceptions.py**: Custom exceptions like `WebDavException`, `NotFound`, `RemoteResourceNotFound`
- **aiodav/__init__.py**: Package entry point, defines version (`__version__ = "0.1.14"`)
- **requirements.txt**: Lists dependencies (aiohttp, aiofiles, faust-cchardet, aiodns, lxml)
- **pyproject.toml**: Modern Python packaging configuration

### Known Issues
- **urn.py SyntaxWarning**: Line 11 has invalid escape sequence `'\.'` - this is a cosmetic issue that doesn't affect functionality
- **Network Timeouts**: `python3 -m build` may fail due to PyPI timeout issues - use `pip3 install -e .` instead for development
- **Async Requirement**: Client class requires async context (event loop) - cannot be used in sync code

### Working with the Client
- Always use within async context: `async with Client(...) as client:`
- Client supports various WebDAV operations: upload, download, list, exists, delete, copy, move
- Authentication via login/password or token
- Progress callbacks supported for upload/download operations

### CI/CD Information
- **GitHub Actions**: Only has publishing workflow (.github/workflows/python-publish.yml) 
- **No Test Suite**: Repository doesn't include test files (tests/ is gitignored)
- **No Linting**: No configured linting tools (flake8, black, mypy, etc.)

## Installation Commands Reference
```bash
# Check Python version (requires 3.6+)
python3 --version

# Install in development mode
pip3 install -e .

# Basic import test
python3 -c "import aiodav; print('Success!')"

# Show package info
pip3 show aiodav

# Compile check (will show SyntaxWarning)
python3 -m py_compile aiodav/*.py
```

## Typical Development Workflow

### Standard Development Process
1. **Before making changes**: Run validation to ensure clean baseline
2. **Make code changes** in aiodav/ directory (client.py, exceptions.py, etc.)
3. **Syntax validation**: `python3 -m py_compile aiodav/*.py`
4. **Import test**: `python3 -c "import aiodav; print('Import OK')"`
5. **Full validation**: Run the comprehensive validation script
6. **Manual testing**: Create specific tests for your changes using async/await patterns
7. **Final check**: Ensure all validation scenarios pass

### Creating Tests for New Features
Since no formal test suite exists, create manual validation scripts:

```python
# Example test for new WebDAV method
import asyncio
from aiodav import Client

async def test_new_feature():
    async with Client('https://mock.webdav.server', login='test', password='test') as client:
        # Test your new functionality here
        if hasattr(client, 'new_method'):
            print("✓ New method exists")
        else:
            print("✗ New method missing")

asyncio.run(test_new_feature())
```

### Code Style Guidelines
- Follow existing async/await patterns in client.py
- Use type hints where present in existing code
- Handle exceptions appropriately (import from aiodav.exceptions)
- Maintain Python 3.6+ compatibility
- Use aiohttp patterns for HTTP operations