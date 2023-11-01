# Brimstone
Fendas: you've yeed your last haw

![The missile knows where you are at all times](logo.png)

Brimstone is a semi-automatic anti-liberation tool for NationStates R/D gameplay. 
It works by polling the API for recent inbound users, then passing them to be banned with the press of a button. 
This method allows for rapid banning of inbound nations during and around update, which in turn makes defenders have a very hard time. 

To use Brimstone, simply run the Python file, enter the prompted variables, and spam space. When an inbound nation is detected, it will be prepared for banjection, which will occur on the next spacebar press. Note that Brimstone will log out of your nation on all browsers and other scripts; do not log into the RO nation until Brimstone is no longer running, to prevent a subsequent login from logging Brimstone out. 

## How does it work?
A brief summary of Brimstone's target selection algorithm is as follows: 

Brimstone knows where the defender is at all times. It knows this because it knows where it isn’t. By subtracting where it is from where it isn’t, it obtains a difference, or deviation. The guidance system uses difference to generate corrective commands. In the event that the position the defender is in is now where it wasn’t, Brimstone corrects for this with a “banjection”. The defender now isn’t where it was, and in the position where it wasn’t, it now is. In the event the defender still isn’t where it wasn’t, the system has acquired an error. Brimstone may issue further corrective commands.

In summary, Brimstone’s guidance works as follows. Brimstone is not sure just where the defender is. However, it is sure where it isn’t. If Brimstone detects an object it performs the algebraic sum of where they were and where they shouldn’t be, and if it is now where it shouldn’t, it sends it to where it wasn’t.

