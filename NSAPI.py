from benedict import benedict
from prettyprinter import PrettyPrinter
import requests
import time
from random import random

printer = PrettyPrinter()

def canonicalize(nation):
    return nation.lower().replace(" ","_")

class API():
    def __init__(self, user, version, delay, jitter): 
        self.user = user
        self.version = version
        self.delay = delay
        self.jitter = jitter
        self.user_agent = f"Brimstone/{self.version} (API component); Developed by nation=Volstrostia; in use by nation={self.user}"

    # Stolen from nsdotpy :P 
    def regionAPI(self, url):
        r = requests.get(url, headers={"User-Agent":self.user_agent})

        head = r.headers

        if "X-Pin" in head:
            self.pin = head["X-Pin"]

        if waiting_time := head.get("Retry-After"):
            printer.warning(f"\r[!] Rate limited. Waiting {waiting_time} seconds.")
            time.sleep(int(waiting_time))
        # slow down requests so we dont hit the rate limit in the first place
        requests_left = int(head["RateLimit-Remaining"])

        # If we have <10 requests left in this window, sloooow down
        if requests_left < 10:
            seconds_until_reset = int(head["RateLimit-Reset"])
            delay = float(seconds_until_reset) / float(requests_left)

            # Parent function will call its own delay of at least delay milliseconds
            # Ergo, if the API demands more than that, we can just tack on the extra
            if delay > self.delay:
                time.sleep(self.delay - delay)

        parsed_response = benedict.from_xml(r.text, keyattr_dynamic=True)
        parsed_response.standardize()
        parsed_response: benedict = parsed_response["region"]  # type: ignore
        return parsed_response

    def nationAPI(self, url):
        r = requests.get(url, headers={"User-Agent":self.user_agent})

        head = r.headers

        if "X-Pin" in head:
            self.pin = head["X-Pin"]

        if waiting_time := head.get("Retry-After"):
            printer.warning(f"\r[!] Rate limited. Waiting {waiting_time} seconds.")
            time.sleep(int(waiting_time))
        # slow down requests so we dont hit the rate limit in the first place
        requests_left = int(head["RateLimit-Remaining"])

        # If we have <10 requests left in this window, sloooow down
        if requests_left < 10:
            seconds_until_reset = int(head["RateLimit-Reset"])
            delay = float(seconds_until_reset) / float(requests_left)
            time.sleep(delay)

        parsed_response = benedict.from_xml(r.text, keyattr_dynamic=True)
        parsed_response.standardize()
        parsed_response: benedict = parsed_response["nation"]  # type: ignore
        return parsed_response

    # Get a given shard for a given region
    def getRegionShard(self, region, shard):
        if not self.user:
            raise RuntimeError("We need a user to identify you")

        #userAgent = f"Brimstone/{version} (API component); Developed by nation=Volstrostia; in use by nation={user}"
        URL = f"https://nationstates.net/cgi-bin/api.cgi?region={region}&q={shard}"
        return self.regionAPI(URL)

    # Get the region a nation resides in
    def getRegion(self, nation):
#        userAgent = f"Brimstone/{version} (API component); Developed by nation=Volstrostia; in use by nation={user}"
        URL = f"https://nationstates.net/cgi-bin/api.cgi?nation={nation}&q=region"
        residingregion = self.nationAPI(URL)
        if residingregion and "region" in residingregion:
            return residingregion["region"]

    # Get list of all nations
    def getNations(self, region):
        nations = self.getRegionShard(region, "nations")
        if nations and "nations" in nations:
            nationList = nations["nations"]
            if nationList and ":" in nationList:
                return nationList.split(":")
            elif nationList:
                return [nationList]
            else:
                return []
        else:
            return []

# Get list of all WA nations
    def getWANations(self, region):
        nations = self.getRegionShard(region, "wanations")
        if nations and "unnations" in nations:
            nationList = nations["unnations"]
            if nationList and "," in nationList:
                return nationList.split(",")
            elif nationList:
                return [nationList]
            else:
                return []
        else:
            return []

    def getROs(self, region):
        ROs = self.getRegionShard(region, "officers+delegate")
        officers = []

        if ROs and "delegate" in ROs:
            if str(ROs.delegate) != "0":
                officers.append(ROs.delegate)

        if ROs and "officers" in ROs:
            raw = ROs.officers.officer
            ROList = []
            if type(raw) != list:
                raw = [raw] # If there's only one RO, NS will not return it as an array... for some reason

            for office in raw:
                if office.nation:
                    officers.append(office.nation)

        if officers:
            return officers
        else:
            return []

class Radar():
    def __init__(self, user, region, inbound, WA_only, whitelists, blacklists, ban_bogeys, delay, jitter, version):
        self.user = user
        self.region = region
        self.inbound = inbound
        self.WA_only = WA_only
        self.whitelists = whitelists
        self.blacklists = blacklists
        self.ban_bogeys = ban_bogeys
        self.version = version

        self.delay = delay
        self.jitter = jitter

        self.oldNations = []
        self.newNations = []

        # Instantiate an API instance
        self.api = API(user, version, delay, jitter)
        self.initialize()

    def sleep(self):
        # Useful so ROs don't overlap eachothers scan times
        # This will lend a random RO the chance to be "first"
        # And allow time around the 1s timer to drift around the clock
        # during Brimstone operations, allowing for a higher likelyhood
        # that someone is polling at any given moment
        if self.jitter:
            jitter = random() % float(self.jitter)
        else:
            jitter = 0.0

        time.sleep(self.delay + jitter)

    def fetch_nations(self):
        # For non-WA nations
        if not self.WA_only:
            nationlist = self.api.getNations(canonicalize(self.region))
        # WA-only mode
        else:
            nationlist = self.api.getWANations(canonicalize(self.region))

        return nationlist

    # Populate the radar with "background" 
    def initialize(self):
        self.oldNations = self.fetch_nations()

    # 0 - Friendly, save
    # 1 - Foe, ban
    # 2 - Unknown, ban
    # 3 - Unknown, save
    def IFF(self, nation):
        if canonicalize(nation) in self.whitelists["explicit"]:
            return 0

        elif canonicalize(nation) in self.blacklists["explicit"]:
            return 1

        elif canonicalize(nation) in self.blacklists["implicit"]:
            return 1

        elif canonicalize(nation) in self.whitelists["implicit"]:
            return 0

        # We've never seen this puppet before
        else:
            if self.ban_bogeys:
                return 2
            else:
                return 3

    # Return a list of inbounds
    def ping(self):
        self.newNations = self.fetch_nations()

        for nation in self.inbound: 
            if canonicalize(nation) not in self.newNations: 
                try:
                    self.inbound.remove(canonicalize(nation))
                except:
                    printer.warning(f"FAILED TO REMOVE BOGEY FROM TRACKING: {canonicalize(nation).upper()}")

        for nation in self.newNations: 
            # Bogey on radar: friend or foe?
            if canonicalize(nation) not in self.oldNations and canonicalize(nation) not in self.inbound:
                IFFcode = self.IFF(canonicalize(nation))

                # Foe
                if IFFcode == 1:
                    #print(f"\r[!] RADAR DETECTED INBOUND BANDIT: {canonicalize(nation).upper()}")
                    printer.bandit_detected(canonicalize(nation))
                    self.inbound.append(canonicalize(nation))

                # Friend
                elif IFFcode == 0:
                    printer.friendly_detected(canonicalize(nation))

                # Bogey, ban
                elif IFFcode == 2:
                    printer.bogey_detected_ban(canonicalize(nation))
                    self.inbound.append(canonicalize(nation))

                # Bogey, spare
                elif IFFcode == 3:
                    printer.bogey_detected_safe(canonicalize(nation))

        self.oldNations = self.newNations
        return self.inbound


