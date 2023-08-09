from nsdotpy.session import NSSession, canonicalize
from multiprocessing import Process, Manager
from getpass import getpass
import random
import time

with open("banner.txt","r") as f:
    print(f.read())

user = input("Your main nation: ")
session = NSSession("Brimstone","0.1","Volstrostia",user)


region = canonicalize(input("Region: ")) # TODO: Track from nation
nation = canonicalize(input("RO Nation: "))
password = getpass("Password: ")

WA_only = False


def fetch_nations(session, region, WA_only=False):
    # For non-WA nations
    if not WA_only:
        nations = session.api_request("region",target=region,shard="nations", constant_rate_limit=True)
        if ":" in nations["nations"]:
            nationlist = nations["nations"].split(":")
        else:
            nationlist = [nations["nations"]]

    # WA-only mode
    else:
        nations = session.api_request("region",target=region,shard="unnations", constant_rate_limit=True)
        if "," in nations["unnations"]:
            nationlist = nations["unnations"].split(",")
        else:
            nationlist = [nations["unnations"]]

    return nationlist

def track_inbounds(session, region, inbound, WA_only=False):
    print("Radar online. Keeping our eye on the sky.")
    oldNations = []
    newNations = []

    oldNations = fetch_nations(session, region, WA_only)

    try:
        while True:
            newNations = fetch_nations(session, region, WA_only)

            # Remove nations that have left from our hitlist
            for nation in inbound:
                if canonicalize(nation) not in newNations:
                    inbound.remove(canonicalize(nation))

            for nation in newNations:
                if canonicalize(nation) not in oldNations and canonicalize(nation) not in inbound:
                    print(f"[!] Radar detected inbound nation!: {canonicalize(nation)}")
                    inbound.append(canonicalize(nation))
            
            # Now, set the state to the new one, to detect next second
            oldNations = newNations
            time.sleep(0.7)
    except KeyboardInterrupt:
        print("Shutting down radar at user request")

print("Launcher initialized. Press SPACE to start tracking.")
if session.login(nation, password):
    print("Login successful!")
    manager = Manager()
    inbound = manager.list()

    radar = Process(target=track_inbounds, args=(session, region, inbound))
    radar.start()

    print("SAM missiles online. Ready to blast em to smithereens.")
    try: 
        while True:
            if inbound:
                target = random.choice(inbound)
                print(f"[+] ACQUIRED MISSILE LOCK ON -[ {target.upper()} ]-")
                if session.banject(target):
                    print(f"[+] IMPACT CONFIRMED: {target.upper()}")
                    inbound.remove(target)
                else:
                    print("[!] LAUNCH FAILED")
    except KeyboardInterrupt:
        print("Disarming SAM missiles at user request")

    print("Goodbye")
