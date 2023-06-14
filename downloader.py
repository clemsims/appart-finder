import json
import logging
import os
import pathlib
import re
import sys
from datetime import datetime
from os import path
from time import sleep
from typing import Dict, List

import urllib3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
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
    def __init__(self):
        self.gmail = GMAIL
        self.directory = DIRECTORY
        self.home_url: str = HOMEURL
        self.login_url: str = LOGIN_URL
        self.url: str = URL
        self.driver = None
        self.results = {}
        self.apartments = []
        self.rooms = {}

    def run(self):
        self.driver = self.get_connection()
        self.apartments = self.get_apartments()
        self.rooms = self.get_rooms()

    def get_webdriver(self):
        attempts_left: int = 5
        CHROME_USER_DIR = r"C:\Users\cleme\AppData\Local\Google\Chrome\User Data"
        options_gmail = webdriver.ChromeOptions()
        caps = DesiredCapabilities().CHROME
        # caps["pageLoadStrategy"] = "normal"
        options_gmail.add_argument(f"user-data-dir={CHROME_USER_DIR}")
        options_gmail.add_argument("profile-directory=Profile 4")
        options_gmail.add_argument("--disable-extensions")
        options_gmail.add_argument("--window-size=1920,1080")

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

    def get_connection(self):
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

        return driver

    def get_apartments(self):
        """
        Each apt can be found inside a following <a ... class="AccomodationBlock">

        <a href="/fr/residence/2383" target="_blank" data-accomodation-id="residence_2383" class="AccomodationBlock"><div class="AccomodationBlock_image"><div class="SliderSimple AccomodationBlock_slider"><div class="SliderSimple_controls"><a href="#" class="SliderSimple_control SliderSimple_control--left"><button class="ButtonRectangle ButtonRectangle--xs ButtonRectangle--round ButtonRectangle--light"><span class="ButtonRectangle_content"><!----><!----><i class="fal fa-chevron-left"></i></span><div class="ButtonRectangle_loader"><i class="fal fa-spinner-third"></i></div></button></a> <a href="#" class="SliderSimple_control SliderSimple_control--right"><button class="ButtonRectangle ButtonRectangle--xs ButtonRectangle--round ButtonRectangle--light"><span class="ButtonRectangle_content"><!----><!----><i class="fal fa-chevron-right"></i></span><div class="ButtonRectangle_loader"><i class="fal fa-spinner-third"></i></div></button></a> <div class="SliderSimple_indicators"><div class="SliderSimple_indicatorsRail" style="--position: 0;"><div class="SliderSimple_indicator is-active"></div><div class="SliderSimple_indicator"></div><div class="SliderSimple_indicator"></div><div class="SliderSimple_indicator"></div><div class="SliderSimple_indicator"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div><div class="SliderSimple_indicator is-disabled"></div></div></div></div> <div class="SliderSimple_rail" style="transform: translateX(0%);"><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;/media/cache/residence_images_small/626ba75e57c82.jpg&quot;);"></span> <img src="/media/cache/residence_images_small/626ba75e57c82.jpg" style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;/media/cache/residence_images_small/5d848eaa8746e.png&quot;);"></span> <img src="/media/cache/residence_images_small/5d848eaa8746e.png" style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div><div class="SliderSimple_item is-horizontal"><span class="SliderSimple_imageBackground" style="background-image: url(&quot;&quot;);"></span> <img style="transform: translate3d(-50%, -50%, 0px) rotate(0deg);"> <!----></div></div></div> <div class="Accomodation_rightCta"><!----> <a href="#" class="ButtonRectangle AccomodationBlock_favorite ButtonRectangle--xs ButtonRectangle--round ButtonRectangle--light" data-test="accommodationFavorite"><span class="ButtonRectangle_content"><!----><!----><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="12" class="AccomodationBlock_favorite AccomodationBlock_favorite--full fill-r"><path d="M462.3 62.6C407.5 15.9 326 24.3 275.7 76.2L256 96.5l-19.7-20.3C186.1 24.3 104.5 15.9 49.7 62.6c-62.8 53.6-66.1 149.8-9.9 207.9l193.5 199.8a31.35 31.35 0 0045.3 0l193.5-199.8c56.3-58.1 53-154.3-9.8-207.9z"></path></svg> <i class="AccomodationBlock_favorite--empty fal fa-heart fa-sm"></i></span><div class="ButtonRectangle_loader"><i class="fal fa-spinner-third"></i></div></a></div> <div class="Accomodation_play"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512" width="20"><path fill="currentColor" d="M424.4 214.7L72.4 6.6C43.8-10.3 0 6.1 0 47.9V464c0 37.5 40.7 60.1 72.4 41.3l352-208c31.4-18.5 31.5-64.1 0-82.6z"></path></svg></div> <!----> <div class="AccomodationBlock_tags"><!----></div></div> <div class="AccomodationBlock_content"><div class="AccomodationBlock_contentContainer"><div class="d-flex"><div class="AccomodationBlock_contentLeft"><div><p class="ft-xs"><!---->
                                Logement en résidence
                            </p> <p class="AccomodationBlock_title mb-5 ft-bold ellipsis-2">Twenty Campus Gif-sur-Yvette</p></div> <!----> <!----></div> <div class="AccomodationBlock_contentRight"><div><p class="line-1">à partir de</p> <p class="ft-l color-ft ft-m@s"><b>580€</b> <span class="ft-2xs">cc</span></p> <p class="line-1">/ mois</p></div></div></div> <div class="AccomodationBlock_location mt-10 ellipsis-1">
                    1 chambre - Meublé - Salle de sport - Cafétéria
                </div></div> <div class="AccomodationBlock_ctas"><p class="AccomodationBlock_availability"><span class="AccomodationBlock_notif is-active"></span> <b>Disponible immédiatement</b></p> <!----></div></div> <!----></a>F
        """
        driver = self.driver
        # get the list of apartments
        logger.info("Getting the list of apartments")

        apt_list = []

        # let's find all the apt divs : tag is the following: "class": "p-relative col-12"
        driver.get(self.home_url)

        # Loading condition:

        # wait for the page to load so that we can no longer find:
        # <h2 class="Title Title--l ft-m@s"><b><i class="fal fa-spinner-third spin-l mr-10 color-ft-weak"></i>
        #     Recherche en cours...
        # </b></h2>
        # around the page

        # After loading, it will become:
        # <h2 class="Title Title--l ft-m@s"><b>
        #                 25 logements disponibles
        #             </b></h2>

        sleep(15)
        # FIXME:
        # 15s wait is a quick workaround the fact that some JS code is in-between the loading and the filling of the DOM...
        # This is not a good practice, but I don't have time to find a better solution for now.
        # Code below should work in most cases where connection is extremely bad...
        logger.info("Waiting for the page to load")
        WebDriverWait(
            driver, 10
        ).until_not(
            EC.presence_of_element_located(
                (
                    By.CLASS_NAME, "fal fa-spinner-third spin-l mr-10 color-ft-weak"
                )
            ),
            "Page not loaded"
        )
        logger.info("Page loaded")

        # Exploring each apts:

        # divs_ containing each apt are in the following tag:
        # <div class="p-relative col-12"> but nb of cols is not always 12
        # so let's use the following tag:
        apt_divs = driver.find_elements(By.CLASS_NAME, "AccomodationBlock")

        logger.info("Found %d apartments", len(apt_divs))
        if len(apt_divs) == 0:
            with open("error.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            raise Exception("No apartment found")

        for div_ in apt_divs:
            # 1 apt_link = href in the class "AccomodationBlock"
            # 1 apt_name = p content in the class "AccomodationBlock_title"
            # Warning; a true apt div must have a href!!!

            if not div_.get_attribute("href"):
                logger.warning("No href found for this div, skipping")
                continue
            apt_name = div_.find_element(
                By.CLASS_NAME, "AccomodationBlock_title").text
            apt_url = div_.get_attribute("href")
            apt_list.append({"name": apt_name, "url": apt_url})
            logger.info("Found - %s", apt_name)

        logger.info("Found %d apartments", len(apt_list))
        return apt_list

    def get_rooms(self):
        """
        Then in the page, each room is designated in the div:

        <div class="PropertyBlock available PropertyBlock--background js-filter-item" data-id="room-7762" data-propertyid="63870" data-filter-category="1" data-filter-month="202306,202307"> <div class="PropertyBlock_body"> <div class="PropertyBlock_gallery js-popin-generic-open" data-id="room-7762" style="background-image: url('https://www.studapart.com/media/cache/residence_images_large/6321cf7fc31d6.jpg')"> <div class="PropertyBlock_imageCount">+27</div> <div class="TagElement PropertyBlock_push TagElement--no-click TagElement--blue"> <p class="TagElement_text">Dernières places disponibles</p> </div>                            </div> <div class="PropertyBlock_content"> <div class="PropertyBlock_header"> <div class="PropertyBlock_details pb-10 js-popin-generic-open" data-id="room-7762"> <div class="d-flex fx-justify-between"> <div class="pr-10"> <h4 class="Title d-block color-ft"> Chambre privée en coliving de 8m² à 16m² </h4> </div> <div> <div class="d-flex fx-align-center"> <span class="ft-2xl"> <b>666€</b> </span> </div> <div class="n-mt-3 text-right ft-xs ft-medium color-ft-weaker"> / mois </div> </div> </div> <div class="mt-10 row mb-10@s"> <div class="col-6 mb-5 col-12@s"> <div class="ServiceInline  "> <div class="ServiceInline_icon"> <i class="fal fa-couch fa-sm"></i> </div> <div class="ServiceInline_text"> Meublé <span class="ServiceInline_shared"></span> </div> </div> </div> <div class="col-6 mb-5 col-12@s"> <div class="ServiceInline  "> <div class="ServiceInline_icon"> <i class="fal fa-users fa-sm"></i> </div> <div class="ServiceInline_text"> 3 pers. max. <span class="ServiceInline_shared"></span> </div> </div> </div> <div class="col-6 mb-5 col-12@s"> <div class="ServiceInline ServiceInline--shared "> <div class="ServiceInline_icon"> <i class="fal fa-hat-chef fa-sm"></i> </div> <div class="ServiceInline_text"> Cuisine <span class="ServiceInline_shared"></span> <span class="ServiceInline_status">(partagé)</span> </div> </div> </div> <div class="col-12"> <div class="ServiceInline ServiceInline--more "> <div class="ServiceInline_icon"> <i class="fal fa-plus-circle fa-sm"></i> </div> <div class="ServiceInline_text"> <button class="ButtonLink  "> <p class="ButtonLink_content"> <span class="ButtonLink_content"> Voir plus </span> </p> </button> </div> </div> </div> </div> </div> </div> <div class="PropertyBlock_footer"> <p class="ft-s color-ft mb-10 residence-availability-from"> Disponible à partir du <b>13 juin 2023</b> </p> <div class="d-flex fx-justify-end"> <button class="ButtonRectangle js-popin-generic-open ButtonRectangle--bordered ButtonRectangle--s" data-id="contact-popup" data-option="63870" data-test="roomContactModal"> <span class="ButtonRectangle_content"> <span class="ButtonRectangle_text"> Envoyer un message à la résidence </span> </span> <div class="ButtonRectangle_loader"> <i class="fal fa-spinner-third"></i> </div> </button> <a href="/fr/request/residence/63870" class="ButtonRectangle ml-5 ButtonRectangle--green ButtonRectangle--small ButtonRectangle--auto" data-test="bookRoom"> <span class="ButtonRectangle_content"> <span class="ButtonRectangle_text"> Candidater </span> </span> <div class="ButtonRectangle_loader"> <i class="fal fa-spinner-third"></i> </div> </a>
          </div> </div> </div> </div> </div>

        Extract all relevant infos and especially the available date (e.g. 13 juin 2023).

        Parse the month and if the month is either août or september; then, save the apartment name and the available date to a file.
        """
        driver = self.driver
        rooms = {}
        apt_list = self.apartments
        # get the list of rooms
        for apt in apt_list:
            logger.info("Getting rooms for %s", apt["name"])
            apt_url = apt["url"]
            apt_name = apt["name"]

            driver.get(apt_url)

            room_divs = driver.find_elements(
                By.CLASS_NAME, "PropertyBlock_content")
            logger.info("Found %d rooms", len(room_divs))
            if len(room_divs) == 0:
                logger.warning("No room found for %s", apt_name)
                continue

            for room_div in room_divs:
                # room_id: look for the tag data-id="..."
                room_id = room_div.get_attribute("data-id")
                room_name = room_div.find_element(By.CSS_SELECTOR, "h4").text
                try:
                    room_price = room_div.find_element(
                        By.CSS_SELECTOR, "span.ft-2xl").text
                    room_price = int(room_price.replace("€", ""))
                except Exception as e:
                    logger.warning("No price found for %s", room_name)
                    room_price = "CHECK"
                    # BUG: some rooms have ranging prices; e.g. 500€ - 600€
                    # TODO: handle this case
                try:
                    room_available = room_div.find_element(By.CSS_SELECTOR,
                                                           "p.ft-s.color-ft.mb-10.residence-availability-from").text
                    room_available = room_available.replace(
                        "Disponible à partir du ", "")
                # TODO: use datetime (parse using spaces in str, bc it's in french)
                # if room_available >= "2023-08-01" and room_available <= "2023-09-30":
                #     logger.info(
                #         f"{apt_name} - {room_name} - {room_price} - {room_available}")

                except Exception as e:
                    room_available = "Indisponible"

                rooms[apt_name] = {
                    'room_id': room_id,
                    'room_name': room_name,
                    'room_price': room_price,
                    'room_available': room_available
                }  # TODO: hash it? + stick to the code that was given to the apts in the url!

                logger.info(
                    f"{apt_name} - {room_name} - {room_price} - {room_available}")

                # TODO: change to csv and name the files according to metadata (system date, etc...)
                with open("rooms.txt", "a") as f:
                    f.write(
                        f"{apt_name} - {room_name} - {room_price} - {room_available}\n")

        logger.info("Found %d rooms in total", len(rooms))
        return rooms
