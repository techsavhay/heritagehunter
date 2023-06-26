function fetchPubData() {
  fetch('/api/pubs/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
    },
    body: JSON.stringify({}),
  })
    .then(response => response.json())
    .then(data => {
      // Sort pubs alphabetically by name
      sorted_pubs = data.sort(function(a, b) {
        if (a.pub.name < b.pub.name) {
          return -1;
        }
        if (a.pub.name > b.pub.name) {
          return 1;
        }
        return 0;
      });

      // Process data and update HTML elements
      const pubsContainer = document.querySelector('#pubs-container');
      pubsContainer.innerHTML = '';

      sorted_pubs.forEach(item => {
        const pub = item.pub;
        // Access pub properties
        const name = pub.name;
        const address = pub.address;

        const pubElement = document.createElement('div');
        pubElement.classList.add('pub');

        pubElement.innerHTML = `
          <h5>${name}</h5>
          <p class="pub-address">${address}</p>
        `;

        // Event listener to pub element
        pubElement.addEventListener('click', () => {
          pubElement.classList.toggle('pub-expanded');
          pubsContainer.style.height = 'auto'; // Reset the container height

          // Delay the height calculation so CSS transition takes effect
          setTimeout(() => {
            const containerHeight = pubsContainer.offsetHeight;
            pubsContainer.style.height = `${containerHeight}px`;

            if (pubElement.classList.contains('pub-expanded')) {
              const expandedPubHeight = pubElement.offsetHeight * 2;
              pubElement.style.height = `${expandedPubHeight}px`;
            } else {
              pubElement.style.height = 'auto';
            }
          }, 0);
        });

        pubsContainer.appendChild(pubElement);
      });
    })
    .catch(error => {
      // log errors
      console.error('Error fetching data:', error);
    });
}

fetchPubData();
