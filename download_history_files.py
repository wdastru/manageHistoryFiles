#!/usr/bin/env python3
import subprocess
import os
from pathlib import Path
from time import sleep
from termcolor import colored
import glob
import re
import shutil
import gzip

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
                                     max_rotations: int = 3,
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

start_ssh_agent_if_needed()

if not agent_has_identities():
    for key in KEYS:
        add_key_with_passphrase(key)
else:
    print("ssh-agent already has identities loaded.")

REMOTES_DATA = [
    {
        "host": "AV600-nmrsu",
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

rsync_count = 1

for remote in REMOTES_DATA:
    host = remote["host"]

    if host in [
        '''"AV600-nmrsu"''', 
        "AV300", 
        "AvanceNeo400", 
        "PharmaScan",
        ] :
        continue

    print(f"\n### Processing {host}...")

    user = remote["user"]
    apps = remote["apps"]
    usernames = remote["usernames"]
    
    for app in apps:

        print(f"\n    *** Processing {app}... ***\n")

        for username in usernames:
            remote_path = f"/opt/{app}/prog/curdir/{username}/"
            remote_spec = f"{user}@{host}:{remote_path}"
            dest_dir = Path(f"./{host}/{app}/{username}/.")

            if not dest_dir.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {dest_dir}")
            else:
                print(f"Directory already exists: {dest_dir}")
                # Matches 'name.<number>' or 'name.<number>.gz' (for compressed rotations)
                #_suffix_re = re.compile(r"\.(\d+)$")
                _suffix_re = re.compile(r"\.(?P<number>\d+)(?:\.gz)?$")
                
                max_n = 0
                # Look for files named 'stem.<n>' and 'stem.<n>.gz' in the same directory
                for p in dest_dir.glob("*"):
                    m = _suffix_re.search(p.name)
                    if m :
                        try:
                            n = int(m.group("number"))
                            if n > max_n:
                                max_n = n
                        except ValueError:
                            pass
                
                if max_n != 0:
                    print(f"  Existing backups found up to .{max_n} in {dest_dir}")
                    rotate_numbered_backup_logrotate(
                        dest_file=f"{dest_dir}/history",
                        max_rotations = 3,
                        compress=False,
                        )

            cmd = [
                "rsync", 
                "-av", 
                "--dry-run",
                "--checksum",
                "--itemize-changes",
                "--backup",
                "--suffix=.1",
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

            print(f"-> [{rsync_count}] Running:", " ".join(cmd))
            
            n_tries = 1
            while True:
                res = subprocess.run(cmd, capture_output=True, text=True)
                
                ## Basic rsync diagnostics
                #print("Return code:", res.returncode)
                #if res.stderr:
                #    print("STDERR:\n", res.stderr)
                #
                ## Full rsync output (human-readable but parseable)
                #print("STDOUT:\n", res.stdout)

                if res.returncode == 0:
                    print(f"{colored("[ OK  ]",(0, 255, 0), attrs=['bold'])} Try {n_tries}: synced {host}/{app}/{username}\n")
                    break
                elif res.returncode == 23:
                    print(f"{colored("[WARN ]",(255, 255, 0), attrs=['bold'])} Try {n_tries}: missing files for {host}/{app}/{username}; continuing.\n")
                    break
                else:
                    print(f"{colored("[ERROR]",(0, 255, 255), attrs=['bold'])} Try {n_tries}: rsync failed (rc={res.returncode}): {res.stderr.strip()}")
                    print("Retrying in 60 seconds...")
                    sleep(60)
                    if n_tries >= 10:
                        print(f"{colored("[FATAL]",(255, 0, 0), attrs=['bold'])} Try {n_tries}: rsync failed after {n_tries} attempts; moving to next.\n")
                        break
                    n_tries += 1
            
            rsync_count += 1

            

