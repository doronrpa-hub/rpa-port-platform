#!/usr/bin/env python3
"""
RCB Test Runner
===============
Run all unit tests for RCB modules.

Usage:
    python run_tests.py          # Run all tests
    python run_tests.py -v       # Verbose output
    python run_tests.py -k name  # Run tests matching 'name'
    python run_tests.py --cov    # Run with coverage report
"""
import subprocess
import sys
import os

def main():
    # Change to tests directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(test_dir)
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add any command line args
    cmd.extend(sys.argv[1:])
    
    # Default: verbose and show short summary
    if "-v" not in sys.argv and "-q" not in sys.argv:
        cmd.append("-v")
    
    # Run pytest
    print("=" * 60)
    print("🧪 RCB Unit Tests")
    print("=" * 60)
    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd)
    
    print("-" * 60)
    if result.returncode == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ Tests failed (exit code: {result.returncode})")
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
