from prettyprinter import PrettyPrinter
from nsdotpy.session import NSSession, canonicalize
from threading import Thread
from pwinput import pwinput
import logging
import rtoml
import random
import time
import NSAPI
import os

version = "2.0"

nsdotpylogger = logging.getLogger("NSDotPy")
nsdotpylogger.setLevel(logging.WARNING)
printer = PrettyPrinter()
running = True

# TODO: track stoponupdate
def track_inbounds(radar, inbound):
    global running
    while running:
        bogeys = radar.ping()

        inbound = bogeys
        radar.sleep() # Delay AFTER the ping, so the detections are delivered as fast as possible

def main(): 
    if os.name == "posix" and os.getuid() != 0:
        printer.error("Brimstone must be run as root on Linux-based systems")
        exit()

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
        printer.warning("Rate limit too low; overriding to 600ms")
        delay = 600

    jitter = config["config"].get("jitter") or "0" ; jitter = int(jitter)

    user = canonicalize(printer.ask("Your main nation: "))
    ro_nation = canonicalize(printer.ask("RO Nation: "))
    password = printer.password()

    print()
    printer.info("SETTINGS:")
    printer.indent(f"Main Nation:        {user}")
    printer.indent(f"RO Nation:          {ro_nation}")
    print()
    printer.indent(f"Only target WA:     {WA_only}")
    printer.indent(f"Ignore ROs:         {spare_ROs}")
    printer.indent(f"Ignore residents:   {ignore_residents}")
    printer.indent(f"Ban unknowns:       {ban_bogeys}")
    printer.indent(f"Killswitch:         {upd_killswitch}")
    print()
    printer.indent(f"Delay interval:     {delay}ms")
    printer.indent(f"Jitter:             {str(jitter).zfill(len(str(delay)))}ms")
    print()

    delay = float(delay) / 1000.0
    jitter = float(jitter) / 1000.0

    inbound = []

    # Create an API session for polling setup data ONLY
    # Another instance in another thread will handle the radar work after this is disused
    api = NSAPI.API(user, version, delay, jitter) 
    target_region = canonicalize(api.getRegion(ro_nation))

    printer.info("Initializing SAM site, please wait...")
    session = NSSession("Brimstone",version,"Volstrostia",user,link_to_src="https://github.com/rootabeta/brimstone",logger=nsdotpylogger)

    printer.info("Initializing IFF system, please wait...")
    if spare_ROs: 
        printer.info("Adding ROs to whitelist")
        for RO in api.getROs(target_region):
            whitelist["explicit"].add(canonicalize(RO)) # Hard-whitelist ROs. They will not be banned. 
        time.sleep(delay) # Clear ratelimit

    for nation in config["whitelist"].get("nations"):
        whitelist["explicit"].add(canonicalize(nation)) # Add any specific whitelists from the config

    if ignore_residents and target_region not in config["whitelist"].get("regions"): 
        printer.info(f"Adding all nations in {target_region} to whitelist")
        for nation in api.getNations(canonicalize(target_region)):
            whitelist["implicit"].add(canonicalize(nation))
        time.sleep(delay)


    for region in config["whitelist"].get("regions"):
        printer.info(f"Adding all nations in {region} to whitelist")
        for nation in api.getNations(canonicalize(region)):
            whitelist["implicit"].add(canonicalize(nation))
        time.sleep(delay)

    for nation in config["blacklist"].get("nations"):
        blacklist["explicit"].add(canonicalize(nation))

    for region in config["blacklist"].get("regions"):
        printer.info(f"Adding all nations in {region} to blacklist")
        for nation in api.getNations(canonicalize(region)):
            blacklist["implicit"].add(canonicalize(nation))
        time.sleep(delay)

    printer.info("IFF System Initialized")
    printer.indent(f"Explicitly permitted:  {len(whitelist['explicit'])}")
    printer.indent(f"Implicitly permitted:  {len(whitelist['implicit'])}")
    printer.indent(f"Explicitly targetted:  {len(blacklist['explicit'])}")
    printer.indent(f"Implicitly targetted:  {len(blacklist['implicit'])}")

    printer.success(f"Ready to eliminate incursions into the airspace of: {target_region.upper()}", prompt="RDY")
    api = None # Destroy setup API client, just in case
    radar = NSAPI.Radar(user, target_region, inbound, WA_only, whitelist, blacklist, ban_bogeys, delay, jitter, version)

    exit("Terminating") if printer.ask("Activate SAM site? (Y/n) ",prompt="CNF").lower().startswith("n") else printer.success("SAM site initialized. Press SPACE to arm missiles.",prompt="RDY")

    if session.login(ro_nation, password):
        printer.success("Missiles armed. Starting radar.")

        # Open a thread to run track_inbounds (poll API regularly for nations)
        #radar = Process(target=track_inbounds, args=(user, region, inbound, WA_only, ROs))
        #radar = Thread(target=track_inbounds, args=(user, region, inbound, WA_only, ROs, whitelists, blacklists, delay, jitter, version))
        radarThread = Thread(target=track_inbounds, args=(radar,inbound))
        radarThread.start()

        printer.info("Radar online.")
        printer.success("BIRD AFFIRM; PREPARED TO ENGAGE", prompt="RDY")
        try: 
            while True:
                if inbound:
                    # Pick a random target from the list
                    target = random.choice(inbound)
                    printer.missile_lock(target)
#                    print(f"\r[+] ACQUIRED MISSILE LOCK; TRACKING -[ {target.upper()} ]-")
                    if session.banject(target):
                        printer.hit_confirmed(target)
                        #print(f"\r[+] BIRD AWAY; HIT CONFIRMED: {target.upper()}")
                        if target in inbound:
                            try:
                                inbound.remove(target)
                            except:
                                printer.warning(f"FAILED TO REMOVE BOGEY FROM TRACKING: {canonicalize(nation).upper()}")

                    else:
                        printer.fail_hit(target)

        except KeyboardInterrupt:
            printer.info("Disarming SAM missiles at user request")
            global running
            running = False

    else:
        printer.error("Check your credentials, ya dingus")

if __name__ == "__main__":
    main()
