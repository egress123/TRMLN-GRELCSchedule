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
        
        # Get full page text for debugging
        body_text = page.inner_text("body")
        print(f"=== FULL PAGE TEXT ===\n{body_text}\n=== END ===")
        
        # Initialize result
        result = {
            "today_control": "Unknown",
            "today_times": "N/A",
            "today_probability": "N/A",
            "tomorrow_control": "Unknown",
            "tomorrow_times": "N/A",
            "tomorrow_probability": "N/A",
            "last_updated": "N/A"
        }
        
        # Try to find last updated timestamp
        try:
            if "Last Updated:" in body_text:
                match = re.search(r'Last Updated:\s*([^\n]+)', body_text)
                if match:
                    result["last_updated"] = match.group(1).strip()
        except Exception as e:
            print(f"Error getting last updated: {e}")
        
        # Look for Interruptible Water Heating section
        # The page likely has tables or sections for each program type
        
        # Try to find tables
        tables = page.query_selector_all("table")
        print(f"Found {len(tables)} tables")
        
        for i, table in enumerate(tables):
            table_text = table.inner_text()
            print(f"=== TABLE {i} ===\n{table_text}\n")
            
            # Check if this table contains water heating info
            if "Water" in table_text or "water" in table_text:
                print(f">>> Found water heating in table {i}")
                
                # Try to parse rows
                rows = table.query_selector_all("tr")
                for row in rows:
                    row_text = row.inner_text().lower()
                    if "interruptible" in row_text and "water" in row_text:
                        cells = row.query_selector_all("td")
                        cell_texts = [c.inner_text().strip() for c in cells]
                        print(f"Water heating row: {cell_texts}")
                        
                        # Extract based on column structure
                        # (adjust indices based on actual table structure)
                        if len(cell_texts) >= 3:
                            result["today_times"] = cell_texts[1] if len(cell_texts) > 1 else "N/A"
                            result["today_probability"] = cell_texts[2] if len(cell_texts) > 2 else "N/A"
                        if len(cell_texts) >= 5:
                            result["tomorrow_times"] = cell_texts[3] if len(cell_texts) > 3 else "N/A"
                            result["tomorrow_probability"] = cell_texts[4] if len(cell_texts) > 4 else "N/A"
        
        # Alternative: Look for specific div/span elements
        # Try finding by text content
        try:
            water_elements = page.query_selector_all("//*[contains(text(), 'Water')]")
            for el in water_elements:
                parent = el.evaluate("el => el.closest('tr') ? el.closest('tr').innerText : ''")
                if parent and "interruptible" in parent.lower():
                    print(f"Found via XPath: {parent}")
        except Exception as e:
            print(f"XPath search error: {e}")
        
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
            "today_times": data["today_times"],
            "today_probability": data["today_probability"],
            "tomorrow_times": data["tomorrow_times"],
            "tomorrow_probability": data["tomorrow_probability"],
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
            "today_times": "Error",
            "today_probability": str(e)[:100],
            "tomorrow_times": "Error",
            "tomorrow_probability": "Check logs",
            "last_updated": "N/A"
        }
    }

# ===========================================
# SEND TO TRMNL
# ===========================================
webhook_url = os.environ.get('TRMNL_WEBHOOK_URL')

if not webhook_url:
    print("ERROR: TRMNL_WEBHOOK_URL not set!")
    exit(1)

print("\nSending to TRMNL...")
try:
    response = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    print(f"TRMNL Response: {response.status_code}")
    print(f"TRMNL Body: {response.text}")
except requests.RequestException as e:
    print(f"ERROR sending to TRMNL: {e}")
