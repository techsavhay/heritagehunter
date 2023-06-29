// Defined outside because it's reused multiple times
const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

// A function to make the fetch calls (DRY principle)
function fetchData(url, method, body) {
  return fetch(url, {
    method: method,
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify(body),
  })
  .then(response => {
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    return response.json();
  });
}

// fetches data from API about the pubs, and handles some UI interaction
function fetchPubData() {
  // POST request to fetchData function to get data
  fetchData('/api/pubs/', 'POST', {}).then(displayPubs).catch(console.error);
}

// Function to create a form for editing a pub's details
function createForm(pubElement, pubId, fetchPubData, date_visited, content) {
  let form = pubElement.querySelector('.additional-content');
  let newDate = date_visited;

  if (form) {
    form.remove();
  }

  form = document.createElement('form');
  form.className = 'additional-content';
  pubElement.appendChild(form);

  // Remove existing elements
  const contentElement = pubElement.querySelector('.post');
  if (contentElement) {
    contentElement.remove();
  }

  const dateElement = pubElement.querySelector('.date-visited');
  if (dateElement) {
    dateElement.remove();
  }

  if (content || date_visited) {

    // changing date formath from dd-mm-yy to yyyy-mm-dd so html date module accepts it for editing view
    if (date_visited !="") {
      let dateParts = date_visited.split("-");
      newDate = dateParts.reverse().join("-");
    }

    // if the pub already has a related post populate the form with the post details
    form.innerHTML = `
      <label for="visit">Date of visit (optional):</label>
      <input type="date" id="date_visited" name="date_visited" value="${newDate}"><br>
      <textarea id="content" name="content" rows="3" cols="30" maxlength="280">${content}</textarea>
      <input type="submit" id="save-visit-button" value="Save visit">
    `;
  } else //if the pub doesnt have a post related to it create a blank form
  {
    form.innerHTML = `
      <label for="visit">Date of visit (optional):</label>
      <input type="date" id="date_visited" name="date_visited"><br>
      <textarea id="content" name="content" rows="3" cols="30" maxlength="280" placeholder="Space to write a short review, (optional)..."></textarea>
      <input type="submit" id="save-visit-button" value="Save visit">
    `;
  }

  //logic to resize textarea based on window dimensions.
  const pubWidth = pubElement.offsetWidth;
  const pubHeight = pubElement.offsetHeight;
  const textareaWidthPercentage = 90;
  const textareaHeightPercentage = 35;
  const textareaWidth = (pubWidth * textareaWidthPercentage) / 100;
  const textareaHeight = (pubHeight * textareaHeightPercentage) / 100;

  const textarea = form.querySelector('textarea');
  textarea.style.width = `${textareaWidth}px`;
  textarea.style.height = `${textareaHeight}px`;

  // listener for Save visit button
  form.addEventListener('submit', event => {
    event.preventDefault();

    const dateVisitedInput = form.querySelector('#date_visited');
    const contentInput = form.querySelector('#content');

    let date_visited = dateVisitedInput.value;
    const content = contentInput.value;

    if (date_visited === '') {
      date_visited = null;
    }

    // POST request to fetchData function to save visit
    fetchData('/api/save_visit/', 'POST', {
      date_visited: date_visited,
      content: content,
      pub_id: pubId,
  }).then(data => {
      console.log(data);
      pubElement.classList.add('visited');
      fetchPubData();
  }).catch(error => {
      console.error('Error saving visit:', error);
  });

    dateVisitedInput.value = '';
    contentInput.value = '';
  });
}

// function to take pub data and display it, including adding edit and delete buttons
function displayPubs(data){
  // Alphabetizes the pubs by their names
  const sorted_pubs = data.sort((a, b) => {
    if (a.pub.name < b.pub.name) {
      return -1;
    }
    if (a.pub.name > b.pub.name) {
      return 1;
    }
    return 0;
  });

  // Targets the DOM element to populate with our pubs
  const pubsContainer = document.querySelector('#pubs-container');
  // Clears the container to ensure it's empty before we add to it
  pubsContainer.innerHTML = '';

  // keeps track of the currently expanded pub, if there is one (helps ensure only one open at a time later)
  let expandedPub = null;

  // Loops through the pubs to create DOM elements for each
  sorted_pubs.forEach(item => {
    const pub = item.pub;
    // Gets the most recent post (in case a post has been deleted or edited)
    const post = item.posts[item.posts.length - 1];

    const name = pub.name;
    const address = pub.address;

    // Creates a div for each pub
    const pubElement = document.createElement('div');
    pubElement.classList.add('pub');

    // Assigns the pub's name and address to the new div
    pubElement.innerHTML = `
      <h5>${name}</h5>
      <p class="pub-address">${address}</p>
    `;

    // If the pub has been visited, it gets a 'visited' class
    if (post) {
      pubElement.classList.add('visited');
    } else {
      pubElement.classList.remove('visited');
    }

    // Assigns a click event to each pub
    pubElement.addEventListener('click', event => {
      const clickedElement = event.target;
      const clickedParent = clickedElement.parentElement;

      if (//Makes sure certain elements are ignored when listening for clicks to collapse the entry
        !clickedElement.classList.contains('additional-content') &&
        !clickedElement.classList.contains('edit-button') &&
        !clickedElement.classList.contains('delete-button') &&
        !clickedParent.classList.contains('additional-content') &&
        !clickedParent.classList.contains('edit-button') &&
        !clickedParent.classList.contains('delete-button')
      ) {
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

        // logic to resize pub container based on screen size etc
        const containerHeight = pubsContainer.offsetHeight;
        pubsContainer.style.height = `${containerHeight}px`;

        if (pubElement.classList.contains('pub-expanded')) {
          // if a pub has a post and is clicked
          if (post) {
            if (!pubElement.querySelector('.post')) {
              const expandedPubHeight = pubElement.offsetHeight * 4;
              pubElement.style.height = `${expandedPubHeight}px`;

              const content = post.content;
              let date_visited = post.date_visited;
              if (date_visited == null) {
                date_visited = '';
              }
              
              // create elements and show the date visited and pub review.
              const contentElement = document.createElement('p');
              contentElement.classList.add('post');
              contentElement.innerHTML = `<h6>Date visited:</h6> ${date_visited}<br><p><h6>Review:</h6> ${content}</p>`;
              pubElement.appendChild(contentElement);

              // create an edit button
              const editButton = document.createElement('button');
              editButton.textContent = 'Edit Post';
              editButton.style.margin = '8px';
              editButton.classList.add('edit-button');
              contentElement.appendChild(editButton);

              // create a delete button
              const deleteButton = document.createElement('button');
              deleteButton.textContent = 'Delete Post';
              deleteButton.style.margin = '8px';
              deleteButton.style.float = 'right';
              deleteButton.classList.add('delete-button');
              contentElement.appendChild(deleteButton);

              editButton.addEventListener('click', function () {
                createForm(pubElement, pub.id, fetchPubData, date_visited, content);
              });

              // listener for delete visit button.
              deleteButton.addEventListener('click', function () {
                //fetch request via fetchData function
                fetchData('/api/delete_visit/', 'POST', {
                  id: post.id,
              }).then(data => {
                  fetchPubData();
              }).catch(error => {
                  console.error('There has been a problem with your fetch operation:', error);
              });
              
              });
            }
          } else 
          //if pub doesnt have a post and is clicked, invoke create form funciton
          {
            if (!pubElement.querySelector('.additional-content')) {
              const expandedPubHeight = pubElement.offsetHeight * 4;
              pubElement.style.height = `${expandedPubHeight}px`;

              createForm(pubElement, pub.id, fetchPubData);
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
    // Adds the newly created div to the container
    pubsContainer.appendChild(pubElement);
  });
}

// Calls fetchPubData() to start the process
fetchPubData();