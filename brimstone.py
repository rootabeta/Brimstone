from nsdotpy.session import NSSession, canonicalize
from multiprocessing import Process, Manager
from getpass import getpass
import random
import time
import NSAPI

# Make an API request for all the nations (or all the WA nations, depending on mode)
# Then, delay 700ms to enforce API ratelimit
def fetch_nations(user, region, WA_only):
    # For non-WA nations
    if not WA_only:
        nationlist = NSAPI.getNations(canonicalize(region), canonicalize(user))
    # WA-only mode
    else:
        nationlist = NSAPI.getWANations(canonicalize(region), canonicalize(user))

    # Rate limit
    time.sleep(0.700) 
    return nationlist

# Constantly poll the API for nations
def track_inbounds(user, region, inbound, WA_only):
    print("Radar online. Keeping our eye on the sky.")
    oldNations = []
    newNations = []

    # Get a list of nations we might care about to initialize
    oldNations = fetch_nations(user, region, WA_only)

    try:
        while True:
            # Refresh the list
            newNations = fetch_nations(user, region, WA_only)

            # Remove nations that have left from our hitlist
            for nation in inbound:
                if canonicalize(nation) not in newNations and canonicalize(nation) in inbound:
                    try:
                        inbound.remove(canonicalize(nation))
                    except:
                        print("\r[!] Failed to remove bogey from tracking")

            # This nation wasn't here the last time we checked! Add it to the list of inbounds
            for nation in newNations:
                if canonicalize(nation) not in oldNations and canonicalize(nation) not in inbound:
                    print(f"\r[!] Radar detected inbound bogey: {canonicalize(nation)}")
                    inbound.append(canonicalize(nation))
            
            # Now, set the state to the new one, to detect next second
            oldNations = newNations
            time.sleep(0.7)

    except KeyboardInterrupt:
        print("Shutting down radar at user request")

def main(): 
    with open("banner.txt","r",encoding="utf8") as f:
        print(f.read())

    user = input("Your main nation: ")
    session = NSSession("Brimstone","0.3","Volstrostia",user)

    region = canonicalize(input("Region: ")) # TODO: Track from nation

    nation = canonicalize(input("RO Nation: "))
    password = getpass("Password: ")

    WA_only = False
    WA_only = True if str(input("Only track WA? (y/N) ")).lower().startswith("y") else False
    print("Tracking WA movement" if WA_only else "Tracking movement")

    print("SAM site initialized. Press SPACE to arm missiles.")
    if session.login(nation, password):
        print("\rMissiles armed")
        manager = Manager()
        inbound = manager.list()

        # Open a thread to run track_inbounds (poll API regularly for nations)
        radar = Process(target=track_inbounds, args=(user, region, inbound, WA_only))
        radar.start()

        print("\rBird affirm. Prepared to engage.")
        try: 
            while True:
                if inbound:
                    # Pick a random target from the list
                    target = random.choice(inbound)
                    print(f"\r[+] ACQUIRED MISSILE LOCK; TRACKING -[ {target.upper()} ]-")
                    if session.banject(target):
                        print(f"\r[+] BIRD AWAY; HIT CONFIRMED: {target.upper()}")
                        if target in inbound:
                            try:
                                inbound.remove(target)
                            except:
                                print("\r[!] Failed to remove bogey from tracking")

                    else:
                        print("\r[!] BIRD NEGAT; TRY AGAIN")
        except KeyboardInterrupt:
            print("Disarming SAM missiles at user request")

        print("Goodbye")
    else:
        print("Fatal error - check your credentials, ya dingus")

if __name__ == "__main__":
    main()
