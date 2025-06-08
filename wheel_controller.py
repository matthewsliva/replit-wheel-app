import json
import datetime
import requests

# === Config === #
STATE_FILE = "bot_state.json"
WEBHOOK_URL = "http://localhost:8000/webhook"  # Replace with your external IP if needed

# === Helpers === #
def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"state": "cash", "shares_held": 0, "last_action": None}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def next_expiry():
    today = datetime.date.today()
    # Pick the 3rd Friday of next month
    year, month = (today.year, today.month + 1) if today.month < 12 else (today.year + 1, 1)
    third_friday = [d for d in range(15, 22) 
                    if datetime.date(year, month, d).weekday() == 4][0]
    return f"{year}-{month:02d}-{third_friday:02d}"

def build_signal(state):
    if state["state"] == "cash":
        # Recommend a new PUT
        return {
            "action": "sell_put",
            "symbol": "AAPL",
            "strike": 180.0,
            "expiry": next_expiry(),
            "premium": 1.50
        }
    elif state["state"] == "assigned":
        # Recommend a CALL if shares are held
        return {
            "action": "sell_call",
            "symbol": "AAPL",
            "strike": 190.0,
            "expiry": next_expiry(),
            "premium": 1.75
        }
    else:
        return None

def send_signal(signal):
    try:
        res = requests.post(WEBHOOK_URL, json=signal)
        return res.status_code, res.json()
    except Exception as e:
        return 500, {"error": str(e)}

# === Main Logic === #
if __name__ == "__main__":
    state = load_state()
    signal = build_signal(state)

    if not signal:
        print("[ERROR] Unknown bot state")
        exit(1)

    print("\n[Suggestion] Wheel Strategy Recommends:")
    print(json.dumps(signal, indent=2))

    approve = input("\nApprove this trade? (y/n): ").strip().lower()
    if approve == 'y':
        status, response = send_signal(signal)
        print("[Webhook Result]", status, response)

        # Update state
        if signal['action'] == 'sell_put':
            state['state'] = 'waiting_assignment'
        elif signal['action'] == 'sell_call':
            state['state'] = 'cash'  # Assume called away
            state['shares_held'] = 0

        state['last_action'] = signal
        save_state(state)
    else:
        print("[INFO] Trade not approved. Bot state unchanged.")
