import os
import pandas as pd
import smtplib
import time
from email.message import EmailMessage
from curl_cffi import requests
from datetime import datetime

# --- CONFIGURATION (Uses GitHub Secrets) ---
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
RECEIVER = os.environ.get("RECEIVER_EMAIL")

# A unique ID for each trade is usually a mix of Ticker, Name, and Date
def get_trade_id(row):
    return f"{row['Ticker']}_{row['Insider Name']}_{row['Filing Date']}_{row['Value']}"

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
        # This connects to Gmail's servers. Use smtp.office365.com for Outlook.
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"✅ Email sent for {trade_data['Ticker']}")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def monitor():
    url = "https://openinsider.com/insider-transactions-25k"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    # 1. Load "Memory" of trades we already emailed
    if os.path.exists("seen_trades.csv"):
        seen_df = pd.read_csv("seen_trades.csv")
        seen_ids = set(seen_df['trade_id'].tolist())
    else:
        seen_ids = set()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning OpenInsider...")

    try:
        response = requests.get(url, headers=headers, impersonate="chrome110", timeout=30)
        
        if response.status_code == 200:
            # We look for the table with the class 'tinytable'
            dfs = pd.read_html(response.text, attrs={"class": "tinytable"})
            df = dfs[0]
            
            new_entries = []
            
            # 2. Check each trade in the top 10 rows
            for _, row in df.head(10).iterrows():
                tid = get_trade_id(row)
                
                if tid not in seen_ids:
                    print(f"✨ New Trade Detected: {row['Ticker']}")
                    send_email(row)
                    new_entries.append({"trade_id": tid, "date_added": datetime.now()})
                    seen_ids.add(tid)

            # 3. Update the "Memory" file
            if new_entries:
                new_df = pd.DataFrame(new_entries)
                # Append to the CSV so we don't forget them
                new_df.to_csv("seen_trades.csv", mode='a', header=not os.path.exists("seen_trades.csv"), index=False)
        else:
            print(f"Status {response.status_code}: Blocked by OpenInsider.")

    except Exception as e:
        print(f"Error during scan: {e}")

# --- THE 5-MINUTE LOOP ---
# GitHub Actions allows a job to run for 6 hours max.
start_time = time.time()
while (time.time() - start_time) < 21000: # Run for 5.8 hours (21,000 seconds)
    monitor()
    print("Sleeping for 5 minutes...")
    time.sleep(300)
