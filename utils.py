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

    matches = []

    for root, dirs, files in os.walk(start_dir):
        for fname in files:
            if fname in target_names:
                matches.append(os.path.join(root, fname))

    return matches

def is_contained(smaller, bigger):
    return smaller in bigger

def rename_files_sequentially(file_list, prefix):
    """
    Rinomina i file della lista in modo che gli indici siano consecutivi.
    Il file base (senza suffisso) NON viene rinominato.
    """
    # Estrai indici dai file con suffisso numerico
    indices = []
    for f in file_list:
        m = re.match(rf"{prefix}\.(\d+)$", f)
        if m:
            indices.append(int(m.group(1)))

    # Ordina gli indici
    indices.sort()

    # Rinomina sequenzialmente partendo da 1
    for new_idx, old_idx in enumerate(indices, start=1):
        old_name = f"{prefix}.{old_idx}"
        new_name = f"{prefix}.{new_idx}"
        if old_name != new_name:
            if not os.path.exists(new_name):
                print(f"Renaming {colored(old_name, 'red', attrs=['bold'])} to {colored(new_name, 'green', attrs=['bold'])}")
                os.rename(old_name, new_name)

def fill_gaps(dir_path: str|Path):

    if not isinstance(dir_path, Path):
        dir_path = Path(dir_path)

    history_files = find_history_files(dir_path)
    history_files_old = []
    to_be_removed = set()
    for file_path in history_files:
        if "history.old" in file_path:
            history_files_old.append(file_path)
            to_be_removed.add(file_path)

    for file_path in to_be_removed:
        history_files.remove(file_path)

    rename_files_sequentially(history_files, str(dir_path / "history"))
    rename_files_sequentially(history_files_old, str(dir_path / "history.old"))

def run_containment(dir_path: str|Path):
    
    if not isinstance(dir_path, Path):
        dir_path = Path(dir_path)

    files_with_sizes = [(p, p.stat().st_size) for p in dir_path.glob("*") if p.is_file()]
    # Sort by size (descending)
    files_sorted = sorted(files_with_sizes, key=lambda x: x[1], reverse=True)
    to_be_deleted = set()

    for big_file in files_sorted:
        for small_file in reversed(files_sorted):
            if small_file is big_file:
                break #stop when reachin the same file
            with open(dir_path / small_file[0].name, "rb") as f1, open(dir_path / big_file[0].name, "rb") as f2:
                small = f1.read()
                big = f2.read()
                if is_contained(small, big):
                    print(f"{colored(small_file[0].name, 'red', attrs=['bold'])} will be deleted (contained in {colored(big_file[0].name, 'green', attrs=['bold'])})")
                    to_be_deleted.add(dir_path / small_file[0].name)
                    
    for file_path in to_be_deleted:
        file_path.unlink()

    # TODO: compact backup files