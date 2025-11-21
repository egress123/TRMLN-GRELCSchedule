import requests
import json
import os
import re
from datetime import datetime, timedelta
import pytz
from playwright.sync_api import sync_playwright

# ===========================================
# SCRAPE GRE LOAD MANAGEMENT PAGE
# Target: Residential Interruptible Water Heating + Conservation Gauge
# ===========================================

def scrape_lmguide():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Loading lmguide.grenergy.com...")
        page.goto("https://lmguide.grenergy.com", wait_until="networkidle")
        page.wait_for_timeout(5000)  # Wait 5 seconds for JS to fully render
        
        # Get full page text
        body_text = page.inner_text("body")
        print(f"Main page loaded successfully")
        
        # Get today's and tomorrow's dates in Central Time
        central = pytz.timezone('America/Chicago')
        now_central = datetime.now(central)
        today_date = now_central.strftime('%m/%d')
        tomorrow_date = (now_central + timedelta(days=1)).strftime('%m/%d')
        
        # Get current timestamp for when plugin refreshed
        refresh_time = now_central.strftime('%m/%d/%Y %I:%M %p CST')
        
        # Initialize result
        result = {
            "today_probability": "Unknown",
            "today_time": "Unknown",
            "today_date": today_date,
            "tomorrow_probability": "Unknown",
            "tomorrow_time": "Unknown",
            "tomorrow_date": tomorrow_date,
            "last_updated": "Unknown",
            "conservation_status": "Unknown",
            "refresh_time": refresh_time
        }
        
        # Extract last updated timestamp
        match = re.search(r'Last Updated:\s*(.+?)(?:\n|$)', body_text)
        if match:
            result["last_updated"] = match.group(1).strip()
        
        # Find the Today section for water heating
        today_section = re.search(
            r'Today\s+Program Type\s+Probability\s+Expected Time.*?' +
            r'Residential\s+Interruptible Water Heating\s+(\w+)\s+([^\n]+)',
            body_text,
            re.DOTALL
        )
        
        if today_section:
            result["today_probability"] = today_section.group(1).strip()
            result["today_time"] = today_section.group(2).strip()
            print(f"Today: {result['today_probability']} at {result['today_time']}")
        
        # Find the Next Day section for water heating
        nextday_section = re.search(
            r'Next Day\s+Program Type\s+Probability\s+Expected Time.*?' +
            r'Residential\s+Interruptible Water Heating\s+(\w+)\s+([^\n]+)',
            body_text,
            re.DOTALL
        )
        
        if nextday_section:
            result["tomorrow_probability"] = nextday_section.group(1).strip()
            result["tomorrow_time"] = nextday_section.group(2).strip()
            print(f"Tomorrow: {result['tomorrow_probability']} at {result['tomorrow_time']}")
        
        # ===========================================
        # NOW SCRAPE CONSERVATION GAUGE
        # ===========================================
        print("Loading conservation gauge page...")
        page.goto("https://lmguide.grenergy.com/Conservation_Gauge.aspx", wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        # Look for the gauge image
        images = page.query_selector_all("img")
        for img in images:
            src = img.get_attribute("src")
            if src and "gauge" in src.lower():
                print(f"Found gauge image: {src}")
                
                # Determine conservation status based on image
                if "gauge1.jpg" in src.lower():
                    result["conservation_status"] = "Normal Usage"
                elif "gauge2.jpg" in src.lower():
                    result["conservation_status"] = "Elevated Usage"
                elif "gauge3.jpg" in src.lower():
                    result["conservation_status"] = "Peak Usage"
                elif "gauge4.jpg" in src.lower():
                    result["conservation_status"] = "Critical Usage"
                break
        
        print(f"Conservation Status: {result['conservation_status']}")
        print(f"Extracted data: {json.dumps(result, indent=2)}")
        
        browser.close()
        return result

# ===========================================
# MAIN
# ===========================================
try:
    print("Starting GRE Load Management scraper...")
    data = scrape_lmguide()
    
    # Build payload for TRMNL (max 2kb!)
    payload = {
        "merge_variables": {
            "today_probability": data["today_probability"],
            "today_time": data["today_time"],
            "today_date": data["today_date"],
            "tomorrow_probability": data["tomorrow_probability"],
            "tomorrow_time": data["tomorrow_time"],
            "tomorrow_date": data["tomorrow_date"],
            "conservation_status": data["conservation_status"],
            "last_updated": data["last_updated"],
            "refresh_time": data["refresh_time"]
        }
    }
    
    print(f"\n=== PAYLOAD FOR TRMNL ===\n{json.dumps(payload, indent=2)}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    payload = {
        "merge_variables": {
            "today_probability": "Error",
            "today_time": str(e)[:100],
            "today_date": "N/A",
            "tomorrow_probability": "Error",
            "tomorrow_time": "Check logs",
            "tomorrow_date": "N/A",
            "conservation_status": "Unknown",
            "last_updated": "N/A"
            "refresh_time": "N/A"
            
        }
    }

# ===========================================
# SEND TO TRMNL
# ===========================================
webhook_url = os.environ.get('TRMNL_WEBHOOK_URL')

if not webhook_url:
    print("ERROR: TRMNL_WEBHOOK_URL not set!")
    print("Skipping webhook send - set TRMNL_WEBHOOK_URL secret in GitHub")
else:
    print("\nSending to TRMNL...")
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"TRMNL Response: {response.status_code}")
        print(f"TRMNL Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✓ Successfully sent to TRMNL!")
        else:
            print(f"✗ TRMNL returned status {response.status_code}")
            
    except requests.RequestException as e:
        print(f"ERROR sending to TRMNL: {e}")
