import re
from utils import find_history_files
import pandas as pd

object_pattern = re.compile(
    r"^((?P<date>\d{4}-\d{2}-\d{2})\s+)?"
    r"(?P<time>\d{2}:\d{2}:\d{2})"
    r".*?client changed object to.*?"
    r"(?P<object>\"(?!\/Undefined.*?\/Undefined).*?\")"
    r".*$"
)

host_app_user_pattern = re.compile(
    r"^\.[/\\](?P<host>[^/\\]+?)"       # host segment
    r"[\\/]"
    r"(?P<app>[^/\\]+?)"        # app segment
    r"[\\/]"
    r"(?P<user>[^/\\]+?)"       # user segment
    r"[\\/]"                   
    r"(?P<file>[^/\\]+$)"       # file segment
)

date_pattern = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r".*$"
)

if __name__ == "__main__":
    records = []  # collect rows here
    results = find_history_files(".")
    for path in results:
        match_hauf = host_app_user_pattern.search(path)
        if match_hauf:
            host: str|None = match_hauf.group("host")
            app: str|None = match_hauf.group("app")
            user: str|None = match_hauf.group("user")
            file: str|None = match_hauf.group("file")
                
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                date: str|None = None
                for line in lines:
                    line = line.rstrip()

                    match_date = date_pattern.search(line)
                    if match_date: 
                        date = match_date.group("date")

                    match_dto = object_pattern.search(line)
                    if match_dto:
                        date: str = match_dto.group("date") if match_dto.group("date") else date
                        time: str = match_dto.group("time")
                        object: str = match_dto.group("object")
                        print(f"{date} {time} {host} {app} {user} {object}")
                        # append a structured record
                        records.append({
                            "date": date,   # ideally a datetime.date / str in ISO format
                            "time": time,             # ideally a datetime / time / str in ISO
                            "host": host,
                            "app": app,
                            "user": user,
                            "object": object,
                        })
    
    # export to Excel
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["time"] = pd.to_timedelta(df["time"], errors='coerce')
    
    with pd.ExcelWriter("objects_summary.xlsx", engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Objects")
        ws = writer.sheets["Objects"]

        # Map column names → desired Excel formats
        formats = {
            "date": "yyyy-mm-dd",
            "time": "hh:mm:ss",
        }

        for col_name, col_idx in zip(df.columns, range(1, len(df.columns) + 1)):
            if col_name in formats:
                fmt = formats[col_name]
                (col_cells,) = ws.iter_cols(min_col=col_idx, max_col=col_idx)
                for cell in col_cells:
                    cell.number_format = fmt