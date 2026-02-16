import os
import smtplib
import pandas as pd
import requests
from io import StringIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- SETTINGS ---
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
RECEIVER = os.getenv('RECEIVER_EMAIL')
MIN_VALUE = 50000 
START_DATE = "2026-02-01"

def send_email(ticker, insider, value, date, price):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg['Subject'] = f"🚀 TEST ALERT: {ticker} bought by {insider}"
    
    body = (f"We found a trade!\n\n"
            f"Ticker: {ticker}\n"
            f"Insider: {insider}\n"
            f"Amount: ${value:,.0f}\n"
            f"Price: ${price}\n"
            f"Date: {date}")
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, RECEIVER, msg.as_string())
        print(f"✅ EMAIL SENT for {ticker}")
    except Exception as e:
        print(f"❌ EMAIL FAILED: {e}")

# --- MAIN LOGIC ---
print("--- STARTING SCAN ---")

url = "http://openinsider.com/screener-opt"
params = {'cnt': 100, 't': 'p', 'minval': '50', 'sortcol': '0'}
headers = {"User-Agent": "Mozilla/5.0"}

try:
    response = requests.get(url, params=params, headers=headers)
    print("Website loaded. Processing table...")

    # THIS FIXES THE WARNING
    html_data = StringIO(response.text)
    df = pd.read_html(html_data)[-1]
    
    # CLEAN UP DATA
    df.columns = [c.replace(' ', '_').lower() for c in df.columns]
    df['value'] = pd.to_numeric(df['value'].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
    df['trade_date'] = pd.to_datetime(df['trade_date'])

    # FILTER
    # 1. Must be a Purchase
    # 2. Must be over $50k
    # 3. Must be after Feb 1st
    matches = df[
        (df['trade_type'] == 'P - Purchase') & 
        (df['value'] >= MIN_VALUE) & 
        (df['trade_date'] >= START_DATE)
    ]
    
    print(f"Found {len(matches)} trades matching your criteria.")

    # SEND EMAILS FOR ALL OF THEM (IGNORING HISTORY)
    for index, row in matches.iterrows():
        send_email(
            row['ticker'], 
            row['insider_name'], 
            row['value'], 
            row['trade_date'].strftime('%Y-%m-%d'),
            row['price']
        )

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
