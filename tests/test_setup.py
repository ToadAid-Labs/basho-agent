"""
Test script to verify bot setup and API functionality

Run this script to test your setup:
- Python environment
- Environment variables
- Trust Wallet API connection
"""

__test__ = False

import os
import sys
from typing import Dict, Any
from dotenv import load_dotenv
from tools.trust import TrustWalletAPI

# Load environment variables
load_dotenv()


def test_environment_variables():
    """Test if all required environment variables are set"""
    print("=" * 60)
    print("🔍 TEST 1: Environment Variables")
    print("=" * 60)

    required_vars = {
        "TWAK_ACCESS_ID": "Trust Wallet API Access ID",
        "TWAK_HMAC_SECRET": "Trust Wallet API HMAC Secret",
        "TELEGRAM_BOT_TOKEN": "Telegram Bot Token"
    }

    all_set = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value and value != f"your_{var.lower().replace('_', '')}_here":
            print(f"✅ {var}: {value[:10]}... ({description})")
        else:
            print(f"❌ {var}: Not set or using placeholder")
            all_set = False

    return all_set


def test_trust_wallet_api():
    """Test Trust Wallet API connection and basic functionality"""
    print("\n" + "=" * 60)
    print("🔍 TEST 2: Trust Wallet API")
    print("=" * 60)

    try:
        api = TrustWalletAPI()
        print(f"✅ TrustWalletAPI initialized")
        print(f"✅ Access ID: {api.access_id[:10]}...")
        print(f"✅ Base URL: {api.BASE_URL}")
        return True
    except ValueError as e:
        print(f"❌ API Initialization Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return False


def test_api_endpoints():
    """Test various API endpoints"""
    print("\n" + "=" * 60)
    print("🔍 TEST 3: API Endpoints")
    print("=" * 60)

    try:
        api = TrustWalletAPI()

        # Test 1: Search for USDC (common token)
        print("\n📡 Testing token search (USDC)...")
        results = api.search_token("USDC", "base")

        if results:
            print(f"✅ Search successful! Found {len(results)} tokens")
            for result in results[:3]:
                print(f"   - {result.get('symbol')}: {result.get('name')}")

            # Get price for first result
            token_address = results[0].get('address')
            if token_address:
                print(f"\n📡 Testing price endpoint...")
                price_data = api.get_price(token_address, vs_currency="usd", chain="base")
                price = price_data.get('price', 0)
                print(f"✅ Price endpoint successful!")
                print(f"   - Price: ${price:,.4f}")
        else:
            print("⚠️ No results found for USDC")

        # Test 2: Validate address
        print(f"\n📡 Testing address validation...")
        # Use a common USDC address on Base
        usdc_address = "0x833589fcd6ed6f7cba02c96dcbfc6c6c174b3c7c"
        validation = api.validate_address(usdc_address, "base")
        print(f"✅ Validation endpoint successful!")

        # Test 3: Get token info
        print(f"\n📡 Testing token info endpoint...")
        token_info = api.get_token_info(usdc_address, "base")
        print(f"✅ Token info endpoint successful!")
        print(f"   - Name: {token_info.get('name', 'N/A')}")
        print(f"   - Symbol: {token_info.get('symbol', 'N/A')}")
        print(f"   - Decimals: {token_info.get('decimals', 'N/A')}")

        return True

    except Exception as e:
        print(f"❌ API Endpoint Test Failed: {e}")
        return False


def test_price_helper():
    """Test the price helper function"""
    print("\n" + "=" * 60)
    print("🔍 TEST 4: Price Helper Function")
    print("=" * 60)

    try:
        from tools.trust import get_token_price

        print("📡 Testing get_token_price function...")
        price = get_token_price("USDC", "base")

        if price > 0:
            print(f"✅ Price helper successful!")
            print(f"   - USDC Price: ${price:,.4f}")
            return True
        else:
            print("⚠️ Price returned 0, but no error occurred")
            return False

    except Exception as e:
        print(f"❌ Price Helper Test Failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🚀 TELEGRAM TRADING BOT - SETUP VERIFICATION")
    print("=" * 60)

    # Run tests
    test1 = test_environment_variables()
    test2 = test_trust_wallet_api()
    test3 = test_api_endpoints()
    test4 = test_price_helper()

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    tests = [
        ("Environment Variables", test1),
        ("Trust Wallet API", test2),
        ("API Endpoints", test3),
        ("Price Helper", test4)
    ]

    for test_name, passed in tests:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    # Final verdict
    all_passed = all([test1, test2, test3, test4])

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! You're ready to run the bot.")
        print("=" * 60)
        print("\n📝 Next steps:")
        print("1. Run: python agent.py bot")
        print("2. Open Telegram and search for your bot")
        print("3. Try commands like: /price USDC, /search pepe")
    else:
        print("⚠️ SOME TESTS FAILED")
        print("=" * 60)
        print("\n🔧 Please fix the issues above before running the bot.")

    print("=" * 60 + "\n")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
