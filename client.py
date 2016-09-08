import os

import datetime
import pytz

import requests
import time
import logging
import functools

from logging.handlers import RotatingFileHandler

from requests.exceptions import ConnectionError
from ws4py.client.threadedclient import WebSocketClient

# settings module itself should return local settings so that
# manage.py commands work.
try:
    from settings import LOGIN_URL, WS_URL, PHOTO_STATUS_URL,\
        USER_EMAIL, USER_PASSWORD
except ImportError as e:
    error_message = '{mes} (did you copy settings.example.py to settings.py?)'.format(
        mes=e.args[0],
    )
    e.args = tuple([error_message])

    raise e

from print_image import print_image, PrintImageException

# setting up the logger
log_dir_path = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(log_dir_path):
    os.makedirs(log_dir_path)

logger = logging.getLogger('barebox_printing')
file_handler = RotatingFileHandler(os.path.join(log_dir_path,
                                                'barebox_printing.log'),
                                   maxBytes=10*1024, backupCount=2)
formatter = logging.Formatter('[%(asctime)s] - %(levelname)s: %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)


def log_interrupt(foo):
    """
    Decorator to log exit with KeyboardInterrupt

    """
    @functools.wraps(foo)
    def wrapped(*args, **kwargs):
        try:
            foo(*args, **kwargs)
        except KeyboardInterrupt:
            logger.debug('Exit with KeyboardInterrupt')
    return wrapped


@log_interrupt
def get_ws_connection():
    client = requests.session()

    connection_established = csrftoken = False

    while not (connection_established and csrftoken):
        try:
            logger.debug('Trying to connect to the server...')

            # Retrieving the CSRF token first
            client.get(LOGIN_URL)  # sets cookie
            csrftoken = client.cookies.get('csrftoken')
        except ConnectionError:
            logger.debug('The server is down, '
                         'awaiting for 10 seconds to reconnect...')
            time.sleep(10)
        else:
            connection_established = True

    logger.debug('Trying to establish a session using '
                 'provided user credentials')
    login_data = dict(login=USER_EMAIL, password=USER_PASSWORD,
                      csrfmiddlewaretoken=csrftoken, next='/')
    response = client.post(LOGIN_URL, data=login_data, headers=dict(Referer=LOGIN_URL))

    if response.history[0].status_code != 302:
        logger.debug('Wrong username or password')
    else:
        with PrinterClient(WS_URL + 'print_server?subscribe-user',
                           headers=(
                               ('Cookie',
                                'sessionid={}'.format(client.cookies.get('sessionid'))),
                           ), request_client=client) as ws:
            logger.debug('Trying to establish a websocket connection '
                         'on behalf of logged in user')

            ws.connect()
            ws.run_forever()


class PrinterClient(WebSocketClient):
    def __init__(self, *args, **kwargs):
        self.request_client = kwargs.pop('request_client')
        super(PrinterClient, self).__init__(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        super(PrinterClient, self).close()

    def opened(self):
        logger.debug('Connection established')

    def closed(self, code, reason=None):
        logger.debug("Connection closed down: {}, {}".format(code, reason))

    def terminate(self):
        logger.debug('Connection terminated')
        get_ws_connection()

        super(PrinterClient, self).terminate()

    def received_message(self, m):
        if str(m) != '--heartbeat--':   # omit heartbeat messages
            photo_id, photo_url = str(m).split(',')
            logger.info("Signal for photo printing received (photo_id:{}) {}"
                        .format(photo_id, photo_url))

            request_data = {}

            try:
                print_image(photo_url)
            except PrintImageException as print_exception:
                error = str(print_exception.message) + 'photo: {}'.format(photo_url)
                status = 'print_failed'

                logger.error('Error occurred during image printing: {}'
                             .format(print_exception.message))
            else:
                error = ''
                status = 'print_successful'
                request_data.update(printed_time=datetime.datetime.utcnow().replace(tzinfo=pytz.utc))

            request_data.update(print_status=status, error=error)
            csrftoken = self.request_client.cookies['csrftoken']
            patch_photo_url = '{}{}/'.format(PHOTO_STATUS_URL,
                                             photo_id)

            logger.info('Updating printing status for photo {}: {}'
                        .format(photo_id, status))

            self.request_client.patch(patch_photo_url,
                                      data=request_data,
                                      headers={'X-CSRFToken': csrftoken})

if __name__ == '__main__':
    get_ws_connection()
