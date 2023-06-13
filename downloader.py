import concurrent.futures
import json
import logging
import os
import pathlib
import re
import sys
from datetime import datetime
from os import path
from random import randint
from threading import Thread
from time import sleep
from typing import Dict, List

import requests
import urllib3
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
from requests.adapters import HTTPAdapter
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger("moodle_scraper")
# save logs to file
logging.basicConfig(filename='moodle_scraper.log', level=logging.INFO)
# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# add formatter to ch
ch.setFormatter(formatter)
# add ch to logger
logger.addHandler(ch)

config = json.load(open('scraper.json'))  # TODO: gitignore this file

GMAIL = config.get('gmail', None)
DIRECTORY = config.get('directory', None)
LOGIN_URL = config.get('login_url', None)
HOMEURL = config.get('home_url', None)
URL = config.get('url', None)


class Downloader:
    def __init__(self, debugging=False):
        self.gmail = GMAIL
        self.directory = DIRECTORY
        self.home_url: str = HOMEURL
        self.login_url: str = LOGIN_URL
        self.url: str = URL
        self.session = None
        self.apartments: Dict[str, str] = {}
        self.pool_size: int = 0
        self.save_path: str = ""
        self.wait_time: int = 0
        self.debugging = False

    def run(self):
        self.session = self.get_session()
        self.get_apartments()

    def get_webdriver(self):
        attempts_left: int = 5
        CHROME_USER_DIR = r"C:\Users\cleme\AppData\Local\Google\Chrome\User Data"
        options_gmail = webdriver.ChromeOptions()
        caps = DesiredCapabilities().CHROME
        # caps["pageLoadStrategy"] = "normal"
        options_gmail.add_argument("--window-size=1024,768")

        options_gmail.add_argument(f"user-data-dir={CHROME_USER_DIR}")
        options_gmail.add_argument("profile-directory=Default")

        while attempts_left > 0:
            try:
                driver = webdriver.Chrome(
                    chrome_options=options_gmail, desired_capabilities=caps)
            except Exception as e:
                logger.info(
                    "Encountered error while creating Selenium driver: %s", e)
                attempts_left -= 1
                continue
            break
        else:
            raise RuntimeError(
                "Could not create Selenium driver after 5 tries")

        return driver

    def get_session(self) -> requests.Session:
        if not self.gmail:
            raise ValueError(
                "Username and password must be specified in "
                "environment variables or passed as arguments on the "
                "command line "
            )

        driver = self.get_webdriver()
        assert self.home_url is not None, "No home url specified"

        # Let's go to the login page
        driver.get(self.login_url)

        if "search" in driver.current_url:
            # we are already logged in
            logger.info("Already logged in")
        else:
            # find the google button and click it
            google_button = driver.find_element(
                by=By.XPATH, value="//a[contains(@href, 'google')]")
            google_button.click()

            # find the right div with the right gmail adress and click it (the browser should have been opened with the right gmail account beforehand)
            gmail_button = driver.find_element(
                by=By.XPATH, value="//div[contains(@data-email, '" + self.gmail + "')]")
            gmail_button.click()

            # redirect to the home page
            driver.get(self.home_url)

            # Assert that we don't get redirected to the login page ; otherwise, save the page source to a file and exit
            if driver.current_url != self.home_url:
                with open("login.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logger.warning(
                    "Could not log in. Was redirected to %s", driver.current_url
                )
                driver.close()
                sys.exit(1)

        # Now, we should be logged in. Let's save the cookies
        session_requests = requests.session()
        cookies = driver.get_cookies()
        for cookie in cookies:
            session_requests.cookies.set(cookie["name"], cookie["value"])

        logger.info("Successfully saved cookies")
        driver.close()

        return session_requests

    def get_apartments(self):
        """
        From the home page, let's get the list of apartments

        Inside the div row row-s, we have:
        1 div for each apt :class="p-relative col-12"
        In there, we have link for the apt page in the href of the a tag: e.g.
        <a href="/fr/residence/2778" target="_blank" data-accomodation-id="residence_2778" class="AccomodationBlock">

        Then, let's open the link and get the apartment infos (see below):
        <p class="ft-s ft-medium mb-3"> Logement en résidence </p>
        <h1 class="ft-2xl ft-bold"> Résidence du chateau </h1>


        Then in the page, each room is designated in the div:

        <div class="PropertyBlock available PropertyBlock--background js-filter-item" data-id="room-7762" data-propertyid="63870" data-filter-category="1" data-filter-month="202306,202307"> <div class="PropertyBlock_body"> <div class="PropertyBlock_gallery js-popin-generic-open" data-id="room-7762" style="background-image: url('https://www.studapart.com/media/cache/residence_images_large/6321cf7fc31d6.jpg')"> <div class="PropertyBlock_imageCount">+27</div> <div class="TagElement PropertyBlock_push TagElement--no-click TagElement--blue"> <p class="TagElement_text">Dernières places disponibles</p> </div>                            </div> <div class="PropertyBlock_content"> <div class="PropertyBlock_header"> <div class="PropertyBlock_details pb-10 js-popin-generic-open" data-id="room-7762"> <div class="d-flex fx-justify-between"> <div class="pr-10"> <h4 class="Title d-block color-ft"> Chambre privée en coliving de 8m² à 16m² </h4> </div> <div> <div class="d-flex fx-align-center"> <span class="ft-2xl"> <b>666€</b> </span> </div> <div class="n-mt-3 text-right ft-xs ft-medium color-ft-weaker"> / mois </div> </div> </div> <div class="mt-10 row mb-10@s"> <div class="col-6 mb-5 col-12@s"> <div class="ServiceInline  "> <div class="ServiceInline_icon"> <i class="fal fa-couch fa-sm"></i> </div> <div class="ServiceInline_text"> Meublé <span class="ServiceInline_shared"></span> </div> </div> </div> <div class="col-6 mb-5 col-12@s"> <div class="ServiceInline  "> <div class="ServiceInline_icon"> <i class="fal fa-users fa-sm"></i> </div> <div class="ServiceInline_text"> 3 pers. max. <span class="ServiceInline_shared"></span> </div> </div> </div> <div class="col-6 mb-5 col-12@s"> <div class="ServiceInline ServiceInline--shared "> <div class="ServiceInline_icon"> <i class="fal fa-hat-chef fa-sm"></i> </div> <div class="ServiceInline_text"> Cuisine <span class="ServiceInline_shared"></span> <span class="ServiceInline_status">(partagé)</span> </div> </div> </div> <div class="col-12"> <div class="ServiceInline ServiceInline--more "> <div class="ServiceInline_icon"> <i class="fal fa-plus-circle fa-sm"></i> </div> <div class="ServiceInline_text"> <button class="ButtonLink  "> <p class="ButtonLink_content"> <span class="ButtonLink_content"> Voir plus </span> </p> </button> </div> </div> </div> </div> </div> </div> <div class="PropertyBlock_footer"> <p class="ft-s color-ft mb-10 residence-availability-from"> Disponible à partir du <b>13 juin 2023</b> </p> <div class="d-flex fx-justify-end"> <button class="ButtonRectangle js-popin-generic-open ButtonRectangle--bordered ButtonRectangle--s" data-id="contact-popup" data-option="63870" data-test="roomContactModal"> <span class="ButtonRectangle_content"> <span class="ButtonRectangle_text"> Envoyer un message à la résidence </span> </span> <div class="ButtonRectangle_loader"> <i class="fal fa-spinner-third"></i> </div> </button> <a href="/fr/request/residence/63870" class="ButtonRectangle ml-5 ButtonRectangle--green ButtonRectangle--small ButtonRectangle--auto" data-test="bookRoom"> <span class="ButtonRectangle_content"> <span class="ButtonRectangle_text"> Candidater </span> </span> <div class="ButtonRectangle_loader"> <i class="fal fa-spinner-third"></i> </div> </a>
          </div> </div> </div> </div> </div>

        Extract all relevant infos and especially the available date (e.g. 13 juin 2023).

        Parse the month and if the month is either août or september; then, save the apartment name and the available date to a file.
        """

        apt_list = []
        result = self.session.get(self.home_url, headers=dict(
            referer=self.home_url), verify=False)
        soup = BeautifulSoup(result.text, "html.parser")

        # get the list of apartments
        logger.info("Getting the list of apartments")

        apt_divs = soup.find_all("div", {"class": "p-relative col-12"})

        logger.info("Found %d apartments", len(apt_divs))
        if len(apt_divs) == 0:
            with open("error.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            raise Exception("No apartment found")

        for apt_div in apt_divs:
            apt_link = apt_div.find("a", {"class": "AccomodationBlock"})
            apt_name = apt_link.find("h1").text
            apt_url = self.url + apt_link["href"]
            apt_list.append({"name": apt_name, "url": apt_url})

        # get the list of rooms
        for apt in apt_list:
            apt_url = apt["url"]
            result_apt = self.session.get(
                apt_url, headers=dict(referer=apt_url), verify=False)
            soup = BeautifulSoup(result_apt.text, "html.parser")
            room_divs = soup.find_all("div", {"class": "PropertyBlock"})
            for room_div in room_divs:
                room_name = room_div.find("h4").text
                room_price = room_div.find("span", {"class": "ft-2xl"}).text
                room_price = int(room_price.replace("€", ""))
                room_available = room_div.find(
                    "p", {"class": "ft-s color-ft mb-10 residence-availability-from"}).text
                room_available = room_available.replace(
                    "Disponible à partir du ", "")
                room_available = datetime.strptime(room_available, "%d %B %Y")
                room_available = room_available.strftime("%Y-%m-%d")

                if room_available >= "2023-08-01" and room_available <= "2023-09-30":
                    logger.info(
                        f"{apt['name']} - {room_name} - {room_price} - {room_available}")
                    with open("rooms.txt", "a") as f:
                        f.write(
                            f"{apt['name']} - {room_name} - {room_price} - {room_available}\n")
