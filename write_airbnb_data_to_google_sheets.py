from __future__ import print_function

import argparse
import os.path
import pickle
import pprint

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from scraper import get_airbnb_data

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = "13JRO0Z8ZLVj57kYsbVHFaxyg_d8U1pUiVdHOqAyedzA"
SAMPLE_RANGE_NAME = "April Locations!A1:T1"
SAMPLE_RANGE_NAME2 = "April Locations!A2:T2"

RANGE_CONFIG = "{}!{}{}:{}{}"


def get_credentials():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return creds


def update_all_rows(
    service,
    headers,
    spreadsheet_name,
    airbnb_api_key,
    weather_api_key,
    check_in,
    check_out,
    guests,
):
    link_index = [i for i, x in enumerate(headers) if x == "Link"][0]
    spreadsheet_row = ""
    row = 2
    while True:
        row_range = _create_range_for_row(spreadsheet_name, "A", "Z", row)
        spreadsheet_row = _get_rows(service, row_range)
        if not spreadsheet_row:
            break
        if len(spreadsheet_row) > link_index:
            link = spreadsheet_row[link_index]
            # scrape data
            values = get_airbnb_data(
                airbnb_api_key,
                weather_api_key,
                url=link,
                check_in=check_in,
                check_out=check_out,
                number_guests=guests,
            )
            spreadsheet_row += [""] * (len(values) - len(spreadsheet_row))
            updated_row = [
                val if val is not "" else spreadsheet_row[i]
                for i, val in enumerate(values)
            ]
            _put_rows(service, row_range, updated_row)
        row += 1


def process_headers(service, spreadsheet_name):
    row_range = _create_range_for_row(spreadsheet_name, "A", "Z", 1)
    return _get_rows(service, row_range)


def _create_range_for_row(spreadsheet_name, start, end, row_number):
    return f"{spreadsheet_name}!{start}{row_number}:{end}{row_number}"


def _get_rows(service, row_range):
    sheet = service.spreadsheets()
    result = (
        sheet.values()
        .get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=row_range)
        .execute()
    )
    values = result.get("values", [])
    if not values:
        print("No data found.")
    else:
        return values[0]


def _put_rows(service, row_range, values):
    value_input_option = "USER_ENTERED"  # TODO: Update placeholder value.

    value_range_body = {
        "range": row_range,
        "majorDimension": "ROWS",
        "values": [values],
    }
    request = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=SAMPLE_SPREADSHEET_ID,
            range=row_range,
            valueInputOption=value_input_option,
            body=value_range_body,
        )
    )
    response = request.execute()
    pprint.pprint(response)


# append values to a spreadsheet


def main(args):
    creds = get_credentials()

    service = build("sheets", "v4", credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    headers = process_headers(service, args.spreadsheet_name)

    update_all_rows(
        service,
        headers,
        args.spreadsheet_name,
        args.airbnb_api_key,
        args.weather_api_key,
        args.check_in,
        args.check_out,
        args.guests,
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Enter either an Airbnb URL or a room id, check-in, and check-out date to pull data about an Airbnb listing."
    )
    parser.add_argument(
        "--spreadsheet-name",
        required=True,
        help="Name of the spreadsheet in Covilla",
    )
    parser.add_argument(
        "--airbnb-api-key", required=True, help="API Key for Airbnb"
    )
    parser.add_argument(
        "--weather-api-key", required=True, help="API Key for weather.com"
    )
    parser.add_argument(
        "--check-in",
        help="Check out date of the form YYYY-MM-DD",
    )
    parser.add_argument(
        "--check-out",
        help="Check out date of the form YYYY-MM-DD",
    )
    parser.add_argument(
        "--guests",
        help="Number of guests.",
    )

    args = parser.parse_args()
    main(args)
