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
        self._current_round = None  # Start with no round, fetch dynamically
        self._last_fetched_data = {}  # Initialize to store the last fetched data

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
        
        # Fetch the current round first
        self._fetch_current_round()
        
        # Fetch all fixtures for the entire season in one call
        self._fetch_all_fixtures()



    def _fetch_current_round(self):
        url = f"https://v3.football.api-sports.io/fixtures/rounds?league={self._league_id}&season=2024&current=true"
        headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': self._api_key
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if 'response' in data and data['response']:
                # Extract the current round number from the API response
                self._current_round = int(data['response'][0].split(" - ")[-1])
                self._attributes['current_round'] = self._current_round  # Store the current round in attributes
            else:
                _LOGGER.error("No current round found in API response")
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Error fetching current round: {e}")

    def _fetch_all_fixtures(self):
        url = f"https://v3.football.api-sports.io/fixtures?league={self._league_id}&season=2024"
        headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': self._api_key
        }
        _LOGGER.debug(f"Fetching all fixtures for league ID {self._league_id}")

        retries = 0
        while retries < MAX_RETRIES:
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                if 'response' in data and data['response']:
                    fixtures_by_round = {}
                    for fixture in data['response']:
                        round_number = fixture.get('league', {}).get('round', 'Unknown').split(" - ")[-1]
                        if round_number not in fixtures_by_round:
                            fixtures_by_round[round_number] = []
                        fixtures_by_round[round_number].append({
                            'home_team': fixture.get('teams', {}).get('home', {}).get('name', 'Unknown'),
                            'away_team': fixture.get('teams', {}).get('away', {}).get('name', 'Unknown'),
                            'date': fixture.get('fixture', {}).get('date', 'Unknown'),
                            'venue': fixture.get('fixture', {}).get('venue', {}).get('name', 'Unknown'),
                            'home_team_logo': fixture.get('teams', {}).get('home', {}).get('logo', ''),
                            'away_team_logo': fixture.get('teams', {}).get('away', {}).get('logo', ''),
                            'score': fixture.get('score', {}).get('fulltime', {'home': None, 'away': None})
                        })

                    # Update attributes for all rounds
                    for round_number, fixtures in fixtures_by_round.items():
                        attribute_key = f"Round {round_number} Fixtures"
                        if fixtures != self._last_fetched_data.get(attribute_key):
                            self._attributes[attribute_key] = fixtures
                            self._last_fetched_data[attribute_key] = fixtures  # Update the cache with the latest data
                    self._state = f"{len(fixtures_by_round)} rounds fetched"
                else:
                    _LOGGER.error(f"No fixtures found for league ID {self._league_id}")
                break
            except requests.exceptions.RequestException as e:
                _LOGGER.error(f"Error fetching fixtures from {url}: {e}")
                retries += 1
                if retries < MAX_RETRIES:
                    _LOGGER.info(f"Retrying... ({retries}/{MAX_RETRIES})")
                    time.sleep(2 ** retries)  # Exponential backoff
                else:
                    _LOGGER.error("Max retries reached. Failed to fetch fixtures.")
