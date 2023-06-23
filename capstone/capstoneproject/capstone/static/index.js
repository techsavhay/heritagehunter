function fetchPubData() {
  fetch('/api/pubs/', {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
    },
    body: JSON.stringify({}),
  })
  .then(response => response.json())
  .then(data => {

    // logs the response data in console
    console.log(data);
    // process data and update html elements
    
    const pubsContainer = document.querySelector("#pubs-container");
    pubsContainer.innerHTML = '';

    data.forEach(item => {
      const pub = item.pub;
      // Access pub properties
      const name = pub.name;
      const address = pub.address;

      const pubElement = document.createElement("div");
      pubElement.classList.add("pub");
    
      pubElement.innerHTML = `
        <h5>${name}</h5>
        <p class="pub-address">${address}</p>
      `;
      pubsContainer.appendChild(pubElement);
    });
  })
  .catch(error => {
    // handle errors that occur by telling console
    console.error('Error fetching data:', error);
  });
}

fetchPubData();
