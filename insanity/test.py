# GStreamer QA system
#
#       test.py
#
# Copyright (c) 2007, Edward Hervey <bilboed@bilboed.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA 02110-1301, USA.

"""
Base Test Classes
"""

import os
import time

from insanity.log import error, warning, debug, info, exception
import insanity.utils as utils

import gobject

# Class tree
#
# Test
# |
# +--- Scenario
# |
# +--- DBusTest
#      |
#      +--- PythonDBusTest

class Test(gobject.GObject):
    """
    Runs a series of commands

    @ivar uuid: unique identifier for the test
    """

    SKIPPED = None
    FAILURE = 0
    SUCCESS = 1
    EXPECTED_FAILURE = 2

    __test_name__ = "test-base-class"
    """
    Name of the test

    This name should be unique amongst all tests, it is
    used as an identifier for this test.
    """

    __test_description__ = """Base class for tests"""
    """
    One-liner description of the test
    """

    __test_full_description__ = __test_description__
    """
    Extended description of the test

    By default, the same value as __test_description__ will be
    used, but it can be useful for tests that can not summarize
    in one line their purpose and usage.
    """

    __test_arguments__ = {
        "instance-name": {
            "global": True,
            "description" : "Name assigned by parent.",
            "full_description": "Used to identify similar subtests within a scenario.",
            "type": "s",
            "default_value": ""
        },

        "expected-failures": {
            "global": False,
            "description": "List of expected failing checkpoints",
            "full_description": """ Must be of the form:
            [{
                "arguments": {argname: [broken_value, ...], ...},
                "results": {checkitemname: ['0' or 'None'], ...}
             },
            ...],
            If the test's arguments all match values in arguments, and the
            result of the check matches one in "results", mark the failure as
            expected.""",
            "type": "s",
            "default_value": None
        }
        }
    """
    Dictionnary of arguments this test can take.

    key : name of the argument
    value : tuple of :
         * short description of the argument
         * default value used
         * long description of the argument (if None, same as short description)
    """

    __test_checklist__ = {
        "test-started": {
            "global": False,
            "description": "The test started"},
        "no-timeout": {
            "global": False,
            "description": "The test didn't timeout"},
        "no-unexpected-failures": {
            "global": False,
            "description": "All failed checks were expected."},
        }
    """
    Dictionnary of check items this test will validate.

    For each item, the test will try to validate them as
    being succesfull (True) or not (False).

    key : name of the check item
    value :
         * short description of the check item
    """

    __test_timeout__ = 15
    """
    Allowed duration for the test to run (in seconds).
    """

    __test_extra_infos__ = {
        "test-setup-duration" :
        "How long it took to setup the test (in milliseconds) for asynchronous tests",
        "test-total-duration" :
        "How long it took to run the entire test (in milliseconds)"
        }
    """
    Dictionnary of extra information this test can produce.
    """

    __test_output_files__ = { }
    """
    Dictionnary of output files this test can produce

    key : short name of the output file
    value : description of the contents of the output file

    Temporary names will be automatically created at initialization for use by
    subtests, or can be overridden by setting specific names as the 'outputfiles'
    __init__() argument.
    """

    # Set to True if your setUp doesn't happen synchronously
    __async_setup__ = False
    """
    Indicates if this test starts up asynchronously
    """

    # Subclasses need to call ready within that delay (in seconds)
    __async_setup_timeout__ = 10
    """
    Allowed duration for the test to start up (in seconds)
    """

    # Set to False if you test() method returns immediatly
    __async_test__ = True
    """
    Indicates if this test runs asynchronously
    """

    __gsignals__ = {
        "start" : (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   (gobject.TYPE_INT,)),

        "stop" : (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   (gobject.TYPE_INT,)),

        "done" : (gobject.SIGNAL_RUN_LAST,
                  gobject.TYPE_NONE,
                  ()),

        "check" : (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   (gobject.TYPE_PYOBJECT,
                    gobject.TYPE_PYOBJECT)),

        "extra-info" : (gobject.SIGNAL_RUN_LAST,
                        gobject.TYPE_NONE,
                        (gobject.TYPE_PYOBJECT,
                         gobject.TYPE_PYOBJECT))
        }

    def __init__(self, testrun=None, uuid=None, timeout=None,
                 asynctimeout=None,
                 **kwargs):
        """
        @type testrun: L{TestRun}
        """
        gobject.GObject.__init__(self)
        self._timeout = timeout or self.__test_timeout__
        self._asynctimeout = asynctimeout or self.__async_setup_timeout__
        self._running = False
        self.arguments = utils.unicode_dict(kwargs)
        self.iteration_arguments = {}
        self.iteration_checklist = {}
        self.iteration_extrainfo = {}
        self.iteration_outputfiles = {}
        self.iteration_success_percentage = {}
        self._iteration = 0
        self._stopping = False

        # list of actual check items
        self._checklist = []
        # dictionnary of possible values
        self._possiblechecklist = {}
        # populate checklist with all possible checkitems
        # initialize checklist to False
        self._populateChecklist()
        self._extrainfo = {}
        self._testrun = testrun

        if uuid == None:
            self.uuid = utils.acquire_uuid()
        else:
            self.uuid = uuid
        self.arguments["uuid"] = self.uuid

        self._outputfiles = kwargs.get("outputfiles", {})
        # creating default file names
        if self._testrun:
            self.create_temp_filenames(True)

        self._asynctimeoutid = 0
        self._testtimeoutid = 0
        # time at which events started
        self._asyncstarttime = 0
        self._teststarttime = 0
        # time at which the timeouts should occur,
        # we store this in order to modify timeouts while
        # running
        self._asynctimeouttime = 0
        self._testtimeouttime = 0

        # list of (monitor, monitorargs)
        self._monitors = []
        self._monitorinstances = []

        # see __test_arguments__ for details.
        self._expected_failure_patterns = kwargs.get('expected-failures', [])

        # dict containing (checkitem, True) for every expected failure that happened
        self._expected_failures = {}

        # dict containing (checkitem, explanation) for every failure that has
        # an explanation
        self._error_explanations = {}


    def create_temp_filenames(self, global_files):
        oflist = self.getFullOutputFilesList()
        for ofname in oflist.iterkeys():
            if global_files == oflist[ofname]["global"]:
                if not ofname in self._outputfiles or not global_files:
                    ofd, opath = self._testrun.get_temp_file(nameid=ofname)
                    debug("created temp file name '%s' for outputfile '%s' [%s]",
                          opath, ofname, self.uuid)
                    self._outputfiles[ofname] = opath
                    os.close(ofd)

    @classmethod
    def get_file(cls):
        """
        Returns the absolute path location of this test.

        This method MUST be copied in all subclasses that are not
        in the same module as its parent !
        """
        import os.path
        return os.path.abspath(cls.__file__)

    def __repr__(self):
        if self.uuid:
            return "< %s uuid:%s >" % (self.__class__.__name__, self.uuid)
        return "< %s id:%r >" % (self.__class__.__name__, id(self))

    def _populateChecklist(self):
        """ fill the instance checklist with default values """
        ckl = self.getFullCheckList()
        for key in ckl.keys():
            self._possiblechecklist[key] = False

    def _asyncSetupTimeoutCb(self):
        debug("async setup timeout for %r", self)
        now = time.time()
        if now < self._asynctimeouttime:
            debug("async setup timeout must have changed in the meantime")
            diff = int((self._asynctimeouttime - now) * 1000)
            self._asynctimeoutid = gobject.timeout_add(diff, self._asyncSetupTimeoutCb)
            return False
        self._asynctimeoutid = 0
        self.stop()
        return False

    def _testTimeoutCb(self):
        debug("timeout for %r", self)
        now = time.time()
        if now < self._testtimeouttime:
            debug("timeout must have changed in the meantime")
            diff = int((self._testtimeouttime - now) * 1000)
            self._testtimeoutid = gobject.timeout_add(diff, self._testTimeoutCb)
            return False
        self._testtimeoutid = 0
        self.stop()
        return False

    def run(self):
        # 1. setUp the test
        self._teststarttime = time.time()
        if not self.setUp():
            error("Something went wrong during setup !")
            self.stop()
            return False

        if self.__async_setup__:
            # the subclass will call start() on his own
            # put in a timeout check
            self._asynctimeouttime = time.time() + self._asynctimeout
            self._asynctimeoutid = gobject.timeout_add(self._asynctimeout * 1000,
                                                       self._asyncSetupTimeoutCb)
            return True

        # 2. Start it
        self.start()
        if not self.__async_test__:
            self.stop()

        return True

    def setUp(self):
        """
        Prepare the test, initialize variables, etc...

        Return True if you setUp didn't encounter any issues, else
        return False.

        If you implement this method, you need to chain up to the
        parent class' setUp() at the BEGINNING of your function without
        forgetting to take into account the return value.

        If your test does its setup asynchronously, set the
        __async_setup__ property of your class to True
        """
        # call monitors setup
        if not self._setUpMonitors():
            return False
        return True

    def _setUpMonitors(self):
        for monitor, monitorarg in self._monitors:
            if monitorarg == None:
                monitorarg = {}
            instance = monitor(self._testrun, self, **monitorarg)
            if not instance.setUp():
                return False
            self._monitorinstances.append(instance)
        return True

    def tearDownVmethod(self):
        """
        Virtual method for subclasses to implement teardown

        You should chain up to the parent function at the BEGINNING
        of your method
        """
        pass

    def tearDown(self):
        """
        Clear test

        Subclassed should not implement this method directly but rather
        the tearDownVmethod instead

        Your teardown MUST happen in a synchronous fashion.
        """

        # Tell monitors that we are starting the teardown process
        for instance in self._monitorinstances:
            instance.prepareTearDown()

        self.tearDownVmethod()

        stoptime = time.time()
        if self._asynctimeoutid:
            gobject.source_remove(self._asynctimeoutid)
            self._asynctimeoutid = 0
        if self._testtimeoutid:
            gobject.source_remove(self._testtimeoutid)
            self._testtimeoutid = 0
        for ofname, fname in list(self._outputfiles.iteritems()):
            if os.path.exists(fname):
                if not os.path.getsize(fname):
                    debug("removing empty file from outputfiles dictionnary")
                    os.remove(fname)
                    del self._outputfiles[ofname]
            else:
                debug("removing unexistent file from outputfiles dictionnary")
                del self._outputfiles[ofname]
        if self._teststarttime:
            debug("stoptime:%r , teststarttime:%r",
                  stoptime, self._teststarttime)
            self.extraInfo("test-total-duration",
                           int((stoptime - self._teststarttime) * 1000))

        # Finaly clear monitors
        for instance in self._monitorinstances:
            instance.tearDown()

        self.emit("done")

    def stop(self):
        """
        Stop the test
        Can be called by both the test itself AND external elements
        """
        if self._stopping:
            warning("we were already stopping !!!")
            return
        info("STOPPING %r" % self)
        self._stopping = True
        # if we still have the timeoutid, we didn't timeout
        notimeout = False
        if self._testtimeoutid:
            gobject.source_remove(self._testtimeoutid)
            self._testtimeoutid = 0
            notimeout = True
        self.validateChecklistItem("no-timeout", notimeout)
        self._stopMonitors()
        self.emit("stop", self._iteration)

        self.iteration_checklist[self._iteration] = self._checklist
        self.iteration_extrainfo[self._iteration] = self._extrainfo
        self.iteration_outputfiles[self._iteration] = self._outputfiles
        self.iteration_success_percentage[self._iteration] = self.getSuccessPercentage()

    def _stopMonitors(self):
        for monitorinstance in self._monitorinstances:
            if not monitorinstance.stop():
                info("Could not stop monitor %s", monitorinstance)
                continue

            ofiles =  monitorinstance.getIterationOutputFiles(self._iteration)
            if ofiles:
                self.iteration_outputfiles.update(ofiles)


    def start(self):
        """
        Starts the test.

        Only called by tests that implement asynchronous setUp
        """
        # if we were doing async setup, remove asyncsetup timeout
        self._stopping = False
        self._iteration = self._iteration + 1

        # Upon first start, we save checklist, etc so they can be copied
        # as base for each successive iteration, while keeping the state
        # acquired in setup
        self._startMonitors()
        if self._iteration == 1:
            self._base_checklist = self._checklist[:]
            self._base_extrainfo = self._extrainfo.copy()
            self._base_outputfiles = self._outputfiles.copy()
        self._checklist = self._base_checklist[:]
        self._extrainfo = self._base_extrainfo.copy()
        self._outputfiles = self._base_outputfiles.copy()

        self.create_temp_filenames(False)

        if self.__async_setup__:
            if self._asynctimeoutid:
                gobject.source_remove(self._asynctimeoutid)
                self._asynctimeoutid = 0
            curtime = time.time()
            self.extraInfo("test-setup-duration",
                           int((curtime - self._teststarttime) * 1000))
        self._running = True
        self.emit("start", self._iteration)
        self.validateChecklistItem("test-started")
        if self._iteration > 1:
            iteraction_checklist = self.getIterationCheckList(self._iteration - 1, False)
            for item, value in self.getFullCheckList().iteritems():
                if value.get("global", False):
                    for name, res in iteraction_checklist:
                        if item == name:
                            self.validateChecklistItem(name, res)
                            break

        # start timeout for test !
        self._testtimeouttime = time.time() + self._timeout
        self._testtimeoutid = gobject.timeout_add(self._timeout * 1000,
                                                  self._testTimeoutCb)
        self.test()

    def _startMonitors(self):
        for monitorinstance in self._monitorinstances:
            if not monitorinstance.start(self._iteration):
                info("Could not start monitor %s", monitorinstance)
                return False
        return True

    def test(self):
        """
        This method will be called at the beginning of the test
        """
        raise NotImplementedError


    ## Methods for tests to return information

    def validateChecklistItem(self, checkitem, validated=True, description = None):
        """
        Validate a checklist item in the checklist.
        checkitem is one of the keys of __test_checklist__
        validated is a boolean indicating whether that item should be
           validated or not.

        Called by the test itself
        """
        info("checklist item %s for item %r : %r" % (checkitem, self, validated))
        # check for valid checkitem
        if not checkitem in self._possiblechecklist:
            return
        # check to see if we don't already have it
        if checkitem in dict(self._checklist):
            return
        self._checklist.append((checkitem, bool(validated)))

        if not validated:
            if self.isExpectedFailure(checkitem, self._extrainfo):
                self._expected_failures[checkitem] = True
            if description and description != "":
                explanation = description
            else:
                explanation = self.processFailure(checkitem, self._extrainfo)
            if explanation is not None:
                self._error_explanations[checkitem] = explanation

        self.emit("check", checkitem, validated)

    def isExpectedFailure(self, checkitem, extra_info):
        return self.isExpectedResult(checkitem, self.FAILURE, extra_info)

    def isExpectedResult(self, checkitem, result, extra_info):
        for pattern in self._expected_failure_patterns:

            if checkitem not in pattern["results"]:
                continue

            if str(result) not in pattern["results"][checkitem]:
                if "None" in pattern["results"][checkitem]:
                    debug("This rule only matches skipped checks.")
                elif "0" in pattern["results"][checkitem]:
                    debug("This rule only matches failed checks.")
                else:
                    warning("This rule doesn't match any checks: %s", pattern)
                continue

            if "arguments" in pattern:
                for k, v in pattern["arguments"].items():
                    if k not in self.arguments:
                        break
                    if self.arguments[k] not in v:
                        break
                else:
                    return True
            else:
                return True

        return False

    def extraInfo(self, key, value):
        """
        Give extra information obtained while running the tests.

        If key was already given, the new value will override the value
        previously given for the same key.

        Called by the test itself
        """
        info("uuid:%s, key:%s, value:%r", self.uuid, key, value)
        self._extrainfo[key] = value
        self.emit("extra-info", key, value)

    ## Getters/Setters

    @classmethod
    def getClassFullCheckList(cls):
        """
        Returns the full test checklist. This is used to know all the
        possible check items for this instance, along with their description.
        """
        dc = {}
        for cl in cls.mro():
            if "__test_checklist__" in cl.__dict__:
                dc.update(cl.__test_checklist__)
            if cl == Test:
                break
        return dc

    @classmethod
    def getClassFullArgumentList(cls):
        """
        Returns the full list of arguments with descriptions.

        The format of the returned argument dictionnary is:
        key : argument name
        value : tuple of :
            * short description
            * default value
            * extended description (Can be None)
        """
        dc = {}
        for cl in cls.mro():
            if "__test_arguments__" in cls.__dict__:
                dc.update(cl.__test_arguments__)
            if cl == Test:
                break
        return dc

    @classmethod
    def getClassFullExtraInfoList(cls):
        """
        Returns the full list of extra info with descriptions.
        """
        dc = {}
        for cl in cls.mro():
            if "__test_extra_infos__" in cls.__dict__:
                dc.update(cl.__test_extra_infos__)
            if cl == Test:
                break
        return dc

    @classmethod
    def getClassFullOutputFilesList(cls):
        """
        Returns the full list of output files with descriptions.
        """
        dc = {}
        for cl in cls.mro():
            if "__test_output_files__" in cls.__dict__:
                dc.update(cl.__test_output_files__)
            if cl == Test:
                break
        return dc

    def getIterationCheckList(self, iteration, warn=True):
        """
        Returns the instance checklist as a list of tuples of:
        * checkitem name
        * value indicating whether the success of that checklist item
           That value can be one of: SKIPPED, SUCCESS, FAILURE, EXPECTED_FAILURE
        """
        allk = self.getFullCheckList().keys()
        unexpected_failures = []

        def to_enum(key, val):
            if val:
                return self.SUCCESS
            elif self._expected_failures.get(key, False):
                return self.EXPECTED_FAILURE
            else:
                unexpected_failures.append(key)
                return self.FAILURE

        d = dict((k, to_enum(k, v)) for k, v in self.iteration_checklist[iteration])
        d["no-unexpected-failures"] = 1

        for k in allk:
            if k not in d:
                if self.isExpectedResult(k, self.SKIPPED, self.iteration_extrainfo[iteration]):
                    d[k] = self.EXPECTED_FAILURE
                else:
                    unexpected_failures.append(k)
                    d[k] = self.SKIPPED

        if unexpected_failures:
            if warn:
                warning("The following tests failed unexpectedly: %s",
                        unexpected_failures)
            d["no-unexpected-failures"] = 0

        return d.items()

    def prepareIteration(self,args):
        # arguments are prepared before starting
        self.iteration_arguments[self._iteration + 1] = args

    def getIterationArguments(self,iteration):
        """
        Returns the list of arguments for the given test
        """
        validkeys = self.getFullArgumentList()
        # Hide expected-failures from the storage backend.
        validkeys.pop("expected-failures", [])
        res = {}
        if not iteration in self.iteration_arguments:
            return res
        args = self.iteration_arguments[iteration]
        for key in args.iterkeys():
            if key in validkeys:
                res[key] = args[key]
        return res

    def getIterationSuccessPercentage(self,iteration):
        return self.iteration_success_percentage[iteration]

    def getSuccessPercentage(self):
        """
        Returns the success rate of this instance as a float
        """
        total_nbitems = 0
        total_nbsucc = 0
        for iteration in self.iteration_checklist:
            ckl = self.getIterationCheckList(iteration)
            nbitems = len(self._possiblechecklist)
            nbsucc = len([item for item, val in ckl if val >= 1])
            total_nbitems = total_nbitems + nbitems
            total_nbsucc = total_nbsucc + nbsucc
        if total_nbitems == 0:
            return 0.0
        return (100.0 * total_nbsucc) / total_nbitems

    def getIterationExtraInfo(self,iteration):
        """
        Returns the extra-information dictionnary
        """
        return self.iteration_extrainfo[iteration]

    def getOutputFiles(self):
        """
        Returns the output files generated by the test
        """
        return self._outputfiles

    def getIterationOutputFiles(self,iteration):
        """
        Returns the output files generated by the test
        """
        return self.iteration_outputfiles[iteration]

    def getErrorExplanations(self):
        """
        Returns dict of error explanations for failed check items. Only
        the failed items that have some explanation are present in the
        dict.

        key : name of the failed check item
        value : error explanation
        """
        return self._error_explanations

    def getTimeout(self):
        """
        Returns the currently configured timeout
        """
        return self._timeout

    def setTimeout(self, timeout):
        """
        Set the timeout period for running this test in seconds.
        Returns True if the timeout could be modified, else False.
        """
        debug("timeout : %d", timeout)
        if self._testtimeoutid:
            debug("updating timeout/timeouttime")
            self._testtimeouttime = self._testtimeouttime - self._timeout + timeout
        self._timeout = timeout
        return True

    def getAsyncSetupTimeout(self):
        """
        Returns the currently configured async setup timeout
        """
        return self._asynctimeout

    def setAsyncSetupTimeout(self, timeout):
        """
        Set the timeout period for asynchronous test to startup in
        seconds.
        Returns True if the timeout could be modified, else False.
        """
        debug("timeout : %d", timeout)
        if self._asynctimeoutid:
            debug("updating timeout/timeouttime")
            self._asynctimeouttime -= (self._asynctimeout - timeout)
        self._asynctimeout = timeout
        return True

    def ping(self):
        """
        Reset any pending timeouts because the test is still alive
        """
        if self._asynctimeoutid:
            self._asynctimeouttime = time.time() + self._asynctimeout
        if self._testtimeouttime:
            self._testtimeouttime = time.time() + self._timeout

    def addMonitor(self, monitor, monitorargs=None):
        """
        Add a monitor to this test instance.

        Checks will be done to ensure that the monitor can be applied
        on this instance.

        Returns True if the monitor was applied succesfully.
        """
        debug("monitor:%r, args:%r", monitor, monitorargs)
        # check if monitor is valid
        if not isinstance(self, monitor.__applies_on__):
            warning("The given monitor cannot be applied on this test")
            return False
        self._monitors.append((monitor, monitorargs))

    def processFailure(self, checkitem, extra_info):
        """
        Process the failure and return a human-readable description
        of why it happened (string).

        By default, returns the likely error explanation from
        __test_checklist_errors__. Test subclasses can override
        it to provide detailed processing.

        Returns None if no explanation is available.
        """
        return self.getFullCheckList().get(checkitem, None).get("likely_error", None)

    def getFullCheckList(self):
        raise NotImplementedError

    def getTestName(self):
        return self.__test_name__

    def getTestDescription(self):
        return self.__test_description__

    def getTestFullDescription(self):
        return self.__test_full_description__

# For compatibility:
from insanity.dbustest import DBusTest, PythonDBusTest
