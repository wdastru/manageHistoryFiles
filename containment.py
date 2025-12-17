# containment.py
from pathlib import Path
import sys

def is_contained(smaller, bigger):
    return smaller in bigger

def run_containment(dir_path: str|Path):
    
    if not isinstance(dir_path, Path):
        dir_path = Path(dir_path)

    files_with_sizes = [(p, p.stat().st_size) for p in dir_path.glob("*") if p.is_file()]
    # Sort by size (descending)
    files_sorted = sorted(files_with_sizes, key=lambda x: x[1], reverse=True)
    to_be_deleted = set()

    for big_file in files_sorted:
        for small_file in reversed(files_sorted):
            if big_file[1] <= small_file[1]:
                continue  # only compare smaller files to bigger ones
            with open(dir_path / small_file[0].name, "rb") as f1, open(dir_path / big_file[0].name, "rb") as f2:
                small = f1.read()
                big = f2.read()
                if is_contained(small, big):
                    print(f"{dir_path}/{small_file[0].name} will be deleted (contained in {big_file[0].name})")
                    to_be_deleted.add(dir_path / small_file[0].name)
                    
    for file_path in to_be_deleted:
        file_path.unlink()

def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: python containment.py <dir>")
        return
    run_containment(sys.argv[1])

if __name__ == "__main__":
    main()
