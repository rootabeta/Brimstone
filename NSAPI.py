from benedict import benedict
import requests
import time

def canonicalize(nation):
    return nation.lower().replace(" ","_")

# Stolen from nsdotpy :P 
def regionAPI(url, user_agent):
    r = requests.get(url, headers={"User-Agent":user_agent})

    head = r.headers

    if "X-Pin" in head:
        self.pin = head["X-Pin"]

    if waiting_time := head.get("Retry-After"):
        print(f"\r[!] Rate limited. Waiting {waiting_time} seconds.")
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
    parsed_response: benedict = parsed_response["region"]  # type: ignore
    return parsed_response

def nationAPI(url, user_agent):
    r = requests.get(url, headers={"User-Agent":user_agent})

    head = r.headers

    if "X-Pin" in head:
        self.pin = head["X-Pin"]

    if waiting_time := head.get("Retry-After"):
        print(f"\r[!] Rate limited. Waiting {waiting_time} seconds.")
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
def getRegionShard(region, shard, user, version):
    # nationstates.net/cgi-bin/api.cgi?region=greater_sahara&q=nations
    if not user:
        raise RuntimeError("We need a user to identify you")

    userAgent = f"Brimstone/{version} (API component); Developed by nation=Volstrostia; in use by nation={user}"
    URL = f"https://nationstates.net/cgi-bin/api.cgi?region={region}&q={shard}"
    return regionAPI(URL, userAgent)

# Get the region a nation resides in
def getRegion(nation, user, version):
    userAgent = f"Brimstone/{version} (API component); Developed by nation=Volstrostia; in use by nation={user}"
    URL = f"https://nationstates.net/cgi-bin/api.cgi?nation={nation}&q=region"
    residingregion = nationAPI(URL, userAgent)
    if residingregion and "region" in residingregion:
        return residingregion["region"]

# Get list of all nations
def getNations(region, user, version):
    nations = getRegionShard(region, "nations", user, version)
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
def getWANations(region, user, version):
    nations = getRegionShard(region, "wanations", user, version)
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

def getROs(region, user, version):
    ROs = getRegionShard(region, "officers+delegate", user, version)
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

        self.initialize()

    def sleep(self):
        time.sleep(self.delay)

    def fetch_nations(self):
        # For non-WA nations
        if not self.WA_only:
            nationlist = getNations(canonicalize(self.region), canonicalize(self.user), self.version)
        # WA-only mode
        else:
            nationlist = getWANations(canonicalize(self.region), canonicalize(self.user), self.version)

        return nationlist

    def initialize(self):
        self.oldNations = self.fetch_nations()

    # Return TRUE if clear to fire
    def IFF(self, nation):
        if canonicalize(nation) in self.whitelists["explicit"]:
            return False

        elif canonicalize(nation) in self.blacklists["explicit"]:
            return True

        elif canonicalize(nation) in self.blacklists["implicit"]:
            return True

        elif canonicalize(nation) in self.whitelists["implicit"]:
            return False

        # We've never seen this puppet before
        else:
            if self.ban_bogeys:
                return True
            else:
                return False

    # Return a list of inbounds
    def ping(self):
        self.newNations = self.fetch_nations()

        for nation in self.inbound: 
            if canonicalize(nation) not in self.newNations: 
                try:
                    self.inbound.remove(canonicalize(nation))
                except:
                    print(f"\r[!] FAILED TO REMOVE BOGEY FROM TRACKING: {canonicalize(nation).upper()}")

        for nation in self.newNations: 
            # Bogey on radar: friend or foe?
            if canonicalize(nation) not in self.oldNations and canonicalize(nation) not in self.inbound:
                if self.IFF(canonicalize(nation)):
                    print(f"\r[!] RADAR DETECTED INBOUND BANDIT: {canonicalize(nation).upper()}")
                    self.inbound.append(canonicalize(nation))
                else:
                    print(f"\r[*] RADAR DETECTED INBOUND FRIENDLY: {canonicalize(nation).upper()}")

        self.oldNations = self.newNations
        return self.inbound


