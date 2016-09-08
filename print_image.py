#!/usr/bin/env python
import os
import logging
import requests
import shutil
import platform

import subprocess
from PIL import Image, ImageWin
from urlparse import urlsplit

from requests.packages.urllib3.exceptions import ConnectionError

TMP_IMG_DIR = 'tmp_images'
logger = logging.getLogger('barebox_printing')


class PrintImageException(Exception):
    def __init__(self, message=None):
        self.message = message

    def __str__(self):
        return repr(self.message)


def print_image(image_url):
    file_name = urlsplit(image_url).path.split('/')[-1]
    img_dir_path = os.path.join(os.path.dirname(__file__), TMP_IMG_DIR)
    tmp_img_path = os.path.join(img_dir_path, file_name)

    if not os.path.exists(img_dir_path):
        os.makedirs(img_dir_path)

    # Another way to get file from url:
    # import urllib
    # resource = urllib.urlopen(image_url)
    # output = open(tmp_img_path,"wb")
    # output.write(resource.read())
    # output.close()

    logger.debug('Trying to fetch image from url: {}'.format(image_url))

    try:
        img_request = requests.get(image_url, stream=True)
    except ConnectionError as e:
        raise PrintImageException(e.message)

    if img_request.status_code != requests.codes.ok:
        raise PrintImageException('Image fetching  error, reason: '
                                  'Response status code is not 200 OK')
    else:
        with open(tmp_img_path, 'wb') as f:
            # img_request.raw.decode_content = True
            shutil.copyfileobj(img_request.raw, f)
        del img_request

        logger.debug('Image downloaded from url: {}'.format(image_url))

        if platform.system() == 'Linux' or platform.system() == 'Darwin':
            logger.debug('Printing on UNIX system...')

            lpr_call = subprocess.Popen(['lpr', tmp_img_path],
                                        shell=True,
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        close_fds=True)
            lpr_stdout = lpr_call.stdout.read()

            if 'Error' in lpr_stdout:
                raise PrintImageException(lpr_stdout)

        elif platform.system() == 'Windows':
            logger.debug('Printing on Windows system...')
            import win32print
            import win32ui

            printer_name = win32print.GetDefaultPrinter()

            # http://timgolden.me.uk/python/win32_how_do_i/print.html#rough_and_ready
            #
            # Create a device context from a named printer
            # and assess the printable size of the paper.
            hDC = win32ui.CreateDC()
            hDC.CreatePrinterDC(printer_name)

            bmp = Image.open(tmp_img_path)

            # Start the print job, and draw the bitmap to
            # the printer device
            hDC.StartDoc(tmp_img_path)
            hDC.StartPage()

            dib = ImageWin.Dib(bmp)
            dib.draw(hDC.GetHandleOutput(), (1, 1, 1219, 1829))

            hDC.EndPage()
            hDC.EndDoc()
            hDC.DeleteDC()

        os.remove(tmp_img_path)
