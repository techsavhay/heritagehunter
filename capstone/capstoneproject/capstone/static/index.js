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
    const sorted_pubs = data.sort((a, b) => {
      if (a.pub.name < b.pub.name) {
        return -1;
      }
      if (a.pub.name > b.pub.name) {
        return 1;
      }
      return 0;
    });

    const pubsContainer = document.querySelector('#pubs-container');
    pubsContainer.innerHTML = '';

    let expandedPub = null; 

    sorted_pubs.forEach(item => {
      const pub = item.pub;
      const post = item.posts[0];
      //console.log(post);

      const name = pub.name;
      const address = pub.address;

      const pubElement = document.createElement('div');
      pubElement.classList.add('pub');

      pubElement.innerHTML = `
        <h5>${name}</h5>
        <p class="pub-address">${address}</p>
      `;

      if (post) {
        pubElement.classList.add('visited')
      } else {
        pubElement.classList.remove('visited')
      }

      pubElement.addEventListener('click', event => {
        const clickedElement = event.target;
        const clickedParent = clickedElement.parentElement;

        if (!clickedElement.classList.contains('additional-content') && 
            !clickedParent.classList.contains('additional-content')) {
          if (expandedPub && expandedPub !== pubElement) {
            expandedPub.classList.remove('pub-expanded');
            const additionalContent = expandedPub.querySelector('.additional-content');
            if (additionalContent) {
              additionalContent.remove();
            }
            expandedPub.style.height = 'auto';
          }

          const isExpanded = pubElement.classList.contains('pub-expanded');

          pubElement.classList.toggle('pub-expanded', !isExpanded);

          const containerHeight = pubsContainer.offsetHeight;
          pubsContainer.style.height = `${containerHeight}px`;

          if (pubElement.classList.contains('pub-expanded')) {
            if (post) {
              // Only add post content if it doesn't already exist in the pub.
              if (!pubElement.querySelector('.post')) {
                const expandedPubHeight = pubElement.offsetHeight * 4;
                pubElement.style.height = `${expandedPubHeight}px`;

                const content = post.content;
                let date_visited = post.date_visited;
                if (date_visited == null) {
                  date_visited = "";
                }
                  
                const contentElement = document.createElement('p');
                contentElement.classList.add('post');

                // ADD DELETE AND EDIT POST BUTTONS IN HERE?

                contentElement.innerHTML = `<h6>Date visited:</h6> ${date_visited}<br><p><h6>Review:</h6> ${content}</p>`;
                pubElement.appendChild(contentElement);

              }
            } 
            
            else
            
            {
              // Only add the form if it doesn't already exist in the pub.
              if (!pubElement.querySelector('.additional-content')) {
                const expandedPubHeight = pubElement.offsetHeight * 4;
                pubElement.style.height = `${expandedPubHeight}px`;

                const form = document.createElement('form');
                form.className = "additional-content";

                form.innerHTML = `
                  <label for="visit">Date of visit (optional):</label>
                  <input type="date" id="date_visited" name="date_visited"/><br>
                  <textarea id="content" action="/api/save-visit" method="POST" name="content" rows="3" cols="30" maxlength="280" placeholder="Space to write a short review, (optional)..."></textarea>
                  <input type="submit" id="save-visit-button" value="Save visit">
                `;

                pubElement.appendChild(form);

                const pubWidth = pubElement.offsetWidth; 
                const pubHeight = pubElement.offsetHeight; 
                const textarea = form.querySelector('textarea');

                const textareaWidthPercentage = 90; 
                const textareaHeightPercentage = 35;
                const textareaWidth = (pubWidth * textareaWidthPercentage) / 100;
                const textareaHeight = (pubHeight * textareaHeightPercentage) / 100;
                textarea.style.width = `${textareaWidth}px`;
                textarea.style.height = `${textareaHeight}px`;

                form.addEventListener('submit', event => {
                  //COMMENTED OUT IN ORDER FOR PAGE TO REFRESH WHEN SAVE VISIT IS CLICKED THUS UPDATING COLOURSevent.preventDefault();

                  const dateVisitedInput = form.querySelector('#date_visited');
                  const contentInput = form.querySelector('#content');

                  let date_visited = dateVisitedInput.value;
                  const content = contentInput.value;

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
                    pubElement.classList.add('visited');


                  })
                  .catch(error => {
                    console.error('Error saving visit:', error);
                  });

                  dateVisitedInput.value = '';
                  contentInput.value = '';
                });
              } 
            }
            expandedPub = pubElement;
          } else {
            pubElement.style.height = 'auto';
            const additionalContent = pubElement.querySelector('.additional-content');
            const post = pubElement.querySelector('.post');
            if (additionalContent) {
              additionalContent.remove();
            }
            if (post) {
              post.remove();
            }
          }
        }
      });

      pubsContainer.appendChild(pubElement);
    });
  })
  .catch(error => {
    console.error('Error fetching data:', error);
  });
}

fetchPubData();
