# _____***** INIT CODE *****_____
# Copyright 2001-2016 by Vinay Sajip. All Rights Reserved.
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose and without fee is hereby granted,
# provided that the above copyright notice appear in all copies and that
# both that copyright notice and this permission notice appear in
# supporting documentation, and that the name of Vinay Sajip
# not be used in advertising or publicity pertaining to distribution
# of the software without specific, written prior permission.
# VINAY SAJIP DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING
# ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# VINAY SAJIP BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR
# ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER
# IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""
Logging package for Python. Based on PEP 282 and comments thereto in
comp.lang.python.

Copyright (C) 2001-2016 Vinay Sajip. All Rights Reserved.

To use, simply 'import logging' and log away!
"""

import sys, os, time, io, traceback, warnings, weakref, collections

from string import Template

__all__ = ['BASIC_FORMAT', 'BufferingFormatter', 'CRITICAL', 'DEBUG', 'ERROR',
           'FATAL', 'FileHandler', 'Filter', 'Formatter', 'Handler', 'INFO',
           'LogRecord', 'Logger', 'LoggerAdapter', 'NOTSET', 'NullHandler',
           'StreamHandler', 'WARN', 'WARNING', 'addLevelName', 'basicConfig',
           'captureWarnings', 'critical', 'debug', 'disable', 'error',
           'exception', 'fatal', 'getLevelName', 'getLogger', 'getLoggerClass',
           'info', 'log', 'makeLogRecord', 'setLoggerClass', 'warn', 'warning',
           'getLogRecordFactory', 'setLogRecordFactory', 'lastResort']

try:
    import threading
except ImportError: #pragma: no cover
    threading = None

__author__  = "Vinay Sajip <vinay_sajip@red-dove.com>"
__status__  = "production"
# The following module attributes are no longer updated.
__version__ = "0.5.1.2"
__date__    = "07 February 2010"

#---------------------------------------------------------------------------
#   Miscellaneous module data
#---------------------------------------------------------------------------

#
#_startTime is used as the base when calculating the relative time of events
#
_startTime = time.time()

#
#raiseExceptions is used to see if exceptions during handling should be
#propagated
#
raiseExceptions = True

#
# If you don't want threading information in the log, set this to zero
#
logThreads = True

#
# If you don't want multiprocessing information in the log, set this to zero
#
logMultiprocessing = True

#
# If you don't want process information in the log, set this to zero
#
logProcesses = True

#---------------------------------------------------------------------------
#   Level related stuff
#---------------------------------------------------------------------------
#
# Default levels and level names, these can be replaced with any positive set
# of values having corresponding names. There is a pseudo-level, NOTSET, which
# is only really there as a lower limit for user-defined levels. Handlers and
# loggers are initialized with NOTSET so that they will log all messages, even
# at user-defined levels.
#

CRITICAL = 50
FATAL = CRITICAL
ERROR = 40
WARNING = 30
WARN = WARNING
INFO = 20
DEBUG = 10
NOTSET = 0

_levelToName = {
    CRITICAL: 'CRITICAL',
    ERROR: 'ERROR',
    WARNING: 'WARNING',
    INFO: 'INFO',
    DEBUG: 'DEBUG',
    NOTSET: 'NOTSET',
}
_nameToLevel = {
    'CRITICAL': CRITICAL,
    'ERROR': ERROR,
    'WARN': WARNING,
    'WARNING': WARNING,
    'INFO': INFO,
    'DEBUG': DEBUG,
    'NOTSET': NOTSET,
}

def getLevelName(level):
    """
    Return the textual representation of logging level 'level'.

    If the level is one of the predefined levels (CRITICAL, ERROR, WARNING,
    INFO, DEBUG) then you get the corresponding string. If you have
    associated levels with names using addLevelName then the name you have
    associated with 'level' is returned.

    If a numeric value corresponding to one of the defined levels is passed
    in, the corresponding string representation is returned.

    Otherwise, the string "Level %s" % level is returned.
    """
    # See Issues #22386, #27937 and #29220 for why it's this way
    result = _levelToName.get(level)
    if result is not None:
        return result
    result = _nameToLevel.get(level)
    if result is not None:
        return result
    return "Level %s" % level

def addLevelName(level, levelName):
    """
    Associate 'levelName' with 'level'.

    This is used when converting levels to text during message formatting.
    """
    _acquireLock()
    try:    #unlikely to cause an exception, but you never know...
        _levelToName[level] = levelName
        _nameToLevel[levelName] = level
    finally:
        _releaseLock()

if hasattr(sys, '_getframe'):
    currentframe = lambda: sys._getframe(3)
else: #pragma: no cover
    def currentframe():
        """Return the frame object for the caller's stack frame."""
        try:
            raise Exception
        except Exception:
            return sys.exc_info()[2].tb_frame.f_back

#
# _srcfile is used when walking the stack to check when we've got the first
# caller stack frame, by skipping frames whose filename is that of this
# module's source. It therefore should contain the filename of this module's
# source file.
#
# Ordinarily we would use __file__ for this, but frozen modules don't always
# have __file__ set, for some reason (see Issue #21736). Thus, we get the
# filename from a handy code object from a function defined in this module.
# (There's no particular reason for picking addLevelName.)
#

_srcfile = os.path.normcase(addLevelName.__code__.co_filename)

# _srcfile is only used in conjunction with sys._getframe().
# To provide compatibility with older versions of Python, set _srcfile
# to None if _getframe() is not available; this value will prevent
# findCaller() from being called. You can also do this if you want to avoid
# the overhead of fetching caller information, even when _getframe() is
# available.
#if not hasattr(sys, '_getframe'):
#    _srcfile = None


def _checkLevel(level):
    if isinstance(level, int):
        rv = level
    elif str(level) == level:
        if level not in _nameToLevel:
            raise ValueError("Unknown level: %r" % level)
        rv = _nameToLevel[level]
    else:
        raise TypeError("Level not an integer or a valid string: %r" % level)
    return rv

#---------------------------------------------------------------------------
#   Thread-related stuff
#---------------------------------------------------------------------------

#
#_lock is used to serialize access to shared data structures in this module.
#This needs to be an RLock because fileConfig() creates and configures
#Handlers, and so might arbitrary user threads. Since Handler code updates the
#shared dictionary _handlers, it needs to acquire the lock. But if configuring,
#the lock would already have been acquired - so we need an RLock.
#The same argument applies to Loggers and Manager.loggerDict.
#
if threading:
    _lock = threading.RLock()
else: #pragma: no cover
    _lock = None


def _acquireLock():
    """
    Acquire the module-level lock for serializing access to shared data.

    This should be released with _releaseLock().
    """
    if _lock:
        _lock.acquire()

def _releaseLock():
    """
    Release the module-level lock acquired by calling _acquireLock().
    """
    if _lock:
        _lock.release()

#---------------------------------------------------------------------------
#   The logging record
#---------------------------------------------------------------------------

class LogRecord(object):
    """
    A LogRecord instance represents an event being logged.

    LogRecord instances are created every time something is logged. They
    contain all the information pertinent to the event being logged. The
    main information passed in is in msg and args, which are combined
    using str(msg) % args to create the message field of the record. The
    record also includes information such as when the record was created,
    the source line where the logging call was made, and any exception
    information to be logged.
    """
    def __init__(self, name, level, pathname, lineno,
                 msg, args, exc_info, func=None, sinfo=None, **kwargs):
        """
        Initialize a logging record with interesting information.
        """
        ct = time.time()
        self.name = name
        self.msg = msg
        #
        # The following statement allows passing of a dictionary as a sole
        # argument, so that you can do something like
        #  logging.debug("a %(a)d b %(b)s", {'a':1, 'b':2})
        # Suggested by Stefan Behnel.
        # Note that without the test for args[0], we get a problem because
        # during formatting, we test to see if the arg is present using
        # 'if self.args:'. If the event being logged is e.g. 'Value is %d'
        # and if the passed arg fails 'if self.args:' then no formatting
        # is done. For example, logger.warning('Value is %d', 0) would log
        # 'Value is %d' instead of 'Value is 0'.
        # For the use case of passing a dictionary, this should not be a
        # problem.
        # Issue #21172: a request was made to relax the isinstance check
        # to hasattr(args[0], '__getitem__'). However, the docs on string
        # formatting still seem to suggest a mapping object is required.
        # Thus, while not removing the isinstance check, it does now look
        # for collections.Mapping rather than, as before, dict.
        if (args and len(args) == 1 and isinstance(args[0], collections.Mapping)
            and args[0]):
            args = args[0]
        self.args = args
        self.levelname = getLevelName(level)
        self.levelno = level
        self.pathname = pathname
        try:
            self.filename = os.path.basename(pathname)
            self.module = os.path.splitext(self.filename)[0]
        except (TypeError, ValueError, AttributeError):
            self.filename = pathname
            self.module = "Unknown module"
        self.exc_info = exc_info
        self.exc_text = None      # used to cache the traceback text
        self.stack_info = sinfo
        self.lineno = lineno
        self.funcName = func
        self.created = ct
        self.msecs = (ct - int(ct)) * 1000
        self.relativeCreated = (self.created - _startTime) * 1000
        if logThreads and threading:
            self.thread = threading.get_ident()
            self.threadName = threading.current_thread().name
        else: # pragma: no cover
            self.thread = None
            self.threadName = None
        if not logMultiprocessing: # pragma: no cover
            self.processName = None
        else:
            self.processName = 'MainProcess'
            mp = sys.modules.get('multiprocessing')
            if mp is not None:
                # Errors may occur if multiprocessing has not finished loading
                # yet - e.g. if a custom import hook causes third-party code
                # to run when multiprocessing calls import. See issue 8200
                # for an example
                try:
                    self.processName = mp.current_process().name
                except Exception: #pragma: no cover
                    pass
        if logProcesses and hasattr(os, 'getpid'):
            self.process = os.getpid()
        else:
            self.process = None

    def __str__(self):
        return '<LogRecord: %s, %s, %s, %s, "%s">'%(self.name, self.levelno,
            self.pathname, self.lineno, self.msg)

    __repr__ = __str__

    def getMessage(self):
        """
        Return the message for this LogRecord.

        Return the message for this LogRecord after merging any user-supplied
        arguments with the message.
        """
        msg = str(self.msg)
        if self.args:
            msg = msg % self.args
        return msg

#
#   Determine which class to use when instantiating log records.
#
_logRecordFactory = LogRecord

def setLogRecordFactory(factory):
    """
    Set the factory to be used when instantiating a log record.

    :param factory: A callable which will be called to instantiate
    a log record.
    """
    global _logRecordFactory
    _logRecordFactory = factory

def getLogRecordFactory():
    """
    Return the factory to be used when instantiating a log record.
    """

    return _logRecordFactory

def makeLogRecord(dict):
    """
    Make a LogRecord whose attributes are defined by the specified dictionary,
    This function is useful for converting a logging event received over
    a socket connection (which is sent as a dictionary) into a LogRecord
    instance.
    """
    rv = _logRecordFactory(None, None, "", 0, "", (), None, None)
    rv.__dict__.update(dict)
    return rv

#---------------------------------------------------------------------------
#   Formatter classes and functions
#---------------------------------------------------------------------------

class PercentStyle(object):

    default_format = '%(message)s'
    asctime_format = '%(asctime)s'
    asctime_search = '%(asctime)'

    def __init__(self, fmt):
        self._fmt = fmt or self.default_format

    def usesTime(self):
        return self._fmt.find(self.asctime_search) >= 0

    def format(self, record):
        return self._fmt % record.__dict__

class StrFormatStyle(PercentStyle):
    default_format = '{message}'
    asctime_format = '{asctime}'
    asctime_search = '{asctime'

    def format(self, record):
        return self._fmt.format(**record.__dict__)


class StringTemplateStyle(PercentStyle):
    default_format = '${message}'
    asctime_format = '${asctime}'
    asctime_search = '${asctime}'

    def __init__(self, fmt):
        self._fmt = fmt or self.default_format
        self._tpl = Template(self._fmt)

    def usesTime(self):
        fmt = self._fmt
        return fmt.find('$asctime') >= 0 or fmt.find(self.asctime_format) >= 0

    def format(self, record):
        return self._tpl.substitute(**record.__dict__)

BASIC_FORMAT = "%(levelname)s:%(name)s:%(message)s"

_STYLES = {
    '%': (PercentStyle, BASIC_FORMAT),
    '{': (StrFormatStyle, '{levelname}:{name}:{message}'),
    '$': (StringTemplateStyle, '${levelname}:${name}:${message}'),
}

class Formatter(object):
    """
    Formatter instances are used to convert a LogRecord to text.

    Formatters need to know how a LogRecord is constructed. They are
    responsible for converting a LogRecord to (usually) a string which can
    be interpreted by either a human or an external system. The base Formatter
    allows a formatting string to be specified. If none is supplied, the
    default value of "%s(message)" is used.

    The Formatter can be initialized with a format string which makes use of
    knowledge of the LogRecord attributes - e.g. the default value mentioned
    above makes use of the fact that the user's message and arguments are pre-
    formatted into a LogRecord's message attribute. Currently, the useful
    attributes in a LogRecord are described by:

    %(name)s            Name of the logger (logging channel)
    %(levelno)s         Numeric logging level for the message (DEBUG, INFO,
                        WARNING, ERROR, CRITICAL)
    %(levelname)s       Text logging level for the message ("DEBUG", "INFO",
                        "WARNING", "ERROR", "CRITICAL")
    %(pathname)s        Full pathname of the source file where the logging
                        call was issued (if available)
    %(filename)s        Filename portion of pathname
    %(module)s          Module (name portion of filename)
    %(lineno)d          Source line number where the logging call was issued
                        (if available)
    %(funcName)s        Function name
    %(created)f         Time when the LogRecord was created (time.time()
                        return value)
    %(asctime)s         Textual time when the LogRecord was created
    %(msecs)d           Millisecond portion of the creation time
    %(relativeCreated)d Time in milliseconds when the LogRecord was created,
                        relative to the time the logging module was loaded
                        (typically at application startup time)
    %(thread)d          Thread ID (if available)
    %(threadName)s      Thread name (if available)
    %(process)d         Process ID (if available)
    %(message)s         The result of record.getMessage(), computed just as
                        the record is emitted
    """

    converter = time.localtime

    def __init__(self, fmt=None, datefmt=None, style='%'):
        """
        Initialize the formatter with specified format strings.

        Initialize the formatter either with the specified format string, or a
        default as described above. Allow for specialized date formatting with
        the optional datefmt argument (if omitted, you get the ISO8601 format).

        Use a style parameter of '%', '{' or '$' to specify that you want to
        use one of %-formatting, :meth:`str.format` (``{}``) formatting or
        :class:`string.Template` formatting in your format string.

        .. versionchanged:: 3.2
           Added the ``style`` parameter.
        """
        if style not in _STYLES:
            raise ValueError('Style must be one of: %s' % ','.join(
                             _STYLES.keys()))
        self._style = _STYLES[style][0](fmt)
        self._fmt = self._style._fmt
        self.datefmt = datefmt

    default_time_format = '%Y-%m-%d %H:%M:%S'
    default_msec_format = '%s,%03d'

    def formatTime(self, record, datefmt=None):
        """
        Return the creation time of the specified LogRecord as formatted text.

        This method should be called from format() by a formatter which
        wants to make use of a formatted time. This method can be overridden
        in formatters to provide for any specific requirement, but the
        basic behaviour is as follows: if datefmt (a string) is specified,
        it is used with time.strftime() to format the creation time of the
        record. Otherwise, the ISO8601 format is used. The resulting
        string is returned. This function uses a user-configurable function
        to convert the creation time to a tuple. By default, time.localtime()
        is used; to change this for a particular formatter instance, set the
        'converter' attribute to a function with the same signature as
        time.localtime() or time.gmtime(). To change it for all formatters,
        for example if you want all logging times to be shown in GMT,
        set the 'converter' attribute in the Formatter class.
        """
        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            t = time.strftime(self.default_time_format, ct)
            s = self.default_msec_format % (t, record.msecs)
        return s

    def formatException(self, ei):
        """
        Format and return the specified exception information as a string.

        This default implementation just uses
        traceback.print_exception()
        """
        sio = io.StringIO()
        tb = ei[2]
        # See issues #9427, #1553375. Commented out for now.
        #if getattr(self, 'fullstack', False):
        #    traceback.print_stack(tb.tb_frame.f_back, file=sio)
        traceback.print_exception(ei[0], ei[1], tb, None, sio)
        s = sio.getvalue()
        sio.close()
        if s[-1:] == "\n":
            s = s[:-1]
        return s

    def usesTime(self):
        """
        Check if the format uses the creation time of the record.
        """
        return self._style.usesTime()

    def formatMessage(self, record):
        return self._style.format(record)

    def formatStack(self, stack_info):
        """
        This method is provided as an extension point for specialized
        formatting of stack information.

        The input data is a string as returned from a call to
        :func:`traceback.print_stack`, but with the last trailing newline
        removed.

        The base implementation just returns the value passed in.
        """
        return stack_info

    def format(self, record):
        """
        Format the specified record as text.

        The record's attribute dictionary is used as the operand to a
        string formatting operation which yields the returned string.
        Before formatting the dictionary, a couple of preparatory steps
        are carried out. The message attribute of the record is computed
        using LogRecord.getMessage(). If the formatting string uses the
        time (as determined by a call to usesTime(), formatTime() is
        called to format the event time. If there is exception information,
        it is formatted using formatException() and appended to the message.
        """
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        s = self.formatMessage(record)
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + record.exc_text
        if record.stack_info:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + self.formatStack(record.stack_info)
        return s

#
#   The default formatter to use when no other is specified
#
_defaultFormatter = Formatter()

class BufferingFormatter(object):
    """
    A formatter suitable for formatting a number of records.
    """
    def __init__(self, linefmt=None):
        """
        Optionally specify a formatter which will be used to format each
        individual record.
        """
        if linefmt:
            self.linefmt = linefmt
        else:
            self.linefmt = _defaultFormatter

    def formatHeader(self, records):
        """
        Return the header string for the specified records.
        """
        return ""

    def formatFooter(self, records):
        """
        Return the footer string for the specified records.
        """
        return ""

    def format(self, records):
        """
        Format the specified records and return the result as a string.
        """
        rv = ""
        if len(records) > 0:
            rv = rv + self.formatHeader(records)
            for record in records:
                rv = rv + self.linefmt.format(record)
            rv = rv + self.formatFooter(records)
        return rv

#---------------------------------------------------------------------------
#   Filter classes and functions
#---------------------------------------------------------------------------

class Filter(object):
    """
    Filter instances are used to perform arbitrary filtering of LogRecords.

    Loggers and Handlers can optionally use Filter instances to filter
    records as desired. The base filter class only allows events which are
    below a certain point in the logger hierarchy. For example, a filter
    initialized with "A.B" will allow events logged by loggers "A.B",
    "A.B.C", "A.B.C.D", "A.B.D" etc. but not "A.BB", "B.A.B" etc. If
    initialized with the empty string, all events are passed.
    """
    def __init__(self, name=''):
        """
        Initialize a filter.

        Initialize with the name of the logger which, together with its
        children, will have its events allowed through the filter. If no
        name is specified, allow every event.
        """
        self.name = name
        self.nlen = len(name)

    def filter(self, record):
        """
        Determine if the specified record is to be logged.

        Is the specified record to be logged? Returns 0 for no, nonzero for
        yes. If deemed appropriate, the record may be modified in-place.
        """
        if self.nlen == 0:
            return True
        elif self.name == record.name:
            return True
        elif record.name.find(self.name, 0, self.nlen) != 0:
            return False
        return (record.name[self.nlen] == ".")

class Filterer(object):
    """
    A base class for loggers and handlers which allows them to share
    common code.
    """
    def __init__(self):
        """
        Initialize the list of filters to be an empty list.
        """
        self.filters = []

    def addFilter(self, filter):
        """
        Add the specified filter to this handler.
        """
        if not (filter in self.filters):
            self.filters.append(filter)

    def removeFilter(self, filter):
        """
        Remove the specified filter from this handler.
        """
        if filter in self.filters:
            self.filters.remove(filter)

    def filter(self, record):
        """
        Determine if a record is loggable by consulting all the filters.

        The default is to allow the record to be logged; any filter can veto
        this and the record is then dropped. Returns a zero value if a record
        is to be dropped, else non-zero.

        .. versionchanged:: 3.2

           Allow filters to be just callables.
        """
        rv = True
        for f in self.filters:
            if hasattr(f, 'filter'):
                result = f.filter(record)
            else:
                result = f(record) # assume callable - will raise if not
            if not result:
                rv = False
                break
        return rv

#---------------------------------------------------------------------------
#   Handler classes and functions
#---------------------------------------------------------------------------

_handlers = weakref.WeakValueDictionary()  #map of handler names to handlers
_handlerList = [] # added to allow handlers to be removed in reverse of order initialized

def _removeHandlerRef(wr):
    """
    Remove a handler reference from the internal cleanup list.
    """
    # This function can be called during module teardown, when globals are
    # set to None. It can also be called from another thread. So we need to
    # pre-emptively grab the necessary globals and check if they're None,
    # to prevent race conditions and failures during interpreter shutdown.
    acquire, release, handlers = _acquireLock, _releaseLock, _handlerList
    if acquire and release and handlers:
        acquire()
        try:
            if wr in handlers:
                handlers.remove(wr)
        finally:
            release()

def _addHandlerRef(handler):
    """
    Add a handler to the internal cleanup list using a weak reference.
    """
    _acquireLock()
    try:
        _handlerList.append(weakref.ref(handler, _removeHandlerRef))
    finally:
        _releaseLock()

class Handler(Filterer):
    """
    Handler instances dispatch logging events to specific destinations.

    The base handler class. Acts as a placeholder which defines the Handler
    interface. Handlers can optionally use Formatter instances to format
    records as desired. By default, no formatter is specified; in this case,
    the 'raw' message as determined by record.message is logged.
    """
    def __init__(self, level=NOTSET):
        """
        Initializes the instance - basically setting the formatter to None
        and the filter list to empty.
        """
        Filterer.__init__(self)
        self._name = None
        self.level = _checkLevel(level)
        self.formatter = None
        # Add the handler to the global _handlerList (for cleanup on shutdown)
        _addHandlerRef(self)
        self.createLock()

    def get_name(self):
        return self._name

    def set_name(self, name):
        _acquireLock()
        try:
            if self._name in _handlers:
                del _handlers[self._name]
            self._name = name
            if name:
                _handlers[name] = self
        finally:
            _releaseLock()

    name = property(get_name, set_name)

    def createLock(self):
        """
        Acquire a thread lock for serializing access to the underlying I/O.
        """
        if threading:
            self.lock = threading.RLock()
        else: #pragma: no cover
            self.lock = None

    def acquire(self):
        """
        Acquire the I/O thread lock.
        """
        if self.lock:
            self.lock.acquire()

    def release(self):
        """
        Release the I/O thread lock.
        """
        if self.lock:
            self.lock.release()

    def setLevel(self, level):
        """
        Set the logging level of this handler.  level must be an int or a str.
        """
        self.level = _checkLevel(level)

    def format(self, record):
        """
        Format the specified record.

        If a formatter is set, use it. Otherwise, use the default formatter
        for the module.
        """
        if self.formatter:
            fmt = self.formatter
        else:
            fmt = _defaultFormatter
        return fmt.format(record)

    def emit(self, record):
        """
        Do whatever it takes to actually log the specified logging record.

        This version is intended to be implemented by subclasses and so
        raises a NotImplementedError.
        """
        raise NotImplementedError('emit must be implemented '
                                  'by Handler subclasses')

    def handle(self, record):
        """
        Conditionally emit the specified logging record.

        Emission depends on filters which may have been added to the handler.
        Wrap the actual emission of the record with acquisition/release of
        the I/O thread lock. Returns whether the filter passed the record for
        emission.
        """
        rv = self.filter(record)
        if rv:
            self.acquire()
            try:
                self.emit(record)
            finally:
                self.release()
        return rv

    def setFormatter(self, fmt):
        """
        Set the formatter for this handler.
        """
        self.formatter = fmt

    def flush(self):
        """
        Ensure all logging output has been flushed.

        This version does nothing and is intended to be implemented by
        subclasses.
        """
        pass

    def close(self):
        """
        Tidy up any resources used by the handler.

        This version removes the handler from an internal map of handlers,
        _handlers, which is used for handler lookup by name. Subclasses
        should ensure that this gets called from overridden close()
        methods.
        """
        #get the module data lock, as we're updating a shared structure.
        _acquireLock()
        try:    #unlikely to raise an exception, but you never know...
            if self._name and self._name in _handlers:
                del _handlers[self._name]
        finally:
            _releaseLock()

    def handleError(self, record):
        """
        Handle errors which occur during an emit() call.

        This method should be called from handlers when an exception is
        encountered during an emit() call. If raiseExceptions is false,
        exceptions get silently ignored. This is what is mostly wanted
        for a logging system - most users will not care about errors in
        the logging system, they are more interested in application errors.
        You could, however, replace this with a custom handler if you wish.
        The record which was being processed is passed in to this method.
        """
        if raiseExceptions and sys.stderr:  # see issue 13807
            t, v, tb = sys.exc_info()
            try:
                sys.stderr.write('--- Logging error ---\n')
                traceback.print_exception(t, v, tb, None, sys.stderr)
                sys.stderr.write('Call stack:\n')
                # Walk the stack frame up until we're out of logging,
                # so as to print the calling context.
                frame = tb.tb_frame
                while (frame and os.path.dirname(frame.f_code.co_filename) ==
                       __path__[0]):
                    frame = frame.f_back
                if frame:
                    traceback.print_stack(frame, file=sys.stderr)
                else:
                    # couldn't find the right stack frame, for some reason
                    sys.stderr.write('Logged from file %s, line %s\n' % (
                                     record.filename, record.lineno))
                # Issue 18671: output logging message and arguments
                try:
                    sys.stderr.write('Message: %r\n'
                                     'Arguments: %s\n' % (record.msg,
                                                          record.args))
                except Exception:
                    sys.stderr.write('Unable to print the message and arguments'
                                     ' - possible formatting error.\nUse the'
                                     ' traceback above to help find the error.\n'
                                    )
            except OSError: #pragma: no cover
                pass    # see issue 5971
            finally:
                del t, v, tb

class StreamHandler(Handler):
    """
    A handler class which writes logging records, appropriately formatted,
    to a stream. Note that this class does not close the stream, as
    sys.stdout or sys.stderr may be used.
    """

    terminator = '\n'

    def __init__(self, stream=None):
        """
        Initialize the handler.

        If stream is not specified, sys.stderr is used.
        """
        Handler.__init__(self)
        if stream is None:
            stream = sys.stderr
        self.stream = stream

    def flush(self):
        """
        Flushes the stream.
        """
        self.acquire()
        try:
            if self.stream and hasattr(self.stream, "flush"):
                self.stream.flush()
        finally:
            self.release()

    def emit(self, record):
        """
        Emit a record.

        If a formatter is specified, it is used to format the record.
        The record is then written to the stream with a trailing newline.  If
        exception information is present, it is formatted using
        traceback.print_exception and appended to the stream.  If the stream
        has an 'encoding' attribute, it is used to determine how to do the
        output to the stream.
        """
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg)
            stream.write(self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

class FileHandler(StreamHandler):
    """
    A handler class which writes formatted logging records to disk files.
    """
    def __init__(self, filename, mode='a', encoding=None, delay=False):
        """
        Open the specified file and use it as the stream for logging.
        """
        #keep the absolute path, otherwise derived classes which use this
        #may come a cropper when the current directory changes
        self.baseFilename = os.path.abspath(filename)
        self.mode = mode
        self.encoding = encoding
        self.delay = delay
        if delay:
            #We don't open the stream, but we still need to call the
            #Handler constructor to set level, formatter, lock etc.
            Handler.__init__(self)
            self.stream = None
        else:
            StreamHandler.__init__(self, self._open())

    def close(self):
        """
        Closes the stream.
        """
        self.acquire()
        try:
            try:
                if self.stream:
                    try:
                        self.flush()
                    finally:
                        stream = self.stream
                        self.stream = None
                        if hasattr(stream, "close"):
                            stream.close()
            finally:
                # Issue #19523: call unconditionally to
                # prevent a handler leak when delay is set
                StreamHandler.close(self)
        finally:
            self.release()

    def _open(self):
        """
        Open the current base file with the (original) mode and encoding.
        Return the resulting stream.
        """
        return open(self.baseFilename, self.mode, encoding=self.encoding)

    def emit(self, record):
        """
        Emit a record.

        If the stream was not opened because 'delay' was specified in the
        constructor, open it before calling the superclass's emit.
        """
        if self.stream is None:
            self.stream = self._open()
        StreamHandler.emit(self, record)

class _StderrHandler(StreamHandler):
    """
    This class is like a StreamHandler using sys.stderr, but always uses
    whatever sys.stderr is currently set to rather than the value of
    sys.stderr at handler construction time.
    """
    def __init__(self, level=NOTSET):
        """
        Initialize the handler.
        """
        Handler.__init__(self, level)

    @property
    def stream(self):
        return sys.stderr


_defaultLastResort = _StderrHandler(WARNING)
lastResort = _defaultLastResort

#---------------------------------------------------------------------------
#   Manager classes and functions
#---------------------------------------------------------------------------

class PlaceHolder(object):
    """
    PlaceHolder instances are used in the Manager logger hierarchy to take
    the place of nodes for which no loggers have been defined. This class is
    intended for internal use only and not as part of the public API.
    """
    def __init__(self, alogger):
        """
        Initialize with the specified logger being a child of this placeholder.
        """
        self.loggerMap = { alogger : None }

    def append(self, alogger):
        """
        Add the specified logger as a child of this placeholder.
        """
        if alogger not in self.loggerMap:
            self.loggerMap[alogger] = None

#
#   Determine which class to use when instantiating loggers.
#

def setLoggerClass(klass):
    """
    Set the class to be used when instantiating a logger. The class should
    define __init__() such that only a name argument is required, and the
    __init__() should call Logger.__init__()
    """
    if klass != Logger:
        if not issubclass(klass, Logger):
            raise TypeError("logger not derived from logging.Logger: "
                            + klass.__name__)
    global _loggerClass
    _loggerClass = klass

def getLoggerClass():
    """
    Return the class to be used when instantiating a logger.
    """
    return _loggerClass

class Manager(object):
    """
    There is [under normal circumstances] just one Manager instance, which
    holds the hierarchy of loggers.
    """
    def __init__(self, rootnode):
        """
        Initialize the manager with the root node of the logger hierarchy.
        """
        self.root = rootnode
        self.disable = 0
        self.emittedNoHandlerWarning = False
        self.loggerDict = {}
        self.loggerClass = None
        self.logRecordFactory = None

    def getLogger(self, name):
        """
        Get a logger with the specified name (channel name), creating it
        if it doesn't yet exist. This name is a dot-separated hierarchical
        name, such as "a", "a.b", "a.b.c" or similar.

        If a PlaceHolder existed for the specified name [i.e. the logger
        didn't exist but a child of it did], replace it with the created
        logger and fix up the parent/child references which pointed to the
        placeholder to now point to the logger.
        """
        rv = None
        if not isinstance(name, str):
            raise TypeError('A logger name must be a string')
        _acquireLock()
        try:
            if name in self.loggerDict:
                rv = self.loggerDict[name]
                if isinstance(rv, PlaceHolder):
                    ph = rv
                    rv = (self.loggerClass or _loggerClass)(name)
                    rv.manager = self
                    self.loggerDict[name] = rv
                    self._fixupChildren(ph, rv)
                    self._fixupParents(rv)
            else:
                rv = (self.loggerClass or _loggerClass)(name)
                rv.manager = self
                self.loggerDict[name] = rv
                self._fixupParents(rv)
        finally:
            _releaseLock()
        return rv

    def setLoggerClass(self, klass):
        """
        Set the class to be used when instantiating a logger with this Manager.
        """
        if klass != Logger:
            if not issubclass(klass, Logger):
                raise TypeError("logger not derived from logging.Logger: "
                                + klass.__name__)
        self.loggerClass = klass

    def setLogRecordFactory(self, factory):
        """
        Set the factory to be used when instantiating a log record with this
        Manager.
        """
        self.logRecordFactory = factory

    def _fixupParents(self, alogger):
        """
        Ensure that there are either loggers or placeholders all the way
        from the specified logger to the root of the logger hierarchy.
        """
        name = alogger.name
        i = name.rfind(".")
        rv = None
        while (i > 0) and not rv:
            substr = name[:i]
            if substr not in self.loggerDict:
                self.loggerDict[substr] = PlaceHolder(alogger)
            else:
                obj = self.loggerDict[substr]
                if isinstance(obj, Logger):
                    rv = obj
                else:
                    assert isinstance(obj, PlaceHolder)
                    obj.append(alogger)
            i = name.rfind(".", 0, i - 1)
        if not rv:
            rv = self.root
        alogger.parent = rv

    def _fixupChildren(self, ph, alogger):
        """
        Ensure that children of the placeholder ph are connected to the
        specified logger.
        """
        name = alogger.name
        namelen = len(name)
        for c in ph.loggerMap.keys():
            #The if means ... if not c.parent.name.startswith(nm)
            if c.parent.name[:namelen] != name:
                alogger.parent = c.parent
                c.parent = alogger

#---------------------------------------------------------------------------
#   Logger classes and functions
#---------------------------------------------------------------------------

class Logger(Filterer):
    """
    Instances of the Logger class represent a single logging channel. A
    "logging channel" indicates an area of an application. Exactly how an
    "area" is defined is up to the application developer. Since an
    application can have any number of areas, logging channels are identified
    by a unique string. Application areas can be nested (e.g. an area
    of "input processing" might include sub-areas "read CSV files", "read
    XLS files" and "read Gnumeric files"). To cater for this natural nesting,
    channel names are organized into a namespace hierarchy where levels are
    separated by periods, much like the Java or Python package namespace. So
    in the instance given above, channel names might be "input" for the upper
    level, and "input.csv", "input.xls" and "input.gnu" for the sub-levels.
    There is no arbitrary limit to the depth of nesting.
    """
    def __init__(self, name, level=NOTSET):
        """
        Initialize the logger with a name and an optional level.
        """
        Filterer.__init__(self)
        self.name = name
        self.level = _checkLevel(level)
        self.parent = None
        self.propagate = True
        self.handlers = []
        self.disabled = False

    def setLevel(self, level):
        """
        Set the logging level of this logger.  level must be an int or a str.
        """
        self.level = _checkLevel(level)

    def debug(self, msg, *args, **kwargs):
        """
        Log 'msg % args' with severity 'DEBUG'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.debug("Houston, we have a %s", "thorny problem", exc_info=1)
        """
        if self.isEnabledFor(DEBUG):
            self._log(DEBUG, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """
        Log 'msg % args' with severity 'INFO'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.info("Houston, we have a %s", "interesting problem", exc_info=1)
        """
        if self.isEnabledFor(INFO):
            self._log(INFO, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """
        Log 'msg % args' with severity 'WARNING'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.warning("Houston, we have a %s", "bit of a problem", exc_info=1)
        """
        if self.isEnabledFor(WARNING):
            self._log(WARNING, msg, args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        warnings.warn("The 'warn' method is deprecated, "
            "use 'warning' instead", DeprecationWarning, 2)
        self.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """
        Log 'msg % args' with severity 'ERROR'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.error("Houston, we have a %s", "major problem", exc_info=1)
        """
        if self.isEnabledFor(ERROR):
            self._log(ERROR, msg, args, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        """
        Convenience method for logging an ERROR with exception information.
        """
        self.error(msg, *args, exc_info=exc_info, **kwargs)

    def critical(self, msg, *args, **kwargs):
        """
        Log 'msg % args' with severity 'CRITICAL'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.critical("Houston, we have a %s", "major disaster", exc_info=1)
        """
        if self.isEnabledFor(CRITICAL):
            self._log(CRITICAL, msg, args, **kwargs)

    fatal = critical

    def log(self, level, msg, *args, **kwargs):
        """
        Log 'msg % args' with the integer severity 'level'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.log(level, "We have a %s", "mysterious problem", exc_info=1)
        """
        if not isinstance(level, int):
            if raiseExceptions:
                raise TypeError("level must be an integer")
            else:
                return
        if self.isEnabledFor(level):
            self._log(level, msg, args, **kwargs)

    def findCaller(self, stack_info=False):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        f = currentframe()
        #On some versions of IronPython, currentframe() returns None if
        #IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)", None
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile:
                f = f.f_back
                continue
            sinfo = None
            if stack_info:
                sio = io.StringIO()
                sio.write('Stack (most recent call last):\n')
                traceback.print_stack(f, file=sio)
                sinfo = sio.getvalue()
                if sinfo[-1] == '\n':
                    sinfo = sinfo[:-1]
                sio.close()
            rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
            break
        return rv

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None):
        """
        A factory method which can be overridden in subclasses to create
        specialized LogRecords.
        """
        rv = _logRecordFactory(name, level, fn, lno, msg, args, exc_info, func,
                             sinfo)
        if extra is not None:
            for key in extra:
                if (key in ["message", "asctime"]) or (key in rv.__dict__):
                    raise KeyError("Attempt to overwrite %r in LogRecord" % key)
                rv.__dict__[key] = extra[key]
        return rv

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False):
        """
        Low-level logging routine which creates a LogRecord and then calls
        all the handlers of this logger to handle the record.
        """
        sinfo = None
        if _srcfile:
            #IronPython doesn't track Python frames, so findCaller raises an
            #exception on some versions of IronPython. We trap it here so that
            #IronPython can use logging.
            try:
                fn, lno, func, sinfo = self.findCaller(stack_info)
            except ValueError: # pragma: no cover
                fn, lno, func = "(unknown file)", 0, "(unknown function)"
        else: # pragma: no cover
            fn, lno, func = "(unknown file)", 0, "(unknown function)"
        if exc_info:
            if isinstance(exc_info, BaseException):
                exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
            elif not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()
        record = self.makeRecord(self.name, level, fn, lno, msg, args,
                                 exc_info, func, extra, sinfo)
        self.handle(record)

    def handle(self, record):
        """
        Call the handlers for the specified record.

        This method is used for unpickled records received from a socket, as
        well as those created locally. Logger-level filtering is applied.
        """
        if (not self.disabled) and self.filter(record):
            self.callHandlers(record)

    def addHandler(self, hdlr):
        """
        Add the specified handler to this logger.
        """
        _acquireLock()
        try:
            if not (hdlr in self.handlers):
                self.handlers.append(hdlr)
        finally:
            _releaseLock()

    def removeHandler(self, hdlr):
        """
        Remove the specified handler from this logger.
        """
        _acquireLock()
        try:
            if hdlr in self.handlers:
                self.handlers.remove(hdlr)
        finally:
            _releaseLock()

    def hasHandlers(self):
        """
        See if this logger has any handlers configured.

        Loop through all handlers for this logger and its parents in the
        logger hierarchy. Return True if a handler was found, else False.
        Stop searching up the hierarchy whenever a logger with the "propagate"
        attribute set to zero is found - that will be the last logger which
        is checked for the existence of handlers.
        """
        c = self
        rv = False
        while c:
            if c.handlers:
                rv = True
                break
            if not c.propagate:
                break
            else:
                c = c.parent
        return rv

    def callHandlers(self, record):
        """
        Pass a record to all relevant handlers.

        Loop through all handlers for this logger and its parents in the
        logger hierarchy. If no handler was found, output a one-off error
        message to sys.stderr. Stop searching up the hierarchy whenever a
        logger with the "propagate" attribute set to zero is found - that
        will be the last logger whose handlers are called.
        """
        c = self
        found = 0
        while c:
            for hdlr in c.handlers:
                found = found + 1
                if record.levelno >= hdlr.level:
                    hdlr.handle(record)
            if not c.propagate:
                c = None    #break out
            else:
                c = c.parent
        if (found == 0):
            if lastResort:
                if record.levelno >= lastResort.level:
                    lastResort.handle(record)
            elif raiseExceptions and not self.manager.emittedNoHandlerWarning:
                sys.stderr.write("No handlers could be found for logger"
                                 " \"%s\"\n" % self.name)
                self.manager.emittedNoHandlerWarning = True

    def getEffectiveLevel(self):
        """
        Get the effective level for this logger.

        Loop through this logger and its parents in the logger hierarchy,
        looking for a non-zero logging level. Return the first one found.
        """
        logger = self
        while logger:
            if logger.level:
                return logger.level
            logger = logger.parent
        return NOTSET

    def isEnabledFor(self, level):
        """
        Is this logger enabled for level 'level'?
        """
        if self.manager.disable >= level:
            return False
        return level >= self.getEffectiveLevel()

    def getChild(self, suffix):
        """
        Get a logger which is a descendant to this one.

        This is a convenience method, such that

        logging.getLogger('abc').getChild('def.ghi')

        is the same as

        logging.getLogger('abc.def.ghi')

        It's useful, for example, when the parent logger is named using
        __name__ rather than a literal string.
        """
        if self.root is not self:
            suffix = '.'.join((self.name, suffix))
        return self.manager.getLogger(suffix)

class RootLogger(Logger):
    """
    A root logger is not that different to any other logger, except that
    it must have a logging level and there is only one instance of it in
    the hierarchy.
    """
    def __init__(self, level):
        """
        Initialize the logger with the name "root".
        """
        Logger.__init__(self, "root", level)

_loggerClass = Logger

class LoggerAdapter(object):
    """
    An adapter for loggers which makes it easier to specify contextual
    information in logging output.
    """

    def __init__(self, logger, extra):
        """
        Initialize the adapter with a logger and a dict-like object which
        provides contextual information. This constructor signature allows
        easy stacking of LoggerAdapters, if so desired.

        You can effectively pass keyword arguments as shown in the
        following example:

        adapter = LoggerAdapter(someLogger, dict(p1=v1, p2="v2"))
        """
        self.logger = logger
        self.extra = extra

    def process(self, msg, kwargs):
        """
        Process the logging message and keyword arguments passed in to
        a logging call to insert contextual information. You can either
        manipulate the message itself, the keyword args or both. Return
        the message and kwargs modified (or not) to suit your needs.

        Normally, you'll only need to override this one method in a
        LoggerAdapter subclass for your specific needs.
        """
        kwargs["extra"] = self.extra
        return msg, kwargs

    #
    # Boilerplate convenience methods
    #
    def debug(self, msg, *args, **kwargs):
        """
        Delegate a debug call to the underlying logger.
        """
        self.log(DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """
        Delegate an info call to the underlying logger.
        """
        self.log(INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """
        Delegate a warning call to the underlying logger.
        """
        self.log(WARNING, msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        warnings.warn("The 'warn' method is deprecated, "
            "use 'warning' instead", DeprecationWarning, 2)
        self.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """
        Delegate an error call to the underlying logger.
        """
        self.log(ERROR, msg, *args, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        """
        Delegate an exception call to the underlying logger.
        """
        self.log(ERROR, msg, *args, exc_info=exc_info, **kwargs)

    def critical(self, msg, *args, **kwargs):
        """
        Delegate a critical call to the underlying logger.
        """
        self.log(CRITICAL, msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        """
        Delegate a log call to the underlying logger, after adding
        contextual information from this adapter instance.
        """
        if self.isEnabledFor(level):
            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, msg, args, **kwargs)

    def isEnabledFor(self, level):
        """
        Is this logger enabled for level 'level'?
        """
        if self.logger.manager.disable >= level:
            return False
        return level >= self.getEffectiveLevel()

    def setLevel(self, level):
        """
        Set the specified level on the underlying logger.
        """
        self.logger.setLevel(level)

    def getEffectiveLevel(self):
        """
        Get the effective level for the underlying logger.
        """
        return self.logger.getEffectiveLevel()

    def hasHandlers(self):
        """
        See if the underlying logger has any handlers.
        """
        return self.logger.hasHandlers()

root = RootLogger(WARNING)
Logger.root = root
Logger.manager = Manager(Logger.root)

#---------------------------------------------------------------------------
# Configuration classes and functions
#---------------------------------------------------------------------------

def basicConfig(**kwargs):
    """
    Do basic configuration for the logging system.

    This function does nothing if the root logger already has handlers
    configured. It is a convenience method intended for use by simple scripts
    to do one-shot configuration of the logging package.

    The default behaviour is to create a StreamHandler which writes to
    sys.stderr, set a formatter using the BASIC_FORMAT format string, and
    add the handler to the root logger.

    A number of optional keyword arguments may be specified, which can alter
    the default behaviour.

    filename  Specifies that a FileHandler be created, using the specified
              filename, rather than a StreamHandler.
    filemode  Specifies the mode to open the file, if filename is specified
              (if filemode is unspecified, it defaults to 'a').
    format    Use the specified format string for the handler.
    datefmt   Use the specified date/time format.
    style     If a format string is specified, use this to specify the
              type of format string (possible values '%', '{', '$', for
              %-formatting, :meth:`str.format` and :class:`string.Template`
              - defaults to '%').
    level     Set the root logger level to the specified level.
    stream    Use the specified stream to initialize the StreamHandler. Note
              that this argument is incompatible with 'filename' - if both
              are present, 'stream' is ignored.
    handlers  If specified, this should be an iterable of already created
              handlers, which will be added to the root handler. Any handler
              in the list which does not have a formatter assigned will be
              assigned the formatter created in this function.

    Note that you could specify a stream created using open(filename, mode)
    rather than passing the filename and mode in. However, it should be
    remembered that StreamHandler does not close its stream (since it may be
    using sys.stdout or sys.stderr), whereas FileHandler closes its stream
    when the handler is closed.

    .. versionchanged:: 3.2
       Added the ``style`` parameter.

    .. versionchanged:: 3.3
       Added the ``handlers`` parameter. A ``ValueError`` is now thrown for
       incompatible arguments (e.g. ``handlers`` specified together with
       ``filename``/``filemode``, or ``filename``/``filemode`` specified
       together with ``stream``, or ``handlers`` specified together with
       ``stream``.
    """
    # Add thread safety in case someone mistakenly calls
    # basicConfig() from multiple threads
    _acquireLock()
    try:
        if len(root.handlers) == 0:
            handlers = kwargs.pop("handlers", None)
            if handlers is None:
                if "stream" in kwargs and "filename" in kwargs:
                    raise ValueError("'stream' and 'filename' should not be "
                                     "specified together")
            else:
                if "stream" in kwargs or "filename" in kwargs:
                    raise ValueError("'stream' or 'filename' should not be "
                                     "specified together with 'handlers'")
            if handlers is None:
                filename = kwargs.pop("filename", None)
                mode = kwargs.pop("filemode", 'a')
                if filename:
                    h = FileHandler(filename, mode)
                else:
                    stream = kwargs.pop("stream", None)
                    h = StreamHandler(stream)
                handlers = [h]
            dfs = kwargs.pop("datefmt", None)
            style = kwargs.pop("style", '%')
            if style not in _STYLES:
                raise ValueError('Style must be one of: %s' % ','.join(
                                 _STYLES.keys()))
            fs = kwargs.pop("format", _STYLES[style][1])
            fmt = Formatter(fs, dfs, style)
            for h in handlers:
                if h.formatter is None:
                    h.setFormatter(fmt)
                root.addHandler(h)
            level = kwargs.pop("level", None)
            if level is not None:
                root.setLevel(level)
            if kwargs:
                keys = ', '.join(kwargs.keys())
                raise ValueError('Unrecognised argument(s): %s' % keys)
    finally:
        _releaseLock()

#---------------------------------------------------------------------------
# Utility functions at module level.
# Basically delegate everything to the root logger.
#---------------------------------------------------------------------------

def getLogger(name=None):
    """
    Return a logger with the specified name, creating it if necessary.

    If no name is specified, return the root logger.
    """
    if name:
        return Logger.manager.getLogger(name)
    else:
        return root

def critical(msg, *args, **kwargs):
    """
    Log a message with severity 'CRITICAL' on the root logger. If the logger
    has no handlers, call basicConfig() to add a console handler with a
    pre-defined format.
    """
    if len(root.handlers) == 0:
        basicConfig()
    root.critical(msg, *args, **kwargs)

fatal = critical

def error(msg, *args, **kwargs):
    """
    Log a message with severity 'ERROR' on the root logger. If the logger has
    no handlers, call basicConfig() to add a console handler with a pre-defined
    format.
    """
    if len(root.handlers) == 0:
        basicConfig()
    root.error(msg, *args, **kwargs)

def exception(msg, *args, exc_info=True, **kwargs):
    """
    Log a message with severity 'ERROR' on the root logger, with exception
    information. If the logger has no handlers, basicConfig() is called to add
    a console handler with a pre-defined format.
    """
    error(msg, *args, exc_info=exc_info, **kwargs)

def warning(msg, *args, **kwargs):
    """
    Log a message with severity 'WARNING' on the root logger. If the logger has
    no handlers, call basicConfig() to add a console handler with a pre-defined
    format.
    """
    if len(root.handlers) == 0:
        basicConfig()
    root.warning(msg, *args, **kwargs)

def warn(msg, *args, **kwargs):
    warnings.warn("The 'warn' function is deprecated, "
        "use 'warning' instead", DeprecationWarning, 2)
    warning(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    """
    Log a message with severity 'INFO' on the root logger. If the logger has
    no handlers, call basicConfig() to add a console handler with a pre-defined
    format.
    """
    if len(root.handlers) == 0:
        basicConfig()
    root.info(msg, *args, **kwargs)

def debug(msg, *args, **kwargs):
    """
    Log a message with severity 'DEBUG' on the root logger. If the logger has
    no handlers, call basicConfig() to add a console handler with a pre-defined
    format.
    """
    if len(root.handlers) == 0:
        basicConfig()
    root.debug(msg, *args, **kwargs)

def log(level, msg, *args, **kwargs):
    """
    Log 'msg % args' with the integer severity 'level' on the root logger. If
    the logger has no handlers, call basicConfig() to add a console handler
    with a pre-defined format.
    """
    if len(root.handlers) == 0:
        basicConfig()
    root.log(level, msg, *args, **kwargs)

def disable(level):
    """
    Disable all logging calls of severity 'level' and below.
    """
    root.manager.disable = level

def shutdown(handlerList=_handlerList):
    """
    Perform any cleanup actions in the logging system (e.g. flushing
    buffers).

    Should be called at application exit.
    """
    for wr in reversed(handlerList[:]):
        #errors might occur, for example, if files are locked
        #we just ignore them if raiseExceptions is not set
        try:
            h = wr()
            if h:
                try:
                    h.acquire()
                    h.flush()
                    h.close()
                except (OSError, ValueError):
                    # Ignore errors which might be caused
                    # because handlers have been closed but
                    # references to them are still around at
                    # application exit.
                    pass
                finally:
                    h.release()
        except: # ignore everything, as we're shutting down
            if raiseExceptions:
                raise
            #else, swallow

#Let's try and shutdown automatically on application exit...
import atexit
atexit.register(shutdown)

# Null handler

class NullHandler(Handler):
    """
    This handler does nothing. It's intended to be used to avoid the
    "No handlers could be found for logger XXX" one-off warning. This is
    important for library code, which may contain code to log events. If a user
    of the library does not configure logging, the one-off warning might be
    produced; to avoid this, the library developer simply needs to instantiate
    a NullHandler and add it to the top-level logger of the library module or
    package.
    """
    def handle(self, record):
        """Stub."""

    def emit(self, record):
        """Stub."""

    def createLock(self):
        self.lock = None

# Warnings integration

_warnings_showwarning = None

def _showwarning(message, category, filename, lineno, file=None, line=None):
    """
    Implementation of showwarnings which redirects to logging, which will first
    check to see if the file parameter is None. If a file is specified, it will
    delegate to the original warnings implementation of showwarning. Otherwise,
    it will call warnings.formatwarning and will log the resulting string to a
    warnings logger named "py.warnings" with level logging.WARNING.
    """
    if file is not None:
        if _warnings_showwarning is not None:
            _warnings_showwarning(message, category, filename, lineno, file, line)
    else:
        s = warnings.formatwarning(message, category, filename, lineno, line)
        logger = getLogger("py.warnings")
        if not logger.handlers:
            logger.addHandler(NullHandler())
        logger.warning("%s", s)

def captureWarnings(capture):
    """
    If capture is true, redirect all warnings to the logging package.
    If capture is False, ensure that warnings are not redirected to logging
    but to their original destinations.
    """
    global _warnings_showwarning
    if capture:
        if _warnings_showwarning is None:
            _warnings_showwarning = warnings.showwarning
            warnings.showwarning = _showwarning
    else:
        if _warnings_showwarning is not None:
            warnings.showwarning = _warnings_showwarning
            _warnings_showwarning = None

# _____***** LOGGING CODE *****_____


# Copyright 2001-2016 by Vinay Sajip. All Rights Reserved.
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose and without fee is hereby granted,
# provided that the above copyright notice appear in all copies and that
# both that copyright notice and this permission notice appear in
# supporting documentation, and that the name of Vinay Sajip
# not be used in advertising or publicity pertaining to distribution
# of the software without specific, written prior permission.
# VINAY SAJIP DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING
# ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# VINAY SAJIP BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR
# ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER
# IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""
Additional handlers for the logging package for Python. The core package is
based on PEP 282 and comments thereto in comp.lang.python.

Copyright (C) 2001-2016 Vinay Sajip. All Rights Reserved.

To use, simply 'import Handlers' and log away!
"""

import logging, socket, os, pickle, struct, time, re
from stat import ST_DEV, ST_INO, ST_MTIME
import queue
try:
    import threading
except ImportError: #pragma: no cover
    threading = None

#
# Some constants...
#

DEFAULT_TCP_LOGGING_PORT    = 9020
DEFAULT_UDP_LOGGING_PORT    = 9021
DEFAULT_HTTP_LOGGING_PORT   = 9022
DEFAULT_SOAP_LOGGING_PORT   = 9023
SYSLOG_UDP_PORT             = 514
SYSLOG_TCP_PORT             = 514

_MIDNIGHT = 24 * 60 * 60  # number of seconds in a day

class BaseRotatingHandler(logging.FileHandler):
    """
    Base class for handlers that rotate log files at a certain point.
    Not meant to be instantiated directly.  Instead, use RotatingFileHandler
    or TimedRotatingFileHandler.
    """
    def __init__(self, filename, mode, encoding=None, delay=False):
        """
        Use the specified filename for streamed logging
        """
        logging.FileHandler.__init__(self, filename, mode, encoding, delay)
        self.mode = mode
        self.encoding = encoding
        self.namer = None
        self.rotator = None

    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in doRollover().
        """
        try:
            if self.shouldRollover(record):
                self.doRollover()
            logging.FileHandler.emit(self, record)
        except Exception:
            self.handleError(record)

    def rotation_filename(self, default_name):
        """
        Modify the filename of a log file when rotating.

        This is provided so that a custom filename can be provided.

        The default implementation calls the 'namer' attribute of the
        handler, if it's callable, passing the default name to
        it. If the attribute isn't callable (the default is None), the name
        is returned unchanged.

        :param default_name: The default name for the log file.
        """
        if not callable(self.namer):
            result = default_name
        else:
            result = self.namer(default_name)
        return result

    def rotate(self, source, dest):
        """
        When rotating, rotate the current log.

        The default implementation calls the 'rotator' attribute of the
        handler, if it's callable, passing the source and dest arguments to
        it. If the attribute isn't callable (the default is None), the source
        is simply renamed to the destination.

        :param source: The source filename. This is normally the base
                       filename, e.g. 'test.log'
        :param dest:   The destination filename. This is normally
                       what the source is rotated to, e.g. 'test.log.1'.
        """
        if not callable(self.rotator):
            # Issue 18940: A file may not have been created if delay is True.
            if os.path.exists(source):
                os.rename(source, dest)
        else:
            self.rotator(source, dest)

class RotatingFileHandler(BaseRotatingHandler):
    """
    Handler for logging to a set of files, which switches from one file
    to the next when the current file reaches a certain size.
    """
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False):
        """
        Open the specified file and use it as the stream for logging.

        By default, the file grows indefinitely. You can specify particular
        values of maxBytes and backupCount to allow the file to rollover at
        a predetermined size.

        Rollover occurs whenever the current log file is nearly maxBytes in
        length. If backupCount is >= 1, the system will successively create
        new files with the same pathname as the base file, but with extensions
        ".1", ".2" etc. appended to it. For example, with a backupCount of 5
        and a base file name of "app.log", you would get "app.log",
        "app.log.1", "app.log.2", ... through to "app.log.5". The file being
        written to is always "app.log" - when it gets filled up, it is closed
        and renamed to "app.log.1", and if files "app.log.1", "app.log.2" etc.
        exist, then they are renamed to "app.log.2", "app.log.3" etc.
        respectively.

        If maxBytes is zero, rollover never occurs.
        """
        # If rotation/rollover is wanted, it doesn't make sense to use another
        # mode. If for example 'w' were specified, then if there were multiple
        # runs of the calling application, the logs from previous runs would be
        # lost if the 'w' is respected, because the log file would be truncated
        # on each run.
        if maxBytes > 0:
            mode = 'a'
        BaseRotatingHandler.__init__(self, filename, mode, encoding, delay)
        self.maxBytes = maxBytes
        self.backupCount = backupCount

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self.rotation_filename("%s.%d" % (self.baseFilename, i))
                dfn = self.rotation_filename("%s.%d" % (self.baseFilename,
                                                        i + 1))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.rotation_filename(self.baseFilename + ".1")
            if os.path.exists(dfn):
                os.remove(dfn)
            self.rotate(self.baseFilename, dfn)
        if not self.delay:
            self.stream = self._open()

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.
        """
        if self.stream is None:                 # delay was set...
            self.stream = self._open()
        if self.maxBytes > 0:                   # are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        return 0

class TimedRotatingFileHandler(BaseRotatingHandler):
    """
    Handler for logging to a file, rotating the log file at certain timed
    intervals.

    If backupCount is > 0, when rollover is done, no more than backupCount
    files are kept - the oldest ones are deleted.
    """
    def __init__(self, filename, when='h', interval=1, backupCount=0, encoding=None, delay=False, utc=False, atTime=None):
        BaseRotatingHandler.__init__(self, filename, 'a', encoding, delay)
        self.when = when.upper()
        self.backupCount = backupCount
        self.utc = utc
        self.atTime = atTime
        # Calculate the real rollover interval, which is just the number of
        # seconds between rollovers.  Also set the filename suffix used when
        # a rollover occurs.  Current 'when' events supported:
        # S - Seconds
        # M - Minutes
        # H - Hours
        # D - Days
        # midnight - roll over at midnight
        # W{0-6} - roll over on a certain day; 0 - Monday
        #
        # Case of the 'when' specifier is not important; lower or upper case
        # will work.
        if self.when == 'S':
            self.interval = 1 # one second
            self.suffix = "%Y-%m-%d_%H-%M-%S"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(\.\w+)?$"
        elif self.when == 'M':
            self.interval = 60 # one minute
            self.suffix = "%Y-%m-%d_%H-%M"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}(\.\w+)?$"
        elif self.when == 'H':
            self.interval = 60 * 60 # one hour
            self.suffix = "%Y-%m-%d_%H"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}(\.\w+)?$"
        elif self.when == 'D' or self.when == 'MIDNIGHT':
            self.interval = 60 * 60 * 24 # one day
            self.suffix = "%Y-%m-%d"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}(\.\w+)?$"
        elif self.when.startswith('W'):
            self.interval = 60 * 60 * 24 * 7 # one week
            if len(self.when) != 2:
                raise ValueError("You must specify a day for weekly rollover from 0 to 6 (0 is Monday): %s" % self.when)
            if self.when[1] < '0' or self.when[1] > '6':
                raise ValueError("Invalid day specified for weekly rollover: %s" % self.when)
            self.dayOfWeek = int(self.when[1])
            self.suffix = "%Y-%m-%d"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}(\.\w+)?$"
        else:
            raise ValueError("Invalid rollover interval specified: %s" % self.when)

        self.extMatch = re.compile(self.extMatch, re.ASCII)
        self.interval = self.interval * interval # multiply by units requested
        if os.path.exists(filename):
            t = os.stat(filename)[ST_MTIME]
        else:
            t = int(time.time())
        self.rolloverAt = self.computeRollover(t)

    def computeRollover(self, currentTime):
        """
        Work out the rollover time based on the specified time.
        """
        result = currentTime + self.interval
        # If we are rolling over at midnight or weekly, then the interval is already known.
        # What we need to figure out is WHEN the next interval is.  In other words,
        # if you are rolling over at midnight, then your base interval is 1 day,
        # but you want to start that one day clock at midnight, not now.  So, we
        # have to fudge the rolloverAt value in order to trigger the first rollover
        # at the right time.  After that, the regular interval will take care of
        # the rest.  Note that this code doesn't care about leap seconds. :)
        if self.when == 'MIDNIGHT' or self.when.startswith('W'):
            # This could be done with less code, but I wanted it to be clear
            if self.utc:
                t = time.gmtime(currentTime)
            else:
                t = time.localtime(currentTime)
            currentHour = t[3]
            currentMinute = t[4]
            currentSecond = t[5]
            currentDay = t[6]
            # r is the number of seconds left between now and the next rotation
            if self.atTime is None:
                rotate_ts = _MIDNIGHT
            else:
                rotate_ts = ((self.atTime.hour * 60 + self.atTime.minute)*60 +
                    self.atTime.second)

            r = rotate_ts - ((currentHour * 60 + currentMinute) * 60 +
                currentSecond)
            if r < 0:
                # Rotate time is before the current time (for example when
                # self.rotateAt is 13:45 and it now 14:15), rotation is
                # tomorrow.
                r += _MIDNIGHT
                currentDay = (currentDay + 1) % 7
            result = currentTime + r
            # If we are rolling over on a certain day, add in the number of days until
            # the next rollover, but offset by 1 since we just calculated the time
            # until the next day starts.  There are three cases:
            # Case 1) The day to rollover is today; in this case, do nothing
            # Case 2) The day to rollover is further in the interval (i.e., today is
            #         day 2 (Wednesday) and rollover is on day 6 (Sunday).  Days to
            #         next rollover is simply 6 - 2 - 1, or 3.
            # Case 3) The day to rollover is behind us in the interval (i.e., today
            #         is day 5 (Saturday) and rollover is on day 3 (Thursday).
            #         Days to rollover is 6 - 5 + 3, or 4.  In this case, it's the
            #         number of days left in the current week (1) plus the number
            #         of days in the next week until the rollover day (3).
            # The calculations described in 2) and 3) above need to have a day added.
            # This is because the above time calculation takes us to midnight on this
            # day, i.e. the start of the next day.
            if self.when.startswith('W'):
                day = currentDay # 0 is Monday
                if day != self.dayOfWeek:
                    if day < self.dayOfWeek:
                        daysToWait = self.dayOfWeek - day
                    else:
                        daysToWait = 6 - day + self.dayOfWeek + 1
                    newRolloverAt = result + (daysToWait * (60 * 60 * 24))
                    if not self.utc:
                        dstNow = t[-1]
                        dstAtRollover = time.localtime(newRolloverAt)[-1]
                        if dstNow != dstAtRollover:
                            if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
                                addend = -3600
                            else:           # DST bows out before next rollover, so we need to add an hour
                                addend = 3600
                            newRolloverAt += addend
                    result = newRolloverAt
        return result

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        record is not used, as we are just comparing times, but it is needed so
        the method signatures are the same
        """
        t = int(time.time())
        if t >= self.rolloverAt:
            return 1
        return 0

    def getFilesToDelete(self):
        """
        Determine the files to delete when rolling over.

        More specific than the earlier method, which just used glob.glob().
        """
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        result = []
        prefix = baseName + "."
        plen = len(prefix)
        for fileName in fileNames:
            if fileName[:plen] == prefix:
                suffix = fileName[plen:]
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dirName, fileName))
        result.sort()
        if len(result) < self.backupCount:
            result = []
        else:
            result = result[:len(result) - self.backupCount]
        return result

    def doRollover(self):
        """
        do a rollover; in this case, a date/time stamp is appended to the filename
        when the rollover happens.  However, you want the file to be named for the
        start of the interval, not the current time.  If there is a backup count,
        then we have to get a list of matching filenames, sort them and remove
        the one with the oldest suffix.
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        # get the time that this sequence started at and make it a TimeTuple
        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)
        dfn = self.rotation_filename(self.baseFilename + "." +
                                     time.strftime(self.suffix, timeTuple))
        if os.path.exists(dfn):
            os.remove(dfn)
        self.rotate(self.baseFilename, dfn)
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)
        if not self.delay:
            self.stream = self._open()
        newRolloverAt = self.computeRollover(currentTime)
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval
        #If DST changes and midnight or weekly rollover, adjust for this.
        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
                if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
                    addend = -3600
                else:           # DST bows out before next rollover, so we need to add an hour
                    addend = 3600
                newRolloverAt += addend
        self.rolloverAt = newRolloverAt

class WatchedFileHandler(logging.FileHandler):
    """
    A handler for logging to a file, which watches the file
    to see if it has changed while in use. This can happen because of
    usage of programs such as newsyslog and logrotate which perform
    log file rotation. This handler, intended for use under Unix,
    watches the file to see if it has changed since the last emit.
    (A file has changed if its device or inode have changed.)
    If it has changed, the old file stream is closed, and the file
    opened to get a new stream.

    This handler is not appropriate for use under Windows, because
    under Windows open files cannot be moved or renamed - logging
    opens the files with exclusive locks - and so there is no need
    for such a handler. Furthermore, ST_INO is not supported under
    Windows; stat always returns zero for this value.

    This handler is based on a suggestion and patch by Chad J.
    Schroeder.
    """
    def __init__(self, filename, mode='a', encoding=None, delay=False):
        logging.FileHandler.__init__(self, filename, mode, encoding, delay)
        self.dev, self.ino = -1, -1
        self._statstream()

    def _statstream(self):
        if self.stream:
            sres = os.fstat(self.stream.fileno())
            self.dev, self.ino = sres[ST_DEV], sres[ST_INO]

    def emit(self, record):
        """
        Emit a record.

        First check if the underlying file has changed, and if it
        has, close the old stream and reopen the file to get the
        current stream.
        """
        # Reduce the chance of race conditions by stat'ing by path only
        # once and then fstat'ing our new fd if we opened a new log stream.
        # See issue #14632: Thanks to John Mulligan for the problem report
        # and patch.
        try:
            # stat the file by path, checking for existence
            sres = os.stat(self.baseFilename)
        except FileNotFoundError:
            sres = None
        # compare file system stat with that of our stream file handle
        if not sres or sres[ST_DEV] != self.dev or sres[ST_INO] != self.ino:
            if self.stream is not None:
                # we have an open file handle, clean it up
                self.stream.flush()
                self.stream.close()
                self.stream = None  # See Issue #21742: _open () might fail.
                # open a new file handle and get new stat info from that fd
                self.stream = self._open()
                self._statstream()
        logging.FileHandler.emit(self, record)


class SocketHandler(Handler):
    """
    A handler class which writes logging records, in pickle format, to
    a streaming socket. The socket is kept open across logging calls.
    If the peer resets it, an attempt is made to reconnect on the next call.
    The pickle which is sent is that of the LogRecord's attribute dictionary
    (__dict__), so that the receiver does not need to have the logging module
    installed in order to process the logging event.

    To unpickle the record at the receiving end into a LogRecord, use the
    makeLogRecord function.
    """

    def __init__(self, host, port):
        """
        Initializes the handler with a specific host address and port.

        When the attribute *closeOnError* is set to True - if a socket error
        occurs, the socket is silently closed and then reopened on the next
        logging call.
        """
        Handler.__init__(self)
        self.host = host
        self.port = port
        if port is None:
            self.address = host
        else:
            self.address = (host, port)
        self.sock = None
        self.closeOnError = False
        self.retryTime = None
        #
        # Exponential backoff parameters.
        #
        self.retryStart = 1.0
        self.retryMax = 30.0
        self.retryFactor = 2.0

    def makeSocket(self, timeout=1):
        """
        A factory method which allows subclasses to define the precise
        type of socket they want.
        """
        if self.port is not None:
            result = socket.create_connection(self.address, timeout=timeout)
        else:
            result = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            result.settimeout(timeout)
            try:
                result.connect(self.address)
            except OSError:
                result.close()  # Issue 19182
                raise
        return result

    def createSocket(self):
        """
        Try to create a socket, using an exponential backoff with
        a max retry time. Thanks to Robert Olson for the original patch
        (SF #815911) which has been slightly refactored.
        """
        now = time.time()
        # Either retryTime is None, in which case this
        # is the first time back after a disconnect, or
        # we've waited long enough.
        if self.retryTime is None:
            attempt = True
        else:
            attempt = (now >= self.retryTime)
        if attempt:
            try:
                self.sock = self.makeSocket()
                self.retryTime = None # next time, no delay before trying
            except OSError:
                #Creation failed, so set the retry time and return.
                if self.retryTime is None:
                    self.retryPeriod = self.retryStart
                else:
                    self.retryPeriod = self.retryPeriod * self.retryFactor
                    if self.retryPeriod > self.retryMax:
                        self.retryPeriod = self.retryMax
                self.retryTime = now + self.retryPeriod

    def send(self, s):
        """
        Send a pickled string to the socket.

        This function allows for partial sends which can happen when the
        network is busy.
        """
        if self.sock is None:
            self.createSocket()
        #self.sock can be None either because we haven't reached the retry
        #time yet, or because we have reached the retry time and retried,
        #but are still unable to connect.
        if self.sock:
            try:
                self.sock.sendall(s)
            except OSError: #pragma: no cover
                self.sock.close()
                self.sock = None  # so we can call createSocket next time

    def makePickle(self, record):
        """
        Pickles the record in binary format with a length prefix, and
        returns it ready for transmission across the socket.
        """
        ei = record.exc_info
        if ei:
            # just to get traceback text into record.exc_text ...
            dummy = self.format(record)
        # See issue #14436: If msg or args are objects, they may not be
        # available on the receiving end. So we convert the msg % args
        # to a string, save it as msg and zap the args.
        d = dict(record.__dict__)
        d['msg'] = record.getMessage()
        d['args'] = None
        d['exc_info'] = None
        # Issue #25685: delete 'message' if present: redundant with 'msg'
        d.pop('message', None)
        s = pickle.dumps(d, 1)
        slen = struct.pack(">L", len(s))
        return slen + s

    def handleError(self, record):
        """
        Handle an error during logging.

        An error has occurred during logging. Most likely cause -
        connection lost. Close the socket so that we can retry on the
        next event.
        """
        if self.closeOnError and self.sock:
            self.sock.close()
            self.sock = None        #try to reconnect next time
        else:
            Handler.handleError(self, record)

    def emit(self, record):
        """
        Emit a record.

        Pickles the record and writes it to the socket in binary format.
        If there is an error with the socket, silently drop the packet.
        If there was a problem with the socket, re-establishes the
        socket.
        """
        try:
            s = self.makePickle(record)
            self.send(s)
        except Exception:
            self.handleError(record)

    def close(self):
        """
        Closes the socket.
        """
        self.acquire()
        try:
            sock = self.sock
            if sock:
                self.sock = None
                sock.close()
            Handler.close(self)
        finally:
            self.release()

class DatagramHandler(SocketHandler):
    """
    A handler class which writes logging records, in pickle format, to
    a datagram socket.  The pickle which is sent is that of the LogRecord's
    attribute dictionary (__dict__), so that the receiver does not need to
    have the logging module installed in order to process the logging event.

    To unpickle the record at the receiving end into a LogRecord, use the
    makeLogRecord function.

    """
    def __init__(self, host, port):
        """
        Initializes the handler with a specific host address and port.
        """
        SocketHandler.__init__(self, host, port)
        self.closeOnError = False

    def makeSocket(self):
        """
        The factory method of SocketHandler is here overridden to create
        a UDP socket (SOCK_DGRAM).
        """
        if self.port is None:
            family = socket.AF_UNIX
        else:
            family = socket.AF_INET
        s = socket.socket(family, socket.SOCK_DGRAM)
        return s

    def send(self, s):
        """
        Send a pickled string to a socket.

        This function no longer allows for partial sends which can happen
        when the network is busy - UDP does not guarantee delivery and
        can deliver packets out of sequence.
        """
        if self.sock is None:
            self.createSocket()
        self.sock.sendto(s, self.address)

class SysLogHandler(Handler):
    """
    A handler class which sends formatted logging records to a syslog
    server. Based on Sam Rushing's syslog module:
    http://www.nightmare.com/squirl/python-ext/misc/syslog.py
    Contributed by Nicolas Untz (after which minor refactoring changes
    have been made).
    """

    # from <linux/sys/syslog.h>:
    # ======================================================================
    # priorities/facilities are encoded into a single 32-bit quantity, where
    # the bottom 3 bits are the priority (0-7) and the top 28 bits are the
    # facility (0-big number). Both the priorities and the facilities map
    # roughly one-to-one to strings in the syslogd(8) source code.  This
    # mapping is included in this file.
    #
    # priorities (these are ordered)

    LOG_EMERG     = 0       #  system is unusable
    LOG_ALERT     = 1       #  action must be taken immediately
    LOG_CRIT      = 2       #  critical conditions
    LOG_ERR       = 3       #  error conditions
    LOG_WARNING   = 4       #  warning conditions
    LOG_NOTICE    = 5       #  normal but significant condition
    LOG_INFO      = 6       #  informational
    LOG_DEBUG     = 7       #  debug-level messages

    #  facility codes
    LOG_KERN      = 0       #  kernel messages
    LOG_USER      = 1       #  random user-level messages
    LOG_MAIL      = 2       #  mail system
    LOG_DAEMON    = 3       #  system daemons
    LOG_AUTH      = 4       #  security/authorization messages
    LOG_SYSLOG    = 5       #  messages generated internally by syslogd
    LOG_LPR       = 6       #  line printer subsystem
    LOG_NEWS      = 7       #  network news subsystem
    LOG_UUCP      = 8       #  UUCP subsystem
    LOG_CRON      = 9       #  clock daemon
    LOG_AUTHPRIV  = 10      #  security/authorization messages (private)
    LOG_FTP       = 11      #  FTP daemon

    #  other codes through 15 reserved for system use
    LOG_LOCAL0    = 16      #  reserved for local use
    LOG_LOCAL1    = 17      #  reserved for local use
    LOG_LOCAL2    = 18      #  reserved for local use
    LOG_LOCAL3    = 19      #  reserved for local use
    LOG_LOCAL4    = 20      #  reserved for local use
    LOG_LOCAL5    = 21      #  reserved for local use
    LOG_LOCAL6    = 22      #  reserved for local use
    LOG_LOCAL7    = 23      #  reserved for local use

    priority_names = {
        "alert":    LOG_ALERT,
        "crit":     LOG_CRIT,
        "critical": LOG_CRIT,
        "debug":    LOG_DEBUG,
        "emerg":    LOG_EMERG,
        "err":      LOG_ERR,
        "error":    LOG_ERR,        #  DEPRECATED
        "info":     LOG_INFO,
        "notice":   LOG_NOTICE,
        "panic":    LOG_EMERG,      #  DEPRECATED
        "warn":     LOG_WARNING,    #  DEPRECATED
        "warning":  LOG_WARNING,
        }

    facility_names = {
        "auth":     LOG_AUTH,
        "authpriv": LOG_AUTHPRIV,
        "cron":     LOG_CRON,
        "daemon":   LOG_DAEMON,
        "ftp":      LOG_FTP,
        "kern":     LOG_KERN,
        "lpr":      LOG_LPR,
        "mail":     LOG_MAIL,
        "news":     LOG_NEWS,
        "security": LOG_AUTH,       #  DEPRECATED
        "syslog":   LOG_SYSLOG,
        "user":     LOG_USER,
        "uucp":     LOG_UUCP,
        "local0":   LOG_LOCAL0,
        "local1":   LOG_LOCAL1,
        "local2":   LOG_LOCAL2,
        "local3":   LOG_LOCAL3,
        "local4":   LOG_LOCAL4,
        "local5":   LOG_LOCAL5,
        "local6":   LOG_LOCAL6,
        "local7":   LOG_LOCAL7,
        }

    #The map below appears to be trivially lowercasing the key. However,
    #there's more to it than meets the eye - in some locales, lowercasing
    #gives unexpected results. See SF #1524081: in the Turkish locale,
    #"INFO".lower() != "info"
    priority_map = {
        "DEBUG" : "debug",
        "INFO" : "info",
        "WARNING" : "warning",
        "ERROR" : "error",
        "CRITICAL" : "critical"
    }

    def __init__(self, address=('localhost', SYSLOG_UDP_PORT),
                 facility=LOG_USER, socktype=None):
        """
        Initialize a handler.

        If address is specified as a string, a UNIX socket is used. To log to a
        local syslogd, "SysLogHandler(address="/dev/log")" can be used.
        If facility is not specified, LOG_USER is used. If socktype is
        specified as socket.SOCK_DGRAM or socket.SOCK_STREAM, that specific
        socket type will be used. For Unix sockets, you can also specify a
        socktype of None, in which case socket.SOCK_DGRAM will be used, falling
        back to socket.SOCK_STREAM.
        """
        Handler.__init__(self)

        self.address = address
        self.facility = facility
        self.socktype = socktype

        if isinstance(address, str):
            self.unixsocket = True
            # Syslog server may be unavailable during handler initialisation.
            # C's openlog() function also ignores connection errors.
            # Moreover, we ignore these errors while logging, so it not worse
            # to ignore it also here.
            try:
                self._connect_unixsocket(address)
            except OSError:
                pass
        else:
            self.unixsocket = False
            if socktype is None:
                socktype = socket.SOCK_DGRAM
            host, port = address
            ress = socket.getaddrinfo(host, port, 0, socktype)
            if not ress:
                raise OSError("getaddrinfo returns an empty list")
            for res in ress:
                af, socktype, proto, _, sa = res
                err = sock = None
                try:
                    sock = socket.socket(af, socktype, proto)
                    if socktype == socket.SOCK_STREAM:
                        sock.connect(sa)
                    break
                except OSError as exc:
                    err = exc
                    if sock is not None:
                        sock.close()
            if err is not None:
                raise err
            self.socket = sock
            self.socktype = socktype

    def _connect_unixsocket(self, address):
        use_socktype = self.socktype
        if use_socktype is None:
            use_socktype = socket.SOCK_DGRAM
        self.socket = socket.socket(socket.AF_UNIX, use_socktype)
        try:
            self.socket.connect(address)
            # it worked, so set self.socktype to the used type
            self.socktype = use_socktype
        except OSError:
            self.socket.close()
            if self.socktype is not None:
                # user didn't specify falling back, so fail
                raise
            use_socktype = socket.SOCK_STREAM
            self.socket = socket.socket(socket.AF_UNIX, use_socktype)
            try:
                self.socket.connect(address)
                # it worked, so set self.socktype to the used type
                self.socktype = use_socktype
            except OSError:
                self.socket.close()
                raise

    def encodePriority(self, facility, priority):
        """
        Encode the facility and priority. You can pass in strings or
        integers - if strings are passed, the facility_names and
        priority_names mapping dictionaries are used to convert them to
        integers.
        """
        if isinstance(facility, str):
            facility = self.facility_names[facility]
        if isinstance(priority, str):
            priority = self.priority_names[priority]
        return (facility << 3) | priority

    def close(self):
        """
        Closes the socket.
        """
        self.acquire()
        try:
            self.socket.close()
            Handler.close(self)
        finally:
            self.release()

    def mapPriority(self, levelName):
        """
        Map a logging level name to a key in the priority_names map.
        This is useful in two scenarios: when custom levels are being
        used, and in the case where you can't do a straightforward
        mapping by lowercasing the logging level name because of locale-
        specific issues (see SF #1524081).
        """
        return self.priority_map.get(levelName, "warning")

    ident = ''          # prepended to all messages
    append_nul = True   # some old syslog daemons expect a NUL terminator

    def emit(self, record):
        """
        Emit a record.

        The record is formatted, and then sent to the syslog server. If
        exception information is present, it is NOT sent to the server.
        """
        try:
            msg = self.format(record)
            if self.ident:
                msg = self.ident + msg
            if self.append_nul:
                msg += '\000'

            # We need to convert record level to lowercase, maybe this will
            # change in the future.
            prio = '<%d>' % self.encodePriority(self.facility,
                                                self.mapPriority(record.levelname))
            prio = prio.encode('utf-8')
            # Message is a string. Convert to bytes as required by RFC 5424
            msg = msg.encode('utf-8')
            msg = prio + msg
            if self.unixsocket:
                try:
                    self.socket.send(msg)
                except OSError:
                    self.socket.close()
                    self._connect_unixsocket(self.address)
                    self.socket.send(msg)
            elif self.socktype == socket.SOCK_DGRAM:
                self.socket.sendto(msg, self.address)
            else:
                self.socket.sendall(msg)
        except Exception:
            self.handleError(record)

class SMTPHandler(Handler):
    """
    A handler class which sends an SMTP email for each logging event.
    """
    def __init__(self, mailhost, fromaddr, toaddrs, subject,
                 credentials=None, secure=None, timeout=5.0):
        """
        Initialize the handler.

        Initialize the instance with the from and to addresses and subject
        line of the email. To specify a non-standard SMTP port, use the
        (host, port) tuple format for the mailhost argument. To specify
        authentication credentials, supply a (username, password) tuple
        for the credentials argument. To specify the use of a secure
        protocol (TLS), pass in a tuple for the secure argument. This will
        only be used when authentication credentials are supplied. The tuple
        will be either an empty tuple, or a single-value tuple with the name
        of a keyfile, or a 2-value tuple with the names of the keyfile and
        certificate file. (This tuple is passed to the `starttls` method).
        A timeout in seconds can be specified for the SMTP connection (the
        default is one second).
        """
        Handler.__init__(self)
        if isinstance(mailhost, (list, tuple)):
            self.mailhost, self.mailport = mailhost
        else:
            self.mailhost, self.mailport = mailhost, None
        if isinstance(credentials, (list, tuple)):
            self.username, self.password = credentials
        else:
            self.username = None
        self.fromaddr = fromaddr
        if isinstance(toaddrs, str):
            toaddrs = [toaddrs]
        self.toaddrs = toaddrs
        self.subject = subject
        self.secure = secure
        self.timeout = timeout

    def getSubject(self, record):
        """
        Determine the subject for the email.

        If you want to specify a subject line which is record-dependent,
        override this method.
        """
        return self.subject

    def emit(self, record):
        """
        Emit a record.

        Format the record and send it to the specified addressees.
        """
        try:
            import smtplib
            from email.message import EmailMessage
            import email.utils

            port = self.mailport
            if not port:
                port = smtplib.SMTP_PORT
            smtp = smtplib.SMTP(self.mailhost, port, timeout=self.timeout)
            msg = EmailMessage()
            msg['From'] = self.fromaddr
            msg['To'] = ','.join(self.toaddrs)
            msg['Subject'] = self.getSubject(record)
            msg['Date'] = email.utils.localtime()
            msg.set_content(self.format(record))
            if self.username:
                if self.secure is not None:
                    smtp.ehlo()
                    smtp.starttls(*self.secure)
                    smtp.ehlo()
                smtp.login(self.username, self.password)
            smtp.send_message(msg)
            smtp.quit()
        except Exception:
            self.handleError(record)

class NTEventLogHandler(Handler):
    """
    A handler class which sends events to the NT Event Log. Adds a
    registry entry for the specified application name. If no dllname is
    provided, win32service.pyd (which contains some basic message
    placeholders) is used. Note that use of these placeholders will make
    your event logs big, as the entire message source is held in the log.
    If you want slimmer logs, you have to pass in the name of your own DLL
    which contains the message definitions you want to use in the event log.
    """
    def __init__(self, appname, dllname=None, logtype="Application"):
        Handler.__init__(self)
        try:
            import win32evtlogutil, win32evtlog
            self.appname = appname
            self._welu = win32evtlogutil
            if not dllname:
                dllname = os.path.split(self._welu.__file__)
                dllname = os.path.split(dllname[0])
                dllname = os.path.join(dllname[0], r'win32service.pyd')
            self.dllname = dllname
            self.logtype = logtype
            self._welu.AddSourceToRegistry(appname, dllname, logtype)
            self.deftype = win32evtlog.EVENTLOG_ERROR_TYPE
            self.typemap = {
                logging.DEBUG   : win32evtlog.EVENTLOG_INFORMATION_TYPE,
                logging.INFO    : win32evtlog.EVENTLOG_INFORMATION_TYPE,
                logging.WARNING : win32evtlog.EVENTLOG_WARNING_TYPE,
                logging.ERROR   : win32evtlog.EVENTLOG_ERROR_TYPE,
                logging.CRITICAL: win32evtlog.EVENTLOG_ERROR_TYPE,
         }
        except ImportError:
            print("The Python Win32 extensions for NT (service, event "\
                        "logging) appear not to be available.")
            self._welu = None

    def getMessageID(self, record):
        """
        Return the message ID for the event record. If you are using your
        own messages, you could do this by having the msg passed to the
        logger being an ID rather than a formatting string. Then, in here,
        you could use a dictionary lookup to get the message ID. This
        version returns 1, which is the base message ID in win32service.pyd.
        """
        return 1

    def getEventCategory(self, record):
        """
        Return the event category for the record.

        Override this if you want to specify your own categories. This version
        returns 0.
        """
        return 0

    def getEventType(self, record):
        """
        Return the event type for the record.

        Override this if you want to specify your own types. This version does
        a mapping using the handler's typemap attribute, which is set up in
        __init__() to a dictionary which contains mappings for DEBUG, INFO,
        WARNING, ERROR and CRITICAL. If you are using your own levels you will
        either need to override this method or place a suitable dictionary in
        the handler's typemap attribute.
        """
        return self.typemap.get(record.levelno, self.deftype)

    def emit(self, record):
        """
        Emit a record.

        Determine the message ID, event category and event type. Then
        log the message in the NT event log.
        """
        if self._welu:
            try:
                id = self.getMessageID(record)
                cat = self.getEventCategory(record)
                type = self.getEventType(record)
                msg = self.format(record)
                self._welu.ReportEvent(self.appname, id, cat, type, [msg])
            except Exception:
                self.handleError(record)

    def close(self):
        """
        Clean up this handler.

        You can remove the application name from the registry as a
        source of event log entries. However, if you do this, you will
        not be able to see the events as you intended in the Event Log
        Viewer - it needs to be able to access the registry to get the
        DLL name.
        """
        #self._welu.RemoveSourceFromRegistry(self.appname, self.logtype)
        Handler.close(self)

class HTTPHandler(Handler):
    """
    A class which sends records to a Web server, using either GET or
    POST semantics.
    """
    def __init__(self, host, url, method="GET", secure=False, credentials=None,
                 context=None):
        """
        Initialize the instance with the host, the request URL, and the method
        ("GET" or "POST")
        """
        Handler.__init__(self)
        method = method.upper()
        if method not in ["GET", "POST"]:
            raise ValueError("method must be GET or POST")
        if not secure and context is not None:
            raise ValueError("context parameter only makes sense "
                             "with secure=True")
        self.host = host
        self.url = url
        self.method = method
        self.secure = secure
        self.credentials = credentials
        self.context = context

    def mapLogRecord(self, record):
        """
        Default implementation of mapping the log record into a dict
        that is sent as the CGI data. Overwrite in your class.
        Contributed by Franz Glasner.
        """
        return record.__dict__

    def emit(self, record):
        """
        Emit a record.

        Send the record to the Web server as a percent-encoded dictionary
        """
        try:
            import http.client, urllib.parse
            host = self.host
            if self.secure:
                h = http.client.HTTPSConnection(host, context=self.context)
            else:
                h = http.client.HTTPConnection(host)
            url = self.url
            data = urllib.parse.urlencode(self.mapLogRecord(record))
            if self.method == "GET":
                if (url.find('?') >= 0):
                    sep = '&'
                else:
                    sep = '?'
                url = url + "%c%s" % (sep, data)
            h.putrequest(self.method, url)
            # support multiple hosts on one IP address...
            # need to strip optional :port from host, if present
            i = host.find(":")
            if i >= 0:
                host = host[:i]
            h.putheader("Host", host)
            if self.method == "POST":
                h.putheader("Content-type",
                            "application/x-www-form-urlencoded")
                h.putheader("Content-length", str(len(data)))
            if self.credentials:
                import base64
                s = ('%s:%s' % self.credentials).encode('utf-8')
                s = 'Basic ' + base64.b64encode(s).strip().decode('ascii')
                h.putheader('Authorization', s)
            h.endheaders()
            if self.method == "POST":
                h.send(data.encode('utf-8'))
            h.getresponse()    #can't do anything with the result
        except Exception:
            self.handleError(record)

class BufferingHandler(Handler):
    """
  A handler class which buffers logging records in memory. Whenever each
  record is added to the buffer, a check is made to see if the buffer should
  be flushed. If it should, then flush() is expected to do what's needed.
    """
    def __init__(self, capacity):
        """
        Initialize the handler with the buffer size.
        """
        Handler.__init__(self)
        self.capacity = capacity
        self.buffer = []

    def shouldFlush(self, record):
        """
        Should the handler flush its buffer?

        Returns true if the buffer is up to capacity. This method can be
        overridden to implement custom flushing strategies.
        """
        return (len(self.buffer) >= self.capacity)

    def emit(self, record):
        """
        Emit a record.

        Append the record. If shouldFlush() tells us to, call flush() to process
        the buffer.
        """
        self.buffer.append(record)
        if self.shouldFlush(record):
            self.flush()

    def flush(self):
        """
        Override to implement custom flushing behaviour.

        This version just zaps the buffer to empty.
        """
        self.acquire()
        try:
            self.buffer = []
        finally:
            self.release()

    def close(self):
        """
        Close the handler.

        This version just flushes and chains to the parent class' close().
        """
        try:
            self.flush()
        finally:
            Handler.close(self)

class MemoryHandler(BufferingHandler):
    """
    A handler class which buffers logging records in memory, periodically
    flushing them to a target handler. Flushing occurs whenever the buffer
    is full, or when an event of a certain severity or greater is seen.
    """
    def __init__(self, capacity, flushLevel=logging.ERROR, target=None):
        """
        Initialize the handler with the buffer size, the level at which
        flushing should occur and an optional target.

        Note that without a target being set either here or via setTarget(),
        a MemoryHandler is no use to anyone!
        """
        BufferingHandler.__init__(self, capacity)
        self.flushLevel = flushLevel
        self.target = target

    def shouldFlush(self, record):
        """
        Check for buffer full or a record at the flushLevel or higher.
        """
        return (len(self.buffer) >= self.capacity) or \
                (record.levelno >= self.flushLevel)

    def setTarget(self, target):
        """
        Set the target handler for this handler.
        """
        self.target = target

    def flush(self):
        """
        For a MemoryHandler, flushing means just sending the buffered
        records to the target, if there is one. Override if you want
        different behaviour.

        The record buffer is also cleared by this operation.
        """
        self.acquire()
        try:
            if self.target:
                for record in self.buffer:
                    self.target.handle(record)
                self.buffer = []
        finally:
            self.release()

    def close(self):
        """
        Flush, set the target to None and lose the buffer.
        """
        try:
            self.flush()
        finally:
            self.acquire()
            try:
                self.target = None
                BufferingHandler.close(self)
            finally:
                self.release()


class QueueHandler(Handler):
    """
    This handler sends events to a queue. Typically, it would be used together
    with a multiprocessing Queue to centralise logging to file in one process
    (in a multi-process application), so as to avoid file write contention
    between processes.

    This code is new in Python 3.2, but this class can be copy pasted into
    user code for use with earlier Python versions.
    """

    def __init__(self, queue):
        """
        Initialise an instance, using the passed queue.
        """
        Handler.__init__(self)
        self.queue = queue

    def enqueue(self, record):
        """
        Enqueue a record.

        The base implementation uses put_nowait. You may want to override
        this method if you want to use blocking, timeouts or custom queue
        implementations.
        """
        self.queue.put_nowait(record)

    def prepare(self, record):
        """
        Prepares a record for queuing. The object returned by this method is
        enqueued.

        The base implementation formats the record to merge the message
        and arguments, and removes unpickleable items from the record
        in-place.

        You might want to override this method if you want to convert
        the record to a dict or JSON string, or send a modified copy
        of the record while leaving the original intact.
        """
        # The format operation gets traceback text into record.exc_text
        # (if there's exception data), and also puts the message into
        # record.message. We can then use this to replace the original
        # msg + args, as these might be unpickleable. We also zap the
        # exc_info attribute, as it's no longer needed and, if not None,
        # will typically not be pickleable.
        self.format(record)
        record.msg = record.message
        record.args = None
        record.exc_info = None
        return record

    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue, preparing it for pickling first.
        """
        try:
            self.enqueue(self.prepare(record))
        except Exception:
            self.handleError(record)

if threading:
    class QueueListener(object):
        """
        This class implements an internal threaded listener which watches for
        LogRecords being added to a queue, removes them and passes them to a
        list of handlers for processing.
        """
        _sentinel = None

        def __init__(self, queue, *handlers, respect_handler_level=False):
            """
            Initialise an instance with the specified queue and
            handlers.
            """
            self.queue = queue
            self.handlers = handlers
            self._thread = None
            self.respect_handler_level = respect_handler_level

        def dequeue(self, block):
            """
            Dequeue a record and return it, optionally blocking.

            The base implementation uses get. You may want to override this method
            if you want to use timeouts or work with custom queue implementations.
            """
            return self.queue.get(block)

        def start(self):
            """
            Start the listener.

            This starts up a background thread to monitor the queue for
            LogRecords to process.
            """
            self._thread = t = threading.Thread(target=self._monitor)
            t.daemon = True
            t.start()

        def prepare(self , record):
            """
            Prepare a record for handling.

            This method just returns the passed-in record. You may want to
            override this method if you need to do any custom marshalling or
            manipulation of the record before passing it to the handlers.
            """
            return record

        def handle(self, record):
            """
            Handle a record.

            This just loops through the handlers offering them the record
            to handle.
            """
            record = self.prepare(record)
            for handler in self.handlers:
                if not self.respect_handler_level:
                    process = True
                else:
                    process = record.levelno >= handler.level
                if process:
                    handler.handle(record)

        def _monitor(self):
            """
            Monitor the queue for records, and ask the handler
            to deal with them.

            This method runs on a separate, internal thread.
            The thread will terminate if it sees a sentinel object in the queue.
            """
            q = self.queue
            has_task_done = hasattr(q, 'task_done')
            while True:
                try:
                    record = self.dequeue(True)
                    if record is self._sentinel:
                        break
                    self.handle(record)
                    if has_task_done:
                        q.task_done()
                except queue.Empty:
                    break

        def enqueue_sentinel(self):
            """
            This is used to enqueue the sentinel record.

            The base implementation uses put_nowait. You may want to override this
            method if you want to use timeouts or work with custom queue
            implementations.
            """
            self.queue.put_nowait(self._sentinel)

        def stop(self):
            """
            Stop the listener.

            This asks the thread to terminate, and then waits for it to do so.
            Note that if you don't call this before your application exits, there
            may be some records still left on the queue, which won't be processed.
            """
            self.enqueue_sentinel()
            self._thread.join()
            self._thread = None
