import os
import smtplib
import pandas as pd
from io import StringIO
from email.message import EmailMessage
from curl_cffi import requests

# --- CONFIGURATION ---
URL = "http://openinsider.com/insider-transactions-25k"
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
    
    # Using curl_cffi to impersonate a Chrome browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        print("Step 1: Contacting OpenInsider via curl_cffi...")
        response = requests.get(URL, headers=headers, impersonate="chrome110")
        
        print("Step 2: Parsing table...")
        # We look for the table containing 'Ticker' to avoid layout garbage
        tables = pd.read_html(StringIO(response.text), match="Ticker")
        
        if not tables:
            print("💥 CRITICAL ERROR: No tables found. Site layout might have changed.")
            return

        df = tables[0]
        
        # Clean up column names (OpenInsider sometimes has weird spacing)
        df.columns = [str(c).replace('\xa0', ' ') for c in df.columns]
        
        # We only care about the core columns
        # OpenInsider cols: ['X', 'Filing Date', 'Trade Date', 'Ticker', 'Company Name', 'Insider Name', 'Title', 'Trade Type', 'Price', 'Qty', 'Owned', 'ΔOwn', 'Value']
        relevant_cols = ['Filing Date', 'Ticker', 'Insider Name', 'Title', 'Trade Type', 'Price', 'Qty', 'Value']
        df = df[relevant_cols]

        # Step 3: Load or create the 'seen trades' database
        if os.path.exists(CSV_FILE):
            seen_df = pd.read_csv(CSV_FILE)
        else:
            seen_df = pd.DataFrame(columns=relevant_cols)
            seen_df.to_csv(CSV_FILE, index=False)

        # Step 4: Identify NEW trades
        # We create a unique ID by combining Filing Date, Ticker, and Value
        df['temp_id'] = df['Filing Date'].astype(str) + df['Ticker'] + df['Value'].astype(str)
        seen_ids = (seen_df['Filing Date'].astype(str) + seen_df['Ticker'] + seen_df['Value'].astype(str)).tolist()
        
        new_trades = df[~df['temp_id'].isin(seen_ids)].copy()
        new_trades.drop(columns=['temp_id'], inplace=True)

        if not new_trades.empty:
            print(f"🎯 Found {len(new_trades)} new trades!")
            
            # Prepare Email Content
            email_body = "New Insider Trades Detected:\n\n"
            email_body += new_trades.to_string(index=False)
            
            send_email(f"🚨 Insider Alert: {len(new_trades)} New Trades", email_body)
            
            # Update the CSV so we don't alert on these again
            updated_df = pd.concat([new_trades, seen_df]).head(500) # Keep last 500
            updated_df.to_csv(CSV_FILE, index=False)
        else:
            print("😴 No new trades found since last scan.")

    except Exception as e:
        print(f"💥 ERROR: {e}")
        # Ensure the file exists even on failure so Git doesn't complain
        if not os.path.exists(CSV_FILE):
            pd.DataFrame().to_csv(CSV_FILE)

    print("--- SCAN FINISHED ---")

if __name__ == "__main__":
    run_scanner()
