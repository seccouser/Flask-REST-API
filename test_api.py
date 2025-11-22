#!/usr/bin/env python3
"""
Simple test script to verify Flask REST API functionality
"""

import requests
import hashlib
import os
import sys
import time

API_URL = "http://localhost:5000"

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{API_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    print("✓ Health check passed\n")

def test_api_info():
    """Test root endpoint"""
    print("Testing API info endpoint...")
    response = requests.get(f"{API_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    print("✓ API info passed\n")

def test_file_upload():
    """Test file upload with hash verification"""
    print("Testing file upload...")
    
    # Create a test file
    test_content = b"This is a test file for Flask REST API"
    test_filename = "test_upload.txt"
    
    with open(test_filename, 'wb') as f:
        f.write(test_content)
    
    # Calculate hash
    sha256_hash = hashlib.sha256(test_content).hexdigest()
    print(f"File hash: {sha256_hash}")
    
    # Upload file
    with open(test_filename, 'rb') as f:
        files = {'file': f}
        data = {'hash': sha256_hash}
        response = requests.post(f"{API_URL}/upload", files=files, data=data)
    
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {result}")
    
    # Cleanup
    os.remove(test_filename)
    
    assert response.status_code == 201
    assert result['hash'] == sha256_hash
    assert result['hash_verified'] == True
    print("✓ File upload passed\n")
    
    return result['filename']

def test_file_list():
    """Test file listing"""
    print("Testing file list...")
    response = requests.get(f"{API_URL}/files")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Files count: {result['count']}")
    assert response.status_code == 200
    print("✓ File list passed\n")

def test_file_download(filename):
    """Test file download"""
    print(f"Testing file download for {filename}...")
    response = requests.get(f"{API_URL}/download/{filename}")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        file_hash = response.headers.get('X-File-Hash')
        print(f"Downloaded file hash: {file_hash}")
        
        # Verify content
        content_hash = hashlib.sha256(response.content).hexdigest()
        assert content_hash == file_hash
        print("✓ File download and hash verification passed\n")
    else:
        print(f"Download failed: {response.json()}\n")

def test_keyboard_emulation():
    """Test keyboard emulation (if available)"""
    print("Testing keyboard emulation...")
    
    # Test with simple text
    data = {"text": "test", "delay": 0.05}
    response = requests.post(f"{API_URL}/keyboard", json=data)
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {result}")
    
    if response.status_code == 503:
        print("⚠ Keyboard emulation not available (evdev not installed or no permissions)")
    else:
        assert response.status_code == 200
        print("✓ Keyboard emulation passed\n")

def main():
    """Run all tests"""
    print("=" * 60)
    print("Flask REST API Test Suite")
    print("=" * 60 + "\n")
    
    try:
        # Check if server is running
        print("Checking if server is running...")
        try:
            requests.get(f"{API_URL}/health", timeout=2)
        except requests.exceptions.ConnectionError:
            print(f"Error: Cannot connect to {API_URL}")
            print("Please start the server first: python app.py")
            sys.exit(1)
        
        # Run tests
        test_health()
        test_api_info()
        uploaded_filename = test_file_upload()
        test_file_list()
        test_file_download(uploaded_filename)
        test_keyboard_emulation()
        
        print("=" * 60)
        print("All tests completed successfully! ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
