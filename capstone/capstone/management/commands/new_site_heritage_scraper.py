"""
CAMRA Pub Heritage Scraper (New Site - camra.org.uk) - TARGETED THREE-STAR RUN

Purpose:
- Reads a previously generated JSON file containing full scrape results.
- Filters this data to find pubs marked as "Three star".
- Re-scrapes ONLY the URLs of these identified three-star pubs from camra.org.uk.
- Collects: Pub Name, Address, Description (historical), Inventory Stars,
            Listed Status (with prefix), Status (Closed/Empty), Latitude,
            Longitude, and the scraped URL.

Input Data Source (for filtering):
- Reads a JSON file specified by the 'input_json_path' variable.
- This file should be a LIST of pub dictionaries (output from a previous full run).
- Example entry: {"Pub Name": "...", "Inventory Stars": "Three star - ...", "Url": "..."}

Output:
- Saves the newly scraped data for ONLY the three-star pubs to a timestamped JSON file.
- Output file is placed in the 'scraped_data' subdirectory.
- Filename pattern: 'camra_heritage_THREE_STAR_UPDATE_YYYYMMDD_HHMMSS.json'.
- Includes checkpoint saving every 'CHECKPOINT_INTERVAL' pubs.

How to Run:
1. Ensure Python 3, requests, beautifulsoup4 are installed in the active venv.
2. Verify 'input_json_path' points to your COMPLETE previous scrape results JSON file.
3. Navigate to script directory and run: python new_site_heritage_scraper.py

"""

import requests
from bs4 import BeautifulSoup
import json
import os
import datetime
import time
import traceback # Keep traceback for error reporting

# --- Configuration ---
OUTPUT_DIR = 'scraped_data'
FILENAME_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
REQUEST_DELAY_SECONDS = 1 # Polite delay between requests
CHECKPOINT_INTERVAL = 200 # Save progress every N pubs (less likely to trigger on filtered run)

# --- Helper Function for Saving Data ---
def save_data_to_json(data, filename):
    """
    Saves the provided data list to a JSON file. Overwrites the file.
    """
    try:
        output_dir_path = os.path.dirname(filename)
        if output_dir_path:
             os.makedirs(output_dir_path, exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except IOError as e:
        print(f"\nError writing to file {filename}: {e}")
        return False
    except TypeError as e:
        print(f"\nError serializing data to JSON: {e}")
        return False

# --- Scraper Function (Should be the latest working version) ---
def scrape_camra_pub(url):
    """
    Scrapes a single CAMRA pub page for specific details.
    """
    print(f"Scraping: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching URL {url}: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    # Initialize data dict including Lat/Lon fields
    data = {
        "Pub Name": "", "Address": "", "Description": "",
        "Inventory Stars": "", "Listed": "", "Status": "",
        "Latitude": "", "Longitude": "", "Url": url
    }

    try:
        # Extract Pub Name
        name_element = soup.select_one('h1.mb-3.inline-block')
        if name_element:
            full_name = name_element.get_text(strip=True)
            if ',' in full_name: data["Pub Name"] = full_name.split(',')[0].strip()
            else: data["Pub Name"] = full_name
        else: print(f"  Warning: Could not find Pub Name on {url}")

        # Extract Address
        address_element = soup.select_one('span.user-select-contain')
        if address_element: data["Address"] = address_element.get_text(strip=True)
        else: print(f"  Warning: Could not find Address on {url}")

        # Extract Description (Using longest div.keep-formatting)
        data["Description"] = ""
        desc_elements = soup.select('div.keep-formatting')
        if len(desc_elements) == 1: data["Description"] = desc_elements[0].get_text(separator=' ', strip=True)
        elif len(desc_elements) > 1:
            longest_desc = ""; max_len = -1
            for desc_div in desc_elements:
                text = desc_div.get_text(separator=' ', strip=True)
                if len(text) > max_len: max_len = len(text); longest_desc = text
            data["Description"] = longest_desc
        if not data["Description"]: print(f"  Warning: Could not find Description on {url}")

        # Extract Inventory Stars and Listed Status (with prefix)
        possible_status_elements = soup.find_all('p', class_='font-bold')
        data["Inventory Stars"] = ""; data["Listed"] = ""
        for p_tag in possible_status_elements:
            p_text = p_tag.get_text(strip=True)
            if "star -" in p_text.lower(): data["Inventory Stars"] = p_text
            elif "listed status:" in p_text.lower(): data["Listed"] = p_text
        if not data["Inventory Stars"]: print(f"  Warning: Could not find Inventory Stars on {url}")
        if not data["Listed"]: print(f"  Warning: Could not find Listed Status on {url}")

        # Extract Latitude and Longitude (from JSON-LD)
        data["Latitude"] = ""; data["Longitude"] = ""
        lat = None; lon = None
        try:
            ld_json_scripts = soup.find_all('script', type='application/ld+json')
            for script in ld_json_scripts:
                script_content = script.string
                if script_content:
                    parsed_json = json.loads(script_content)
                    if parsed_json.get('@type') in ["BarOrPub", "Place", "Restaurant"] and 'geo' in parsed_json:
                        geo_data = parsed_json.get('geo')
                        if isinstance(geo_data, dict) and geo_data.get('@type') == 'GeoCoordinates':
                            lat = geo_data.get('latitude'); lon = geo_data.get('longitude')
                            if lat is not None and lon is not None: break
            if lat is not None: data["Latitude"] = str(lat)
            if lon is not None: data["Longitude"] = str(lon)
        except json.JSONDecodeError as e: print(f"  Warning: Could not parse JSON-LD script content: {e}")
        except Exception as e: print(f"  Error processing JSON-LD scripts: {e}")
        if not data["Latitude"]: print(f"  Warning: Could not find Latitude in JSON-LD.")
        if not data["Longitude"]: print(f"  Warning: Could not find Longitude in JSON-LD.")

        # Extract Status (Open/Closed) - Simplified Check
        pub_status = ""
        try:
            alert_elements = soup.select('div[role="alert"]')
            for alert in alert_elements:
                 alert_text = alert.get_text(strip=True).lower()
                 if "closed" in alert_text:
                      pub_status = "Closed"
                      # print(f"DEBUG Found 'closed' text in alert: '{alert.get_text(strip=True)}'") # Optional
                      break
        except Exception as e: print(f"  Warning: Error checking status alerts: {e}")
        data["Status"] = pub_status
        # --- End of Status Extraction ---

    except Exception as e:
        print(f"  Error parsing data on {url}: {e}")
        traceback.print_exc()
        return None

    return data

# --- Main Execution (Modified to Filter for Three-Star Pubs) ---
if __name__ == "__main__":

    # --- Load PREVIOUS FULL SCRAPE results and FILTER for Three-Star URLs ---
    urls_to_scrape = []
    # Path to the JSON file containing the results of your previous full scrape
    # Adjust relative path based on where manage.py is vs where the file is
    # Since manage.py is in ".../capstone/capstone/" and file is in ".../capstone/capstone/"
    # the relative path is just the filename if run from manage.py directory.
    # If file is in project root ".../capstone/", use "../IMPORT_...json"
    input_json_path = 'IMPORT_camra_heritage_data_20250328_114156.json' # Just the filename

    three_star_pubs_found = 0
    try:
        with open(input_json_path, 'r', encoding='utf-8') as infile:
            print(f"Reading PREVIOUS results from: {input_json_path}")
            # Assuming the input JSON is a list of dictionaries
            previous_scrape_data = json.load(infile)

            if isinstance(previous_scrape_data, list):
                for pub_data in previous_scrape_data:
                    # Check if the 'Inventory Stars' field exists and contains 'Three star'
                    inventory_stars = pub_data.get("Inventory Stars", "")
                    if "three star" in inventory_stars.lower(): # Case-insensitive check
                        url = pub_data.get("Url")
                        if url: # Make sure URL exists
                            urls_to_scrape.append(url)
                            three_star_pubs_found += 1
                print(f"Found {three_star_pubs_found} Three-Star pubs to re-scrape.")
            else:
                print(f"ERROR: Input JSON file ({input_json_path}) is not a List as expected.")
                exit()

    except FileNotFoundError:
        print(f"ERROR: Previous results file not found at {input_json_path}")
        print("Please make sure the file exists and the path is correct.")
        exit()
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON from {input_json_path}: {e}")
        exit()
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while reading {input_json_path}: {e}")
        exit()

    if not urls_to_scrape:
        print("ERROR: No Three-Star pub URLs found in the input file.")
        exit()
    # --- End of URL loading/filtering block ---

    # --- Initialize variables for main loop ---
    all_pub_data = []
    success_count = 0

    # Define the output filename *before* the loop
    timestamp = datetime.datetime.now().strftime(FILENAME_TIMESTAMP_FORMAT)
    # New filename pattern for this specific run
    output_filename = os.path.join(OUTPUT_DIR, f'camra_heritage_THREE_STAR_UPDATE_{timestamp}.json')

    print(f"\nStarting targeted scrape for {len(urls_to_scrape)} Three-Star pubs.")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Output file: {output_filename}")
    print(f"Checkpoint interval: {CHECKPOINT_INTERVAL} pubs")

    total_urls = len(urls_to_scrape)
    # --- Main scraping loop ---
    for i, url in enumerate(urls_to_scrape):
        print(f"\nProcessing URL {i+1}/{total_urls}")
        scraped_data = scrape_camra_pub(url)

        if scraped_data:
            all_pub_data.append(scraped_data)
            success_count += 1

            # Checkpoint saving logic
            if CHECKPOINT_INTERVAL > 0 and success_count % CHECKPOINT_INTERVAL == 0:
                print(f"\n--- Reached checkpoint: {success_count} pubs scraped ---")
                print(f"Saving progress to {output_filename}...")
                if save_data_to_json(all_pub_data, output_filename):
                    print("--- Checkpoint saved successfully ---")
                else:
                    print("--- ERROR: Failed to save checkpoint! ---")

        # Optional delay
        if REQUEST_DELAY_SECONDS > 0 and i < total_urls - 1:
            print(f"  Waiting for {REQUEST_DELAY_SECONDS} second(s)...")
            time.sleep(REQUEST_DELAY_SECONDS)

    # --- Final Save After Loop ---
    print("\n--- Scraping loop finished ---")
    if all_pub_data:
         print(f"Performing final save for {success_count} total scraped pubs...")
         if save_data_to_json(all_pub_data, output_filename):
             print(f"Final data saved successfully to: {output_filename}")
         else:
             print("--- ERROR: Failed to save final data! ---")
    else:
        print("\nNo data was successfully scraped.")