from pathlib import Path
import pandas as pd
import polars as pl
from datetime import datetime

import manage_history_files
import objects

SHEET_NAMES: list[str] = ["300", "400", "600", "PS"]
NAMES: dict[str, str] = {
    "300": "AV300",
    "400": "AVNeo400",
    "600": "AV600",
    "PS": "PHARMASCAN",
}

def main():
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
    
    for inst in SHEET_NAMES:
        total_bookings: int = 0
        created_objects_for_booking: int = 0
        percentage_booking:float = 0.0
        for row_bookings in bookings[inst].iter_rows(named = True):
            at_least_one_object: bool = False
            total_bookings += 1
            for row_objects in objects["Objects"].iter_rows(named = True):
                if row_objects["host"] == NAMES[inst]:
                    if row_objects["date"].date() == row_bookings["start"].date():
                        date_and_time: datetime = datetime.combine(
                            row_objects["date"], 
                            row_objects["time"]
                        )
                        if not at_least_one_object:
                            if date_and_time >= row_bookings["start"] and date_and_time <= row_bookings["end"]:
                                created_objects_for_booking += 1
                                at_least_one_object = True
        percentage_booking = 100 * created_objects_for_booking / total_bookings 
        print(f"{inst:>3}: {percentage_booking:.2f} %")

    pass

if __name__ == "__main__":
    manage_history_files.main()
    objects.main()
    main()