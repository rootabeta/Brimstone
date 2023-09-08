from nsdotpy.session import NSSession, canonicalize
from threading import Thread
import rtoml
from pwinput import pwinput
import random
import time
import NSAPI

version = "2.0"

def track_inbounds(radar, inbound):
    while True:
        bogeys = radar.ping()
        inbound = bogeys
        radar.sleep() # Delay AFTER the ping, so the detections are delivered as fast as possible

def main(): 
    with open("banner.txt","r",encoding="utf8") as f:
        print(f.read())

    # TODO: LOAD CONFIG FILE
    with open("config.toml") as f:
        config = rtoml.load(f)

    whitelist = {
        "explicit":set(),
        "implicit":set()
    }

    blacklist = {
        "explicit":set(),
        "implicit":set()
    }

    WA_only = config["config"].get("wa_only")
    spare_ROs = config["config"].get("ignore_ros")
    ban_bogeys = config["config"].get("target_bogeys") 
    upd_killswitch = config["config"].get("stoponupdate")
    ignore_residents = config["config"].get("ignore_residents")
    delay = config["config"].get("pollspeed") or "700" ; delay = int(delay)
    if delay < 600: 
        print("Rate limit too low; overriding to 600ms")
        delay = 600

    jitter = config["config"].get("jitter") or "0" ; jitter = int(jitter)

    user = canonicalize(input("Your main nation: "))
    ro_nation = canonicalize(input("RO Nation: "))
    password = pwinput(mask="*")

    print()
    print("SETTINGS:")
    print(f"Main Nation:        {user}")
    print(f"RO Nation:          {ro_nation}")
    print()
    print(f"Only target WA:     {WA_only}")
    print(f"Ignore ROs:         {spare_ROs}")
    print(f"Ignore residents:   {ignore_residents}")
    print(f"Ban unknowns:       {ban_bogeys}")
    print(f"Killswitch:         {upd_killswitch}")
    print()
    print(f"Delay interval:     {delay}ms")
    print(f"Jitter:             {str(jitter).zfill(len(str(delay)))}ms")
    print()

    delay = float(delay) / 1000.0
    jitter = float(jitter) / 1000.0

    inbound = []

    target_region = canonicalize(NSAPI.getRegion(ro_nation,user, version))

    print("Initializing SAM site, please wait...")
    session = NSSession("Brimstone",version,"Volstrostia",user)

    print("Initializing IFF system, please wait...")
    if spare_ROs: 
        print("Adding ROs to whitelist")
        for RO in NSAPI.getROs(target_region, user, version):
            whitelist["explicit"].add(canonicalize(RO)) # Hard-whitelist ROs. They will not be banned. 
        time.sleep(delay) # Clear ratelimit

    for nation in config["whitelist"].get("nations"):
        whitelist["explicit"].add(canonicalize(nation)) # Add any specific whitelists from the config

    if ignore_residents and target_region not in config["whitelist"].get("regions"): 
        print(f"Adding all nations in {target_region} to whitelist")
        for nation in NSAPI.getNations(canonicalize(target_region), user, version):
            whitelist["implicit"].add(canonicalize(nation))
        time.sleep(delay)


    for region in config["whitelist"].get("regions"):
        print(f"Adding all nations in {region} to whitelist")
        for nation in NSAPI.getNations(canonicalize(region), user, version):
            whitelist["implicit"].add(canonicalize(nation))
        time.sleep(delay)

    for nation in config["blacklist"].get("nations"):
        blacklist["explicit"].add(canonicalize(nation))

    for region in config["blacklist"].get("regions"):
        print(f"Adding all nations in {region} to blacklist")
        for nation in NSAPI.getNations(canonicalize(region), user, version):
            blacklist["implicit"].add(canonicalize(nation))
        time.sleep(delay)

    print("IFF System Initialized")
    print(f"Explicitly permitted:  {len(whitelist['explicit'])}")
    print(f"Implicitly permitted:  {len(whitelist['implicit'])}")
    print(f"Explicitly targetted:  {len(blacklist['explicit'])}")
    print(f"Implicitly targetted:  {len(blacklist['implicit'])}")

    print(f"Preparing to eliminate incursions into the airspace of: {target_region.upper()}")
    radar = NSAPI.Radar(user, target_region, inbound, WA_only, whitelist, blacklist, ban_bogeys, delay, jitter, version)
    exit("Terminating") if input("Activate SAM site? (Y/n) ").lower().startswith("n") else print("SAM site initialized. Press SPACE to arm missiles.")

    if session.login(ro_nation, password):
        print("\rMissiles armed. Starting radar.")

        # Open a thread to run track_inbounds (poll API regularly for nations)
        #radar = Process(target=track_inbounds, args=(user, region, inbound, WA_only, ROs))
        #radar = Thread(target=track_inbounds, args=(user, region, inbound, WA_only, ROs, whitelists, blacklists, delay, jitter, version))
        radarThread = Thread(target=track_inbounds, args=(radar,inbound))
        radarThread.start()

        print("\rRadar online.")
        print("\rBIRD AFFIRM; PREPARED TO ENGAGE")
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
                                print("\r[!] FAILED TO REMOVE BOGEY FROM TRACKING: {canonicalize(nation).upper()}")

                    else:
                        print("\r[!] BIRD NEGATIVE; FAILED TO HIT: {target.upper()}; TRY AGAIN")
        except KeyboardInterrupt:
            print("Disarming SAM missiles at user request")

        print("Goodbye")
    else:
        print("Fatal error - check your credentials, ya dingus")

if __name__ == "__main__":
    main()
