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
        pubElement.addEventListener('click', event => {
          const clickedElement = event.target;
          const clickedParent = clickedElement.parentElement;

          if (//ignore the input fields when looking for a pub click//
            !clickedElement.classList.contains('additional-content') &&
            !clickedParent.classList.contains('additional-content')
          ) {
            pubElement.classList.toggle('pub-expanded');

            // Delay the height calc so CSS transition takes effect
            setTimeout(() => {
              const containerHeight = pubsContainer.offsetHeight;
              pubsContainer.style.height = `${containerHeight}px`;

              if (pubElement.classList.contains('pub-expanded')) {
                const expandedPubHeight = pubElement.offsetHeight * 3;
                pubElement.style.height = `${expandedPubHeight}px`;
                pubElement.insertAdjacentHTML(
                  'beforeend',
                  '<form class="additional-content">Date of visit: <input type="date" name="visit"/><br><textarea id="pubreview" name="pubreview" rows="3" cols="30">Space to write a short review (optional)</textarea><input type="submit" value="Save visit"></form>'
                );
              } else {
                pubElement.style.height = 'auto';
                const additionalContent = pubElement.querySelector('.additional-content');
                if (additionalContent) {
                  additionalContent.remove();
                }
              }
            }, 0);
          }
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
