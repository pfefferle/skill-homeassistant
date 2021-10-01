from requests import get, post
from fuzzywuzzy import fuzz
import json
from requests.exceptions import Timeout, RequestException


__author__ = 'btotharye'

# Timeout time for HA requests
TIMEOUT = 10


class HomeAssistantClient(object):

    def __init__(self, host, token, portnum, ssl=False, verify=True):
        self.ssl = ssl
        self.verify = verify
        if self.ssl:
            self.url = "https://{}".format(host)
        else:
            self.url = "http://{}".format(host)
        if portnum:
            self.url = "{}:{}".format(self.url, portnum)
        self.headers = {
            'Authorization': "Bearer {}".format(token),
            'Content-Type': 'application/json'
        }

    def _get_state(self):
        """Get state object

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)
        """
        if self.ssl:
            req = get("{}/api/states".format(self.url), headers=self.headers,
                      verify=self.verify, timeout=TIMEOUT)
        else:
            req = get("{}/api/states".format(self.url), headers=self.headers,
                      timeout=TIMEOUT)
        req.raise_for_status()
        return req.json()

    def connected(self):
        try:
            self._get_state()
            return True
        except (Timeout, ConnectionError, RequestException):
            return False

    def find_entity(self, entity, types):
        """Find entity with specified name, fuzzy matching

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)
        """
        json_data = self._get_state()
        # require a score above 50%
        best_score = 50
        best_entity = None
        if json_data:
            for state in json_data:
                try:
                    if state['entity_id'].split(".")[0] in types:
                        # something like temperature outside
                        # should score on "outside temperature sensor"
                        # and repetitions should not count on my behalf
                        score = fuzz.token_sort_ratio(
                            entity,
                            state['attributes']['friendly_name'].lower())
                        if score > best_score:
                            best_score = score
                            best_entity = {
                                "id": state['entity_id'],
                                "dev_name": state['attributes']
                                ['friendly_name'],
                                "state": state['state'],
                                "best_score": best_score,
                                "attributes":state['attributes']}
                        score = fuzz.token_sort_ratio(
                            entity,
                            state['entity_id'].lower())
                        if score > best_score:
                            best_score = score
                            best_entity = {
                                "id": state['entity_id'],
                                "dev_name": state['attributes']
                                ['friendly_name'],
                                "state": state['state'],
                                "best_score": best_score,
                                "attributes":state['attributes']}
                except KeyError:
                    pass
            return best_entity

    def find_entity_attr(self, entity):
        """checking the entity attributes to be used in the response dialog.

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)
        """
        json_data = self._get_state()

        if json_data:
            for attr in json_data:
                if attr['entity_id'] == entity:
                    entity_attrs = attr['attributes']
                    try:
                        if attr['entity_id'].startswith('light.'):
                            # Not all lamps do have a color
                            unit_measur = entity_attrs['brightness']
                        else:
                            unit_measur = entity_attrs['unit_of_measurement']
                    except KeyError:
                        unit_measur = ""
                    # IDEA: return the color if available
                    # TODO: change to return the whole attr dictionary =>
                    # free use within handle methods
                    sensor_name = entity_attrs['friendly_name']
                    sensor_state = attr['state']
                    entity_attr = {
                        "unit_measure": unit_measur,
                        "name": sensor_name,
                        "state": sensor_state
                    }
                    return entity_attr
        return None

    def execute_service(self, domain, service, data):
        """Execute service at HAServer

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)
        """
        if self.ssl:
            r = post("{}/api/services/{}/{}".format(self.url, domain, service),
                     headers=self.headers, data=json.dumps(data),
                     verify=self.verify, timeout=TIMEOUT)
        else:
            r = post("{}/api/services/{}/{}".format(self.url, domain, service),
                     headers=self.headers, data=json.dumps(data),
                     timeout=TIMEOUT)
        r.raise_for_status()
        return r

    def find_component(self, component):
        """Check if a component is loaded at the HA-Server

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)
        """
        if self.ssl:
            req = get("{}/api/components".format(self.url),
                      headers=self.headers, verify=self.verify,
                      timeout=TIMEOUT)
        else:
            req = get("%s/api/components" % self.url, headers=self.headers,
                      timeout=TIMEOUT)

        req.raise_for_status()
        return component in req.json()

    def engage_conversation(self, utterance):
        """Engage the conversation component at the Home Assistant server

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)
        Attributes:
            utterance    raw text message to be processed
        Return:
            Dict answer by Home Assistant server
            { 'speech': textual answer,
              'extra_data': ...}
        """
        data = {
            "text": utterance
        }
        if self.ssl:
            r = post("{}/api/conversation/process".format(self.url),
                     headers=self.headers,
                     data=json.dumps(data),
                     verify=self.verify,
                     timeout=TIMEOUT
                     )
        else:
            r = post("{}/api/conversation/process".format(self.url),
                     headers=self.headers,
                     data=json.dumps(data),
                     timeout=TIMEOUT
                     )
        r.raise_for_status()
        return r.json()['speech']['plain']
