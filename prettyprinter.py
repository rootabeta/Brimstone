from colorama import Fore, Back, Style
from pwinput import pwinput

class PrettyPrinter():
    # Standard stuff
    def info(self, string):
        print("\r[" + Style.BRIGHT + Fore.CYAN + "INF" + Style.RESET_ALL + "] " + str(string))

    def warning(self, string):
        print("\r[" + Fore.YELLOW + Style.BRIGHT + "WRN" + Style.RESET_ALL + "] " + str(string))

    def error(self, string):
        print("\r[" + Fore.RED + Style.BRIGHT + "ERR" + Style.RESET_ALL + "] " + str(string))

    def success(self, string, prompt="SCS"):
        print("\r[" + Fore.GREEN + Style.BRIGHT + prompt + Style.RESET_ALL + "] " + str(string))

    def ask(self, string, prompt="INP"):
        return input("\r[" + Fore.BLUE + Style.BRIGHT + prompt + Style.RESET_ALL + "] " + str(string))

    def password(self):
        prompt = "[" + Fore.BLUE + Style.BRIGHT + "PWD" + Style.RESET_ALL + "] Password: "
        return pwinput(prompt=prompt, mask="*")

    def indent(self, string):
        print("\r" + " " * 6 + str(string))

    # Some specific to Brimstone

    def bogey_detected_ban(self, nation):
        print("\r[" + Fore.YELLOW + Style.BRIGHT + "BGY" + Style.RESET_ALL + f"] DETECTED INBOUND BOGEY: {nation.upper()} ; LAUNCH " + Style.BRIGHT + "AUTHORIZED" + Style.RESET_ALL)

    def bogey_detected_safe(self, nation):
        print("\r[" + Fore.YELLOW + Style.BRIGHT + "BGY" + Style.RESET_ALL + f"] DETECTED INBOUND BOGEY: {nation.upper()} ; LAUNCH " + Style.BRIGHT + "NOT" + Style.RESET_ALL + " AUTHORIZED")

    def bandit_detected(self, nation):
        print("\r[" + Fore.RED + Style.BRIGHT + "BND" + Style.RESET_ALL + f"] DETECTED HOSTILE BANDIT: {nation.upper()}")

    def friendly_detected(self, nation):
        print("\r[" + Fore.GREEN + Style.BRIGHT + "FRN" + Style.RESET_ALL + f"] DETECTED INBOUND FRIENDLY: {nation.upper()}")

    def missile_lock(self, nation):
        print("\r[" + Fore.RED + Style.BRIGHT + "LCK" + Style.RESET_ALL + f"] ACQUIRED MISSILE LOCK ON -=[ {nation.upper()} ]=- ; PRESS SPACE TO AUTHORIZE LAUNCH")

    def hit_confirmed(self, nation):
        print("\r[" + Fore.GREEN + Style.BRIGHT + "HIT" + Style.RESET_ALL + f"] BIRD AWAY; CONFIRMED HIT; {nation.upper()} DOWNED")

    def fail_hit(self, nation):
        print("\r[" + Fore.RED + Style.BRIGHT + "LOS" + Style.RESET_ALL + f"] BIRD NEGATIVE; COULD NOT ENGAGE {nation.upper()}; PRESS SPACE TO RE-ACQUIRE")
    
    def testSuite(self, nation="Volstrostia"):
        self.bogey_detected_ban(nation)
        self.bogey_detected_safe(nation)
        self.bandit_detected(nation)
        self.friendly_detected(nation)
        self.missile_lock(nation)
        self.hit_confirmed(nation)
        self.fail_hit(nation)
