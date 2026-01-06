#utils.py
from pathlib import Path
import os
import re
from termcolor import colored

def max_index(filename: str, dest_dir: Path) -> int:
    # Look for files named 'stem.<n>' and 'stem.<n>.gz' in the same directory
    # Matches 'name.<number>' or 'name.<number>.gz' (for compressed rotations)
    #_suffix_re = re.compile(r"\.(\d+)$")
    _suffix_re = re.compile(r"\.(?P<number>\d+)(?:\.gz)?$")
    
    # Look for files named 'stem.<n>' and 'stem.<n>.gz' in the same directory
    max_n = 0
    for p in dest_dir.glob(f"{filename}*"):
        m = _suffix_re.search(p.name)
        if m :
            try:
                n = int(m.group("number"))
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return max_n

def find_history_files(start_dir="."):
    target_names = {"history", "history.old"}
    # Add history.old.n for n = 1..10
    for n in range(1, 11):
        target_names.add(f"history.{n}")
        target_names.add(f"history.old.{n}")

    # Regex for timestamped variants:
    #   history~20251229-131900
    #   history~20251229-131900.old
    # Pattern details:
    #   - YYYYMMDD: 8 digits
    #   - '-'
    #   - HHMMSS: 6 digits (24h)
    #   - optional '.old'
    ts_pattern = re.compile(r"^history~\d{8}-\d{6}(?:\.old)?$")

    matches = []

    for root, dirs, files in os.walk(start_dir):
        for fname in files:
            if fname in target_names or ts_pattern.fullmatch(fname):
                matches.append(os.path.join(root, fname))

    return matches

def is_equal(smaller, bigger):
    return smaller == bigger

def is_contained(smaller, bigger):
    return smaller in bigger

def rename_files_sequentially(file_list: list[Path]) -> None:
    """
    Rinomina i file della lista in modo che gli indici siano consecutivi.
    Il file base (senza suffisso) NON viene rinominato.
    """

    print(f"{colored("Renaming files sequentially actually out of order.", 'red', attrs=['bold'])}")
    return

    # Estrai indici dai file con suffisso numerico
    indices = []
    prefixes: list[str] = []
    file_list.sort()
    max_index: int = 0

    for f in file_list:

        # TODO: gestire i file .old derivanti dal .stversions/
        pattern = r"^(?P<prefix>.+history)" \
                  r"(?P<timestamp>~[0-9]+-[0-9]+)?" \
                  r"(?P<old>\.old)?" \
                  r"(\.)?" \
                  r"(?P<number>[0-9]+)?$"
        m: re.Match[str] | None = re.match(pattern, str(f))
        if m:
            if m.group("prefix"):
                if m.group("old"):
                    prefixes.append(m.group("prefix") + m.group("old"))
                else:
                    prefixes.append(m.group("prefix"))

                if not m.group("timestamp") and not m.group("number"):
                    # history or history.old file
                    indices.append(0)
                    continue
                
                if m.group("number"):
                    indices.append(int(m.group("number")))
                    max_index = int(m.group("number"))
                
                if m.group("timestamp"):
                    max_index += 1
                    indices.append(max_index)
    
    # Controlla che tutti i prefissi siano uguali
    if len(prefixes) > 1:
        if any(p != prefixes[0] for p in prefixes):
            print(f"{colored('Error:', 'red', attrs=['bold'])} File list contains different prefixes, cannot rename sequentially.")
        else: # Ordina gli indici
            indices.sort()
    
    # Rinomina sequenzialmente partendo da 1
    for new_idx, old_idx in enumerate(indices, start=0):
        old_name = f"{prefixes[0]}.{old_idx}"
        new_name = f"{prefixes[0]}.{new_idx}"
        if old_name != new_name:
            if not os.path.exists(new_name):
                print(f"Renaming {colored(old_name, 'red', attrs=['bold'])} to {colored(new_name, 'green', attrs=['bold'])}")
                
                while True:
                    choice = input("Rename the file or not ([yY]/[nN]]): ").strip()
                    if choice in ("y", "Y"):
                        os.rename(old_name, new_name)
                        break
                    elif choice in ("n", "N"):
                        break
                    else:
                        print("Invalid input. Please enter a valid choice.")
                

def fill_gaps(files_list: list[Path]) -> None:

    history_files: list[Path] = files_list
    history_files_old: list[Path] = []
    to_be_removed = set()
    for file_path in history_files:

        m = re.match(rf"^.+history(?P<timestamp>~.+?)?(?P<old>\.old)?(\.[0-9]+)?$", str(file_path))
        if m:
            if m.group("old"):
                history_files_old.append(file_path)
                to_be_removed.add(file_path)

    for file_path in to_be_removed:
        history_files.remove(file_path)

    rename_files_sequentially(history_files)
    rename_files_sequentially(history_files_old)

def is_old(file: Path) -> bool:
    if file.exists():
        if file.suffix == ".old":
            return True
        return False
    else:
        print(f"Warning: file {file} does not exists!")
        exit(1)

def run_containment(files_list: list[Path]) -> bool:
    
    keep_containing = True
    while keep_containing:

        files_with_sizes: list[tuple[Path, int]] = [(p, p.stat().st_size) for p in files_list if p.is_file()]

        # Sort by size (descending)
        files_sorted = sorted(files_with_sizes, key=lambda x: x[0], reverse=True)
        files_sorted = sorted(files_sorted, key=lambda x: x[1], reverse=True)
        to_be_deleted = set()

        for big_file in files_sorted:
            for small_file in reversed(files_sorted):
                if small_file is big_file:
                    break #stop when reaching the same file
                with open(small_file[0], "rb") as f1, open(big_file[0], "rb") as f2:
                    small = f1.read()
                    big = f2.read()
                    if is_equal(small, big):
                        if is_old(big_file[0]): 
                            # big_file is a .old file. 
                            # It could be:
                            # history.old or
                            # history~YYYYMMDD-hhmmss.old file copied from .stversions/
                            # It will be kept, and small file deleted
                            print(f"{colored(small_file[0].name, 'red', attrs=['bold'])} will be deleted (equal to {colored(big_file[0].name, 'green', attrs=['bold'])})")
                            to_be_deleted.add(small_file)
                        else: 
                            # big_file is not a .old file. 
                            # It could be: 
                            # history or 
                            # history.n or 
                            # history.old.n or 
                            # history~YYYYMMDD-hhmmss file copied from .stversions/
                            print(f"{colored(big_file[0].name, 'red', attrs=['bold'])} will be deleted (equal to {colored(small_file[0].name, 'green', attrs=['bold'])})")
                            to_be_deleted.add(big_file)

                    elif is_contained(small, big):
                        print(f"{colored(small_file[0].name, 'red', attrs=['bold'])} will be deleted (contained in {colored(big_file[0].name, 'green', attrs=['bold'])})")
                        to_be_deleted.add(small_file)
                        
        if not to_be_deleted:
            keep_containing = False
        else:
            for file_tuple in to_be_deleted:
                #while True:
                #    choice = input("Delete file or not ([yY]/[nN]]): ").strip()
                #    if choice in ("y", "Y"):
                        file_tuple[0].unlink()
                        files_list.remove(file_tuple[0])
                #        break
                #    elif choice in ("n", "N"):
                #        keep_containing = False
                #        break
                #    else:
                #        print("Invalid input. Please enter a valid choice.")