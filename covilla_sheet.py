#!python3
from __future__ import print_function

import argparse
import itertools
import os.path
import pickle
import pprint
import urllib

import scraper
import sheets

SHEET_ID = "13JRO0Z8ZLVj57kYsbVHFaxyg_d8U1pUiVdHOqAyedzA"


def _room_id_from_link(link):
    return urllib.parse.urlparse(link).path.split("/")[-1]


def _is_empty_row(row):
    return all(col in ("", "FALSE") for col in row)


def _get_link_header_index(headers):
    return next(i for i, x in enumerate(headers) if x == "Link")


def get_listings(
    sheet,
    spreadsheet_name,
    airbnb_api_key,
    weather_api_key,
    check_in,
    check_out,
    guests,
):
    view = sheets.SheetView(sheet, spreadsheet_name)
    link_index = _get_link_header_index(view.headers())
    rows_by_id = {}
    for row in view:
        if not row:
            break
        if len(row) > link_index:
            link = row[link_index]
            if not link:
                break
            room_id = _room_id_from_link(link)
            rows_by_id[room_id] = row
    return rows_by_id


def add_listings(
    sheet,
    room_ids,
    airbnb_api_key,
    weather_api_key,
    check_in,
    check_out,
    guests,
    spreadsheet_name,
):
    room_ids = set(room_ids)
    view = sheets.SheetView(sheet, spreadsheet_name)
    link_index = _get_link_header_index(view.headers())
    row_writer = sheets.SheetWriteBuffer(
        sheet,
        start_index=2,
        sheet_name=spreadsheet_name,
        capacity=5,
    )
    empty_rows = []
    consecutive_empty = 0
    try:
        for i, row in enumerate(view, start=2):
            if len(row) <= link_index or not row[link_index]:
                empty_rows.append(i)
                consecutive_empty += 1
                if len(empty_rows) > len(room_ids) and consecutive_empty >= 10:
                    break
            else:
                consecutive_empty = 0
                room_id = _room_id_from_link(row[link_index])
                room_ids -= set([room_id])
        empty_rows = itertools.chain(
            empty_rows, range(i, len(room_ids) - len(empty_rows))
        )
    except StopIteration:
        empty_rows = range(2, len(room_ids) + 2)
    for room, next_empty in zip(room_ids, empty_rows):
        values = scraper.get_airbnb_data(
            airbnb_api_key,
            weather_api_key,
            room_id=room,
            check_in=check_in,
            check_out=check_out,
            number_guests=guests,
        )
        if next_empty != row_writer.end_index + 1:
            row_writer.flush()
            row_writer.start_index = next_empty
        row_writer.append(values)
    row_writer.flush()


def refresh_listings(
    sheet,
    spreadsheet_name,
    airbnb_api_key,
    weather_api_key,
    check_in,
    check_out,
    guests,
):
    view = sheets.SheetView(sheet, spreadsheet_name)
    link_index = _get_link_header_index(view.headers())
    row_writer = sheets.SheetWriteBuffer(
        sheet,
        start_index=2,
        sheet_name=spreadsheet_name,
        capacity=5,
    )
    existing_room_ids = set()
    for row in view:
        if _is_empty_row(row):
            break
        updated_row = row
        if len(row) > link_index:
            link = row[link_index]
            room_id = _room_id_from_link(link)
            if room_id in existing_room_ids:
                updated_row = [""] * len(row)
            else:
                existing_room_ids.add(room_id)
                try:
                    values = scraper.get_airbnb_data(
                        airbnb_api_key,
                        weather_api_key,
                        url=link,
                        check_in=check_in,
                        check_out=check_out,
                        number_guests=guests,
                    )
                except Exception as e:
                    pprint.pprint("Failed on row {}".format(row))
                    pprint.pprint(f"{e}")
                else:
                    row += [""] * (len(values) - len(row))
                    updated_row = [
                        new_val if (new_val != "" and new_val) else old_val
                        for new_val, old_val in zip(values, row)
                    ]
        row_writer.append(updated_row)
    row_writer.flush()


def main(args):
    refresh_listings(
        sheets.Sheet(SHEET_ID),
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
