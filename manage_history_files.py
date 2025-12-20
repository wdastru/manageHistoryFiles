import os
import re
import datetime
from datetime import timedelta, datetime
import pandas as pd
from utils import find_history_files

# Matches .../<host>/<app>/<user>/history or history.old at the END of the path
host_app_user_pattern = re.compile(
        r"^\.[/\\](?P<host>[^/\\]+?)"       # host segment
        r"[\\/]"
        r"(?P<app>[^/\\]+?)"        # app segment
        r"[\\/]"
        r"(?P<user>[^/\\]+?)"       # user segment
        r"[\\/]"                   
        r"(?P<file>[^/\\]+$)"       # file segment
    )

date_time_start_pattern = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:\s+(?P<start>\d{2}:\d{2}:\d{2})"
    r".*?\bJD\b.*?\bISO\b.*)?$"
)

start_pattern = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}\s+)?"
    r"(?P<start>\d{2}:\d{2}:\d{2})"
    r".*$"
)

end_pattern = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}\s+)?"
    r"(?P<end>\d{2}:\d{2}:\d{2})"
    r".*$"
)

end_duration_pattern = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}\s+)?"                # optional date
    r"(?P<end>\d{1,2}:\d{2}:\d{2})"
    r".*?history\sregistration\sfinished"
    r"(?:\safter\s((?P<duration_h>\d{1,2}:\d{2}:\d{2})(?:.*)?|(?P<duration_s>\d{2}\.\d{3})\ss))?$",
    re.IGNORECASE
)

def calculate_duration(lines: list, date_start:str, start: str, end: str) -> list[str|None]:
    new_date:str|None = None
    for line in reversed(lines):
        match_nd = date_time_start_pattern.search(line.rstrip())
        if match_nd:
            new_date = match_nd.group("date")
            if new_date != date_start:
                break
            else:
                new_date = None
                break
    date_end: str|None = None
    if new_date:
        date_end = f"{new_date}, {end}"
    else:
        date_end = f"{date_start}, {end}"

    date_start = f"{date_start}, {start}"
    
    duration_fmt = "%Y-%m-%d, %H:%M:%S"
    
    try:
        start_dt = datetime.strptime(date_start, duration_fmt)
        end_dt = datetime.strptime(date_end, duration_fmt)
        elapsed = end_dt - start_dt
        hours, remainder = divmod(elapsed.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        duration = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02} h" 
        return [date_end.split(",")[0], duration]

    except ValueError:
        print(f"Error parsing dates in buffer.")
        return ["Error", "Error"]
    
def extract_data(raw_lines) -> str|None:
    date_start: str|None
    date_end: str|None
    start: str|None
    end: str|None
    duration: str|None
    lines = raw_lines.splitlines()
    try:
        if len(lines) >= 1:
            match_ds = date_time_start_pattern.search(lines[0].rstrip())
            if match_ds:
                date_start = match_ds.group("date")
                date_end = date_start
                start = match_ds.group("start")
                duration = None
                if not start:
                    match_s = start_pattern.search(lines[2].rstrip())
                    if match_s:
                        start = match_s.group("start")
                
                match_ed = end_duration_pattern.search(lines[-1].rstrip())

                if match_ed:
                    end: str|None = match_ed.group("end")
                    duration_h: str|None = match_ed.group("duration_h")
                    duration_s: str|None = match_ed.group("duration_s")
                    if duration_h:
                        duration = f"{duration_h} h"
                    elif duration_s:
                        duration = f"{duration_s} s"
                    else:
                        date_end, duration = calculate_duration(lines, date_start, start, end)

                    return date_start, date_end, start, end, normalize_time(duration)
                else:
                    for line in reversed(lines):
                        match_e = end_pattern.search(line.rstrip())
                        if match_e:
                            end: str|None = match_e.group("end")
                            date_end, duration = calculate_duration(lines, date_start, start, end)
                            return date_start, date_end, start, end, normalize_time(duration)
                        continue
            else:
                return None, None, None, None, None
        else:
            print(f"Buffer has less than 3 lines.")
            return None, None, None, None, None
    except Exception as e:
        print(f"Exception caught: {e}")
        return None, None, None, None, None

def normalize_time(value: str) -> str:
    value = value.strip().lower()
    if value.endswith('h'):  # e.g., "14:56:45 h"
        # Remove 'h' and return as HH:MM:SS
        return value.replace(' h', '')
    elif value.endswith('s'):  # e.g., "29.442 s"
        # Extract seconds, discard milliseconds
        seconds = float(value.replace(' s', ''))
        whole_seconds = int(round(seconds))  # discard ms
        # Convert to HH:MM:SS
        return str(timedelta(seconds=whole_seconds))
    else:
        return value  # fallback

if __name__ == "__main__":
    records = []  # collect rows here
    results = find_history_files(".")
    for path in results:
        match = host_app_user_pattern.search(path)
        if match:
            host: str|None = match.group("host")
            app: str|None = match.group("app")
            user: str|None = match.group("user")
            file: str|None = match.group("file")

            #if host in ["AV600-nmrsu",
            #            "AV300", 
            #            "AvanceNeo400",
            #            "PharmaScan"] :
            #    continue

            buffer = ''
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                buffer_number = 1
                
                for i, raw_line in enumerate(lines):
                   
                    line = raw_line.rstrip("\n")
                    if line:
                        if date_time_start_pattern.match(line.lstrip()) or (i == len(lines) - 1):
                            # processa buffer precedente
                            if buffer:
                                
                                ### TODO: cosa fa questo check?
                                if raw_line == lines[-1]:
                                    buffer += line + "\n"
                                
                                #print(f"Processing buffer {buffer_number}")
                                date_start, date_end, start, end, duration = extract_data(buffer)
                                print(f"Found {host}/{app}/{user} -> {file} ({date_start}, {start}, {date_end}, {end}, {duration})")
                                
                                # append a structured record
                                records.append({
                                    "host": host,
                                    "app": app,
                                    "user": user,
                                    "file": file,
                                    "date_start": date_start,   # ideally a datetime.date / str in ISO format
                                    "date_end": date_end,       # ideally a datetime.date / str in ISO format
                                    "start": start,             # ideally a datetime / time / str in ISO
                                    "end": end,                 # ideally a datetime.date / str in ISO format
                                    "duration": duration        # seconds, HH:MM:SS, etc.
                                })

                                buffer_number += 1

                                buffer = line + "\n"   # start new buffer
                            else:
                                # riga di continuazione
                                buffer += line + "\n"
                        else:
                            # riga di continuazione
                            buffer += line + "\n"
    
    # export to Excel
    df = pd.DataFrame(records)
    df["date_start"] = pd.to_datetime(df["date_start"], errors="coerce")
    df["date_end"] = pd.to_datetime(df["date_end"], errors="coerce")
    df["start"] = pd.to_timedelta(df["start"], errors='coerce')
    df["end"] = pd.to_timedelta(df["end"], errors='coerce')
    df["duration"] = pd.to_timedelta(df["duration"], errors='coerce')

    with pd.ExcelWriter("history_files_summary.xlsx", engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="History")
        ws = writer.sheets["History"]

        # Map column names → desired Excel formats
        formats = {
            "date_start": "yyyy-mm-dd",
            "date_end": "yyyy-mm-dd",
            "start": "hh:mm:ss",
            "end": "hh:mm:ss",
            "duration": "hh:mm:ss",
        }

        for col_name, col_idx in zip(df.columns, range(1, len(df.columns) + 1)):
            if col_name in formats:
                fmt = formats[col_name]
                (col_cells,) = ws.iter_cols(min_col=col_idx, max_col=col_idx)
                for cell in col_cells:
                    cell.number_format = fmt