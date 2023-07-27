// Defined outside because it's reused multiple times
const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

// declaring global variable which will store all the pub data from the fetch request
let pubData;

// global variable to hold map
let map;

// global variable for map markers
let markers = [];

// global variable for tracking if a marker was clicked (to prevent panTo)
let markerClicked = false;

// global for total 3 star pubs stat
let total3starpubs = 0;

// global for how many pubs the user has visited
let userVisitCount = 0

// global map for markers
let markerMap = new Map();

// global variable which will contain user id (updated as part of pubs api fetch request.)
let currentUserId;

// global variable to store pubs visited percentage
let pubsVisitedPercentage = 0;

// global variable for map marker info window (will help to track only one being opened at a time)
let InfoWindow;

// gets variable from html for user_is_logged_in
let bodyElement = document.querySelector('body');
let user_is_logged_in = bodyElement.getAttribute('data-user-logged-in') === 'True';


// Get the modal (welcome screen)
var modal = document.getElementById("welcomeScreen");

// When the user is not logged in, open the modal welcome screen
if (!user_is_logged_in) { // This variable is passed from  views to  template
    modal.style.display = "block";
}


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

// fetches pub data from fetchdata function 
function fetchPubData() {
  // POST request to fetchData function to get data
  fetchData('/api/pubs/', 'POST', {})
    .then(data => {
      pubData = data.pubs;  // Store the pub data in the global variable, can then be used by dynamicSearch etc
      console.log(pubData);
      currentUserId = data.user_id;
      console.log("currentUserId: ",currentUserId); // Logs the user's id to the console
      pubStats(currentUserId); // call pubStats function
      displayPubs(pubData); 
      displayMap(pubData);
    })
    .catch(console.error);
}

// Function to create a form for editing a pub's details
function createForm(pubElement, pubId, fetchPubData, date_visited, content) {
  let form = pubElement.querySelector('.additional-content');

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

  let newDate = '';
  if (date_visited) {
    // changing date format from dd-mm-yy to yyyy-mm-dd so html date module accepts it for editing view
    let dateParts = date_visited.split("-");
    newDate = dateParts.reverse().join("-");
  }
  
  /* If 'date_visited' exists, set 'dateValue' to it. Otherwise, it remains empty. */
  const dateValue = date_visited ? `value="${newDate}"` : '';

  /* If 'content' exists, set 'textValue' to it. Otherwise, it remains empty. */
  const textValue = content ? content : '';

  /* If 'content' doesn't exist, display a placeholder in the textarea. Otherwise, no placeholder is needed. */
  const placeholderText = !content ? 'placeholder="Space to write a short review, (optional)..."' : '';

  
  form.innerHTML = `
    <div class="input-row">
      <label for="visit" style="white-space: nowrap;">Date of visit (optional):</label>
      <input type="date" id="date_visited" name="date_visited" ${dateValue}>
    </div>
    <textarea id="content" name="content" maxlength="280" ${placeholderText}>${textValue}</textarea>
    <input type="submit" id="save-visit-button" value="Save visit">
  `;
  


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
      //users_visited: currentUserId,
  }).then(data => {
      console.log(data);
      pubElement.classList.add('visited');

      // Fetch the latest pub data after saving the visit
      return fetchData('/api/pubs/', 'POST', {});

    }).then(data => {
      // Update pubData with the latest data and then update the displayed pubs
      pubData = data.pubs;
      updateDisplayedPubs();
      displayMap(pubData)

      // Update the pint glass animation
      pubStats(currentUserId);

      console.log("pubsVisitedPercentage:", pubsVisitedPercentage);


  }).catch(error => {
      console.error('Error:', error);
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
    const custom_pub_id = pub.custom_pub_id;
    const url = pub.url;

    // Creates a div for each pub
    const pubElement = document.createElement('div');
    pubElement.classList.add('pub');

    // gives each pub element a custom_pub_id (from model)
    pubElement.id = custom_pub_id;

    // Assigns the pub's name and address to the new div
    pubElement.innerHTML = `
      <p class="pub-name">${name}</p>
      <p class="pub-address">${address}</p>
    `;

    // If the pub has been visited by the user, it gets a 'visited' class
    let userHasVisited = pub.users_visited.includes(currentUserId);

    if (userHasVisited) {
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

    // zoom map out before then zooming into clicked marker
    if (!isExpanded && !markerClicked) {
      const clickedMarker = markerMap.get(custom_pub_id);
      if (clickedMarker){
        // Zoom out before panning to new location
        map.setZoom(7);
        setTimeout(function() {
          map.panTo(clickedMarker.getPosition());
          setTimeout(function() {
            map.setZoom(11);
          }, 500);
        }, 500);
      }
  }


        if (pubElement.classList.contains('pub-expanded')) {
          // if a pub has a post and is clicked
          if (userHasVisited) {
            if (!pubElement.querySelector('.post')) {
              //const expandedPubHeight = pubElement.offsetHeight * 4;
              //pubElement.style.height = `${expandedPubHeight}px`;

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
              editButton.classList.add('edit-button');
              contentElement.appendChild(editButton);

              // create a delete button
              const deleteButton = document.createElement('button');
              deleteButton.textContent = 'Delete post & visit';
              deleteButton.classList.add('delete-button');
              contentElement.appendChild(deleteButton);

              editButton.addEventListener('click', function () {
                createForm(pubElement, pub.id, fetchPubData, date_visited, content);
              });

              // listener for delete visit button.
              deleteButton.addEventListener('click', function () {
              //fetch request via fetchData function
                fetchData('/api/delete_visit/', 'POST', {
                  pub_id: pub.id,
              }).then(data => {
              // Fetch the latest pub data after deleting the visit
              return fetchData('/api/pubs/', 'POST', {});
              }).then(data => {
              // Update pubData with the latest data and then update the displayed pubs
              pubData = data.pubs;
              updateDisplayedPubs();
              displayMap(pubData);

              console.log("pubsVisitedPercentage:", pubsVisitedPercentage);

              // Update the pint glass animation
              pubStats(currentUserId);

              }).catch(error => {
                  console.error('There has been a problem with your fetch operation:', error);
              });
            });
          }
             } else 
          //if pub doesnt have a post and is clicked, invoke create form function
          {

            if (!pubElement.querySelector('.additional-content')) {
             // const expandedPubHeight = pubElement.offsetHeight * 4;
              //pubElement.style.height = `${expandedPubHeight}px`;

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
          if (userHasVisited) {
            post.remove();
          }
        }
      }
    });
    // Adds the newly created div to the container
    pubsContainer.appendChild(pubElement);
  });
}

// display the map with markers
function displayMap(pubData) {
  //clear exisiting map markers
  for (let i = 0; i < markers.length; i++) {
    markers[i].setMap(null);
  }

  // Clear the markers array
  markers = [];

// Add a marker for each pub
pubData.forEach(item => {
  const pub = item.pub;
  const name = pub.name;
  const  lat = pub.latitude;
  const lng = pub.longitude;
  const custom_pub_id = pub.custom_pub_id;
  const url = pub.url; 
  // DEBUGGING STATEMENT WITH COORDS FOR EACH PUB console.log("Pub:", name, "Longitude:", lng, "Lattitude:", lat);

  let icon;
  let userhasvisited = pub.users_visited.includes(currentUserId);
  if (userhasvisited) {
    icon = '/static/BEERmarker3.png';
  }
  else {
    icon = '/static/LIGHTBLUEmarker3.png';
  }
  
  let marker = new google.maps.Marker({
    position: {lat: lat, lng: lng},
    map,
    title: name,
    icon: icon,
  });

  // add custom_id_property to the map marker
  marker.custom_pub_id = custom_pub_id;

  // set custom pub id as a key and the marker as the value for use in panTo map
  markerMap.set(custom_pub_id, marker);
  
  // join the pub name and url and other text in preparation for populating map marker info windows
  const infoWindowContent = `
  <div class="infoWindowHTML" style="text-align: center;">
    <p><a class='urlHTML' href="${url}" target="_blank" style="font-size:18px;font-family: 'Cabin', sans-serif; ">
     ${name}</a><br></p>
    <p class='infoWindowmaintext' style="font-size:13px; font-family: 'Cabin', sans-serif;word-wrap: break-word;">(The link takes you to the pub's inventory listing at CAMRA where you can find out more.)</p>
  </div>`;


  let InfoWindow = new google.maps.InfoWindow({
    content: infoWindowContent,
  })

  marker.addListener("click", function() {
    markerClicked = true;
    // Set content and open the InfoWindow
    InfoWindow.setContent(infoWindowContent);
    InfoWindow.open(map, marker);
    scrollToPub(custom_pub_id);
    markerClicked = false;
});

  

        // Store the marker for future use
        markers.push(marker);
})

  // Sets the map on all markers in the array.
  for (let i = 0; i < markers.length; i++) {
    markers[i].setMap(map);
  }
}

// clears the searchbox, scrolls the pub whose map marker was clicked to the top of the window and then clicks it.
function scrollToPub(custom_pub_id) {
  document.getElementById('searchInput').value ="";

  // Manually trigger 'input' event
  const event = new Event('input', {
    bubbles: true,
    cancelable: true,
  });
  searchInput.dispatchEvent(event);

  const selectedPub = document.getElementById(custom_pub_id);
  selectedPub.scrollIntoView({behavior: "smooth", block: "start"})
  selectedPub.click()
}

// displays pubs whose name or address is a match or partial match to the search box value.
function updateDisplayedPubs() {
  // Get the current filter value from the search input
  var searchInput = document.getElementById('searchInput');
  var filter = searchInput.value.toUpperCase();

  // Filter the pubs and display the ones that match the filter
  const filteredpubData = pubData.filter(pub =>
    pub.pub.name.toUpperCase().includes(filter) || 
    pub.pub.address.toUpperCase().includes(filter)
  );
  
  displayPubs(filteredpubData);
}


// search box functionality, to search dynamically
function dynamicSearch(){
  updateDisplayedPubs();
}

//creates stats for how many pubs the user has visited, out of XXX many and others.
function pubStats(userid){
  total3starpubs = pubData.length;
  console.log("total3starpubs:", total3starpubs)

  userVisitCount = pubData.filter(pub => pub.pub.users_visited.includes(userid)).length;
  console.log("userVisitCount:", userVisitCount);

   pubsVisitedPercentage = Math.round(((userVisitCount / total3starpubs)*100) * 10) / 10; //working out percentage and rounding it to nearest whole number.
  console.log("pubsVisitedPercentage:", pubsVisitedPercentage);

  // update the pint glass animation now
  updatePintGlassAnimation();

  return {total3starpubs, userVisitCount, pubsVisitedPercentage};
}

function updatePintGlassAnimation() {
  const water = document.querySelector("#animation-water");
  const animationText = document.querySelector("#animation-text");

  let percentage = pubsVisitedPercentage / 100;
  if (percentage > 1) {
    percentage = 1;
  } else if (percentage < 0) {
    percentage = 0;
  }
  water.style.transform = `scaleY(${percentage})`;
  animationText.innerHTML = `${pubsVisitedPercentage}%`;

  const pintBottomContainer = document.querySelector("#pint-bottomcontainer");
  pintBottomContainer.innerHTML = `<br /><h5>(That's ${userVisitCount} out of ${total3starpubs} pubs.)</h5>`
}

// initilise the map
window.initMap = function() {
  map = new google.maps.Map(document.getElementById('map-container'), {
    mapId:'5d9e03b671899eb4',
          center: {lat: 54.09341667, lng: -2.89477778},
      zoom: 6
  });
    // Initialize InfoWindow 
    InfoWindow = new google.maps.InfoWindow();
}

// calls main function
document.addEventListener('DOMContentLoaded', (event) => {
  console.log("user_is_logged_in = ", user_is_logged_in, " Type: ", typeof user_is_logged_in);

  // Check if user is logged in before fetching pub data
  if (user_is_logged_in) {
      fetchPubData();
      console.log("fetchPubData was called");
  }
});


// only runs google maps script if user is logged in.
if (user_is_logged_in) {
  // Create the script tag, set the appropriate attributes
  var script = document.createElement('script');
  script.src = 'https://maps.googleapis.com/maps/api/js?key=***REMOVED***&callback=initMap';
  script.defer = true;

  // Append the 'script' element to 'head'
  document.head.appendChild(script);
}
