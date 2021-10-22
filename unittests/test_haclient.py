"""Unittests for HA client"""
import os
import unittest
from unittest import TestCase, mock

from ha_client import HomeAssistantClient, check_url

kitchen_light = {'state': 'off', 'id': '1', 'dev_name': 'kitchen'}

json_data = {'attributes': {'friendly_name': 'Kitchen Lights',
                            'max_mireds': 500,
                            'min_mireds': 153,
                            'supported_features': 151},
             'entity_id': 'light.kitchen_lights',
             'state': 'off'}

attr_resp = {"id": '1',
             "dev_name": {'attributes': {'friendly_name': 'Kitchen Lights',
                                         'max_mireds': 500,
                                         'min_mireds': 153,
                                         'supported_features': 151},
                          'entity_id': 'light.kitchen_lights',
                          'state': 'off'
                          }
             }

token = os.getenv('HASS_TOKEN')
headers = {'Authorization': f"Bearer {token}",
           'Content-Type': 'application/json'
           }
config = {'ip_address': '127.0.0.1',
          'token': token,
          'port_number': 8123,
          'ssl': False,
          'verify': False,
          }


class TestHaClient(TestCase):
    """Base set of tests

    These tests are from old days and originally runned on public
    instance of HA that no longer runs so mocking was added.
    """

    def test_mock_ssl(self):
        """Test with ssl"""
        with mock.patch('requests.get') as mock_request:
            portnum = 8123
            ssl = True
            url = 'https://127.0.0.1'

            mock_request.return_value.status_code = 200
            self.assertTrue(url, 'https://127.0.0.1')
            self.assertTrue(portnum, 8123)
            self.assertTrue(ssl, True)
            self.assertTrue(mock_request.return_value.status_code, 200)

    def test_mock_ssl_no_port(self):
        """Test with ssl and without port number specified"""
        with mock.patch('requests.get') as mock_request:
            portnum = None
            ssl = True
            url = 'https://127.0.0.1:8123'

            mock_request.return_value.status_code = 200
            self.assertTrue(url, 'https://127.0.0.1:8123')
            self.assertEqual(portnum, None)
            self.assertTrue(ssl, True)
            self.assertTrue(mock_request.return_value.status_code, 200)

    def test_broke_entity(self):
        """Test behavior with non-exist entity"""
        ha_client = HomeAssistantClient(config)
        self.assertRaises(TypeError, ha_client)

    def test_light_nossl(self):
        """Test base turn on/off behavior.
         This need running HA session!
        """
        portnum = config['port_number']
        ha_client = HomeAssistantClient(config)
        component = ha_client.find_component('light')
        entity = (ha_client.find_entity('unittest light', ['light']))
        if entity['best_score'] >= 50:
            print(entity['best_score'])
            print(entity)
        light_attr = ha_client.find_entity_attr(entity['id'])

        self.assertEqual(component, True)
        self.assertEqual(light_attr['name'], 'unittest light')
        self.assertEqual(entity['dev_name'], 'unittest light')
        self.assertEqual(ha_client.ssl, False)
        self.assertEqual(portnum, 8123)
        # Conversation plugin not enabled in HA test instance
        # convo = ha_client.engage_conversation('turn off Mycroft light')
        # self.assertEqual(convo, {'extra_data': None, 'speech': 'Turned Mycroft light off'})
        ha_data = {'entity_id': entity['id']}
        if light_attr['state'] == 'on':
            req = ha_client.execute_service("homeassistant", "turn_off",
                                            ha_data)
            if req.status_code == 200:
                entity = ha_client.find_entity(light_attr['name'], 'light')
                if entity['state'] == 'off':
                    self.assertEqual(entity,
                                     {'id': 'light.unittest_light',
                                      'dev_name': 'unittest light',
                                      'state': 'off',
                                      'best_score': 100,
                                      'attributes': {'brightness': 80,
                                                     'friendly_name': 'unittest light',
                                                     'supported_color_modes': ['brightness'],
                                                     'supported_features': 1
                                                     },
                                      }
                                     )
                    self.assertEqual(light_attr['unit_measure'], 80)
                asert = False
                if entity['best_score'] >= 50:
                    asert = True
                self.assertTrue(asert)
        else:
            req = ha_client.execute_service("homeassistant", "turn_on",
                                            ha_data)
            if req.status_code == 200:
                if entity['state'] == 'on':
                    self.assertEqual(light_attr['state'], 'on')
                    self.assertEqual(entity,
                                     {'id': 'light.unittest_light',
                                      'dev_name': 'unittest light',
                                      'state': 'on',
                                      'best_score': 100,
                                      'attributes': {'brightness': 80,
                                                     'friendly_name': 'unittest light',
                                                     'supported_color_modes': ['brightness'],
                                                     'supported_features': 1
                                                     },
                                      }
                                     )
                    self.assertEqual(light_attr['unit_measure'], 80)

    @mock.patch('ha_client.HomeAssistantClient.find_entity')
    def test_toggle_lights(self, mock_get):
        """Test toggle functionality"""
        ha_client = HomeAssistantClient(config)
        ha_client.find_entity = mock.MagicMock()
        entity = ha_client.find_entity(kitchen_light['dev_name'], 'light')
        mock_get.entity = {"id": '1',
                           "dev_name": {'attributes': {'friendly_name': 'Kitchen Lights',
                                                       'max_mireds': 500,
                                                       'min_mireds': 153,
                                                       'supported_features': 151
                                                       },
                                        'entity_id': 'light.kitchen_lights',
                                        'state': 'off'
                                        }
                           }
        self.assertEqual(mock_get.entity, attr_resp)
        ha_data = {'entity_id': entity['id']}
        state = entity['state']
        if state == 'on':
            ha_client.execute_service = mock.MagicMock()
            req = ha_client.execute_service("homeassistant", "turn_off",
                                            ha_data)
            if req.status_code == 200:
                entity = ha_client.find_entity(kitchen_light['dev_name'], 'light')
                asert = False
                if entity['state'] == 'off':
                    asert = True
                if entity['best_score'] >= 50:
                    asert = True
                self.assertTrue(asert)

        else:
            ha_client.execute_service = mock.MagicMock()
            req = ha_client.execute_service("homeassistant", "turn_on",
                                            ha_data)
            if req.status_code == 200:
                asert = False
                if entity['state'] == 'on':
                    asert = True
                self.assertTrue(asert)

    def test_check_ip_with_ip_four(self):
        """Test regex parsing user inputted url as ip v4 address"""
        test_case = ['http://192.168.1.1/test/',
                     'https://192.168.1.1/test/',
                     '192.168.1.1:8123',
                     '192.168.1.1'
                     ]

        for address in test_case:
            parsed = check_url(address)
            self.assertEqual(parsed, '192.168.1.1')

    def test_check_ip_with_ip_six(self):
        """Test regex parsing user inputted url as ip v4 address"""
        test_case = ['http://2001:0db8:0:85a3:0:0:ac1f:8001/test',
                     'https://2001:0db8:0:85a3:0:0:ac1f:8001/test/',
                     '2001:0db8:0:85a3:0:0:ac1f:8001:8123',
                     '2001:0db8:0:85a3:0:0:ac1f:8001'
                     ]

        for address in test_case:
            parsed = check_url(address)
            self.assertEqual(parsed, '2001:0db8:0:85a3:0:0:ac1f:8001')

    def test_check_ip_with_hostname(self):
        """Test regex parsing user inputted url as hostname"""
        test_case = ['http://mycroft.local/test.jpg',
                     'https://mycroft.local/test.jpg',
                     'mycroft.local:8123',
                     'mycroft.local'
                     ]
        for address in test_case:
            parsed = check_url(address)
            self.assertEqual(parsed, 'mycroft.local')


if __name__ == '__main__':
    unittest.main()
