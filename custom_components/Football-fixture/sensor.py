from datetime import timedelta
import requests
import logging
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import time

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Football Fixture'
SCAN_INTERVAL = timedelta(minutes=120)  # Set the update interval to 120 minutes (2 hours)
MAX_RETRIES = 3  # Number of retries for API requests

# Define the platform schema, requiring the API key and allowing an optional name
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    # Retrieve the API key and name from the configuration
    api_key = config.get(CONF_API_KEY)
    name = config.get(CONF_NAME)

    # Create an instance of FootballFixtureSensor with the API key and name
    add_entities([FootballFixtureSensor(api_key, name)], True)

class FootballFixtureSensor(Entity):
    def __init__(self, api_key, name):
        self._api_key = api_key  # Store the API key for use in requests
        self._name = name        # Store the name of the sensor
        self._state = None
        self._attributes = {}
        self._league_id = "140"  # Default to La Liga

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        self._fetch_fixtures()

    def _fetch_fixtures(self):
        url = f"https://v3.football.api-sports.io/fixtures?season=2024&league={self._league_id}&round=Regular Season - 1"
        headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': self._api_key  # Use the API key in the headers for authentication
        }
        _LOGGER.debug(f"Fetching fixtures for league ID {self._league_id}")
        
        retries = 0
        while retries < MAX_RETRIES:
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()  # Raises an HTTPError if the response was unsuccessful
                
                try:
                    data = response.json()
                    _LOGGER.debug("Fixtures response data: %s", data)
                    break  # Exit the loop on successful data retrieval
                except ValueError as json_err:
                    _LOGGER.error(f"Error decoding JSON response: {json_err}")
                    self._state = "Invalid API response"
                    self._attributes = {}
                    return

            except requests.exceptions.RequestException as e:
                _LOGGER.error(f"Error fetching fixtures from {url}: {e}")
                retries += 1
                if retries < MAX_RETRIES:
                    _LOGGER.info(f"Retrying... ({retries}/{MAX_RETRIES})")
                    time.sleep(2 ** retries)  # Exponential backoff
                else:
                    self._state = "API error"
                    self._attributes = {}
                    return

        # Process the data if successfully retrieved
        if data and 'response' in data and data['response']:
            self._state = f"{len(data['response'])} fixtures found"
            self._attributes['fixtures'] = [
                {
                    'home_team': fixture.get('teams', {}).get('home', {}).get('name', 'Unknown'),
                    'away_team': fixture.get('teams', {}).get('away', {}).get('name', 'Unknown'),
                    'date': fixture.get('fixture', {}).get('date', 'Unknown'),
                    'venue': fixture.get('fixture', {}).get('venue', {}).get('name', 'Unknown'),
                    'home_team_logo': fixture.get('teams', {}).get('home', {}).get('logo', ''),
                    'away_team_logo': fixture.get('teams', {}).get('away', {}).get('logo', ''),
                    'score': fixture.get('score', {}).get('fulltime', {'home': None, 'away': None})
                }
                for fixture in data['response']
            ]
        else:
            self._state = "No fixtures found"
            self._attributes = {}
