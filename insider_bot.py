import os
import pandas as pd
import smtplib
import time
import io
from email.message import EmailMessage
from curl_cffi import requests
from datetime import datetime

# --- CONFIG ---
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
RECEIVER = os.environ.get("RECEIVER_EMAIL")

def get_trade_id(row):
    return f"{row['Ticker']}_{row['Insider Name']}_{row['Value']}".replace(" ", "_")

def send_summary_email(trades_list):
    """Sends one email containing all new trades found in this scan."""
    print(f"📧 Sending summary email for {len(trades_list)} trades...")
    
    # Build the email body text
    body = "🚨 NEW INSIDER TRADES DETECTED 🚨\n\n"
    for t in trades_list:
        body += f"🔹 {t['Ticker']} | {t['Insider Name']} | {t['Trade Type']} | {t['Value']}\n"
        body += f"   Link: https://openinsider.com/{t['Ticker']}\n"
        body += "-------------------------------------------\n"
    
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = f"🔥 Insider Alert: {len(trades_list)} New Trades Found"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print("✅ Summary email sent!")
    except Exception as e:
        print(f"❌ EMAIL ERROR: {e}")

def monitor():
    url = "http://openinsider.com/insider-transactions-25k"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 1. Load Memory
    seen_ids = set()
    if os.path.exists("seen_trades.csv"):
        try:
            seen_df = pd.read_csv("seen_trades.csv")
            seen_ids = set(seen_df['trade_id'].astype(str).tolist())
        except:
            pass

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Fetching OpenInsider...")

    try:
        response = requests.get(url, headers=headers, impersonate="chrome110", timeout=30)
        
        if response.status_code == 200:
            dfs = pd.read_html(io.StringIO(response.text), match="Ticker")
            df = dfs[0]
            
            new_trades_to_report = []
            new_ids_for_csv = []

            # 2. Collect all new trades from the top 20 rows
            for _, row in df.head(20).iterrows():
                tid = get_trade_id(row)
                if tid not in seen_ids:
                    new_trades_to_report.append(row)
                    new_ids_for_csv.append({"trade_id": tid, "date": datetime.now()})
                    seen_ids.add(tid)

            # 3. If we found anything new, send ONE email and update CSV
            if new_trades_to_report:
                send_summary_email(new_trades_to_report)
                
                # Update memory file
                mem_df = pd.DataFrame(new_ids_for_csv)
                mem_df.to_csv("seen_trades.csv", mode='a', index=False, header=not os.path.exists("seen_trades.csv"))
            else:
                print("😴 No new trades found.")
        else:
            print(f"🚫 Status {response.status_code}")

    except Exception as e:
        print(f"⚠️ ERROR: {e}")

# --- RUN LOOP ---
start_time = time.time()
while (time.time() - start_time) < 20000:
    monitor()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 Waiting 5 minutes...")
    time.sleep(300)
