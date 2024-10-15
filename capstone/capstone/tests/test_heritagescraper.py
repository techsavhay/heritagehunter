import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import requests  # Make sure to import requests

# Adding the path for heritagescraper manually to ensure it can be imported for testing.
sys.path.append(os.path.join(os.path.dirname(__file__), '../management/commands'))

from heritagescraper import extract_pub_info  # Adjusted to import directly from the heritagescraper file

class TestHeritageScraper(unittest.TestCase):

    @patch('requests.get')
    def test_extract_pub_info_success(self, mock_get):
        # Simulate a successful response from the target URL
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Provide mock HTML content that the scraper expects to parse successfully
        mock_response.content = """
        <html>
            <h1>Sample Pub</h1>
            <address>123 Sample Street</address>
            <div class="full_description">Sample description</div>
            <p class='ni-status'><span>3 Stars</span></p>
            <p class='mt-3'>Listed Status</p>
            <p class="bright-red"><strong>Open</strong></p>
        </html>
        """
        mock_get.return_value = mock_response

        # Call the extract_pub_info function with a valid URL
        pub_data, url = extract_pub_info("https://pubheritage.camra.org.uk/pubs/valid")
        
        # Validate that the function returns correct data
        self.assertIsNotNone(pub_data)
        self.assertEqual(pub_data['Pub Name'], 'Sample Pub')
        self.assertEqual(pub_data['Address'], '123 Sample Street')

    @patch('requests.get')
    def test_extract_pub_info_404(self, mock_get):
        # Simulate a 404 Not Found response with minimal HTML structure to avoid NoneType errors
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = """
        <html>
            <h1></h1>
            <address></address>
            <div class="brief_description"></div>  <!-- Add empty description element -->
            <p class='ni-status'></p>  <!-- Add empty inventory stars element -->
            <p class='mt-3'></p>  <!-- Add empty listed status element -->
        </html>
        """  # Provide an empty structure for all elements to avoid errors
        mock_get.return_value = mock_response

        # Call the extract_pub_info function with an invalid URL that simulates a 404 response
        pub_data, url = extract_pub_info("https://pubheritage.camra.org.uk/pubs/invalid")

        # Define expected output for a 404 response - should contain empty values
        expected_data = {
            'Pub Name': '',
            'Address': '',
            'Description': '',
            'Inventory Stars': None,
            'Listed': '',
            'Status': '',
            'Url': 'https://pubheritage.camra.org.uk/pubs/invalid'
        }
        
        # Validate that the function returns the expected empty data structure
        self.assertEqual(pub_data, expected_data)

    @patch('requests.get')
    def test_extract_pub_info_connection_error(self, mock_get):
        # Simulate a connection error when trying to access the URL
        mock_get.side_effect = requests.exceptions.ConnectionError
        
        # Call the extract_pub_info function with an invalid URL that simulates a connection error
        pub_data, url = extract_pub_info("https://pubheritage.camra.org.uk/pubs/invalid")
        
        # Validate that the function returns None when a connection error occurs
        self.assertIsNone(pub_data)

if __name__ == '__main__':
    unittest.main()