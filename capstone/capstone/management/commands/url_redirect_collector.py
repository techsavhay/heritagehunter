import requests
import json
import time

# Define the range of old URLs to check
ranges_to_scrape = [(1, 13620)]

# Output file to store redirected URLs
redirected_urls_file = "redirected_urls.json"

# Storage for collected URLs
redirected_urls = {}

def get_redirected_url(old_url):
    """
    Function to follow a redirect and return the final destination URL.
    """
    try:
        response = requests.get(old_url, allow_redirects=True, timeout=5)
        response.raise_for_status()  # Ensure it's a valid request
        return response.url  # Return the final redirected URL
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {old_url}: {e}")
        return None

# Loop through the old numbered URLs
for range_start, range_end in ranges_to_scrape:
    for pub_id in range(range_start, range_end + 1):
        old_url = f"https://pubheritage.camra.org.uk/pubs/{pub_id}"
        new_url = get_redirected_url(old_url)
        
        if new_url:
            redirected_urls[old_url] = new_url
            print(f"{old_url} -> {new_url}")
        
        # Sleep to avoid rate-limiting (adjust as needed)
        time.sleep(1)

# Save to a JSON file for easy future use
with open(redirected_urls_file, "w", encoding="utf-8") as file:
    json.dump(redirected_urls, file, indent=4)

print(f"✅ Redirected URLs saved to {redirected_urls_file}")
