#!/usr/bin/env python3
"""
Setup Verification Script
Verifies the execution layer setup and all dependencies
"""

import sys
import os


def check_module(module_name):
    """Check if a module can be imported"""
    try:
        __import__(module_name)
        return True, "✅"
    except ImportError as e:
        return False, f"❌ {str(e)}"


def check_file(filename):
    """Check if a file exists"""
    return os.path.exists(filename), "✅" if os.path.exists(filename) else "❌"


def check_directory(directory):
    """Check if a directory exists"""
    return os.path.exists(directory), "✅" if os.path.exists(directory) else "❌"


def main():
    """Run all verification checks"""
    print("\n" + "=" * 60)
    print("EXECUTION LAYER SETUP VERIFICATION")
    print("=" * 60)

    results = []

    # Check modules
    print("\n📋 MODULES:")
    modules = [
        ("execution_layer", "Main execution layer"),
        ("trust_wallet", "Trust Wallet API client"),
        ("market_analyzer", "Market analysis module"),
        ("models", "Data models"),
        ("utils", "Utility functions")
    ]

    for module, description in modules:
        status, symbol = check_module(module)
        results.append(status)
        print(f"   {symbol} {module:20s} - {description}")

    # Check files
    print("\n📄 FILES:")
    files = [
        ("requirements.txt", "Python dependencies"),
        (".env.example", "Environment variables template"),
        ("README.md", "Project documentation"),
        ("EXECUTION_LAYER_README.md", "Execution layer documentation"),
        ("demo_simple.py", "Simple demo script"),
        ("execution_layer.py", "Main execution layer implementation"),
        ("trust_wallet.py", "Trust Wallet API client"),
        ("market_analyzer.py", "Market analysis module")
    ]

    for filename, description in files:
        status, symbol = check_file(filename)
        results.append(status)
        print(f"   {symbol} {filename:25s} - {description}")

    # Check directories
    print("\n📁 DIRECTORIES:")
    directories = [
        ("tests", "Test directory"),
        ("config", "Configuration files")
    ]

    for directory, description in directories:
        status, symbol = check_directory(directory)
        results.append(status)
        print(f"   {symbol} {directory:20s} - {description}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"\n✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {failed}/{total}")

    if failed == 0:
        print("\n🎉 All checks passed! Setup is complete.")
        print("\n📚 Next steps:")
        print("   1. Copy .env.example to .env and configure:")
        print("      cp .env.example .env")
        print("   2. Install dependencies:")
        print("      pip install -r requirements.txt")
        print("   3. Run the demo:")
        print("      python demo_simple.py")
        print("   4. Read the documentation:")
        print("      cat EXECUTION_LAYER_README.md")
        return 0
    else:
        print(f"\n⚠️  {failed} check(s) failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())