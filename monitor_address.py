import requests
import json
import time

def check_address(address):
    # Using public BaseScan API (Rate limited, but works for manual checks)
    url = f"https://api.basescan.org/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=5&sort=desc"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data["status"] == "1":
            txs = data["result"]
            print(f"--- Recent Activity for {address} ---")
            for tx in txs:
                # Basic parsing of transaction
                method = tx.get("functionName", "Transfer/Other").split("(")[0]
                value_eth = float(tx["value"]) / 10**18
                print(f"Time: {time.ctime(int(tx['timeStamp']))} | Method: {method} | Value: {value_eth:.4f} ETH | Hash: {tx['hash'][:10]}...")
        else:
            print(f"Error: {data['message']}")
    except Exception as e:
        print(f"Failed to fetch data: {e}")

if __name__ == "__main__":
    DEPLOYER_ADDR = "0x7daD356c8f480509d5761c208dC4ECb2518dDDA0"
    check_address(DEPLOYER_ADDR)
