# Heritage Hunter
This project is a web application that helps users find and track their visits to the United Kingdom's most unspoilt historic pubs.

---

## Distinctiveness and Complexity

I have outlined the projects complex and distinctive properties below.

The webapp’s fundamental concept is very unique. I wanted to create something that hadn’t been made before, and although there are websites that map pubs throughout the United Kingdom, this is a web app which exclusively deals with the approximately 300 that are deemed nationally significant and its  interactive features  makes it unique.

It doesn't just present information to the user. Once they have logged in, there are a number of collaborative features including:
Clicking a marker on the map will scroll the pub list to the corresponding entry and open it for editing. From there, users can mark it as visited, specify the date of their visit, and add notes.
Marking a pub as ‘visited’ will trigger several actions:
   - Update the database to save the visit using a POST request.
   - Change the colour of the pub entry and the corresponding marker on the map
   - Update the 'totalometer' on the right-hand side of the page.

For login and sign-up, I used OAuth, and incorporated Gmail's 'Social Sign-In' functions for user convenience. The sign-in page was customized with a Google logo, and the CSS on other pages was adjusted to fit the theme of the website. To mitigate potential server costs and charges from using the Google Maps JavaScript API, I created a function to present a 'welcome page' to users not already logged in. This page outlines the web app's concept and directs users to log in or sign up, preventing unnecessary API calls. This setup also enables the monitoring of each user's API usage if needed in the future.

The app includes a Google Map at its centre, which necessitated learning the requirements of the Google Maps JavaScript API. The map was customized using Google's Map Styles Editor to harmonize with the look and feel of the web app. 

I aimed for an interactive and engaging map experience. Thus, when a user selects a pub from the pub list, a form appears in the list while the map simultaneously relocates and zooms into the selected pub. This seamless interaction was achieved using the Google Maps JavaScript API. 

The initial pub data didn't include GPS or other location information, apart from the postal addresses. Consequently, I created a new Django command to geocode the pub addresses using Google's Geocoding API. With this extra data stored in my database, I was able to generate markers for each pub. To ensure enhanced responsiveness and reduced server traffic/costs, my code runs locally in JavaScript only needing to fetch data from the server when initially loading, and then on save and delete commands.


Beyond clicking the map markers, a user can find a pub by scrolling the alphabetical list or using the dynamic search box above the list. This dynamic search feature enhances interactivity by providing real-time result updates as the user types their query. To improve the search's usability, users can search across multiple attributes of a pub, such as its name and address. Advanced filtering algorithms were implemented for case-insensitive, partial text matching across different fields of our data structure, making the application more flexible and user-friendly.

Another distinctive feature is a pint glass SVG animation that updates according to the user's pub visits. The animation fills beer into a glass to represent the percentage of three-star heritage pubs the user has visited. 

The pint glass animation's functionality is multi-layered. The app calculates the total number of three-star pubs in the database and how many of those have been visited by the user, which required me to work with array methods and manage the state in JavaScript. The pint glass animation is created using SVG and CSS. As users visit more pubs, the 'scaleY' property of the SVG element, representing the beer, changes dynamically. This required a sound understanding of CSS transformations and SVG manipulation. In addition to the animation, I included real-time updates to the information displayed below the glass, providing raw statistics. This was achieved using real-time DOM manipulation, which updates the UI based on user actions.
I have ensured that my web app is also mobile responsive by adding in various css rules to resize and reorder the elements accordingly.

Anticipating potential future expansion, my database contains over 2000 pub entries (including three-star, two-star, and one-star pubs). This enables potential incorporation of these entries into my app at a later date, if required.

In order to efficiently manage, serve, and manipulate pub and user data for my web app, I created a custom API using Django. The custom API supports several key features of the app, including user login, retrieval, and modification of pub information, and tracking of pub visits.
The two models I defined represent 'Pubs' and 'Posts'. Each Pub object includes fields such as id, name, address, GPS coordinates, a custom pub id (on which I added distinct hashes based on the addresses), a description, and a URL. I also created a ‘users_visited’ field that keeps track of which users have visited each pub.

The Post model is used to save details about each user's visits to different pubs, including the date and any notes or comments they made about the visit.
One key aspect of my API is the 'pubs_api' function. This function is protected by the ‘login_required’ decorator to ensure only authenticated users can access it. It fetches the data for all three-star pubs that are open. It also fetches the posts associated with each pub and the current user, which is done by filtering the pub's posts with the current user.

This data is then structured into a format suitable for the application's needs and is sent back as a JSON response. To ensure the data is correctly formatted before sending it back, I created the 'encode_pub' and 'encode_post' functions.

To keep track of visits, I created the 'save_visit' function, which allows a user to log a pub visit. The function uses the POST HTTP method, meaning it will update the server with new information, such as a new visit to a pub. The function first loads the data sent by the client, then gets the pub associated with the sent ‘pub_id’, creates a new Post object with the received data, saves it, and finally adds the user to the pub's ‘users_visited’ field.

Lastly, there is the 'delete_visit' function, which removes a user's visit to a pub. This function also uses the POST HTTP method. The function first loads the data sent by the client, finds all posts related to a specific pub by a specific user, removes the user from the pub's users_visited field, and then deletes the associated posts.

This custom API has allowed me to tailor the functionality of my web app to its specific needs and allow for future expansion.

---

## What’s contained in each file.
#### geocode_addresses.py
This file contain code which takes an address (from more pub database) and using the google maps geocode API generates a latitude and longitude value for it. This can then be used later on to add markers to the map. This file is set up to be able to run as a command.
#### json_importer.py
This file deals with converting the pub data from a json format and importing it into my Django ‘pub’ model. 
It opens the json file and loads its contents, it then iterates over each pub doing the following:
Extracts relevant fields from the data, such as the pub name, address, description, inventory stars, status, and URL.
It maps the 'Inventory Stars' string to a corresponding numeric value. If there's no mapping, it assigns None.
It determines if the pub is open based on the 'Status' field.
It generates a unique id for each pub. I created a ‘generate_unique_id’ function to give each pub a unique ID based off of its address (which wont change) as I was worried that relying on Django’s built in numbering was potentially vulnerable to errors later down the line if some of the data needed reimporting or updating.
It checks if a pub with the same ID already exists in the database. If it does, it updates the existing pub's information. If it doesn't, it creates a new Pub instance and saves it to the database.
#### migrations folder and files
Stores Django’s migrations. In here you can see the evolution of my models including test models I made to trial import functions.
#### static > images folder and files
Stores images to be used on the web app. The images that are used are two different marker colours for the maps and a google sign-in logo.
#### VERIFIED_pub_info_2023-06-06_16-45-00.json
This is a json file containing pub data.
#### index.js
This is my front end main javascript file. It contains function which call upon my API to fetch information from the Pubs and Posts models. It can also ask the api to save new or edited posts as well as delete posts.
It deals with displaying the pub list, post and forms, map (with markers), calculating the statistics (to be passed to the animation) and the dynamic search functionality. 
The main function only runs if a user is logged in.

#### styles.css
This contains the majority of the css rules for my web app. Some of the rules overrule bootstrap and others are designed to ensure it runs and displays well on smartphones. 
#### base.html 
django-allauth package allows you to override its built in login templates by creating your own with the same name in your project's templates directory. Base.html is one of these, and just deals with displaying the various login and logout templates.
#### login.html
This is a template which overrides the default django-allauth login template, allowing me to change the styling which I have done here by using inline css in the html code.
#### logout.html
This is a template which overrides the default django-allauth logout template, allowing me to change the styling which I have done here by using inline css in the html code.
#### profile.html
This is a template which overrides the default django-allauth profile template, allowing me to change the styling and html.
#### signup.html
This is a template which overrides the default django-allauth signup template, allowing me to change the styling which I have done here by using inline css in the html code.

#### provider_list.html
This is a template which overrides the default django-allauth social login provider list allowing me to change the styling which I have done here by adding a google sign in logo to make the sign in process feel more familiar to users.

#### index.html
This is the main html page for my web app. It contains html code as well as some bootstrap and Django. It creates a navigation bar at the top of the page with a search box, page title and login/ logout button. Below that it creates three containers, the first is to hold the list of pubs, the second is to hold the google map and the third is to display the pint glass animation.
If a user isn’t logged in it displays a welcome page over the top of the page.

#### admin.py
This is part of Django’s built in infrastructure but has been adapted. The script first fetches the User model and registers it with the Django admin interface. Two models, Pub and Post, are explicitly configured for the admin interface. The Pub model's admin interface is customized to display and filter by the name, address, inventory stars, and open status of the pubs. It also overrides the search functionality to include searching by the usernames of users who have visited the pubs. The Post model's admin interface, shows and filters by the post content, date visited, owner, and the creation date. It also includes a method to retrieve the associated pub's name.
#### models.py
This is Django’s built in models file. In it I have created twp models, Post and Pub. Post stores users posts and defines rules for each field as well as having a foreign key relationship with the Pub model.
Pub defines the fields and rules for each pub including fields that are not currently used in this app (description, photos etc) but that leave open future development.
#### tests.py
This file includes a straightforward test for an API endpoint, fetching data related to 'pubs' and 'posts'. The script sends a request to the 'pubs_api' endpoint, verifies that the request was successful, and checks that the response contains the expected data. It also ensures that there are at least three 'pubs' in the data before printing the results in a neatly formatted manner.
#### urls.py
This file establishes the URL routes for the application. It includes a homepage, accessible at the root URL (""), and routes for account management, user profiles, and actions related to 'pubs', such as viewing a list of all pubs, saving a visit to a pub, and deleting a recorded visit. 
#### views.py
This contains several Django view functions that handle requests from the javascript web app. It defines utility functions ‘encode_pub’ and ‘encode_post’ that convert Pub and Post models into dictionaries for conversion to JSON. The index function serves the homepage of the app, where it lists the pubs if the user is authenticated. 
In the pubs_api function, it retrieves the authenticated user's posts related to specific pubs and returns them in a JSON response. Two other views, save_visit and delete_visit, handle the posting and deletion of a visit to a pub. They receive post data in JSON format, extract the necessary details, and then create or delete Post instances and update the Pub model's ‘users_visited’ field.
#### capstone project > staticfiles folder
This folder was automatically created after running a command to gather all the static files in one place. It has added images and other css files to the sub folders.
#### db.sqlite3
This is a file automatically created by Django, there are two in my project, one contains the database for my project including pubs and posts, the other is empty.
#### settings.py
This is settings file created by Django. I have amended it to deal with allauth social login, and also to point to the correct database and static files.
#### urls.py (capstoneproject folder)
In this file, I've made sure to activate the built-in Django admin interface by linking it to the /admin/ URL. I've also tied in the URLs from my 'capstone' application, ensuring they're accessible directly from the root URL (/). This effectively incorporates any URL routes that I've outlined within my 'capstone' application into the project's main navigation.

#### wsgi.py
Sets up the Web Server Gateway Interface for the project.

#### .gitignore
A file which contains a list of files that I don’t want git to commit to the repository. Usually for security or efficiency reasons.

#### manage.py
Allows command line operations for certain management tasks.

#### readme.md
Contains information on the project, how to run it, my it is distinct and unique and info on files I created **#meta**

#### requirements.txt
Contains a list of packages that need to be installed in order to run the project successfully.

---

## How to run the application
To run the application do the following:

1. make sure Python and Django are installed. 

2. Navigate to the project 

3. Install the dependencies 

>pip install -r requirements.txt

4. Apply the migrations to create your database

>python manage.py makemigrations

>python manage.py migrate

5. Run the development server

>python manage.py runserver

6. Click the link and view the web app in a modern web browser that supports html5 and the latest JavaScript.

## Anything else

I am unsure how other people could run the app without me shared my google api credentials/ login. therefore i have told google to accept requests from localhost which hopefully will help you to run the code.

