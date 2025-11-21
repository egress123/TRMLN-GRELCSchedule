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
        
        # Parse the schedule using text parsing
        lines = body_text.split('\n')
        
        # Find "Today" section
        today_found = False
        nextday_found = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Look for the Today section header
            if line == "Today":
                today_found = True
                nextday_found = False
                continue
            
            # Look for the Next Day section header
            if line == "Next Day":
                today_found = False
                nextday_found = True
                continue
            
            # When we find "Residential Interruptible Water Heating"
            if "Residential" in line and "Interruptible Water Heating" in line:
                # The next lines should contain probability and time
                # Look ahead to find the data
                
                # Sometimes the data is on the same line, sometimes separate
                # Let's check the next few lines
                for j in range(i+1, min(i+5, len(lines))):
                    next_line = lines[j].strip()
                    
                    # Check if this line has probability keywords
                    if any(prob in next_line for prob in ["Unlikely", "Possible", "Likely", "Scheduled"]):
                        if today_found:
                            result["today_probability"] = next_line
                        elif nextday_found:
                            result["tomorrow_probability"] = next_line
                    
                    # Check if this line has time info
                    if "Undetermined" in next_line or ":" in next_line or "AM" in next_line or "PM" in next_line:
                        if today_found:
                            result["today_time"] = next_line
                        elif nextday_found:
                            result["tomorrow_time"] = next_line
        
        # Alternative parsing: use regex to find the pattern
        # Pattern: Residential\s+Interruptible Water Heating\s+(\w+)\s+(.+)
        today_match = re.search(
            r'Today.*?Residential\s+Interruptible Water Heating\s+(\w+)\s+([^\n]+)',
            body_text,
            re.DOTALL
        )
        if today_match:
            result["today_probability"] = today_match.group(1).strip()
            result["today_time"] = today_match.group(2).strip()
        
        nextday_match = re.search(
            r'Next Day.*?Residential\s+Interruptible Water Heating\s+(\w+)\s+([^\n]+)',
            body_text,
            re.DOTALL
        )
        if nextday_match:
            result["tomorrow_probability"] = nextday_match.group(1).strip()
            result["tomorrow_time"] = nextday_match.group(2).strip()
        
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
