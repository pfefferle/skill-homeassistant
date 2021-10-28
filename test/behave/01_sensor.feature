@allure.suite:behave
Feature: Get sensor state
  Scenario: default sensor
    Given an English speaking user
    When the user says "give me the value of Mycroft sensor please"
    Then mycroft reply should contain "122"
  Scenario: climate sensor
    Given an English speaking user
    When the user says "give me the value of Mycroft climate please"
    Then "skill-homeassistant" should reply with dialog from "homeassistant.sensor.thermostat.dialog"
