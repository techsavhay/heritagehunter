"""
Screen scraper program which pulls information from the CAMRA Pub Heritage site.
"""

import json
import os
import datetime
from bs4 import BeautifulSoup
import requests
import time

# Disable pylint warnings
# pylint: disable=W0621
# pylint: disable=W0105

# Get the current date and time
current_time = datetime.datetime.now()

# Format the timestamp in a desired way
timestamp = current_time.strftime("%Y-%m-%d_%H-%M-%S")

# set the names for the files that outputs the urls that worked and the json
url_list_file_path = f'pub_urls_{timestamp}.txt'
FILE_PATH = f'pub_info_{timestamp}.json'

current_range_start = None
current_range_end = None

# Define multiple ranges to scrape. Usual range =  (1, 6000) See logs to refine?
ranges_to_scrape = [
    (1, 13620),
]


def extract_pub_info(url, max_retries=3, backoff_factor=5):
    """
    Extracts information about a pub from the given URL with retry mechanism.

    Parameters:
    - url (str): The URL of the pub detail page.
    - max_retries (int): The maximum number of retry attempts.
    - backoff_factor (int): The time (in seconds) to wait before retrying.

    Returns:
    - dict: A dictionary containing the extracted pub information or None if failed.
    """
    print(f"Attempting URL: {url}") #prints url being attempted

    attempt = 0
    while attempt < max_retries:
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()  # Raises HTTPError for bad responses
            break  # If the request is successful, break out of the loop
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"404 Not Found: {url}")
                return None, None
            else:
                print(f"HTTP Error: {e}. (At {url})")
                return None, None
        except requests.exceptions.Timeout:
            print(f"Timeout error: {url}")
            return None, None
        except requests.exceptions.ConnectionError as e:
            attempt += 1
            print(f"Connection error on attempt {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(backoff_factor * attempt)  # Exponential backoff
            else:
                print(f"Failed after {max_retries} attempts. Skipping URL: {url}")
                return None, None
        except Exception as e:
            print(f"An unexpected error occurred: {e}.")
            return None, None

    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract pub name
    pub_name = soup.find('h1').text.strip()

    # Extract pub address
    address = soup.find('address').text.strip().replace('\n', ', ')
    address = address.replace('\t', '').strip()
    address = address.rstrip(",")  # removes final comma from address
    address = address.replace(' ,', ',')

    # Extract full description
    description_element = soup.find('div', {'class': 'full_description'})
    description = description_element.text.strip() if description_element else None
    if not description:
        description = soup.find('div', {'class': 'brief_description'}).text.strip()
        if not description:
            print(f"Pub at {url} has no descriptions (full or brief)")

    # Extract pub heritage stars
    inventory_stars = soup.find('p', class_='ni-status').find('span')
    if inventory_stars:
        inventory_stars = inventory_stars.text.strip()
    if not inventory_stars:
        print(f"The pub at {url} has no ni_status / inventory stars")

    # Extract listed status
    listed = soup.find('p', class_='mt-3').text.strip()
    if not listed:
        print(f"The pub at {url} has no listed status")

    # Extract open/closed status
    status_element = soup.find('p', class_='bright-red')
    status = status_element.find('strong').text.strip() if status_element else ""

    pub_info = {
        'Pub Name': pub_name,
        'Address': address,
        'Description': description,
        'Inventory Stars': inventory_stars,
        'Listed': listed,
        'Status': status,
        'Url': url
    }

    return pub_info, url




def save_pub_info(data, file_path):
    """
    Saves the pub information to a JSON file.

    Parameters:
    - data (list): The list of pub dictionaries to be saved.
    - file_path (str): The path to the JSON file.
    """
    file_exists = os.path.isfile(file_path)
    with open(file_path, 'a', encoding='utf-8') as file:
        if not file_exists:
            file.write('[')
            file.write('\n')
        else:
            file.seek(file.tell() - 1, os.SEEK_SET)
            file.truncate()
            file.write(',')
            file.write('\n')

        for i, pub in enumerate(data):
            json.dump(pub, file, indent=4, ensure_ascii=True)
            if i < len(data) - 1:
                file.write(',')
                file.write('\n')

        file.write('\n')
        file.write(']')


def log_successful_urls(url_list_file, start, end):
    if start is not None:
        url_list_file.write(f"https://pubheritage.camra.org.uk/pubs/ {start} - {end} successful.\n")


    
# Loop through pub detail pages and extract information, also log the ranges that were successful
with open(url_list_file_path, 'w', encoding='utf-8') as url_list_file:
    url_list_file.write(f"Attempted URL Ranges: {ranges_to_scrape}\n\n")
    for range_start, range_end in ranges_to_scrape:
        current_range_start = None
        current_range_end = None
        for pub_url in range(range_start, range_end + 1):
            url = f'https://pubheritage.camra.org.uk/pubs/{pub_url}'
            pub_data, success_url = extract_pub_info(url)
            if pub_data is not None:
                save_pub_info([pub_data], FILE_PATH)
                if current_range_start is None:
                    current_range_start = pub_url
                current_range_end = pub_url
            elif current_range_start is not None:
                log_successful_urls(url_list_file, current_range_start, current_range_end)
                current_range_start = None

        log_successful_urls(url_list_file, current_range_start, current_range_end)