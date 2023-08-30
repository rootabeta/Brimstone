from benedict import benedict
import requests
import time

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
        delay = seconds_until_reset / requests_left

        # A 700ms delay is invoked by the parent function
        # If that is enough, don't sleep more. Otherwise, sleep that long
        if delay > 700:
            time.sleep(699 - delay)

    parsed_response = benedict.from_xml(r.text, keyattr_dynamic=True)
    parsed_response.standardize()
    parsed_response: benedict = parsed_response["region"]  # type: ignore
    return parsed_response

# Get a given shard for a given region
def getRegionShard(region, shard, user):
    # nationstates.net/cgi-bin/api.cgi?region=greater_sahara&q=nations
    if not user:
        raise RuntimeError("We need a user to identify you")

    userAgent = f"Brimstone/0.3 (API component); Developed by nation=Volstrostia; in use by nation={user}"
    URL = f"https://nationstates.net/cgi-bin/api.cgi?region={region}&q={shard}"
    return regionAPI(URL, userAgent)

# Get the region a nation resides in
def getRegion(nation, user):
    userAgent = f"Brimstone/0.3 (API component); Developed by nation=Volstrostia; in use by nation={user}"
    URL = f"https://nationstates.net/cgi-bin/api.cgi?nation={nation}&q=region"
    region = regionAPI(URL, userAgent)

# Get list of all nations
def getNations(region, user):
    nations = getRegionShard(region, "nations", user)
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
def getWANations(region, user):
    nations = getRegionShard(region, "wanations", user)
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

