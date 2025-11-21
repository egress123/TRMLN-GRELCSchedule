import requests
import json
import os
import re
from playwright.sync_api import sync_playwright

# ===========================================
# SCRAPE GRE LOAD MANAGEMENT PAGE
# Target: Residential Interruptible Water Heating
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
        print(f"Page loaded successfully")
        
        # Initialize result
        result = {
            "today_probability": "Unknown",
            "today_time": "Unknown",
            "tomorrow_probability": "Unknown",
            "tomorrow_time": "Unknown",
            "last_updated": "Unknown"
        }
        
        # Extract last updated timestamp
        match = re.search(r'Last Updated:\s*(.+?)(?:\n|$)', body_text)
        if match:
            result["last_updated"] = match.group(1).strip()
        
        # Split by major sections
        # The format is:
        # Today   Program Type   Probability   Expected Time (CPT)
        # ...
        # Residential   Interruptible Water Heating   Unlikely   Undetermined
        # Next Day   Program Type   Probability   Expected Time (CPT)
        # ...
        # Residential   Interruptible Water Heating   Unlikely   Undetermined
        
        # Find the Today section
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
        
        # Find the Next Day section
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
            "tomorrow_probability": data["tomorrow_probability"],
            "tomorrow_time": data["tomorrow_time"],
            "last_updated": data["last_updated"]
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
            "tomorrow_probability": "Error",
            "tomorrow_time": "Check logs",
            "last_updated": "N/A"
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
