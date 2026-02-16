import os
import smtplib
import requests
import pandas as pd
from io import StringIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- SETTINGS ---
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
RECEIVER = os.getenv('RECEIVER_EMAIL')
MIN_VALUE = 50000 
START_DATE = "2026-02-01"

def send_email(ticker, insider, value, date):
    print(f"📧 Attempting to send email for {ticker}...")
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg['Subject'] = f"🚀 Insider Buy: {ticker} (${value:,.0f})"
    
    body = f"Ticker: {ticker}\nInsider: {insider}\nValue: ${value:,.0f}\nDate: {date}"
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, RECEIVER, msg.as_string())
        print(f"✅ SUCCESS: Email sent for {ticker}")
    except Exception as e:
        print(f"❌ ERROR: Email failed for {ticker}. Reason: {e}")

# --- THE LOGIC ---
print("--- STARTING SCAN ---")

url = "http://openinsider.com/screener-opt"
params = {'cnt': 100, 't': 'p', 'minval': '50', 'sortcol': '0'}
headers = {"User-Agent": "Mozilla/5.0"}

try:
    print("Step 1: Contacting OpenInsider...")
    response = requests.get(url, params=params, headers=headers)
    
    print("Step 2: Parsing table (No warnings allowed!)...")
    # This is the modern way to do it
    df = pd.read_html(StringIO(response.text))[-1]
    
    print(f"Step 3: Found {len(df)} total rows. Cleaning names...")
    df.columns = [c.replace(' ', '_').lower() for c in df.columns]
    
    # Convert 'value' to numbers
    df['value'] = pd.to_numeric(df['value'].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
    
    print("Step 4: Applying filters...")
    matches = df[
        (df['trade_type'] == 'P - Purchase') & 
        (df['value'] >= MIN_VALUE) & 
        (df['trade_date'] >= START_DATE)
    ]
    
    print(f"Step 5: Found {len(matches)} matches after filtering.")

    for index, row in matches.iterrows():
        send_email(row['ticker'], row['insider_name'], row['value'], row['trade_date'])

except Exception as e:
    print(f"💥 CRITICAL ERROR: {e}")

print("--- SCAN FINISHED ---")
