
#!/usr/bin/env python3
import subprocess
import glob
import os
from pathlib import Path
from time import sleep
from termcolor import colored

import os
import subprocess
import getpass
from pathlib import Path

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

    #if host in ["AV600-nmrsu", "AV300", "AvanceNeo400", "PharmaScan"] :
    #    continue

    print(f"\n### Processing {host}...")

    user = remote["user"]
    apps = remote["apps"]
    usernames = remote["usernames"]
    
    for app in apps:

        print(f"\n--> Processing {app}...")

        for username in usernames:
            remote_path = f"/opt/{app}/prog/curdir/{username}/"
            remote_spec = f"{user}@{host}:{remote_path}"
            dest_dir = Path(f"./{host}/{app}/{username}/.")

            if not dest_dir.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {dest_dir}")
            else:
                print(f"Directory already exists: {dest_dir}")

            cmd = [
                "rsync", "-av"
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
                if res.returncode == 0:
                    print(f"{colored("[ OK  ]",(0, 255, 0), attrs=['bold'])} Try {n_tries}: synced {host}/{app}/{username}")
                    break
                elif res.returncode == 23:
                    print(f"{colored("[WARN ]",(255, 255, 0), attrs=['bold'])} Try {n_tries}: missing files for {host}/{app}/{username}; continuing.")
                    break
                else:
                    print(f"{colored("[ERROR]",(0, 255, 255), attrs=['bold'])} Try {n_tries}: rsync failed (rc={res.returncode}): {res.stderr.strip()}")
                    sleep(60)
                    if n_tries >= 10:
                        print(f"{colored("[FATAL]",(255, 0, 0), attrs=['bold'])} Try {n_tries}: rsync failed after {n_tries} attempts; moving to next.")
                        break
                    n_tries += 1
            
            rsync_count += 1

            

