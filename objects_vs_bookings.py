from pathlib import Path
import pandas as pd
import polars as pl
from datetime import datetime
import argparse

import manage_history_files
import objects

SHEET_NAMES: list[str] = ["300", "400", "600", "PS"]
NAMES: dict[str, str] = {
    "300": "AV300",
    "400": "AVNeo400",
    "600": "AV600",
    "PS" : "PHARMASCAN",
}
PI_DIRS: dict[str, dict[str, str]] = {
    "Longo": {
        "300": "Dario_L",
        "400": "",
        "600": "",
        "PS":  "",
    },
    "Di Gregorio": {
        "300": "",
        "400": "",
        "600": "",
        "PS":  "",
    },
    "Reineri": {
        "300": "",
        "400": "FraR",
        "600": "utente7",
        "PS":  "",
    },
    "Geninatti": {
        "300": "Simonetta_GC",
        "400": "",
        "600": "utente8",
        "PS":  "Simonetta",
    },
    "Delli Castelli": {
        "300": "Daniela_DC",
        "400": "",
        "600": "utente16",
        "PS":  "Daniela",
    },
    "Gianolio": {
        "300": "",
        "400": "GIANOLIO",
        "600": "utente4",
        "PS":  "",
    },
    "Ferrauto": {
        "300": "Giuseppe_F",
        "400": "Ferrauto",
        "600": "",
        "PS":  "",
    },
    "Terreno": {
        "300": "Enzo_T",
        "400": "TERRENO",
        "600": "utente6",
        "PS":  "Francesca",
    },
    "Bifone": {
        "300": "",
        "400": "",
        "600": "",
        "PS":  "Angelo",
    },
}
def find_outer_key_by_inner_value(target_value: str) -> str | None:
    global PI_DIRS
    if not target_value:  # Handle None or empty string
        return None
    for outer_key, inner_dict in PI_DIRS.items():
        if target_value in inner_dict.values():
            return outer_key
    return None  # or raise an exception if you prefer

def from_bookings_to_objects(bookings, objects, start=None):
    for inst in SHEET_NAMES:
        total_bookings: int = 0
        created_objects_for_booking: int = 0
        percentage_booking:float = 0.0
        for row_booking in bookings[inst].iter_rows(named = True):
            if start and row_booking["start"].date() < start:
                continue

            at_least_one_object: bool = False
            total_bookings += 1
            obj: str = ""
            usr: str = ""
            for row_object in objects['Objects'].iter_rows(named = True):
                if row_object["date"].date() == row_booking["start"].date():
                    # the start date matches
                    if row_object["host"] == NAMES[inst]:
                        # the instrument matches
                        date_and_time: datetime = datetime.combine(
                            row_object["date"], 
                            row_object["time"]
                        )
                        if not at_least_one_object:
                            # not yet found an object for that booking
                            if date_and_time >= row_booking["start"] and date_and_time <= row_booking["end"]:
                                # object date is inside start and end time of booking
                                at_least_one_object = True          # that booking created at least an object
                                created_objects_for_booking += 1    # increase the number of bookings that at least created an object
                                #obj = row_objects["object"]
                                #usr = row_objects["user"]

            #if at_least_one_object:
            #    print(f"{row_bookings['summary']:40} {str(row_bookings['start']):<16} : {usr:<16} {obj} ")

        percentage_booking = 100 * created_objects_for_booking / total_bookings 
        print(f"{inst:>3}: {percentage_booking:.2f} %")

def from_objects_to_bookings(bookings, objects, start=None):
    for inst in SHEET_NAMES:
        total_objects: int = 0
        booking_for_object: int = 0
        percentage_booking:float = 0.0
        for row_object in objects['Objects'].iter_rows(named = True):
            if start and row_object["date"].date() < start:
                continue

            if not row_object["host"] == NAMES[inst]:
                continue

            date_and_time: datetime = datetime.combine(
                row_object["date"], 
                row_object["time"]
            )

            booking_found: bool = False
            total_objects += 1
            for row_booking in bookings[inst].iter_rows(named = True):
                if row_booking["start"].date() == row_object["date"].date():
                    # the start date matches
                    if not booking_found:
                        # not yet found a booking for that object
                        if "userdir" in row_object.keys():
                            if not row_booking["PI"] == find_outer_key_by_inner_value(target_value=row_object["userdir"]):
                                if "user" in row_object.keys():
                                    if not row_booking["PI"] == find_outer_key_by_inner_value(target_value=row_object["user"]):
                                        continue

                        # the PI matches
                        if date_and_time >= row_booking["start"] and date_and_time <= row_booking["end"]:
                            # object date is inside start and end time of booking
                            booking_found = True          # that object has a booking
                            booking_for_object += 1       # increase the number of object that has bookings
                            print(f"{total_objects} - {date_and_time} {row_object['object']:<100} : {row_booking['uid']}")
                            break
                
            if not booking_found:
                print(f"{total_objects} - {date_and_time} {row_object['object']:<100} : NO BOOKING !!!")

        print(f"total object: {total_objects}")
        percentage_objects = 100 * booking_for_object / total_objects 
        print(f"{inst:>3}: {percentage_objects:.2f} %")
        pass

def main(start=None):
    #objects_file_path: str = "D:/Walter/src/Python/manageHistoryFiles/objects_summary.xlsx"
    #bookings_file_path: str = "D:/Walter/src/Python/download_google_calendars/cost_calendar.xlsx"
    objects_file_path: str = "/mnt/d/Walter/src/Python/manageHistoryFiles/objects_summary.xlsx"
    bookings_file_path: str = "/mnt/d/Walter/src/Python/download_google_calendars/cost_calendar.xlsx"
    # Parse the Excel files
    print(f"  [parsing] {Path(objects_file_path).name}")
    objects: dict[str, pl.DataFrame] = {key: pl.DataFrame(df) for key, df in pl.read_excel(
        objects_file_path, sheet_name = ["Objects"], engine="openpyxl"
    ).items()}
    print(f"  [parsing] {Path(bookings_file_path).name}")
    bookings: dict[str, pl.DataFrame] = {key: pl.DataFrame(df) for key, df in pl.read_excel(
        bookings_file_path, sheet_name = SHEET_NAMES, engine="openpyxl"
    ).items()}
    
    from_bookings_to_objects(bookings=bookings, objects=objects, start=start)
    from_objects_to_bookings(bookings=bookings, objects=objects, start=start)

def parse_date(date_str) -> datetime.date :
    date_str: str = str.replace(date_str, '/', '-')
    try:
        # Convert string like "16-03-2025" to a date object
        return datetime.strptime(date_str, "%d-%m-%Y").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date: '{date_str}'. Expected format dd-mm-yyyy")

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-recalc", action="store_true", help="Do no recalc objects")
    parser.add_argument(
        "--start",
        type=parse_date,
        default=None,
        help="Start date (dd-mm-yyyy)"
    )

    args: argparse.Namespace = parser.parse_args()    

    if not args.no_recalc:
        manage_history_files.main()
        objects.main()

    if args.start:
        main(args.start)
    else:
        main()
