import requests
import json
import os

ADDRESS = "0x7daD356c8f480509d5761c208dC4ECb2518dDDA0"
RPC_URL = "https://mainnet.base.org"
STATE_FILE = "workspace/stalker_state.json"

def get_tx_count(addr):
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getTransactionCount",
        "params": [addr, "latest"],
        "id": 1
    }
    response = requests.post(RPC_URL, json=payload).json()
    return int(response['result'], 16)

def get_balance(addr):
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [addr, "latest"],
        "id": 1
    }
    response = requests.post(RPC_URL, json=payload).json()
    return int(response['result'], 16) / 10**18

def run_check():
    current_count = get_tx_count(ADDRESS)
    current_balance = get_balance(ADDRESS)
    
    last_count = 0
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            last_count = state.get("last_count", 0)
    
    if current_count > last_count:
        print(f"🚨 ALERT: New activity detected! Total TXs: {current_count}")
        print(f"Current Balance: {current_balance:.4f} ETH")
        # Update state
        with open(STATE_FILE, 'w') as f:
            json.dump({"last_count": current_count, "balance": current_balance}, f)
        return True
    else:
        print("✅ No new activity since last check.")
        return False

if __name__ == "__main__":
    run_check()
