#!/usr/bin/env python3
"""
Test to verify the fix for large file upload issue.

This test ensures that files larger than 20KB are uploaded correctly
and not as empty files.
"""

import asyncio
import tempfile
import os
import aiofiles
from unittest.mock import AsyncMock
from aiodav import Client


class MockClient(Client):
    """Mock client that captures upload data without making network requests"""
    
    def __init__(self, hostname="http://test.example.com"):
        # Initialize minimal client state without network setup
        self._chunk_size = 65536
        self._hostname = hostname
        self._root = ""
        self.uploaded_data = []
        
    async def _execute_request(self, action, path, data=None, headers_ext=None):
        """Mock request execution that captures upload data"""
        if action == "upload":
            if isinstance(data, bytes):
                # Direct upload path - data should be bytes
                self.uploaded_data.append({
                    'type': 'bytes',
                    'size': len(data),
                    'path': path
                })
            elif hasattr(data, '__aiter__'):
                # Generator path - consume the async generator
                total_size = 0
                async for chunk in data:
                    total_size += len(chunk)
                    
                self.uploaded_data.append({
                    'type': 'generator', 
                    'size': total_size,
                    'path': path
                })
            else:
                self.uploaded_data.append({
                    'type': str(type(data)),
                    'size': 0,
                    'path': path
                })
        
        # Return mock successful response
        response = AsyncMock()
        response.status = 201
        return response
        
    async def exists(self, path):
        """Mock exists check"""
        return True


async def test_large_file_upload():
    """Test that large files (>20KB) are uploaded correctly"""
    
    test_cases = [
        ("small_file", 5 * 1024),      # 5KB  
        ("medium_file", 20 * 1024),    # 20KB
        ("large_file", 50 * 1024),     # 50KB  
        ("very_large_file", 100 * 1024), # 100KB
    ]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for name, size_bytes in test_cases:
            print(f"Testing {name}: {size_bytes} bytes")
            
            # Create test file with unique content
            test_file = os.path.join(temp_dir, f"{name}.bin")
            content = os.urandom(size_bytes)  # Random binary content
            
            with open(test_file, "wb") as f:
                f.write(content)
                
            # Test upload without progress callback
            print(f"  Testing direct upload (no progress callback)...")
            client = MockClient()
            await client.upload_file(f"/remote/{name}.bin", test_file)
            
            # Verify upload data
            assert len(client.uploaded_data) == 1, f"Expected 1 upload, got {len(client.uploaded_data)}"
            upload_info = client.uploaded_data[0]
            
            assert upload_info['type'] == 'bytes', f"Expected bytes upload, got {upload_info['type']}"
            assert upload_info['size'] == size_bytes, f"Expected {size_bytes} bytes, got {upload_info['size']}"
            
            print(f"  ✅ SUCCESS: {upload_info['size']} bytes uploaded correctly")
            
            # Test upload with progress callback
            print(f"  Testing generator upload (with progress callback)...")
            
            progress_calls = []
            def progress_callback(current, total):
                progress_calls.append((current, total))
                
            client = MockClient()
            await client.upload_file(f"/remote/{name}.bin", test_file, progress=progress_callback)
            
            # Verify upload data
            assert len(client.uploaded_data) == 1, f"Expected 1 upload, got {len(client.uploaded_data)}"
            upload_info = client.uploaded_data[0]
            
            assert upload_info['type'] == 'generator', f"Expected generator upload, got {upload_info['type']}"
            assert upload_info['size'] == size_bytes, f"Expected {size_bytes} bytes, got {upload_info['size']}"
            
            # Verify progress callback was called
            assert len(progress_calls) >= 2, f"Expected at least 2 progress calls, got {len(progress_calls)}"
            assert progress_calls[-1] == (size_bytes, size_bytes), f"Final progress should be ({size_bytes}, {size_bytes}), got {progress_calls[-1]}"
            
            print(f"  ✅ SUCCESS: {upload_info['size']} bytes uploaded correctly with progress tracking")


async def test_upload_to_direct():
    """Test upload_to method directly with different buffer types"""
    
    print("Testing upload_to method with different buffer types...")
    
    content = b"Test content for upload_to method" * 1000  # ~33KB
    
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
        
    try:
        # Test with aiofiles object (no progress callback)
        print("  Testing with aiofiles buffer (direct path)...")
        client = MockClient()
        
        async with aiofiles.open(tmp_file_path, 'rb') as file_buffer:
            await client.upload_to("/remote/test.txt", file_buffer, buffer_size=len(content))
            
        assert len(client.uploaded_data) == 1
        upload_info = client.uploaded_data[0]
        assert upload_info['type'] == 'bytes'
        assert upload_info['size'] == len(content)
        print(f"  ✅ SUCCESS: {upload_info['size']} bytes uploaded from aiofiles buffer")
        
        # Test with aiofiles object (with progress callback)  
        print("  Testing with aiofiles buffer (generator path)...")
        client = MockClient()
        
        def dummy_progress(current, total):
            pass
            
        async with aiofiles.open(tmp_file_path, 'rb') as file_buffer:
            await client.upload_to("/remote/test.txt", file_buffer, buffer_size=len(content), progress=dummy_progress)
            
        assert len(client.uploaded_data) == 1
        upload_info = client.uploaded_data[0] 
        assert upload_info['type'] == 'generator'
        assert upload_info['size'] == len(content)
        print(f"  ✅ SUCCESS: {upload_info['size']} bytes uploaded from aiofiles buffer with progress")
        
    finally:
        os.unlink(tmp_file_path)


if __name__ == "__main__":
    asyncio.run(test_large_file_upload())
    asyncio.run(test_upload_to_direct())
    print("\nAll tests passed! 🎉")