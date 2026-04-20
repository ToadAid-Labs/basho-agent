import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.trust import TrustWalletAPI

# Test API instantiation
api = TrustWalletAPI()

# Check credentials
print('Access ID:', api.access_id[:20] + '...')
print('HMAC Secret: ************')
print()

# Test token search
print('Searching for USDC...')
results = api.search_token('USDC', 'base')
if results:
    print(f'Search successful! Found {len(results)} tokens')
    for r in results[:3]:
        print(f'  - {r.get("name")} ({r.get("symbol")}) - ${r.get("price", 0):.4f}')
else:
    print('No results from search')
print()

# Test price
if results:
    print('Getting price...')
    price = api.get_price(results[0]['address'], 'usd', 'base')
    print(f'Price: ${price.get("price", 0):,.4f}')
    print()
    print('All API tests passed!')
