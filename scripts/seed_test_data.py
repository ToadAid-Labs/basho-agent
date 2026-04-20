import requests
import json
import time

def seed_data():
    base_url = "http://127.0.0.1:5000"
    telegram_id = 12345
    
    print(f"Seeding data for Telegram ID: {telegram_id}")
    
    # 1. Initialize paper trading account
    resp = requests.post(f"{base_url}/api/paper-trading/initialize", json={"telegram_id": telegram_id})
    
    # 2. Open some positions that fit in $10,000
    positions = [
        {"symbol": "BTC", "quantity": 0.05, "price": 65000.0, "strategy": "trend_following"}, # $3250
        {"symbol": "ETH", "quantity": 1.0, "price": 3500.0, "strategy": "mean_reversion"},   # $3500
        {"symbol": "SOL", "quantity": 10.0, "price": 150.0, "strategy": "momentum"}          # $1500
    ]
    
    for pos in positions:
        pos["user_id"] = telegram_id
        resp = requests.post(f"{base_url}/api/paper-trading/open-position", json=pos)
        print(f"Open {pos['symbol']}: {resp.status_code}")
    
    # 3. Close SOL for some realized PnL
    time.sleep(1)
    close_pos = {"user_id": telegram_id, "symbol": "SOL", "quantity": 10.0, "price": 170.0, "notes": "Target reached"}
    resp = requests.post(f"{base_url}/api/paper-trading/close-position", json=close_pos)
    print(f"Close SOL: {resp.status_code}")
    
    # 4. Open SOL again to have it as an open position
    resp = requests.post(f"{base_url}/api/paper-trading/open-position", json={"user_id": telegram_id, "symbol": "SOL", "quantity": 5.0, "price": 168.0, "strategy": "momentum"})
    print(f"Open SOL again: {resp.status_code}")

if __name__ == "__main__":
    seed_data()
