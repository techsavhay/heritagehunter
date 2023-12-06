"""
Screen scraper program which pulls information from the CAMRA Pub Heritage site.
"""

import json
import os
import datetime
from bs4 import BeautifulSoup
import requests

# Disable pylint warnings
# pylint: disable=W0621
# pylint: disable=W0105

def extract_pub_info(url):
    """
    Extracts information about a pub from the given URL.

    Parameters:
    - url (str): The URL of the pub detail page.

    Returns:
    - dict: A dictionary containing the extracted pub information.
    """
    try:
        response = requests.get(url, timeout=10)
    except requests.exceptions.Timeout:
        print(f"Timeout error: {url}")
        return None
    if response.status_code == 404:
        #print(f"404 Error: {url}") COMMENTED OUT AS NOT NEEDED?
        return None
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

    return pub_info


# Get the current date and time
current_time = datetime.datetime.now()

# Format the timestamp in a desired way
timestamp = current_time.strftime("%Y-%m-%d_%H-%M-%S")

FILE_PATH = f'pub_info_{timestamp}.json'


def save_pub_info(data, file_path):
    """
    Saves the pub information to a JSON file.

    Parameters:
    - data (list): The list of pub dictionaries to be saved.
    - file_path (str): The path to the JSON file.
    """
    # Check if file exists
    file_exists = os.path.isfile(file_path)

    with open(file_path, 'a', encoding='utf-8') as file:
        if not file_exists:
            # Write the opening bracket for the array
            file.write('[')
            file.write('\n')
        else:
            # Move the file pointer to the second last character
            file.seek(file.tell() - 1, os.SEEK_SET)

            # Remove the last character (closing bracket)
            file.truncate()

            # Write a comma and line break before appending the next object
            file.write(',')
            file.write('\n')

        # Write each pub object to the file
        for i, pub in enumerate(data):
            # Write the current pub object to the file
            json.dump(pub, file, indent=4, ensure_ascii=True)

            # Write a comma and a line break before appending the next object
            if i < len(data) - 1:
                file.write(',')
                file.write('\n')

        # Write the closing bracket for the array
        file.write('\n')
        file.write(']')


# Test URLs
test_urls = [
    'https://pubheritage.camra.org.uk/pubs/10199',
    'https://pubheritage.camra.org.uk/pubs/10200',
    'https://pubheritage.camra.org.uk/pubs/10201',
    'https://pubheritage.camra.org.uk/pubs/1',
    'https://pubheritage.camra.org.uk/pubs/2',
    'https://pubheritage.camra.org.uk/pubs/3',
    'https://pubheritage.camra.org.uk/pubs/4'
]

# Loop through pub detail pages and extract information FOR TEST PURPOSES ONLY UNCOMMENT TO USE
"""for pub_url in test_urls:
    pub_data = extract_pub_info(pub_url)
    if pub_data is not None:
        save_pub_info([pub_data], FILE_PATH)"""

# Loop through pub detail pages and extract information
# pylint: disable=W0621 disable=C0304
#UNCOMMENT OUT AND CHANGE RANGE TO RUN THE PROGRAMME. REMEMBER TO OUTPUT FILE TO .TXT
for pub_url in range(1, 13620):
    url = f'https://pubheritage.camra.org.uk/pubs/{pub_url}'
    pub_data = extract_pub_info(url)
    if pub_data is not None:
        save_pub_info([pub_data], FILE_PATH)