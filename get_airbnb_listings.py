#!python3
import argparse
import json
import pprint
import urllib.parse

import covilla_sheet
import enum
import requests
import sheets
from scraper import get_value_from_path

USER_AGENT = "PostmanRuntime/7.26.8"

# NOTE: This appears to be the max permitted by the endpoint.
MAX_BATCH_SIZE = 50


@enum.unique
class Amenity(enum.Enum):
    POOL = 7
    HOTTUB = 25

    @classmethod
    def from_string(cls, value):
        return cls[value.upper()]


def get_listings_from_location(
    api_key,
    location,
    check_in,
    check_out,
    *,
    guests=1,
    min_bedrooms=1,
    offset=0,
    batch_size=MAX_BATCH_SIZE,
    amenities=None,
    price_max=None,
):
    req = {
        "request": {
            "metadataOnly": False,
            "itemsPerGrid": batch_size,
            "itemsOffset": offset,
            "refinementPaths": ["/homes"],
            "checkin": check_in,
            "checkout": check_out,
            "minBedrooms": min_bedrooms,
            "query": location,
            "adults": guests,
            "amenities": amenities or [],
            "priceMax": price_max,
        }
    }
    pprint.pprint("request \n :{}".format(req))
    exts = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": "2934608b8b7600024baa490b2221e3d94e8e00ccf905ea7d2d89882d0a1b09e9",
        },
    }
    url = (
        f"https://www.airbnb.com/api/v3/ExploreSearch"
        f"?operationName=ExploreSearch&locale=en&currency=USD"
        f"&extensions={urllib.parse.quote(json.dumps(exts))}"
        f"&variables={urllib.parse.quote(json.dumps(req))}"
    )

    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "content-type": "application/json",
        "origin": "https://www.airbnb.com",
        "x-airbnb-api-key": api_key,
    }

    return requests.request("GET", url, headers=headers)


def query_listings(args):
    listings = []
    while len(listings) < args.max_results:
        response = get_listings_from_location(
            args.airbnb_api_key,
            args.location,
            args.check_in,
            args.check_out,
            guests=args.guests,
            min_bedrooms=args.min_bedrooms,
            offset=len(listings),
            batch_size=MAX_BATCH_SIZE,
            amenities=[x.value for x in args.amenity],
            price_max=args.price_max,
        )
        new_listings = get_value_from_path(
            response,
            'data.dora.exploreV3.sections[__typename == "DoraExploreV3ListingsSection"].items',
        )
        print(f"found {len(new_listings)} listings at offset {len(listings)}")
        listings.extend([x["listing"]["id"] for x in new_listings])
        if len(new_listings) < MAX_BATCH_SIZE:
            break

    return listings[: args.max_results]


def merge_listings(args):
    sheet = sheets.Sheet(covilla_sheet.SHEET_ID)

    covilla_sheet.refresh_listings(
        sheet,
        args.spreadsheet_name,
        args.airbnb_api_key,
        args.weather_api_key,
        args.check_in,
        args.check_out,
        args.guests,
    )

    new_listings = query_listings(args)

    # Prompt user to allow them to cancel operation.
    print(f"Found {len(new_listings)} Listings")
    prompt_msg = "Write entries to spreadsheet? (Y/n) "
    try:
        response = input(prompt_msg)
        while response not in ("Y", "n"):
            response = input(prompt_msg)
    except EOFError:
        response = "n"
    if response != "Y":
        return

    covilla_sheet.add_listings(
        sheet,
        new_listings,
        args.airbnb_api_key,
        args.weather_api_key,
        args.check_in,
        args.check_out,
        args.guests,
        args.spreadsheet_name,
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Query a city's Airbnb listings using a number of criteria."
    )
    parser.add_argument(
        "--airbnb-api-key", required=True, help="API Key for Airbnb"
    )
    parser.add_argument(
        "--check-in",
        help="Check out date of the form YYYY-MM-DD",
        required=True,
    )
    parser.add_argument(
        "--check-out",
        help="Check out date of the form YYYY-MM-DD",
        required=True,
    )
    parser.add_argument(
        "--guests",
        type=int,
        help="Number of guests.",
    )
    parser.add_argument(
        "--location",
        help="The location to search for listings in.",
    )
    parser.add_argument(
        "--min-bedrooms",
        help="The minimum number of bedrooms to search for.",
    )
    parser.add_argument(
        "--amenity",
        type=Amenity.from_string,
        action="append",
        default=[],
        help="To search for places with a hottub.",
    )
    parser.add_argument(
        "--max-results",
        default=200,
        type=int,
        help="The maximum number of results to return.",
    )
    parser.add_argument(
        "--price-max",
        type=int,
        help="The maximum price of the airbnb.",
    )
    parser.add_argument(
        "--weather-api-key", required=True, help="API Key for weather.com"
    )
    parser.add_argument(
        "--spreadsheet-name",
        required=True,
        help="Name of the spreadsheet in Covilla",
    )

    args = parser.parse_args()
    merge_listings(args)
