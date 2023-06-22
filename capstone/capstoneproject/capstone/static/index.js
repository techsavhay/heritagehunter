

function fetchPubData() {
    fetch('/api/pubs/', {
        method: "POST",
      })
      .then(response => response.json())
      .then(data => {
        // process data and update html elements
        
        pubsContainer = document.querySelector("#pubs-container");
        pubsContainer.innerHTML = '';

        data.pubs.forEach(pub => {
            const postElement = document.createElement("div");
            postElement.classList.add("pub");
        
        postElement.innerHTML = `
        <h5>${pub.name}</h5>
        <p class="pub-address">${pub.address}</p>
        `
        })
      })
      .catch(error => {
        // handle errors that occur by telling console
        console.error('Error fetching data:', error);
      })
    }