"""
Whatson Ingest

This code handles scraping the theatres defined in the config file, and
ingesting them into the database pointed to by the `DATABASE_URL` environment
variable.
"""

import json
import argparse
from html import unescape
import configparser
import datetime
import logging
from urllib.parse import urlencode
import re
from bs4.element import Tag
from bs4 import BeautifulSoup
from psycopg2.errors import UniqueViolation  # pylint: disable=no-name-in-module
from selenium import webdriver
import requests
from .db import DB, reset_database

LOG = logging.getLogger("whatson")
LOG.setLevel(logging.WARNING)

# Database management


def upload(theatre, show):
    """Given a show extracted from the theatre page, upload the show to the database"""
    LOG.debug("uploading %s - %s", show["title"], theatre)
    with DB as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO shows (theatre, title, image_url, link_url, start_date, end_date)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    theatre,
                    show["title"],
                    show["image_url"],
                    show["link_url"],
                    show["start_date"],
                    show["end_date"],
                ),
            )
        except UniqueViolation:
            # We have added this show already
            LOG.debug("duplicate show %s found, skipping", show["title"])
            return
        except:
            LOG.exception("unhandled exception")
            raise


# Show fetching
CLIENT = requests.Session()
CLIENT.headers["User-Agent"] = "whatson/0.1.0"


# Lazy initialisation
# XXX this will cause a race condition if we use multiple threads around this (mutex?)
DRIVER = None


def _fetch_html_requests(url):
    LOG.debug("fetching from url %s", url)

    response = CLIENT.get(url)
    response.raise_for_status()
    return response.text


def _fetch_html_selenium(url):
    global DRIVER

    LOG.debug("fetching from url %s", url)

    # Lazy initialisation of driver
    if DRIVER is None:
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        DRIVER = webdriver.Chrome(chrome_options=options)
        DRIVER.implicitly_wait(3)

    DRIVER.get(url)
    return DRIVER.page_source


# Regex replacer to remove 1st/2nd/3rd/4th etc.
DATE_REPLACER = re.compile(r"\b([0123]?[0-9])(st|th|nd|rd)\b")
CURRENT_YEAR = datetime.date.today().year


def weekday_replacer(text):
    """Replace Thurs -> Thu, Tues -> Tue"""
    return text.replace("Thurs", "Thu").replace("Tues", "Tue")


class FetcherList(type):
    fetchers = set()

    def __new__(cls, name, bases, dct):
        c = super().__new__(cls, name, bases, dct)
        if name != "Fetcher":
            c.fetchers.add(c)
        return c


class ValidationError(ValueError):
    pass


class Fetcher(metaclass=FetcherList):
    url = None
    root_url = None
    name = None
    active = None

    def __init__(self):
        self.fetchers = self.__class__.fetchers

        # Validate the data
        if self.url is None:
            raise ValidationError(f"{self}: self.url is None")

        if self.root_url is None:
            raise ValidationError(f"{self}: self.root_url is None")

        if self.name is None:
            raise ValidationError(f"{self}: self.name is None")

        if self.active is None:
            raise ValidationError(f"{self}: self.active is None")


class AlbanyFetcher(Fetcher):

    name = "Albany"
    root_url = "https://albanytheatre.co.uk/"
    url = "https://albanytheatre.co.uk/whats-on/"
    active = True

    def fetch(self):
        """Fetch shows from the Albany Theatre"""
        html = _fetch_html_requests(self.url)
        soup = BeautifulSoup(html, "lxml")

        container = soup.find("div", class_="query_block_content")
        for elem in container.children:
            if not isinstance(elem, Tag):
                continue

            try:
                date_str = elem.find(class_="show-date").text.lower()
            except AttributeError:
                continue

            title = elem.find("h4").find("a").text.strip()
            image_url = elem.find("img").attrs["src"]
            image_url = "".join([self.root_url, image_url])

            link_url = elem.find("h4").find("a").attrs["href"]
            link_url = "".join([self.root_url, link_url])

            # Parse date string
            if "-" in date_str:
                # Two separate dates
                parts = [part.strip() for part in date_str.split("-")]
                end_date = datetime.datetime.strptime(parts[1], "%d %B %Y").date()

                date_month = datetime.datetime.strptime(parts[0], "%d %B").date()
                start_date = datetime.date(
                    end_date.year, date_month.month, date_month.day
                )
            else:
                # One date therefore start_date = end_date
                start_date = datetime.datetime.strptime(date_str, "%d %B %Y").date()
                end_date = start_date

            yield {
                "title": title,
                "image_url": image_url,
                "link_url": link_url,
                "start_date": start_date,
                "end_date": end_date,
            }


class BelgradeFetcher(Fetcher):

    name = "Belgrade"
    root_url = "http://www.belgrade.co.uk/"
    url = "http://www.belgrade.co.uk/whats-on/"
    active = True

    def fetch(self):
        """Fetch shows from the Belgrade Theatre"""
        html = _fetch_html_requests(self.url)
        soup = BeautifulSoup(html, "lxml")

        container = soup.find("div", class_="list-productions", id="secondary-content")

        # The month and year _should_ be set up by the first child container, which
        # will hopefully be a month/year panel. If this is not the case, then we
        # have to rethink the way this date/time parsing works.
        month = None
        year = None

        for elem in container.children:
            if not isinstance(elem, Tag):
                continue

            if elem.name == "h2":
                # Month/Year section
                date_text = elem.text.lower()
                tmp_date = datetime.datetime.strptime(date_text, "%B %Y").date()
                month = tmp_date.month
                year = tmp_date.year

                LOG.info("found month/year panel, month = %s, year = %s", month, year)
                continue

            if "class" not in elem.attrs:
                continue

            if "production-list-item" not in elem.attrs["class"]:
                continue

            # We should always have a month and year, as hopefully the first panel
            # is a month/day panel
            assert month is not None
            assert year is not None

            title = elem.find("h3").text.strip()
            date_text = elem.find("p", class_="date").text.strip().lower()

            link_url = elem.find("a", class_="production-link").attrs["href"]
            link_url = "".join([self.root_url, link_url])

            image_url = (
                elem.find("a", class_="production-link").find("img").attrs["src"]
            )
            image_url = "".join([self.root_url, image_url])

            # Parse the date from this panel. First we replace instances of e.g.
            # 1st -> 1 so that strptime can parse the day and month
            date_text = DATE_REPLACER.sub(r"\1", date_text)

            def parse_single_date(text):
                try:
                    tmp_date = datetime.datetime.strptime(text, "%d %B").date()
                except ValueError as exc:
                    if "day is out of range for month" in str(exc):
                        # Leap year? Try parsing with the current year
                        text = f"{text} {year}"
                        tmp_date = datetime.datetime.strptime(text, "%d %B %Y").date()
                return datetime.datetime(year, tmp_date.month, tmp_date.day).date()

            if "-" in date_text:
                # Separate start and end dates
                parts = [part.strip() for part in date_text.split("-")]
                start_date = parse_single_date(parts[0])
                end_date = parse_single_date(parts[1])
            else:
                # Single date
                start_date = parse_single_date(date_text)
                end_date = start_date

            # Check if the start date and end date make sense. The start date must
            # be the same as the date panel. If this is not the case, something is
            # up. Therefore if the end date is before the start date then we must
            # add one to the end date year.
            assert start_date.year == year
            if end_date < start_date:
                end_date = datetime.date(
                    end_date.year + 1, end_date.month, end_date.day
                )

            yield {
                "title": title,
                "image_url": image_url,
                "link_url": link_url,
                "start_date": start_date,
                "end_date": end_date,
            }


class SymphonyHallFetcher(Fetcher):

    name = "Symphony Hall"
    root_url = "https://www.thsh.co.uk/"
    url = "https://www.thsh.co.uk/whats-on/"
    active = True

    def fetch(self):
        """Fetch shows from Symphony Hall"""
        url = self.url

        # Loop over all pages
        while True:
            html = _fetch_html_requests(url)
            soup = BeautifulSoup(html, "lxml")

            container = soup.find("ul", class_="grid cf")
            assert len(container.contents) <= 16
            for elem in container.contents:
                # The title is in capitals so we must turn this into a nicer
                # format. Note we should treat each word separately rather than
                # calling the `.title` method as this does not support embedded
                # apostrophes (https://stackoverflow.com/a/1549644)
                raw_title = elem.find("h3").text
                title = " ".join(w.capitalize() for w in raw_title.split())

                link_url = elem.find("a", class_="event-block").attrs["href"]
                image_url = (
                    elem.find("img", class_="o-image__full")
                    .attrs["data-srcset"]
                    .split()[0]
                )

                date_container = elem.find("span", class_="event-block__time")
                times = date_container.find_all("time")
                if len(times) == 1:
                    # Simple case, only a single time available
                    start_date = datetime.datetime.fromisoformat(
                        times[0].attrs["datetime"]
                    ).date()
                    end_date = start_date
                elif len(times) == 2:
                    # We have start time and end time
                    assert times[0].attrs["itemprop"] == "startDate"
                    assert times[1].attrs["itemprop"] == "endDate"

                    start_date = datetime.datetime.fromisoformat(
                        times[0].attrs["datetime"]
                    ).date()
                    end_date = datetime.datetime.fromisoformat(
                        times[1].attrs["datetime"]
                    ).date()
                else:
                    raise NotImplementedError(
                        f"cannot parse dates from {date_container}"
                    )

                yield {
                    "title": title,
                    "image_url": image_url,
                    "link_url": link_url,
                    "start_date": start_date,
                    "end_date": end_date,
                }

            # Handle pagination
            next_link = soup.find("a", class_="pagination__link--next")
            if next_link and "disabled" not in next_link.attrs["class"]:
                url = next_link.attrs["href"]
            else:
                break


class HippodromeFetcher(Fetcher):

    name = "Hippodrome"
    root_url = "https://www.birminghamhippodrome.com/"
    url = "https://www.birminghamhippodrome.com/whats-on/"
    active = True

    def fetch(self):
        """Fetch shows from the Hippodrome Theatre"""
        url = self.url

        while True:
            html = _fetch_html_requests(url)
            soup = BeautifulSoup(html, "lxml")
            container = soup.find("ul", class_="main-events-list")

            for elem in container.find_all("li", class_="events-list-item"):
                item = elem.find("div", class_="performance-listing")

                try:
                    image_url = elem.find("a", class_="block").find("img").attrs["src"]
                except AttributeError:
                    image_url = ""

                link_url = item.find("a", class_="block").attrs["href"]

                details = item.find("div", class_="event-details")
                title = details.find("h5", class_="performance-listing-title").text

                date_text = details.find("p", class_="performance-listing-date").text

                def parse_single_date(txt):
                    # Try parsing with the year
                    try:
                        dtime = datetime.datetime.strptime(txt, "%a %d %b %Y").date()
                    except ValueError as exc:
                        if "does not match format" in str(exc):
                            # We do not have the year, so assume the current year
                            full_date_text = f"{txt} {CURRENT_YEAR}"
                            dtime = datetime.datetime.strptime(
                                full_date_text, "%a %d %b %Y"
                            ).date()
                        else:
                            raise

                    return dtime

                if "-" in date_text or "&" in date_text:
                    if "-" in date_text:
                        parts = [part.strip() for part in date_text.split("-")]
                    elif "&" in date_text:
                        parts = [part.strip() for part in date_text.split("&")]

                    start_date = parse_single_date(parts[0])
                    end_date = parse_single_date(parts[1])
                else:
                    start_date = parse_single_date(date_text)
                    end_date = start_date

                yield {
                    "title": title,
                    "image_url": image_url,
                    "link_url": link_url,
                    "start_date": start_date,
                    "end_date": end_date,
                }

            next_link = soup.find("a", class_="next")
            if next_link:
                url = next_link.attrs["href"]
            else:
                break


class ResortsWorldFetcher(Fetcher):

    name = "Resortsworld Arena"
    root_url = "https://www.resortsworldarena.co.uk/"
    url = "https://www.resortsworldarena.co.uk/whats-on/"
    active = True

    def fetch(self):
        html = _fetch_html_selenium(self.url)
        soup = BeautifulSoup(html, "lxml")

        # First build up a mapping of event name to image url. This is JSON after
        # HTML escaping so we must:
        #
        # * fetch the text
        # * unencode the text
        # * parse into JSON
        # * create a dictionary

        data_mapping_encoded = soup.find("input", id="all-events").attrs["value"]
        data_mapping = json.loads(unescape(data_mapping_encoded))

        image_mapping = {
            item["eventName"].lower(): item["thumbnailUrl"]
            for item in data_mapping["events"]
        }

        container = soup.find("div", id="home-results")
        if not container:
            raise ValueError("cannot find container element in HTML")

        events = container.find_all("div", class_="event-card")
        if not events:
            raise ValueError("cannot find event items")

        for event in events:
            link_tag = event.find("a", class_="eventhref")
            title = link_tag.find("span", class_="title").text
            link_url = "".join([self.root_url, link_tag.attrs["href"]])
            image_url = image_mapping[title.lower()]
            date_text = event.find("span", class_="date").text

            if "-" in date_text:
                parts = [part.strip() for part in date_text.split("-")]
                end_date = datetime.datetime.strptime(parts[1], "%d %B %Y").date()

                try:
                    # Assume day month no year
                    augmented_date = f"{parts[0]} {end_date.year}"
                    start_date = datetime.datetime.strptime(
                        augmented_date, "%d %B %Y"
                    ).date()
                except ValueError:
                    # Assume day no month no year
                    augmented_date = f"{parts[0]} {end_date.month} {end_date.year}"
                    start_date = datetime.datetime.strptime(
                        augmented_date, "%d %m %Y"
                    ).date()

            else:
                start_date = datetime.datetime.strptime(date_text, "%d %B %Y").date()
                end_date = start_date

            yield {
                "title": title,
                "image_url": image_url,
                "link_url": link_url,
                "start_date": start_date,
                "end_date": end_date,
            }


class ArenaBirminghamFetcher(Fetcher):

    name = "Arena Birmingham"
    root_url = "https://www.arenabham.co.uk/"
    url = "https://www.arenabham.co.uk/whats-on/"
    active = True

    def fetch(self):
        html = _fetch_html_selenium(self.url)
        soup = BeautifulSoup(html, "lxml")

        # First build up a mapping of event name to image url. This is JSON after
        # HTML escaping so we must:
        #
        # * fetch the text
        # * unencode the text
        # * parse into JSON
        # * create a dictionary

        data_mapping_encoded = soup.find("input", id="all-events").attrs["value"]
        data_mapping = json.loads(unescape(data_mapping_encoded))

        image_mapping = {
            item["eventName"].lower(): item["thumbnailUrl"]
            for item in data_mapping["events"]
        }

        supercontainer = soup.find("div", class_="content-area")
        if supercontainer is None:
            raise ValueError("cannot find supercontainer in HTML content")
        container = supercontainer.find("div", class_="events-wrap")

        events = container.find_all("div", class_="event-card")
        if not events:
            raise ValueError("cannot find events")

        for event in events:
            link_tag = event.find("a", class_="eventhref")
            link_url = "".join([self.root_url, link_tag.attrs["href"]])

            title = event.find("span", class_="title").text

            image_url = image_mapping[title.lower()]

            date_text = (
                event.find("div", class_="information").find("span", class_="date").text
            )

            if "-" in date_text:
                parts = [part.strip() for part in date_text.split("-")]
                end_date = datetime.datetime.strptime(parts[1], "%d %B %Y").date()

                # Assume the start date is the full format
                try:
                    augmented_date = f"{parts[0]} {end_date.year}"
                    tmp_date = datetime.datetime.strptime(
                        augmented_date, "%d %B %Y"
                    ).date()
                except ValueError as exc:
                    if "does not match format" in str(exc):
                        augmented_date = f"{parts[0]} {end_date.month} {end_date.year}"
                        start_date = datetime.datetime.strptime(
                            augmented_date, "%d %m %Y"
                        ).date()
                    else:
                        LOG.warning("unhandled exception: %s", exc)
                        raise exc

            else:
                start_date = datetime.datetime.strptime(date_text, "%d %B %Y").date()
                end_date = start_date

            yield {
                "title": title,
                "image_url": image_url,
                "link_url": link_url,
                "start_date": start_date,
                "end_date": end_date,
            }


class ArtrixFetcher(Fetcher):

    name = "Artrix"
    root_url = "https://www.artrix.co.uk/"
    url = "https://www.artrix.co.uk/whats-on/"
    active = True

    def fetch(self):
        page = 1

        # Loop over all pages
        while True:
            params = urlencode({"page": page})
            url = self.url + "?" + params

            html = _fetch_html_requests(url)
            soup = BeautifulSoup(html, "lxml")

            container = soup.find("ul", id="gridview-new")
            events = container.find_all("li", class_="Exhib")
            if not events:
                # We must have reached the end of the pages
                break

            for event in events:
                link_tag = event.find("div", class_="imgBox_Intrment").find("a")
                link_url = "".join([self.root_url, link_tag.attrs["href"]])

                image_url = "".join([self.root_url, link_tag.find("img").attrs["src"]])

                title = event.find("div", class_="intrment_info").find("a").text

                date_text = event.find("div", class_="postDate_l").text

                def parse_date_part(text, end_date=None):
                    text = weekday_replacer(DATE_REPLACER.sub(r"\1", text))
                    try:
                        date = datetime.datetime.strptime(text, "%a %d %b %Y").date()
                    except ValueError as exc:
                        if "does not match format" in str(exc):
                            # No year available
                            try:
                                date = datetime.datetime.strptime(
                                    f"{text} {CURRENT_YEAR}", "%a %d %b %Y"
                                ).date()
                            except ValueError as exc:
                                if "does not match format" in str(exc):
                                    # no month available, we must get the month from the end date
                                    date = datetime.datetime.strptime(
                                        f"{text} {end_date.month} {CURRENT_YEAR}",
                                        "%a %d %m %Y",
                                    ).date()

                    return date

                if "-" in date_text:
                    parts = [part.strip() for part in date_text.split("-")]

                    end_date = parse_date_part(parts[1])
                    start_date = parse_date_part(parts[0], end_date=end_date)
                else:
                    start_date = parse_date_part(date_text)
                    end_date = start_date

                yield {
                    "title": title,
                    "image_url": image_url,
                    "link_url": link_url,
                    "start_date": start_date,
                    "end_date": end_date,
                }

            # Handle pagination
            page += 1


class AlexFetcher(Fetcher):

    name = "New Alexandra"
    root_url = "https://www.atgtickets.com/"
    url = "https://www.atgtickets.com/venues/the-alexandra-theatre-birmingham/"
    active = True

    def fetch(self):
        html = _fetch_html_requests(self.url)
        soup = BeautifulSoup(html, "lxml")

        container = soup.find("section", {"class": re.compile(r"WhatsOnPanel.*")})
        for event in container.contents:
            card_image_tag = event.find("div", {"class": re.compile(r"ShowCard_.*")})

            link_tag = card_image_tag.find("a")
            link_url = "".join([self.root_url, link_tag.attrs["href"]])

            image_tag = card_image_tag.find("img")
            image_url = image_tag.attrs["src"]

            card_details_tag = event.find(
                "div", {"class": re.compile("WhatsOnPanel.*")}
            )
            title = card_details_tag.find("h3").find("a").text

            date_text = card_details_tag.find("div").text

            if "-" in date_text:
                parts = [p.strip() for p in date_text.split("-")]
                end_date = datetime.datetime.strptime(parts[1], "%a %d %b %Y").date()
                try:
                    start_date = datetime.datetime.strptime(
                        parts[0], "%a %d %b %Y"
                    ).date()
                except ValueError as exc:
                    if "does not match format" in str(exc):
                        start_date = datetime.datetime.strptime(
                            f"{parts[0]} {end_date.year}", "%a %d %b %Y"
                        ).date()

            else:
                start_date = datetime.datetime.strptime(date_text, "%a %d %b %Y").date()
                end_date = start_date

            yield {
                "title": title,
                "image_url": image_url,
                "link_url": link_url,
                "start_date": start_date,
                "end_date": end_date,
            }


class WarwickArtsCentreFetcher(Fetcher):

    name = "Warwick Arts Centre"
    root_url = "https://www.warwickartscentre.co.uk/"
    url = "https://www.warwickartscentre.co.uk/whats-on/list"
    active = True

    def fetch(self):
        start_idx = 0

        def fix_date_text(txt):
            """Given a date text, strip out any unrequired terms
            """
            repeated_days = {
                "Mondays",
                "Tuesdays",
                "Wednesdays",
                "Thursdays",
                "Fridays",
                "Saturdays",
                "Sundays",
            }
            words = [w.strip() for w in txt.split()]
            words = [
                w
                for w in words
                if "pm" not in w
                and "am" not in w
                and w != "from"
                and w not in repeated_days
            ]
            newstr = (
                " ".join(words)
                .split(",")[0]
                .rstrip("-")
                .split("(")[0]
                .replace("–", "-")
                .rstrip("&")
            )

            return newstr.strip()

        while True:

            params = urlencode({"start": start_idx})
            url = self.url + "?" + params

            html = _fetch_html_requests(url)
            soup = BeautifulSoup(html, "lxml")

            container = soup.find("div", class_="area-production-list")
            events = container.find_all("article", class_="unit-production-entry")

            if not events:
                LOG.debug("reached end of pages")
                break

            for event in events:

                image_tag = event.find("a", class_="media")
                link_url = "".join([self.root_url, image_tag.attrs["href"]])
                image_url = image_tag.find("img").attrs["src"]

                title = event.find("div", class_="body").find("h2").text

                date_text = event.find("p", class_="date").text.strip()
                LOG.debug(date_text)
                date_text = fix_date_text(date_text)

                try:
                    if "-" in date_text:
                        parts = [p.strip() for p in date_text.split("-")]
                        end_date = datetime.datetime.strptime(
                            parts[1], "%a %d %b %Y"
                        ).date()
                        try:
                            start_date = datetime.datetime.strptime(
                                f"{parts[0]} {end_date.year}", "%a %d %b %Y"
                            ).date()
                        except ValueError as exc:
                            if "does not match format" in str(exc):
                                start_date = datetime.datetime.strptime(
                                    f"{parts[0]} {end_date.month} {end_date.year}",
                                    "%a %d %m %Y",
                                ).date()

                    else:
                        try:
                            start_date = datetime.datetime.strptime(
                                date_text, "%a %d %b %Y"
                            ).date()
                        except ValueError as exc:
                            if "does not match format" in str(exc):
                                start_date = datetime.datetime.strptime(
                                    f"{date_text} {CURRENT_YEAR}", "%a %d %b %Y"
                                ).date()

                        end_date = start_date

                    yield {
                        "title": title,
                        "image_url": image_url,
                        "link_url": link_url,
                        "start_date": start_date,
                        "end_date": end_date,
                    }
                except ValueError:
                    LOG.warning("cannot parse date text %s", date_text)
                    continue

            start_idx += 10


def load_config(fptr):
    """Load the list of theatres from the config file"""
    parser = configparser.ConfigParser()
    fptr.seek(0)
    parser.read_file(fptr)

    for section in parser.sections():
        config = parser[section]
        yield {
            "name": section,
            "active": config.getboolean("active"),
            "root_url": config["root-url"],
            "url": config["url"],
        }


def main():
    """The entrypoint, called by `whatson-ingest`"""
    logging.basicConfig(level=logging.INFO)

    # Set up the command line parser

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r",
        "--reset",
        action="store_true",
        default=False,
        help="Clear database contents before ingesting",
    )
    parser.add_argument("-v", "--verbose", action="store_true", default=False)
    args = parser.parse_args()

    if args.verbose:
        LOG.setLevel(logging.INFO)

    if args.reset:
        reset_database(DB)

    # Run the ingestion

    for fetcher_cls in Fetcher.fetchers:
        LOG.info("fetching using %s", fetcher_cls.name)
        if fetcher_cls.active is False:
            continue

        fetcher = fetcher_cls()
        shows = fetcher.fetch()
        for show in shows:
            upload(fetcher.name, show)
