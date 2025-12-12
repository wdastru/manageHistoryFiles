import os
import re

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

date_start_pattern = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:\s+(?P<start>\d{2}:\d{2}:\d{2}))?"
    r".*$"
)

start_pattern = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2})"
    r".*$"
)

end_duration_pattern = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}\s+)?"                # optional date
    r"(?P<end>\d{1,2}:\d{2}:\d{2})"
    r".*?history\sregistration\sfinished"
    r"(?:\safter\s*(?P<duration>\d{1,2}:\d{2}:\d{2}(?:\.\d+)?.*$|\d{2}\.\d{3}.*$))?$",
    #r"(?:\safter\s((?P<duration_h>\d{1,2}:\d{2}:\d{2})(?:.*)?|(?P<durations_s>\d{2}\.\d{3})\ss)$)?$","
    re.IGNORECASE
)

def find_history_files(start_dir="."):
    target_names = {"history", "history.old"}
    matches = []

    for root, dirs, files in os.walk(start_dir):
        for fname in files:
            if fname in target_names:
                matches.append(os.path.join(root, fname))

    return matches

def extract_data(file_path) -> str|None:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) >= 3:
                match_ds = date_start_pattern.search(lines[2].rstrip())
                if match_ds:
                    date: str|None = match_ds.group("date")
                    start: str|None = match_ds.group("start")
                    if not start:
                        if len(lines) >= 6:
                            match_s = start_pattern.search(lines[5].rstrip())
                            if match_s:
                                start = match_s.group("start")
                    
                    # TODO: find other and last date if present
                    for line in reversed(lines):
                        match_nd = date_start_pattern.search(line.rstrip())
                        if match_nd:
                            new_date: str|None = match_nd.group("date")
                            if new_date != date:
                                print(f"Found different date {new_date} in file {file_path}, not handled yet.")
                                pass
                            break
                    
                    match_ed = end_duration_pattern.search(lines[-1].rstrip())
                    if match_ed:
                        end: str|None = match_ed.group("end")
                        duration: str|None = match_ed.group("duration")
                        if duration:
                            duration = duration.replace("hours", "h")
                        else:
                            # TODO: calculate duration
                            pass
                        return date, start, end, duration
                    else:
                        return date, start, "Registering", "Registering"
                else:
                    return None, None, None, None
            else:
                print(f"{file_path}: File has less than 3 lines.")
                return None, None, None, None
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None, None, None, None

if __name__ == "__main__":
    results = find_history_files(".")
    for path in results:
        match = host_app_user_pattern.search(path)
        if match:
            host: str|None = match.group("host")
            app: str|None = match.group("app")
            user: str|None = match.group("user")
            file: str|None = match.group("file")
            date, start, end, duration = extract_data(path)
            print(f"Found {host}/{app}/{user} -> {file} ({date}, {start}, {end}, {duration})")