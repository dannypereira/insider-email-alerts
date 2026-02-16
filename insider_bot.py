import os
import pandas as pd
from curl_cffi import requests # This mimics browser TLS fingerprints
from datetime import datetime
import time

def scan_insider_trades():
    # The URL for "Latest Filings"
    url = "https://openinsider.com/insider-transactions-25k"
    
    # We must look EXACTLY like a real browser to avoid "Connection Refused"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/ *;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Attempting to scan...")

    try:
        # 'impersonate' makes curl_cffi mimic Chrome's network handshake
        response = requests.get(url, headers=headers, impersonate="chrome110", timeout=30)
        
        if response.status_code == 200:
            # Look for the data table
            dfs = pd.read_html(response.text)
            # Table 11 is usually the main data table on OpenInsider
            df = dfs[11] 
            
            # Filter for only the top row (the most recent trade)
            latest_trade = df.iloc[0]
            print(f"Latest Trade Found: {latest_trade['Ticker']} by {latest_trade['Insider Name']}")
            
            # --- YOUR EMAIL LOGIC GOES HERE ---
            # Check if this trade is "new" (save the ID to a file to compare)
            
        else:
            print(f"Status Code {response.status_code}. They might be blocking the IP.")

    except Exception as e:
        print(f"Connection Error: {e}")

# Run the scan
scan_insider_trades()
