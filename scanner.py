import os
import smtplib
import pandas as pd
import yfinance as yf
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# --- CONFIGURATION ---
# These lines pull the "Secrets" we saved in Step 2
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
RECEIVER = os.getenv('RECEIVER_EMAIL')
MIN_VALUE = 50000
START_DATE = "2026-02-01"

def send_email(subject, body):
    """This function handles the actual mailing process."""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    # Connecting to Google's mail server
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, RECEIVER, msg.as_string())

def get_trades():
    """This function scrapes the website for insider buys."""
    url = "http://openinsider.com/screener-opt"
    # We ask for: 100 rows, Type=Purchase, Min Value=$50k
    params = {'cnt': 100, 't': 'p', 'minval': '50', 'sortcol': '0'}
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, params=params, headers=headers)
        # Convert the website table into a data list
        from io import StringIO
df = pd.read_html(StringIO(response.text))[-1]
        df.columns = [c.replace(' ', '_').lower() for c in df.columns]
        
        # Filter: Must be 'P - Purchase', over $50k, and after Feb 1, 2026
        df['value'] = pd.to_numeric(df['value'].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        filtered_df = df[
            (df['trade_type'] == 'P - Purchase') & 
            (df['value'] >= MIN_VALUE) & 
            (df['trade_date'] >= pd.to_datetime(START_DATE))
        ]
        return filtered_df
    except:
        return pd.DataFrame()

# --- MAIN EXECUTION ---
# 1. Load the "Seen Trades" list so we don't email you twice for the same buy
try:
    seen_ids = pd.read_csv('seen_trades.csv')['id'].tolist()
except:
    seen_ids = []

trades = get_trades()
new_trades_found = []

# 2. Loop through every trade found on the site
for _, row in trades.iterrows():
    # Create a unique 'ID' for this specific trade
    trade_id = f"{row['ticker']}_{row['value']}_{row['trade_date'].strftime('%Y%m%d')}"
    
    if trade_id not in seen_ids:
        # 3. Get extra info (Market Cap, Industry, Live Price)
        stock = yf.Ticker(row['ticker'])
        info = stock.info
        hist = stock.history(period='1d')
        price_now = hist['Close'].iloc[-1] if not hist.empty else 0
        
        # 4. Calculate Gain %
        gain = ((price_now - row['price']) / row['price'] * 100)
        
        # 5. Build the Email Message
        subject = f"🚀 Insider Buy: {row['ticker']} (${row['value']:,.0f})"
        body = (
            f"Ticker: {row['ticker']}\n"
            f"Company: {info.get('longName', 'N/A')}\n"
            f"Industry: {info.get('industry', 'N/A')}\n"
            f"Market Cap: ${info.get('marketCap', 0):,.0f}\n"
            f"Insider: {row['insider_name']} ({row['title']})\n"
            f"Total Value: ${row['value']:,.0f}\n"
            f"Date of Purchase: {row['trade_date'].strftime('%Y-%m-%d')}\n\n"
            f"Price at Buy: ${row['price']:.2f}\n"
            f"Current Price: ${price_now:.2f}\n"
            f"Gain Since Buy: {gain:+.2f}%\n"
        )
        
        print(f"New trade found for {row['ticker']}! Sending email...")
        send_email(subject, body)
        new_trades_found.append(trade_id)

# 6. Save the new trades to the "Seen" list
if new_trades_found:
    updated_ids = seen_ids + new_trades_found
    pd.DataFrame(updated_ids, columns=['id']).to_csv('seen_trades.csv', index=False)
