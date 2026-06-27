""" Geoapify venue fetching """

# libraries
import requests
import streamlit as st

# free API from Geoapify
API_KEY = st.secrets["GEOAPIFY_API_KEY"]   # this is located in secrets folder

def fetch_venues(lat: float, lng: float) -> list[dict]:
    """Fetch nearby restaurants, pubs and cafes

    Args:
    lat: Latitude of the destination
    lng: Longitude of the destination

    Returns a list of dictionaries with each element in the format:
    {'name': 'string',
    'category': 'restaurant, pub or cafe',    # may be unknown by default if it cannot find a caegory
    'lat': float, 
    'lng': float}
    """
    
    # url
    url = "https://api.geoapify.com/v2/places"
    # parameters
    params = {
    "categories":
        "catering.restaurant,"
        "catering.pub,"
        "catering.cafe",

    "filter": f"circle:{lng},{lat},500",   # radius of 500m
    "limit": 20,   # limit to 20 for display map, can be altered
    "apiKey": API_KEY
    }

    # call for info, and check 200 code for connection
    response = requests.get(url, params=params)
    #print(response.status_code)
    data = response.json()

    # build venue list
    
    venues = []

    for place in data["features"]:
        properties = place["properties"]
        
        # extract the venue type
        categories = properties.get("categories", [])
        venue_type = "Unknown"
        
        for category in categories:
            if category.startswith("catering."):
                venue_type = category.replace("catering.", "")
                break
        # add venue to list
        venues.append({
            "name": properties.get("name", "Unknown"),
            "category": venue_type,
            "lat": properties["lat"],
            "lng": properties["lon"]
        })

    return venues
