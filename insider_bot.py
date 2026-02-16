import os
import pandas as pd
import smtplib
import time
import cloudscraper
from email.message import EmailMessage

# CONFIG
USER = os.environ.get("EMAIL_USER")
PASS = os.environ.get("EMAIL_PASS")
DEST = os.environ.get("RECEIVER_EMAIL")

def monitor():
    # This library is what the 'working' GitHub repos use to stay invisible
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    url = "http://openinsider.com/insider-transactions-25k"

    try:
        response = scraper.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"Site blocked access. Code: {response.status_code}")
            return

        # Targeting the exact table class OpenInsider uses
        dfs = pd.read_html(response.text, attrs={"class": "tinytable"})
        if not dfs:
            print("Could not find the data table. The site layout might have changed.")
            return
        
        df = dfs[0].head(15) 

        # Memory using seen.txt
        if not os.path.exists("seen.txt"):
            open("seen.txt", "w").close()
        with open("seen.txt", "r") as f:
            seen = f.read().splitlines()

        new_trades = []
        for _, row in df.iterrows():
            ticker = str(row['Ticker'])
            if not ticker.isalpha(): continue # Skip ad rows
            
            # Create a unique ID for this trade
            tid = f"{ticker}_{row['Insider Name']}_{row['Value']}".replace(" ", "_")
            
            if tid not in seen:
                new_trades.append(f"• {ticker} | {row['Insider Name']} | {row['Value']}")
                with open("seen.txt", "a") as f:
                    f.write(tid + "\n")

        if new_trades:
            msg = EmailMessage()
            msg.set_content("\n".join(new_trades))
            msg['Subject'] = f"Insider Alert: {len(new_trades)} New Trades"
            msg['From'] = USER
            msg['To'] = DEST
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(USER, PASS)
                smtp.send_message(msg)
            print(f"Sent {len(new_trades)} new trades to {DEST}")
        else:
            print("No new trades found in this scan.")

    except Exception as e:
        print(f"Scraper Error: {e}")

# Main loop
while True:
    monitor()
    time.sleep(300)
