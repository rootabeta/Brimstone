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
def track_inbounds(user, region, inbound, WA_only, ROs):
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
                    if canonicalize(nation) not in ROs:
                        # Not an RO, and just appeared - blow em to smithereens
                        print(f"\r[!] Radar detected inbound bogey: {canonicalize(nation)}")
                        inbound.append(canonicalize(nation))
                    else:
                        print(f"\r[*] Radar detected inbound friendly - avoiding buddyspike: {canonicalize(nation)}")
            
            # Now, set the state to the new one, to detect next second
            oldNations = newNations
            time.sleep(0.7)

    except KeyboardInterrupt:
        print("Shutting down radar at user request")

def main(): 
    with open("banner.txt","r",encoding="utf8") as f:
        print(f.read())

    user = canonicalize(input("Your main nation: "))

    print("Initializing SAM site, please wait...")
    session = NSSession("Brimstone","0.4","Volstrostia",user)
    print("SAM site ready to continue setup")
#    region = canonicalize(input("Region: ")) # TODO: Track from nation

    nation = canonicalize(input("RO Nation: "))
    password = getpass("Password: ")
    region = canonicalize(NSAPI.getRegion(nation,user))
    time.sleep(0.7) # CLear ratelimit
    print(f"Preparing to eliminate incursions into the airspace of: {region.upper()}")

    WA_only = False
    WA_only = True if str(input("Only track WA? (y/N) ")).lower().startswith("y") else False
    print("Tracking WA movement" if WA_only else "Tracking movement")

    spare_ROs = True
    spare_ROs = False if str(input("Exempt ROs from targetting? (Y/n) ")).lower().startswith("n") else True

    ROs = []
    if spare_ROs:
        print("Sparing ROs from the wrath of Brimstone")
        print("Initializing IFF system")
        for RO in NSAPI.getROs(region, user):
            print(f"Identified RO: {RO}")
            ROs.append(canonicalize(RO)) # Just in case
        time.sleep(0.7) # Clear ratelimit

    print("SAM site initialized. Press SPACE to arm missiles.")
    if session.login(nation, password):
        print("\rMissiles armed")
        manager = Manager()
        inbound = manager.list()

        # Open a thread to run track_inbounds (poll API regularly for nations)
        radar = Process(target=track_inbounds, args=(user, region, inbound, WA_only, ROs))
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
