'''
Write your own version of Filelog here!

The Filelog Class opens up a file and adds log messages within.
Previous log messages, if any, should not be removed. Also, there
can be only one Filelog object at any time of this
program - that is, creating a second Filelog object should return
the exact same instance as the first one. (See testing code below.)

At least three methods are required:
info(msg), warning(msg), and error(msg).
'''

import logging
import os
import datetime
import time


class Singleton(type):
    def __init__(self, name, bases, mmbs):
        super(Singleton, self).__init__(name, bases, mmbs)
        self._instance = super(Singleton, self).__call__()

    def __call__(self, *args, **kw):
        return self._instance

class FileLog():
    def __init__(self, logger = None):
        if logger == None:
            logger = logging.getLogger("rando")
            handler = logging.FileHandler('main.log', mode='w')
            logger.addHandler(handler)
        self.logger = logger

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)




if __name__ == '__main__':
    '''
    STANDALONE TESTING:
    -------------------
    If you want to test this logging implementation separately. (ie. not relying
    on any other libraries) then you can run the following:

        $ python3 log.py

    This will run the file_log_test() code, which will verify whether or not
    you have a successful singleton implementation.
    '''
    file_log_test()
