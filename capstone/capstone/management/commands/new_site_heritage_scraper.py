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
CHECKPOINT_INTERVAL = 200 # Save progress every N pubs

# --- Helper Function for Saving Data ---
def save_data_to_json(data, filename):
    """
    Saves the provided data list to a JSON file. Overwrites the file.

    Args:
        data (list): The list of pub dictionaries to save.
        filename (str): The full path to the output JSON file.

    Returns:
        bool: True if saving was successful, False otherwise.
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

# --- Scraper Function (Final Version) ---
def scrape_camra_pub(url):
    """
    Scrapes a single CAMRA pub page for specific details.

    Args:
        url (str): The URL of the CAMRA pub page.

    Returns:
        dict: A dictionary containing the scraped pub data, or None if scraping fails.
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
        "Latitude": "", "Longitude": "",
        "Url": url
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
        if address_element:
            data["Address"] = address_element.get_text(strip=True)
        else: print(f"  Warning: Could not find Address on {url}")

        # Extract Description (Using longest div.keep-formatting)
        data["Description"] = ""
        desc_elements = soup.select('div.keep-formatting')
        if len(desc_elements) == 1:
            data["Description"] = desc_elements[0].get_text(separator=' ', strip=True)
        elif len(desc_elements) > 1:
            longest_desc = ""
            max_len = -1
            for desc_div in desc_elements:
                text = desc_div.get_text(separator=' ', strip=True)
                if len(text) > max_len:
                    max_len = len(text)
                    longest_desc = text
            data["Description"] = longest_desc
        if not data["Description"]:
            print(f"  Warning: Could not find Description in any 'div.keep-formatting' on {url}")

        # Extract Inventory Stars and Listed Status (with prefix)
        possible_status_elements = soup.find_all('p', class_='font-bold')
        data["Inventory Stars"] = ""
        data["Listed"] = ""
        for p_tag in possible_status_elements:
            p_text = p_tag.get_text(strip=True)
            if "star -" in p_text.lower():
                data["Inventory Stars"] = p_text
            elif "listed status:" in p_text.lower():
                data["Listed"] = p_text # Store full text including prefix

        if not data["Inventory Stars"]: print(f"  Warning: Could not find Inventory Stars on {url}")
        if not data["Listed"]: print(f"  Warning: Could not find Listed Status on {url}")

        # Extract Latitude and Longitude (from JSON-LD)
        data["Latitude"] = ""
        data["Longitude"] = ""
        lat = None
        lon = None
        try:
            ld_json_scripts = soup.find_all('script', type='application/ld+json')
            for script in ld_json_scripts:
                script_content = script.string
                if script_content:
                    parsed_json = json.loads(script_content)
                    if parsed_json.get('@type') in ["BarOrPub", "Place", "Restaurant"] and 'geo' in parsed_json:
                        geo_data = parsed_json.get('geo')
                        if isinstance(geo_data, dict) and geo_data.get('@type') == 'GeoCoordinates':
                            lat = geo_data.get('latitude')
                            lon = geo_data.get('longitude')
                            if lat is not None and lon is not None:
                                break
            if lat is not None: data["Latitude"] = str(lat)
            if lon is not None: data["Longitude"] = str(lon)
        except json.JSONDecodeError as e:
            print(f"  Warning: Could not parse JSON-LD script content: {e}")
        except Exception as e:
            print(f"  Error processing JSON-LD scripts: {e}")

        if not data["Latitude"]: print(f"  Warning: Could not find Latitude in JSON-LD.")
        if not data["Longitude"]: print(f"  Warning: Could not find Longitude in JSON-LD.")

        # Extract Status (Open/Closed)
        closed_alert_div = soup.find('div', class_='alert alert-danger')
        pub_status = ""
        if closed_alert_div: pub_status = "Closed"
        data["Status"] = pub_status

    except Exception as e:
        print(f"  Error parsing data on {url}: {e}")
        traceback.print_exc()
        return None

    return data

# --- Main Execution (Set for FULL Run from JSON) ---
if __name__ == "__main__":
    # --- Load URLs from JSON file ---
    urls_to_scrape = []
    # Use the correct path to your JSON file
    redirect_json_path = '/home/ianandrewhay/CS50W/web50-projects-2020-x/capstone/capstone/management/commands/redirected_urls_20250327_112254.json'
    try:
        with open(redirect_json_path, 'r', encoding='utf-8') as jsonfile:
            print(f"Reading URLs from: {redirect_json_path}")
            jsonData = json.load(jsonfile)
            if 'redirects' in jsonData and isinstance(jsonData['redirects'], dict):
                urls_to_scrape = list(jsonData['redirects'].values())
            else:
                print(f"ERROR: Could not find a 'redirects' dictionary in {redirect_json_path}")
                exit()
    except FileNotFoundError:
        print(f"ERROR: Redirect file not found at {redirect_json_path}")
        print("Please make sure the JSON file exists in the correct location.")
        exit()
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON from {redirect_json_path}: {e}")
        exit()
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while reading {redirect_json_path}: {e}")
        exit()

    if not urls_to_scrape:
        print("ERROR: No URLs loaded from the 'redirects' section of the JSON file.")
        exit()

    # --- Full Run: Use all loaded URLs ---
    # Commented out or removed the sampling block
    # sample_size = 50
    # if len(urls_to_scrape) > sample_size:
    #     print(f"Taking the first {sample_size} URLs for testing...")
    #     urls_to_scrape = urls_to_scrape[:sample_size] # Slice the list
    # else:
    #     print(f"Using all {len(urls_to_scrape)} URLs found (less than sample size).")
    print(f"Loaded {len(urls_to_scrape)} URLs to process.")
    # --- End of URL loading block ---

    # --- Initialize variables for main loop ---
    all_pub_data = []
    success_count = 0

    # Define the output filename *before* the loop (reverted from _SAMPLE_)
    timestamp = datetime.datetime.now().strftime(FILENAME_TIMESTAMP_FORMAT)
    output_filename = os.path.join(OUTPUT_DIR, f'camra_heritage_data_{timestamp}.json') # Standard filename

    print(f"Starting scrape process. Output directory: {OUTPUT_DIR}")
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
                    # Consider adding 'break' or 'exit()' here if checkpoint failure is critical

        # Optional delay
        if REQUEST_DELAY_SECONDS > 0 and i < total_urls - 1:
            print(f"  Waiting for {REQUEST_DELAY_SECONDS} second(s)...")
            time.sleep(REQUEST_DELAY_SECONDS)

    # --- Final Save After Loop ---
    print("\n--- Scraping loop finished ---")
    if all_pub_data:
         # Check if the final save is necessary (if data hasn't just been saved at the last checkpoint)
        if success_count == 0 or (CHECKPOINT_INTERVAL <= 0 or success_count % CHECKPOINT_INTERVAL != 0):
             print(f"Performing final save for {success_count} total scraped pubs...")
             if save_data_to_json(all_pub_data, output_filename):
                 print(f"Final data saved successfully to: {output_filename}")
             else:
                 print("--- ERROR: Failed to save final data! ---")
        else:
             print(f"Final data for {success_count} pubs already saved at last checkpoint.")
    else:
        print("\nNo data was successfully scraped.")