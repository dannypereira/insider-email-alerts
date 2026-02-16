import os
import smtplib
import pandas as pd
import yfinance as yf
import requests
from io import StringIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# --- CONFIGURATION ---
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
RECEIVER = os.getenv('RECEIVER_EMAIL')
MIN_VALUE = 50000
START_DATE = "2026-02-01"

def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, RECEIVER, msg.as_string())

def get_trades():
    url = "http://openinsider.com/screener-opt"
    params = {'cnt': 100, 't': 'p', 'minval': '50', 'sortcol': '0'}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print("--- CONNECTING TO OPENINSIDER ---")
    response = requests.get(url, params=params, headers=headers)
    
    # 1. Check if the website actually loaded
    if response.status_code != 200:
        print(f"ERROR: Website blocked us. Status Code: {response.status_code}")
        return pd.DataFrame()

    print("Website loaded successfully. Reading table...")
    
    # 2. Fix the FutureWarning using StringIO
    try:
        # Wrap the text in StringIO to make pandas happy
        html_data = StringIO(response.text)
        dfs = pd.read_html(html_data)
        
        if not dfs:
            print("ERROR: No tables found on the page.")
            return pd.DataFrame()
            
        df = dfs[-1]
        print(f"Found raw table with {len(df)} rows.")
        
        # Clean column names
        df.columns = [c.replace(' ', '_').lower() for c in df.columns]
        
        # Clean numeric data
        df['value'] = pd.to_numeric(df['value'].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        # 3. Apply Filters and PRINT the results
        # Filter 1: Type
        df = df[df['trade_type'] == 'P - Purchase']
        print(f"Rows after 'Purchase' filter: {len(df)}")
        
        # Filter 2: Value
        df = df[df['value'] >= MIN_VALUE]
        print(f"Rows after '${MIN_VALUE}' filter: {len(df)}")
        
        # Filter 3: Date
        df = df[df['trade_date'] >= pd.to_datetime(START_DATE)]
        print(f"Rows after Date ({START_DATE}) filter: {len(df)}")
        
        return df

    except Exception as e:
        print(f"CRITICAL ERROR parsing data: {e}")
        return pd.DataFrame()

# --- MAIN EXECUTION ---
print("Starting Scan...")

# Load History
try:
    seen_ids = pd.read_csv('seen_trades.csv')['id'].tolist()
    print(f"Loaded {len(seen_ids)} previously seen trades.")
except:
    print("No history file found. Starting fresh.")
    seen_ids = []

# Get New Trades
trades = get_trades()
new_trades_found = []

if trades.empty:
    print("No trades match your criteria right now.")
else:
    print(f"Processing {len(trades)} potential trades...")

for _, row in trades.iterrows():
    # Create ID
    trade_id = f"{row['ticker']}_{row['value']}_{row['trade_date'].strftime('%Y%m%d')}"
    
    if trade_id in seen_ids:
        print(f"Skipping {row['ticker']} (Already seen).")
        continue

    # Enrich Data
    print(f"Fetching data for {row['ticker']}...")
    try:
        stock = yf.Ticker(row['ticker'])
        hist = stock.history(period='1d')
        price_now = hist['Close'].iloc[-1] if not hist.empty else 0
        gain = ((price_now - row['price']) / row['price'] * 100) if row['price'] else 0
        
        subject = f"🚀 Insider Buy: {row['ticker']} (${row['value']:,.0f})"
        body = (
            f"Ticker: {row['ticker']}\n"
            f"Insider: {row['insider_name']}\n"
            f"Total: ${row['value']:,.0f}\n"
            f"Date: {row['trade_date'].strftime('%Y-%m-%d')}\n"
            f"Gain: {gain:+.2f}%"
        )
        
        print(f"Sending email for {row['ticker']}...")
        send_email(subject, body)
        new_trades_found.append(trade_id)
        
    except Exception as e:
        print(f"Error processing {row['ticker']}: {e}")

# Save History
if new_trades_found:
    print(f"Saving {len(new_trades_found)} new trades to history.")
    updated_ids = seen_ids + new_trades_found
    pd.DataFrame(updated_ids, columns=['id']).to_csv('seen_trades.csv', index=False)
else:
    print("Scan complete. No new emails sent.")
