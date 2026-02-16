import os
import pandas as pd
import smtplib
import time
from email.message import EmailMessage
from curl_cffi import requests
from datetime import datetime

# --- CONFIGURATION ---
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
RECEIVER = os.environ.get("RECEIVER_EMAIL")

def get_trade_id(row):
    # This creates a unique fingerprint for the trade
    return f"{row['Ticker']}_{row['Insider Name']}_{row['Value']}".replace(" ", "_")

def send_email(trade_data):
    msg = EmailMessage()
    msg.set_content(f"""
    🚨 NEW INSIDER TRADE DETECTED 🚨
    
    Ticker: {trade_data['Ticker']}
    Insider: {trade_data['Insider Name']} ({trade_data['Title']})
    Trade Type: {trade_data['Trade Type']}
    Price: {trade_data['Price']}
    Value: {trade_data['Value']}
    
    View here: https://openinsider.com/{trade_data['Ticker']}
    """)
    
    msg['Subject'] = f"🔥 Insider Buy: {trade_data['Ticker']} ({trade_data['Value']})"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"✅ Email sent for {trade_data['Ticker']}")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def monitor():
    url = "https://openinsider.com/insider-transactions-25k"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # --- SMARTER MEMORY LOADING ---
    seen_ids = set()
    if os.path.exists("seen_trades.csv"):
        try:
            seen_df = pd.read_csv("seen_trades.csv")
            if 'trade_id' in seen_df.columns:
                seen_ids = set(seen_df['trade_id'].astype(str).tolist())
            else:
                print("⚠️ Memory file was malformed. Starting fresh.")
        except Exception:
            print("⚠️ Could not read memory file. Starting fresh.")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning...")

    try:
        # Use curl_cffi to bypass blocks
        response = requests.get(url, headers=headers, impersonate="chrome110", timeout=30)
        
        if response.status_code == 200:
            # OpenInsider's main data is usually the only large table
            dfs = pd.read_html(response.text)
            # We look for the dataframe that has 'Ticker' in it
            df = None
            for d in dfs:
                if 'Ticker' in d.columns:
                    df = d
                    break
            
            if df is None:
                print("❌ Could not find the data table on the page.")
                return

            new_entries = []
            # Check the top 5 most recent trades
            for _, row in df.head(5).iterrows():
                tid = get_trade_id(row)
                
                if tid not in seen_ids:
                    print(f"✨ NEW: {row['Ticker']} by {row['Insider Name']}")
                    send_email(row)
                    new_entries.append({"trade_id": tid, "date_added": datetime.now()})
                    seen_ids.add(tid)

            # --- SAVE MEMORY ---
            if new_entries:
                new_df = pd.DataFrame(new_entries)
                # Append to file, create header only if file doesn't exist
                file_exists = os.path.isfile("seen_trades.csv")
                new_df.to_csv("seen_trades.csv", mode='a', index=False, header=not file_exists)
                print(f"💾 Saved {len(new_entries)} new trades to memory.")
        else:
            print(f"🚫 Blocked! Status: {response.status_code}")

    except Exception as e:
        print(f"⚠️ Error: {e}")

# --- RUN LOOP ---
start_time = time.time()
# Run for ~5.5 hours then stop (so GitHub can restart a fresh one)
while (time.time() - start_time) < 20000:
    monitor()
    time.sleep(300) # 5 minutes
