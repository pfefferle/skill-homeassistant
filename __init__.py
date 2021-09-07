from mycroft.skills.core import FallbackSkill
from mycroft.util.format import nice_number
from mycroft import MycroftSkill, intent_handler

from sys import exc_info

from requests.exceptions import (
    RequestException,
    Timeout,
    InvalidURL,
    URLRequired,
    SSLError,
    HTTPError)
from requests.packages.urllib3.exceptions import MaxRetryError

from .ha_client import HomeAssistantClient


__author__ = 'robconnolly, btotharye, nielstron'

# Timeout time for HA requests
TIMEOUT = 10


class HomeAssistantSkill(FallbackSkill):

    def __init__(self):
        MycroftSkill.__init__(self)
        super().__init__(name="HomeAssistantSkill")
        self.ha = None
        self.enable_fallback = False

    def _setup(self, force=False):
        if self.settings is not None and (force or self.ha is None):
            ip = self.settings.get('host')
            token = self.settings.get('token')

            # Check if user filled IP, port and Token in configuration
            if not ip:
                self.speak_dialog('homeassistant.error.setup', data={
                              "field": "I.P."})
                return

            if not token:
                self.speak_dialog('homeassistant.error.setup', data={
                              "field": "token"})
                return

            portnumber = self.settings.get('portnum')
            try:
                portnumber = int(portnumber)
            except TypeError:
                portnumber = 8123
            except ValueError:
                # String might be some rubbish (like '')
                self.speak_dialog('homeassistant.error.setup', data={
                              "field": "port"})
                return

            self.ha = HomeAssistantClient(
                ip,
                token,
                portnumber,
                self.settings.get('ssl'),
                self.settings.get('verify')
            )
            if self.ha.connected():
                # Check if conversation component is loaded at HA-server
                # and activate fallback accordingly (ha-server/api/components)
                # TODO: enable other tools like dialogflow
                conversation_activated = self.ha.find_component(
                    'conversation'
                )
                if conversation_activated:
                    self.enable_fallback = \
                        self.settings.get('enable_fallback')

    def _force_setup(self):
        self.log.debug('Creating a new HomeAssistant-Client')
        self._setup(True)

    def initialize(self):
        self.language = self.config_core.get('lang')

        # Needs higher priority than general fallback skills
        self.register_fallback(self.handle_fallback, 2)
        # Check and then monitor for credential changes
        self.settings_change_callback = self.on_websettings_changed
        self._setup()

    def on_websettings_changed(self):
        # Force a setting refresh after the websettings changed
        # Otherwise new settings will not be regarded
        self._force_setup()

    # Try to find an entity on the HAServer
    # Creates dialogs for errors and speaks them
    # Returns None if nothing was found
    # Else returns entity that was found
    def _find_entity(self, entity, domains):
        self._setup()
        if self.ha is None:
            self.speak_dialog('homeassistant.error.setup')
            return False
        # TODO if entity is 'all', 'any' or 'every' turn on
        # every single entity not the whole group
        ha_entity = self._handle_client_exception(self.ha.find_entity,
                                                  entity, domains)
        if ha_entity is None:
            self.speak_dialog('homeassistant.device.unknown', data={
                              "dev_name": entity})
        return ha_entity

    # Routine for entiti availibility check
    def _check_availability(self, ha_entity):
        """ Simple routine for checking availability of entity inside
        Home Assistent. """

        if ha_entity['state'] == 'unavailable':
            """ Check if state is `unavailable`, if yes, inform user about it. """

            self.speak_dialog('homeassistant.device.unavailable', data={
                            "dev_name": ha_entity['dev_name']})
            """ Return result to underliing function. """
            return False
        return True

    # Calls passed method and catches often occurring exceptions
    def _handle_client_exception(self, callback, *args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except Timeout:
            self.speak_dialog('homeassistant.error.offline')
        except (InvalidURL, URLRequired, MaxRetryError) as e:
            if e.request is None or e.request.url is None:
                # There is no url configured
                self.speak_dialog('homeassistant.error.needurl')
            else:
                self.speak_dialog('homeassistant.error.invalidurl', data={
                                  'url': e.request.url})
        except SSLError:
            self.speak_dialog('homeassistant.error.ssl')
        except HTTPError as e:
            # check if due to wrong password
            if e.response.status_code == 401:
                self.speak_dialog('homeassistant.error.wrong_password')
            else:
                self.speak_dialog('homeassistant.error.http', data={
                    'code': e.response.status_code,
                    'reason': e.response.reason})
        except (ConnectionError, RequestException) as exception:
            # TODO find a nice member of any exception to output
            self.speak_dialog('homeassistant.error', data={
                    'url': exception.request.url})

        return False

    # Intent handlers
    @intent_handler('turn.on.intent')
    def handle_turn_on_intent(self, message):
        self.log.debug("Turn on intent on entity: "+message.data.get("entity"))
        message.data["Entity"] = message.data.get("entity")
        message.data["Action"] = "on"
        self._handle_turn_actions(message)

    @intent_handler('turn.off.intent')
    def handle_turn_off_intent(self, message):
        self.log.debug(message.data)
        self.log.debug("Turn off intent on entity: "+message.data.get("entity"))
        message.data["Entity"] = message.data.get("entity")
        message.data["Action"] = "off"
        self._handle_turn_actions(message)

    @intent_handler('toggle.intent')
    def handle_toggle_intent(self, message):
        self.log.debug("Toggle intent on entity: " + message.data.get("entity"))
        message.data["Entity"] = message.data.get("entity")
        message.data["Action"] = "toggle"
        self._handle_turn_actions(message)

    @intent_handler('sensor.intent')
    def handle_sensor_intent(self, message):
        self.log.debug("Turn on intent on entity: "+message.data.get("entity"))
        message.data["Entity"] = message.data.get("entity")
        self._handle_sensor(message)

    @intent_handler('set.light.brightness.intent')
    def handle_light_set_intent(self, message):
        self.log.debug("Change light intensity: "+message.data.get("entity") \
            +"to"+message.data.get("brightnessvalue")+"percent")
        message.data["Entity"] = message.data.get("entity")
        message.data["Brightnessvalue"] = message.data.get("brightnessvalue")
        self._handle_light_set(message)

    @intent_handler('increase.light.brightness.intent')
    def handle_light_increase_intent(self, message):
        self.log.debug("Increase light intensity: "+message.data.get("entity"))
        message.data["Entity"] = message.data.get("entity")
        message.data["Action"] = "up"
        self._handle_light_adjust(message)

    @intent_handler('decrease.light.brightness.intent')
    def handle_light_decrease_intent(self, message):
        self.log.debug("Decrease light intensity: "+message.data.get("entity"))
        message.data["Entity"] = message.data.get("entity")
        message.data["Action"] = "down"
        self._handle_light_adjust(message)

    @intent_handler('automation.intent')
    def handle_automation_intent(self, message):
        self.log.debug("Automation trigger intent on entity: "+message.data.get("entity"))
        message.data["Entity"] = message.data.get("entity")
        self._handle_automation(message)

    @intent_handler('tracker.intent')
    def handle_tracker_intent(self, message):
        self.log.debug("Turn on intent on entity: "+message.data.get("entity"))
        message.data["Entity"] = message.data.get("entity")
        self._handle_tracker(message)

    @intent_handler('set.climate.intent')
    def handle_set_thermostat_intent(self, message):
        self.log.debug("Set thermostat intent on entity: "+message.data.get("entity"))
        message.data["Entity"] = message.data.get("entity")
        message.data["Temp"] = message.data.get("temp")
        self._handle_set_thermostat(message)

    @intent_handler('add.item.shopping.list.intent')
    def handle_shopping_list_intent(self, message):
        self.log.debug("Add : "+message.data.get("entity")+"to the shoping list")
        message.data["Entity"] = message.data.get("entity")
        self._handle_shopping_list(message)

    def _handle_turn_actions(self, message):
        self.log.debug("Starting Switch Intent")
        entity = message.data["Entity"]
        action = message.data["Action"]
        self.log.debug("Entity: %s" % entity)
        self.log.debug("Action: %s" % action)

        # Handle turn on/off all intent
        try:
            if self.voc_match(entity,"all_lights"):
                domain = "light"
            elif self.voc_match(entity,"all_switches"):
                domain = "switch"
            else:
                domain = None

            if domain is not None:
                ha_entity = {'dev_name': entity}
                ha_data = {'entity_id': 'all'}

                self.ha.execute_service(domain, "turn_%s" % action, ha_data)
                self.speak_dialog('homeassistant.device.%s' % action, data=ha_entity)
                return
        # TODO: need to figure out, if this indeed throws a KeyError
        except KeyError:
            self.log.debug("Not turn on/off all intent")
        except:
            self.log.debug("Unexpected error in turn all intent:", exc_info()[0])

        # Hande single entity

        ha_entity = self._find_entity(
            entity,
            [
                'group',
                'light',
                'fan',
                'switch',
                'scene',
                'input_boolean',
                'climate'
            ]
        )

        # Exit if entiti not found or is unavailabe
        if not ha_entity or not self._check_availability(ha_entity):
            return

        self.log.debug("Entity State: %s" % ha_entity['state'])

        ha_data = {'entity_id': ha_entity['id']}

        # IDEA: set context for 'turn it off' again or similar
        # self.set_context('Entity', ha_entity['dev_name'])
        if ha_entity['state'] == action:
            self.log.debug("Entity in requested state")
            self.speak_dialog('homeassistant.device.already', data={
                "dev_name": ha_entity['dev_name'], 'action': action})
        elif action == "toggle":
            self.ha.execute_service("homeassistant", "toggle",
                                    ha_data)
            if(ha_entity['state'] == 'off'):
                action = 'on'
            else:
                action = 'off'
            self.speak_dialog('homeassistant.device.%s' % action,
                              data=ha_entity)
        elif action in ["on", "off"]:
            self.speak_dialog('homeassistant.device.%s' % action,
                              data=ha_entity)
            self.ha.execute_service("homeassistant", "turn_%s" % action,
                                    ha_data)
        else:
            self.speak_dialog('homeassistant.error.sorry')
            return

    def _handle_light_set(self, message):
        entity = message.data["entity"]
        try:
            brightness_req = float(message.data["Brightnessvalue"])
            if brightness_req > 100 or brightness_req < 0:
                self.speak_dialog('homeassistant.brightness.badreq')
        except KeyError:
            brightness_req = 10.0
        brightness_value = int(brightness_req / 100 * 255)
        brightness_percentage = int(brightness_req)
        self.log.debug("Entity: %s" % entity)
        self.log.debug("Brightness Value: %s" % brightness_value)
        self.log.debug("Brightness Percent: %s" % brightness_percentage)

        ha_entity = self._find_entity(entity, ['group', 'light'])
        # Exit if entiti not found or is unavailabe
        if not ha_entity or not self._check_availability(ha_entity):
            return

        ha_data = {'entity_id': ha_entity['id']}

        # IDEA: set context for 'turn it off again' or similar
        # self.set_context('Entity', ha_entity['dev_name'])
        # Set values for HA
        ha_data['brightness'] = brightness_value
        self.ha.execute_service("light", "turn_on", ha_data)
        # Set values for mycroft reply
        ha_data['dev_name'] = ha_entity['dev_name']
        ha_data['brightness'] = brightness_req
        self.speak_dialog('homeassistant.brightness.dimmed',
                          data=ha_data)

        return

    def _handle_shopping_list(self, message):
        entity = message.data["Entity"]
        ha_data = {'name': entity}
        self.ha.execute_service("shopping_list", "add_item", ha_data)
        self.speak_dialog("homeassistant.shopping.list")
        return

    def _handle_light_adjust(self, message):
        entity = message.data["Entity"]
        action = message.data["Action"]
        brightness_req = 10.0
        brightness_value = int(brightness_req / 100 * 255)
        # brightness_percentage = int(brightness_req) # debating use
        self.log.debug("Entity: %s" % entity)
        self.log.debug("Brightness Value: %s" % brightness_value)

        # Set the min and max brightness for bulbs. Smart bulbs
        # use 0-255 integer brightness, while spoken commands will
        # use 0-100% brightness.
        min_brightness = 5
        max_brightness = 255

        ha_entity = self._find_entity(entity, ['group', 'light'])
        # Exit if entiti not found or is unavailabe
        if not ha_entity or not self._check_availability(ha_entity):
            return
        ha_data = {'entity_id': ha_entity['id']}
        # IDEA: set context for 'turn it off again' or similar
        # self.set_context('Entity', ha_entity['dev_name'])

        if action == "down":
            if ha_entity['state'] == "off":
                self.speak_dialog('homeassistant.brightness.cantdim.off',
                                  data=ha_entity)
            else:
                light_attrs = self.ha.find_entity_attr(ha_entity['id'])
                if light_attrs['unit_measure'] is None:
                    self.speak_dialog(
                        'homeassistant.brightness.cantdim.dimmable',
                        data=ha_entity)
                else:
                    ha_data['brightness'] = light_attrs['unit_measure'] - brightness_value
                    if ha_data['brightness'] < min_brightness:
                        ha_data['brightness'] = min_brightness
                    self.ha.execute_service("homeassistant",
                                            "turn_on",
                                            ha_data)
                    ha_data['dev_name'] = ha_entity['dev_name']
                    ha_data['brightness'] = round(100 / max_brightness * ha_data['brightness'])
                    self.speak_dialog('homeassistant.brightness.decreased',
                                      data=ha_data)
        elif action == "up":
            if ha_entity['state'] == "off":
                self.speak_dialog(
                    'homeassistant.brightness.cantdim.off',
                    data=ha_entity)
            else:
                light_attrs = self.ha.find_entity_attr(ha_entity['id'])
                if light_attrs['unit_measure'] is None:
                    self.speak_dialog(
                        'homeassistant.brightness.cantdim.dimmable',
                        data=ha_entity)
                else:
                    ha_data['brightness'] = light_attrs['unit_measure'] + brightness_value
                    if ha_data['brightness'] > max_brightness:
                        ha_data['brightness'] = max_brightness
                    self.ha.execute_service("homeassistant",
                                            "turn_on",
                                            ha_data)
                    ha_data['dev_name'] = ha_entity['dev_name']
                    ha_data['brightness'] = round(100 / max_brightness * ha_data['brightness'])
                    self.speak_dialog('homeassistant.brightness.increased',
                                      data=ha_data)
        else:
            self.speak_dialog('homeassistant.error.sorry')
            return

    def _handle_automation(self, message):
        entity = message.data["Entity"]
        self.log.debug("Entity: %s" % entity)
        ha_entity = self._find_entity(
            entity,
            ['automation', 'scene', 'script']
        )

        # Exit if entiti not found or is unavailabe
        if not ha_entity or not self._check_availability(ha_entity):
            return

        ha_data = {'entity_id': ha_entity['id']}

        # IDEA: set context for 'turn it off again' or similar
        # self.set_context('Entity', ha_entity['dev_name'])

        self.log.debug("Triggered automation/scene/script: {}".format(ha_data))
        if "automation" in ha_entity['id']:
            self.ha.execute_service('automation', 'trigger', ha_data)
            self.speak_dialog('homeassistant.automation.trigger',
                              data={"dev_name": ha_entity['dev_name']})
        elif "script" in ha_entity['id']:
            self.speak_dialog('homeassistant.automation.trigger',
                              data={"dev_name": ha_entity['dev_name']})
            self.ha.execute_service("script", "turn_on",
                                    data=ha_data)
        elif "scene" in ha_entity['id']:
            self.speak_dialog('homeassistant.scene.on',
                              data=ha_entity)
            self.ha.execute_service("scene", "turn_on",
                                    data=ha_data)

    def _handle_sensor(self, message):
        entity = message.data["Entity"]
        self.log.debug("Entity: %s" % entity)

        ha_entity = self._find_entity(entity, ['sensor', 'switch'])
        # Exit if entiti not found or is unavailabe
        if not ha_entity or not self._check_availability(ha_entity):
            return

        entity = ha_entity['id']

        # IDEA: set context for 'read it out again' or similar
        # self.set_context('Entity', ha_entity['dev_name'])

        unit_measurement = self.ha.find_entity_attr(entity)
        sensor_unit = unit_measurement.get('unit_measure') or ''

        sensor_name = unit_measurement['name']
        sensor_state = unit_measurement['state']
        # extract unit for correct pronounciation
        # this is fully optional
        try:
            from quantulum3 import parser
            quantulumImport = True
        except ImportError:
            quantulumImport = False

        if quantulumImport and unit_measurement != '':
            quantity = parser.parse((u'{} is {} {}'.format(
                sensor_name, sensor_state, sensor_unit)))
            if len(quantity) > 0:
                quantity = quantity[0]
                if (quantity.unit.name != "dimensionless" and
                        (quantity.uncertainty != None and quantity.uncertainty <= 0.5)):
                    sensor_unit = quantity.unit.name
                    sensor_state = quantity.value

        try:
            value = float(sensor_state)
            sensor_state = nice_number(value, lang=self.language)
        except ValueError:
            pass

        self.speak_dialog('homeassistant.sensor', data={
            "dev_name": sensor_name,
            "value": sensor_state,
            "unit": sensor_unit})
        # IDEA: Add some context if the person wants to look the unit up
        # Maybe also change to name
        # if one wants to look up "outside temperature"
        # self.set_context("SubjectOfInterest", sensor_unit)

    # In progress, still testing.
    # Device location works.
    # Proximity might be an issue
    # - overlapping command for directions modules
    # - (e.g. "How far is x from y?")
    def _handle_tracker(self, message):
        entity = message.data["Entity"]
        self.log.debug("Entity: %s" % entity)

        ha_entity = self._find_entity(entity, ['device_tracker'])
        # Exit if entiti not found or is unavailabe
        if not ha_entity or not self._check_availability(ha_entity):
            return

        # IDEA: set context for 'locate it again' or similar
        # self.set_context('Entity', ha_entity['dev_name'])

        entity = ha_entity['id']
        dev_name = ha_entity['dev_name']
        dev_location = ha_entity['state']
        self.speak_dialog('homeassistant.tracker.found',
                          data={'dev_name': dev_name,
                                'location': dev_location})

    def _handle_set_thermostat(self, message):
        entity = message.data["entity"]
        self.log.debug("Entity: %s" % entity)
        self.log.debug("This is the message data: %s" % message.data)
        temperature = message.data["temp"]
        self.log.debug("Temperature: %s" % temperature)

        ha_entity = self._find_entity(entity, ['climate'])
        # Exit if entiti not found or is unavailabe
        if not ha_entity or not self._check_availability(ha_entity):
            return

        climate_data = {
            'entity_id': ha_entity['id'],
            'temperature': temperature
        }
        climate_attr = self.ha.find_entity_attr(ha_entity['id'])
        self.ha.execute_service("climate", "set_temperature",
                                data=climate_data)
        self.speak_dialog('homeassistant.set.thermostat',
                          data={
                              "dev_name": climate_attr['name'],
                              "value": temperature,
                              "unit": climate_attr['unit_measure']})

    def handle_fallback(self, message):
        if not self.enable_fallback:
            return False
        self._setup()
        if self.ha is None:
            self.speak_dialog('homeassistant.error.setup')
            return False
        # pass message to HA-server
        response = self._handle_client_exception(
            self.ha.engage_conversation,
            message.data.get('utterance'))
        if not response:
            return False
        # default non-parsing answer: "Sorry, I didn't understand that"
        answer = response.get('speech')
        if not answer or answer == "Sorry, I didn't understand that":
            return False

        asked_question = False
        # TODO: maybe enable conversation here if server asks sth like
        # "In which room?" => answer should be directly passed to this skill
        if answer.endswith("?"):
            asked_question = True
        self.speak(answer, expect_response=asked_question)
        return True

    def shutdown(self):
        self.remove_fallback(self.handle_fallback)
        super(HomeAssistantSkill, self).shutdown()

    def stop(self):
        pass


def create_skill():
    return HomeAssistantSkill()
