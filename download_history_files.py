#!/usr/bin/env python3
import subprocess
import os
from pathlib import Path
from time import sleep
from attr import attrs
from termcolor import colored
import glob
import re
import shutil
import gzip
from utils import run_containment, max_index, fill_gaps

rsync_count = 1

KEYS = [
    "~/.ssh/id_rsa-centos5",
    "~/.ssh/id_ed25519",
]

def start_ssh_agent_if_needed():
    if "SSH_AUTH_SOCK" in os.environ:
        return
    # Start agent and capture environment exports
    out = subprocess.check_output(["ssh-agent", "-s"], text=True)
    for line in out.splitlines():
        if line.startswith("SSH_AUTH_SOCK"):
            os.environ["SSH_AUTH_SOCK"] = line.split(";")[0].split("=")[1]
        elif line.startswith("SSH_AGENT_PID"):
            os.environ["SSH_AGENT_PID"] = line.split(";")[0].split("=")[1]

def agent_has_identities():
    try:
        out = subprocess.check_output(["ssh-add", "-l"], stderr=subprocess.STDOUT, text=True)
        return "The agent has no identities." not in out
    except subprocess.CalledProcessError:
        # exit code 1 when no identities
        return False

def add_key_with_passphrase(key_path):
    key_path = str(Path(key_path).expanduser())
    # ssh-add reads passphrase from TTY; prompt explicitly for clarity
    print(f"Loading key into agent: {key_path}")
    # You can rely on ssh-add to prompt, or pass via askpass for GUI flows.
    subprocess.check_call(["ssh-add", key_path])

def rotate_numbered_backup_logrotate(dest_file: Path,
                                     max_rotations: int = 100,
                                     compress: bool = False):
    """
    Logrotate-like rotation:
      - Move dest_file -> dest_file.1
      - Shift existing: dest_file.(n) -> dest_file.(n+1), up to max_rotations
      - Delete dest_file.max_rotations if present
      - Optionally compress dest_file.1 as dest_file.1.gz

    Returns the path of the newly created rotation (e.g., dest_file.1 or dest_file.1.gz),
    or None if dest_file does not exist (nothing to rotate).

    Atomic on the same filesystem via os.replace().
    """
    dest_file = Path(dest_file)
    if not dest_file.exists():
        return None

    parent = dest_file.parent
    stem = dest_file.name

    # Step 1: delete oldest gz rotation (max_rotations) if present
    oldest_gz = parent / f"{stem}.{max_rotations}.gz"
    if oldest_gz.exists():
        oldest_gz.unlink()
    
    # Step 2: shift rotations backward from n = max_rotations - 1 down to 1
    # name.(n) -> name.(n+1), prefer moving .gz if it exists
    for n in range(max_rotations - 1, 0, -1):
        src_plain = parent / f"{stem}.{n}"
        src_gz = parent / f"{stem}.{n}.gz"
        dst_plain = parent / f"{stem}.{n+1}"
        dst_gz = parent / f"{stem}.{n+1}.gz"

        # move compressed if present, otherwise plain
        if src_gz.exists():
            # ensure destination not conflicting
            if dst_gz.exists():
                dst_gz.unlink()
            os.replace(src_gz, dst_gz)
        elif src_plain.exists():
            # if destination has a gz, remove to avoid ambiguity
            if dst_gz.exists():
                dst_gz.unlink()
            if dst_plain.exists():
                dst_plain.unlink()
            os.replace(src_plain, dst_plain)

    # Step 3: move current dest_file -> dest_file.1 
    # !!! Done in the rsync call by --suffix=.1 option !!!

    # In case a compressed .1 exists, remove it (we are creating a fresh rotation)
    if (parent / f"{stem}.1.gz").exists():
        (parent / f"{stem}.1.gz").unlink()

    # Step 4: optional compression of .1
    if compress:
        first_rotation = parent / f"{stem}.1"
        gz_path = parent / f"{stem}.1.gz"
        # Compress atomically: write to temp then replace
        tmp_gz = parent / f".{stem}.1.tmp.gz"
        with open(first_rotation, "rb") as f_in, gzip.open(tmp_gz, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.replace(tmp_gz, gz_path)
        # Remove the uncompressed .1
        first_rotation.unlink()

def rsync_files(host, app, username):
    global rsync_count

    remote_path = f"/opt/{app}/prog/curdir/{username}/"
    remote_spec = f"{user}@{host}:{remote_path}"
    dest_dir = Path(f"./{host}/{app}/{username}/.")

    cmd = [
        "rsync", 
        "--dry-run",
        "-av", 
        "--checksum",
        "--itemize-changes",
        "--backup",
        "--suffix=.1",
        "--out-format=%i %n",
    ]

    if host == "AV600":
        cmd.append("-e ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 -oHostKeyAlgorithms=+ssh-dss")
        
    cmd.extend(
            [
                f"{remote_spec}history",
                f"{remote_spec}history.old",
                str(dest_dir)
            ]
        )

    res = subprocess.run(cmd, capture_output=True, text=True)
    
    ## Basic rsync diagnostics
    #print("Return code:", res.returncode)
    #if res.stderr:
    #    print("STDERR:\n", res.stderr)
    #
    ## Full rsync output (human-readable but parseable)
    #print("STDOUT:\n", res.stdout)
    
    if "--dry-run" in cmd:
        cmd.pop(cmd.index("--dry-run"))

    lines = res.stdout.splitlines()
    print_once = True
    history_not_found = True
    for i, line in enumerate(lines):
        line = line.strip()

        if not line: # empty line
            continue
            
        if line.find("history") == -1: # not a history file line
            if (i == len(lines) - 1) and history_not_found: # last line and NO history file found
                print(f"{colored('[WARN ]', 'yellow', attrs=['bold'])} no history file found for {host}/{app}/{username}")
            continue
        else:
            history_not_found = False
        
        if print_once:
            if not dest_dir.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {dest_dir}")
            else:
                print(f"Directory already exists: {dest_dir}")

            print(f"-> [{rsync_count}] Running:", " ".join(cmd))
            print_once = False

        _re = re.compile(rf"^{re.escape(user)}@{re.escape(host)}:.*$")
        for item in reversed(cmd):
            if _re.match(item):
                cmd.pop(cmd.index(item))

        # Expect lines like: ">f..t...... some/path/file.ext"
        # First token is the %i field; everything after space is the name.
        parts = line.split(maxsplit=1)
        if not parts:
            continue
        flags = parts[0]
        # Updated/transfer markers:
        #   startswith(">f") means rsync would write/transfer a file to dst
        # (You can tighten this to only count content changes if needed)
        filename: str|None = None
        if len(parts) > 1:

            filename = parts[1]

            if flags.startswith(">f+"):

                cmd.insert(-1, f"{user}@{host}:{remote_path}{filename}")

                n_tries = 1
                while True:
                    res = subprocess.run(cmd, capture_output=True, text=True)

                    if res.returncode == 0:
                        print(f"{colored('[ NEW ]',  color="white", on_color="on_green", attrs=['bold'])} {host}/{app}/{username}/{filename} is new and will be downloaded")
                        break
                    else:
                        print(f"{colored('[ERROR]', 'cyan', attrs=['bold'])} Try {n_tries}: rsync failed for {host}/{app}/{username}/{filename} (rc={res.returncode}): {res.stderr.strip()}")
                        print("Retrying in 60 seconds...")
                        sleep(60)
                        if n_tries >= 10:
                            print(f"{colored('[FATAL]', 'red', attrs=['bold'])} Try {n_tries}: rsync of {host}/{app}/{username}/{filename} failed after {n_tries} attempts; moving to next.\n")
                            break
                        n_tries += 1
                
            elif flags.startswith(">fc"):

                max_n = max_index(filename, dest_dir)
                if max_n != 0: # there exists at least one local backup
                    print(f"  Existing backups found up to {filename}.{max_n} in {dest_dir}")
                    
                    rotate_numbered_backup_logrotate(
                        dest_file=f"{dest_dir}/{filename}",
                        max_rotations = 10,
                        compress=False,
                        )
                
                cmd.insert(-1, f"{user}@{host}:{remote_path}{filename}")

                n_tries = 1
                while True:
                    res = subprocess.run(cmd, capture_output=True, text=True)

                    if res.returncode == 0:
                        print(f"{colored('[ OK  ]', 'green', attrs=['bold'])} Try {n_tries}: {host}/{app}/{username}/{filename} synced")
                        break
                    else:
                        print(f"{colored('[ERROR]', 'cyan', attrs=['bold'])} Try {n_tries}: rsync failed for {host}/{app}/{username}/{filename} (rc={res.returncode}): {res.stderr.strip()}")
                        print("Retrying in 60 seconds...")
                        sleep(60)
                        if n_tries >= 10:
                            print(f"{colored('[FATAL]', 'red', attrs=['bold'])} Try {n_tries}: rsync of {host}/{app}/{username}/{filename} failed after {n_tries} attempts; moving to next.\n")
                            break
                        n_tries += 1

            elif flags.startswith(".f"):
                print(f"{colored('[ --- ]', 'white', attrs=['bold'])} {host}/{app}/{username}/{filename} is already up to date.")

            continue

    rsync_count += 1

def is_host_reachable(host: str) -> bool:
    try:
        # For Linux/WSL: use '-c 1' for one packet
        result = subprocess.run(
            ["ping", "-c", "1", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except Exception:
        return False

start_ssh_agent_if_needed()

if not agent_has_identities():
    for key in KEYS:
        add_key_with_passphrase(key)
else:
    print("ssh-agent already has identities loaded.")

REMOTES_DATA = [
    {
        "host": "AV600-nmrsu",
        "ip": "130.192.221.166",
        "user": "nmrsu",
        "apps": ["topspin"],
        "usernames": [
            "utente16", "espakm", "guest", "nmr", "nmrsu",
            "utente1", "utente10", "utente11", "utente12",
            "utente13", "utente14", "utente15", "utente3",
            "utente4", "utente6", "utente7", "utente8", "utente9"
        ]
    },
    {
        "host": "AV300",
        "ip": "130.192.221.70",
        "user": "root",
        "apps": [
            "PV-360.1.1",
            "PV-360.2.0.pl.1",
            "PV6.0.1",
            "topspin4.0.7",
            "topspin4.1.4"
        ],
        "usernames": [
            "Daniela_DC", "Dario_L", "Eleonora_C", "Enzo_T",
            "Giuseppe_F", "Simona_B", "Simonetta_GC", "Valeria_M",
            "nmr", "nmrsu"
        ]
    },
    {
        "host": "AvanceNeo400",
        "ip": "192.168.186.31",
        "user": "nmrsu",
        "apps": [
            "topspin4.3.0",
            "topspin4.4.0"
        ],"usernames": [
            "carla_carrera", "nmr", "nmrsu", "reineri_francesca"
        ]
    
    },
    {
        "host": "PharmaScan",
        "ip": "192.168.186.11",
        "user": "root",
        "apps": [
            "topspin4.0.6",
            "PV-360.2.0.pl.1",
            "PV-360.1.1",
        ],"usernames": [ 
            "Angelo", "Daniela", "Dario", "Enzo",
            "Francesca", "Giuseppe", "Simonetta",
            "nmr", "nmrsu",
        ]
    }
]

for remote in REMOTES_DATA:
    host = remote["host"]

    if not is_host_reachable(remote["ip"]):
        print(f"\n### Host {host} is not reachable...")
        continue
    else:
        print(f"\n### Processing {host}...")

    user = remote["user"]
    apps = remote["apps"]
    usernames = remote["usernames"]
    
    for app in apps:

        print(f"\n    *** Processing {app}... ***\n")

        for username in usernames:
            dest_dir = Path(f"./{host}/{app}/{username}/.")
            rsync_files(
                host=host,
                app=app,
                username=username,
                )
            run_containment(dest_dir)
            fill_gaps(dest_dir)
            

            
            
            