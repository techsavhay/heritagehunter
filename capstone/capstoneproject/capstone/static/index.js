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
      const sorted_pubs = data.sort((a, b) => {
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

      let expandedPub = null; // Track the currently expanded pub

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

        // Event listener for pub element
        pubElement.addEventListener('click', event => {
          const clickedElement = event.target;
          const clickedParent = clickedElement.parentElement;

          // Ignore clicks on additional content or its parent elements
          if (
            !clickedElement.classList.contains('additional-content') &&
            !clickedParent.classList.contains('additional-content')
          ) {
            // Collapse the currently expanded pub, if any
            if (expandedPub && expandedPub !== pubElement) {
              expandedPub.classList.remove('pub-expanded');
              const additionalContent = expandedPub.querySelector('.additional-content');
              if (additionalContent) {
                additionalContent.remove();
              }
              expandedPub.style.height = 'auto'; // Reset the height to auto
            }

            // Check if the clicked pub is already expanded
            const isExpanded = pubElement.classList.contains('pub-expanded');

            // Toggle the pub-expanded class
            pubElement.classList.toggle('pub-expanded', !isExpanded);

            // Delay the height calculation so CSS transition takes effect
            setTimeout(() => {
              const containerHeight = pubsContainer.offsetHeight;
              pubsContainer.style.height = `${containerHeight}px`;

              if (pubElement.classList.contains('pub-expanded')) {
                const expandedPubHeight = pubElement.offsetHeight * 4;
                pubElement.style.height = `${expandedPubHeight}px`;

                // Create form
                const form = document.createElement('form');
                form.className = "additional-content";

                form.innerHTML = `
                    <label for="visit">Date of visit (optional):</label>
                    <input type="date" id="date_visited" name="date_visited"/><br>
                    <textarea id="content" action="/api/save-visit" method="POST" name="content" rows="3" cols="30" maxlength="280" placeholder="Space to write a short review, (optional)..."></textarea>
                    <input type="submit" value="Save visit">
                `;

                // Append form to pub element
                pubElement.appendChild(form);

                // Set textarea width as a percentage of pubElement
                const pubWidth = pubElement.offsetWidth; // Get the width of the pub element
                const pubHeight = pubElement.offsetHeight; // Get the height of the pub element
                const textarea = form.querySelector('textarea');

                // Set the width of the textarea as a percentage of the pub width
                const textareaWidthPercentage = 90; // Adjustable
                const textareaHeightPercentage = 35; // Adjustable
                const textareaWidth = (pubWidth * textareaWidthPercentage) / 100;
                const textareaHeight = (pubHeight * textareaHeightPercentage) / 100;
                textarea.style.width = `${textareaWidth}px`;
                textarea.style.height = `${textareaHeight}px`;

                // Add submit event to the form
                form.addEventListener('submit', event => {
                  event.preventDefault();

                  const dateVisitedInput = form.querySelector('#date_visited');
                  const contentInput = form.querySelector('#content');

                  let date_visited = dateVisitedInput.value;
                  const content = contentInput.value;
                  
                  // Check if date_visited is an empty string, if so set it to null
                  if (date_visited === "") {
                    date_visited = null;
}

                  fetch('/api/save_visit', {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    },
                    body: JSON.stringify({
                      date_visited: date_visited,
                      content: content,
                      pub_id: pub.id,
                    }),
                  })
                    .then(response => response.json())
                    .then(data => {
                      console.log(data);
                    })
                    .catch(error => {
                      console.error('Error saving visit:', error);
                    });

                  // Clear form fields
                  dateVisitedInput.value = '';
                  contentInput.value = '';
                });
              } else {
                pubElement.style.height = 'auto';
                const additionalContent = pubElement.querySelector('.additional-content');
                if (additionalContent) {
                  additionalContent.remove();
                }
              }
            }, 0);

            // Update the currently expanded pub
            expandedPub = pubElement;
          }
        });

        pubsContainer.appendChild(pubElement);
      });
    })
    .catch(error => {
      // Log errors
      console.error('Error fetching data:', error);
    });
}

// Call the fetchPubData function
fetchPubData();
