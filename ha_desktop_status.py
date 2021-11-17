#! python3

# Include Python stuff
import logging
import signal
# Include dbus stuff
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
# Include Home-Assistant Stuff
from requests import post
from requests import get
from requests import HTTPError
from timeloop import Timeloop
from datetime import timedelta

# Define Global Variable
DBUS_SCREENSAVER_INTERFACE = "org.gnome.ScreenSaver"
HA_URL = "https://home-assistant.domain.com"
HA_TOKEN = "FILL ME WITH YOUR LONGLIVED TOKEN"
HA_ENTITY = "input_boolean.computer_name_used"

LAST_STATE = True
BACKGROUP_UPDATE_INTERVAL = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HA_Desktop_Status")


# Listen for Term signal from Systemd
def signal_handler():
    signal.signal(signal.SIGTERM, exit_gracefully)


def exit_gracefully(signum=0, frame=None):
    logger.info('Exiting now')
    tl.stop()
    loop.quit()
    ha_update_status(False)
    exit(0)


# Listen for Dbus Screensaver Event
def set_dbus_loop():
    # Create Session bus
    DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    # register for Gnome Screensaver signal
    session_bus.add_signal_receiver(dbus_lock_handler,
                                    dbus_interface=DBUS_SCREENSAVER_INTERFACE)
    # Create loop and start it
    loop = GLib.MainLoop()
    return loop


# React to Dbus Screensaver Event
def dbus_lock_handler(is_lock):
    global LAST_STATE
    if is_lock:
        logger.info('The computer is now locked')
        LAST_STATE = False
    else:
        logger.info('The computer is now unloked')
        LAST_STATE = True
    ha_update_status(LAST_STATE)


# Home assistant API Handler
def ha_call(endpoint, data=None):
    url = "{}{}".format(HA_URL, endpoint)
    headers = {
        "Authorization": "Bearer {}".format(HA_TOKEN),
        "content-type": "application/json",
    }
    if data:
        response = post(url, data, headers=headers, timeout=5)
    else:
        response = get(url, headers=headers, timeout=5)
    if response.ok:
        return response
    else:
        raise HTTPError("{}: {}".format(response.status_code,
                                        response.reason))


# Set the status of my computer state on Homeassistant
def ha_update_status(status):
    if status:
        service = "input_boolean.turn_on"
    else:
        service = "input_boolean.turn_off"
    endpoint = "/api/services/{}".format("/".join(service.split('.')))
    data = '{{"entity_id": "{}"}}'.format(HA_ENTITY)
    try:
        ha_call(endpoint, data)
    except TimeoutError as err:
        logger.warning("{}: The server have timeout, we will try again at the next loop".format(err))


tl = Timeloop()


# Setup loop to push last state again, just in case
@tl.job(interval=timedelta(minutes=BACKGROUP_UPDATE_INTERVAL))
def update_loop():
    ha_update_status(LAST_STATE)
    logger.info('State re-sended : {}'.format(LAST_STATE))


if __name__ == '__main__':
    try:
        signal_handler()
        ha_update_status(True)
        tl.start()
        loop = set_dbus_loop()
        loop.run()
    except KeyboardInterrupt:
        exit_gracefully()