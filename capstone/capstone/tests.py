from django.test import Client
import json

# Create an instance of the test client
client = Client()

# Make a GET request to  API endpoint
response = client.get('pubs_api')

# Check the response status code
assert response.status_code == 200

# Access the response data and parse it as JSON
data = json.loads(response.content)

# Assert that the expected data is present in the JSON response
assert 'pubs' in data
assert 'posts' in data


# assert that there are at least 3 pubs
assert len(data['pubs']) >= 3

# Parse and print the response as JSON
data = json.loads(response.content)
print(json.dumps(data, indent=4)) 