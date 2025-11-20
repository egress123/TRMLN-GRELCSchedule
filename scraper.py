import requests
import json
from bs4 import BeautifulSoup
import os

# Example: Scraping a webpage
url = "https://lmguide.grenergy.com"  # Change this to your target URL

try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract data based on your needs
    # Example 1: Get all text from a specific class
    title = soup.find('h1', class_='page-title')
    title_text = title.get_text(strip=True) if title else "N/A"
    
    # Example 2: Get content from specific div
    content_div = soup.find('div', class_='main-content')
    content_text = content_div.get_text(strip=True)[:200] if content_div else "N/A"  # First 200 chars
    
    # Example 3: Extract multiple items (like prices, items, etc)
    items = []
    for item in soup.find_all('div', class_='item-card')[:5]:  # Get first 5
        item_name = item.find('h3')
        item_price = item.find('span', class_='price')
        items.append({
            'name': item_name.get_text(strip=True) if item_name else "N/A",
            'price': item_price.get_text(strip=True) if item_price else "N/A"
        })
    
    # Format data for TRMNL
    trmnl_payload = {
        "merge_variables": {
            "title": title_text,
            "content": content_text,
            "items": json.dumps(items),
            "last_updated": "Just now"
        }
    }
    
    # Output as JSON for GitHub Actions to pick up
    print(json.dumps(trmnl_payload))
    
    # Also set it as an environment variable for the workflow
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f"data={json.dumps(trmnl_payload)}\n")
    
except requests.RequestException as e:
    print(f"Error fetching URL: {e}")
    error_payload = {
        "merge_variables": {
            "error": f"Failed to fetch data: {str(e)}"
        }
    }
    print(json.dumps(error_payload))
