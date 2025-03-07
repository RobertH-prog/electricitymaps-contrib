"""Parser for AU-NT using https://ntesmo.com.au data, the electricity market operator for the Northen Territories.
Uses some webscrapping as no API seems to be available. Data is available in the form of daily xslx files.
Mapping is done using EDL's website and Territory Generation.
https://edlenergy.com/project/pine-creek/
https://territorygeneration.com.au/about-us/our-power-stations/
"""
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from logging import Logger, getLogger
from typing import TypedDict
from zoneinfo import ZoneInfo

import pandas as pd
from bs4 import BeautifulSoup
from requests import Session
from requests.adapters import Retry

from parsers.lib.config import refetch_frequency, retry_policy
from parsers.lib.exceptions import ParserException

AUSTRALIA_TZ = ZoneInfo("Australia/Darwin")

INDEX_URL = "https://ntesmo.com.au/data/daily-trading/historical-daily-trading-data/{}-daily-trading-data"
DEFAULT_URL = "https://ntesmo.com.au/data/daily-trading/historical-daily-trading-data"
LATEST_URL = "https://ntesmo.com.au/data/daily-trading"
DATA_DOC_PREFIX = "https://ntesmo.com.au/__data/assets/excel_doc/"
# Data is being published after 5 days at the moment.
DELAY = 24 * 5


class Generator(TypedDict):
    power_plant: str
    fuel_type: str


PLANT_MAPPING = {
    "C1": Generator(power_plant="Channel Island Power Station", fuel_type="gas"),
    "C2": Generator(power_plant="Channel Island Power Station", fuel_type="gas"),
    "C3": Generator(power_plant="Channel Island Power Station", fuel_type="gas"),
    "C4": Generator(power_plant="Channel Island Power Station", fuel_type="gas"),
    "C5": Generator(power_plant="Channel Island Power Station", fuel_type="gas"),
    "C6": Generator(power_plant="Channel Island Power Station", fuel_type="gas"),
    "C7": Generator(power_plant="Channel Island Power Station", fuel_type="gas"),
    "C8": Generator(power_plant="Channel Island Power Station", fuel_type="gas"),
    "C9": Generator(power_plant="Channel Island Power Station", fuel_type="gas"),
    "W1": Generator(power_plant="Weddell Power Station", fuel_type="gas"),
    "W2": Generator(power_plant="Weddell Power Station", fuel_type="gas"),
    "W3": Generator(power_plant="Weddell Power Station", fuel_type="gas"),
    "LMS": Generator(
        power_plant="LMS Energy from the Shoal Bay landfill", fuel_type="biomass"
    ),
    "K1": Generator(power_plant="Katherine Power Station", fuel_type="gas"),
    "K2": Generator(power_plant="Katherine Power Station", fuel_type="gas"),
    "K3": Generator(power_plant="Katherine Power Station", fuel_type="gas"),
    "K4": Generator(power_plant="Katherine Power Station", fuel_type="gas"),
    "P1": Generator(power_plant="Pine Creek Power Station", fuel_type="gas"),
    "P2": Generator(power_plant="Pine Creek Power Station", fuel_type="gas"),
    "P3": Generator(power_plant="Pine Creek Power Station", fuel_type="gas"),
    "KS01": Generator(power_plant="", fuel_type="unknown"),
    "MY01": Generator(power_plant="", fuel_type="unknown"),
    "BJ01": Generator(power_plant="", fuel_type="unknown"),
    "BP01": Generator(power_plant="", fuel_type="unknown"),
    "HP01": Generator(power_plant="", fuel_type="unknown"),
}

# For some reason the page doesn't always load on first attempt.
# Therefore we retry a few times.
retry_strategy = Retry(
    total=3,
    status_forcelist=[500, 502, 503, 504],
)

_DT_CLASS = "smp-tiles-article__title"


def construct_latest_index(session: Session) -> dict[date, str]:
    """Browse all links from the latest daily reports page and index them."""
    index = {}
    latest_index_page = session.get(LATEST_URL)
    soup = BeautifulSoup(latest_index_page.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if a["href"].startswith(DATA_DOC_PREFIX):
            dt = pd.to_datetime(a.find("div", {"class": _DT_CLASS}).text)
            index[dt.date()] = a["href"]
    return index


def construct_year_index(year: int, session: Session) -> dict[date, str]:
    """Browse all links on a yearly historical daily data and index them."""
    index = {}
    # For the current we need to go to the default page.
    url = DEFAULT_URL
    if not year == datetime.now(tz=AUSTRALIA_TZ).year:
        url = INDEX_URL.format(year)
    year_index_page = session.get(url)
    soup = BeautifulSoup(year_index_page.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if a["href"].startswith(DATA_DOC_PREFIX):
            dt = pd.to_datetime(a.find("div", {"class": _DT_CLASS}).text)
            index[dt.date()] = a["href"]
    return index


def get_historical_daily_data(link: str, session: Session) -> bytes:
    result = session.get(link)
    return result.content


def extract_production_data(file: bytes) -> pd.DataFrame:
    return pd.read_excel(
        file, "Generating Unit Output", skiprows=4, header=0, usecols="A:AA"
    )


def extract_demand_price_data(file: bytes) -> pd.DataFrame:
    return pd.read_excel(
        file, "System Demand and Market Price", skiprows=4, header=0, usecols="A:C"
    )


def get_data(
    session: Session,
    target_datetime: datetime,
    extraction_func: Callable[[bytes], pd.DataFrame],
    logger: Logger,
) -> pd.DataFrame:
    assert target_datetime is not None, ParserException(
        "NTESMO.py", "Target datetime cannot be None."
    )
    target_date = target_datetime.date()
    latest_links = construct_latest_index(session)
    link = latest_links.get(target_date, None)
    if not link:
        historical_links = construct_year_index(target_datetime.year, session)
        link = historical_links.get(target_date, None)

    try:
        data_file = get_historical_daily_data(link, session)
    except KeyError:
        raise ParserException(
            "NTESMO.py",
            f"Cannot find file on the index page for date {target_datetime}",
        )
    return extraction_func(data_file)


def parse_consumption(
    raw_consumption: pd.DataFrame,
    target_datetime: datetime,
    logger: Logger,
    price: bool = False,
) -> list[dict]:
    data_points = []
    assert target_datetime is not None, ParserException(
        "NTESMO.py", "Target datetime cannot be None."
    )
    for _, consumption in raw_consumption.iterrows():
        # Market day starts at 4:30 and reports up until 4:00 the next day.
        # Therefore timestamps between 0:00 and 4:30 excluded need to have an extra day.
        raw_timestamp = consumption[0]
        timestamp = datetime.combine(date=target_datetime.date(), time=raw_timestamp)
        if raw_timestamp < time(hour=4, minute=30):
            timestamp = timestamp + timedelta(days=1)
        data_point = {
            "zoneKey": "AU-NT",
            "datetime": timestamp.replace(tzinfo=AUSTRALIA_TZ),
            "source": "ntesmo.com.au",
        }
        if price:
            data_point["price"] = consumption["Market Price"]
            data_point["currency"] = "AUD"
        else:
            data_point["consumption"] = consumption["Demand"]
        data_points.append(data_point)
    return data_points


def parse_production_mix(
    raw_production_mix: pd.DataFrame, logger: Logger
) -> list[dict]:
    production_mix = []
    generation_units = set(raw_production_mix.columns)
    generation_units.remove("Period Start")
    generation_units.remove("Period End")
    if not generation_units == PLANT_MAPPING.keys():
        raise ParserException(
            "NTESMO.py",
            f"New generator {generation_units - PLANT_MAPPING.keys()} detected in AU-NT, please update the mapping of generators.",
        )
    raw_production_mix["Period Start"] = raw_production_mix[
        "Period Start"
    ].dt.tz_localize("Australia/Darwin")
    for _, production in raw_production_mix.iterrows():
        data_point = {
            "zoneKey": "AU-NT",
            "datetime": production["Period Start"].to_pydatetime(),
            "source": "ntesmo.com.au",
            "production": dict(),
            "storage": dict(),
        }
        for generator_key, generator in PLANT_MAPPING.items():
            if generator_key not in production:
                raise ParserException(
                    "NTESMO.py",
                    f"Missing generator {generator_key} detected in AU-NT, please update the mapping of generators.",
                )
            # Some decomissioned plants have negative production values.
            if production[generator_key] >= 0:
                if generator["fuel_type"] in data_point["production"]:
                    data_point["production"][generator["fuel_type"]] += production[
                        generator_key
                    ]
                else:
                    data_point["production"][generator["fuel_type"]] = production[
                        generator_key
                    ]
        production_mix.append(data_point)
    return production_mix


@refetch_frequency(timedelta(days=1))
@retry_policy(retry_policy=retry_strategy)
def fetch_consumption(
    zone_key: str = "AU-NT",
    session: Session = Session(),
    target_datetime: datetime | None = None,
    logger: Logger = getLogger(__name__),
):
    if target_datetime is None:
        target_datetime = datetime.now(tz=AUSTRALIA_TZ) - timedelta(hours=DELAY)
    consumption = get_data(session, target_datetime, extract_demand_price_data, logger)
    return parse_consumption(consumption, target_datetime, logger)


@refetch_frequency(timedelta(days=1))
@retry_policy(retry_policy=retry_strategy)
def fetch_price(
    zone_key: str = "AU-NT",
    session: Session = Session(),
    target_datetime: datetime | None = None,
    logger: Logger = getLogger(__name__),
):
    if target_datetime is None:
        target_datetime = datetime.now(tz=AUSTRALIA_TZ) - timedelta(hours=DELAY)
    consumption = get_data(session, target_datetime, extract_demand_price_data, logger)
    return parse_consumption(consumption, target_datetime, logger, price=True)


@refetch_frequency(timedelta(days=1))
@retry_policy(retry_policy=retry_strategy)
def fetch_production_mix(
    zone_key: str = "AU-NT",
    session: Session = Session(),
    target_datetime: datetime | None = None,
    logger: Logger = getLogger(__name__),
):
    if target_datetime is None:
        target_datetime = datetime.now(tz=AUSTRALIA_TZ) - timedelta(hours=DELAY)
    production_mix = get_data(session, target_datetime, extract_production_data, logger)
    return parse_production_mix(production_mix, logger)


if __name__ == "__main__":
    target_datetime = datetime.now() - timedelta(days=2)
    consumption = get_data(
        Session(), target_datetime, extract_production_data, Logger("test")
    )
    print(parse_production_mix(consumption, Logger("test")))
