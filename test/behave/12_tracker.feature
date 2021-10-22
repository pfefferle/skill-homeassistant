@allure.suite:behave
Feature: tracker
  Scenario: tracker
    Given an English speaking user
    When the user says "give me location of the mark"
	  Then mycroft reply should contain "home"
