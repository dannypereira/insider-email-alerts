import os
import smtplib
import pandas as pd
from io import StringIO
from email.message import EmailMessage
from curl_cffi import requests

# --- CONFIGURATION ---
# Switched to HTTPS for better security/compatibility
URL = "https://openinsider.com/insider-transactions-25k"
CSV_FILE = "seen_trades.csv"

# Environment Variables from GitHub Secrets
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

def send_email(subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER_EMAIL

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

def run_scanner():
    print("--- STARTING SCAN ---")
    
    # Enhanced headers to look like a genuine user session
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://openinsider.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        print(f"Step 1: Contacting {URL}...")
        # Using chrome110 impersonation which is very stable
        response = requests.get(URL, headers=headers, impersonate="chrome110", timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if "Table" not in response.text and "Ticker" not in response.text:
            print("⚠️ WARNING: Table keywords not found in response.")
            print("--- HTML SNIPPET (DEBUG) ---")
            print(response.text[:1000]) # See what the site actually sent us
            print("--- END SNIPPET ---")

        print("Step 2: Parsing table...")
        tables = pd.read_html(StringIO(response.text))
        
        # OpenInsider's main data table is usually the one with the most rows
        if not tables:
            print("💥 CRITICAL ERROR: No tables found at all.")
            return

        # Find the table that actually contains trade data
        df = None
        for t in tables:
            if 'Ticker' in t.columns:
                df = t
                break
        
        if df is None:
            print("💥 ERROR: Found tables, but none contained 'Ticker' column.")
            return

        # Clean up column names
        df.columns = [str(c).replace('\xa0', ' ') for c in df.columns]
        
        relevant_cols = ['Filing Date', 'Ticker', 'Insider Name', 'Title', 'Trade Type', 'Price', 'Qty', 'Value']
        df = df[relevant_cols]

        # Step 3: Deduplication Logic
        if os.path.exists(CSV_FILE):
            try:
                seen_df = pd.read_csv(CSV_FILE)
            except:
                seen_df = pd.DataFrame(columns=relevant_cols)
        else:
            seen_df = pd.DataFrame(columns=relevant_cols)

        # Create unique IDs
        df['temp_id'] = df['Filing Date'].astype(str) + df['Ticker'] + df['Value'].astype(str)
        seen_ids = (seen_df['Filing Date'].astype(str) + seen_df['Ticker'] + seen_df['Value'].astype(str)).tolist()
        
        new_trades = df[~df['temp_id'].isin(seen_ids)].copy()
        new_trades.drop(columns=['temp_id'], inplace=True)

        if not new_trades.empty:
            print(f"🎯 Found {len(new_trades)} new trades!")
            email_body = "New Insider Trades Detected:\n\n" + new_trades.to_string(index=False)
            send_email(f"🚨 Insider Alert: {len(new_trades)} New Trades", email_body)
            
            updated_df = pd.concat([new_trades, seen_df]).head(500)
            updated_df.to_csv(CSV_FILE, index=False)
        else:
            print("😴 No new trades found.")

    except Exception as e:
        print(f"💥 ERROR: {e}")
        if not os.path.exists(CSV_FILE):
            pd.DataFrame().to_csv(CSV_FILE, index=False)

    print("--- SCAN FINISHED ---")

if __name__ == "__main__":
    run_scanner()
