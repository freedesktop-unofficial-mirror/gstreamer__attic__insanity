# GStreamer QA system
#
#       testrun.py
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
Test runs

A TestRun is the execution of one or more tests/scenarios with various
arguments.
It will also collect the state of the environment.

The smallest TestRun is a single test without any arguments nor any
monitors.

Tests have access to the TestRun within which they are being executed
so they can look for results of other tests.

Access to the TestRun from test instances will be possible via DBus IPC.
"""

import gobject
import time
import dbus.gobject_service
import tempfile
import os
from insanity.log import error, warning, debug, info
from insanity.test import PythonDBusTest
from insanity.arguments import Arguments
import insanity.environment as environment
import insanity.dbustools as dbustools

from xml.etree.ElementTree import parse
from insanity.utils import get_test_metadata

from insanity.monitor import getMonitorClass
from insanity.generator import Generator

# Not directly used but necessary for eval()
from insanity.generators.filesystem import FileSystemGenerator, URIFileSystemGenerator
from insanity.generators.playlist import PlaylistGenerator
from insanity.generators.external import ExternalGenerator
from insanity.generators.constant import ConstantGenerator, ConstantListGenerator

##
## TODO/FIXME
##
## Add possibility to add/modify/remove env variables
##   This will be needed to run test with different environments
##   WITHOUT having to restart the daemon.


class TestRun(gobject.GObject):
    """
    A TestRun is the execution of one or more tests/scenarios with various
    arguments.
    It will also collect the state of the environment.

    The smallest TestRun is a single test without any arguments nor any
    monitors.

    Tests have access to the TestRun within which they are being executed
    so they can look for results of other tests.

    Access to the TestRun from test instances will be possible via DBus IPC.
    """
    __gsignals__ = {
        "start": (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   ()),
        "done": (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   ()),
        "aborted": (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   ( )),
        # a test started/ended
        # Warning, it is not automatically a SingleTest
        "single-test-done": (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE,
                              (gobject.TYPE_PYOBJECT, )),
        "single-test-start": (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE,
                              (gobject.TYPE_PYOBJECT, gobject.TYPE_INT)),
        "single-test-stop": (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE,
                              (gobject.TYPE_PYOBJECT, gobject.TYPE_INT)),

        # new-remote-test (uuid)
        #  emitted when a new test has appeared on the private bus
        "new-remote-test": (gobject.SIGNAL_RUN_LAST,
                             gobject.TYPE_NONE,
                             (gobject.TYPE_STRING, )),
        "removed-remote-test": (gobject.SIGNAL_RUN_LAST,
                                 gobject.TYPE_NONE,
                                 (gobject.TYPE_STRING, ))
        }

    def __init__(self, maxnbtests=1, workingdir=None, env=None, clientid=None):
        """
        maxnbtests : Maximum number of tests to run simultaneously in each batch.
        workingdir : Working directory (default : getcwd() + /workingdir/)
        env : extra environment variables
        """
        gobject.GObject.__init__(self)
        # dbus
        self._bus = None
        self._bus_address = None
        self._dbusobject = None
        self._dbusiface = None
        self._setupPrivateBus()

        self._tests = [] # list of (test, arguments, monitors, kwargs)
        self._storage = None
        self._currenttest = None
        self._currentmonitors = None
        self._currentkwargs = None
        self._currentarguments = None
        self._runninginstances = []
        self._maxnbtests = maxnbtests
        self._starttime = None
        self._stoptime = None
        self._clientid = clientid
        # disambiguation
        # _environment are the environment information
        # _environ are the environment variables (env)
        self._environment = {}
        self._env = os.environ.copy()
        if env:
            self._env.update(env)
        self._running = False
        self.setWorkingDirectory(workingdir or os.path.join(os.getcwd(), "workingdir"))

    ## PUBLIC API

    def run(self):
        """
        Start executing the tests.
        """
        if self._running:
            error("TestRun is already running")
            return
        self._collectEnvironment()

    def abort(self):
        """
        Abort the tests execution.
        """
        # TODO : fill
        for test in self._runninginstances:
            test.stop()
        self.emit("aborted")

    def setStorage(self, storage):
        """
        Use the given storage for this TestRun
        """
        self._storage = storage

    def addTest(self, test, arguments, monitors=None, kwargs={}):
        """
        Adds test with the given arguments (or generator) and monitors
        to the list of tests to be run

        monitors are a list of tuples containing:
        * the monitor class
        * (optional) the arguments to use on that monitor
        """
        #if not isinstance(test, type) and not issubclass(test, Test):
        #    raise TypeError("Given test is not a Test object !")
        # arguments NEED to be an Arguments object or a dictionnary
        if isinstance(arguments, dict):
            # convert dictionnary to Arguments
            info("Creating Arguments for %r" % arguments)
            arguments = Arguments(**arguments)
        elif not isinstance(arguments, Arguments):
            raise TypeError("Test arguments need to be of type Arguments or dict")

        self._tests.append((test, arguments, monitors, kwargs))

    def getEnvironment(self):
        """
        Returns the environment information of this testrun as a
        dictionnary.
        """
        return self._environment

    ## PRIVATE API

    def _setupPrivateBus(self):
        self._bus = dbustools.get_private_session_bus()
        self._bus_address = dbustools.get_private_bus_address()
        self._dbusobject = self._bus.get_object("org.freedesktop.DBus",
                                                "/org/freedesktop/DBus")
        self._dbusiface = dbus.Interface(self._dbusobject,
                                         "org.freedesktop.DBus")
        self._dbusiface.connect_to_signal("NameOwnerChanged",
                                          self._dbusNameOwnerChangedSignal)

    def _dbusNameOwnerChangedSignal(self, name, oldowner, newowner):
        # we only care about connections named net.gstreamer.Insanity.Test.xxx
        info("name:%s , oldowner:%s, newowner:%s" % (name, oldowner, newowner))
        if not name.startswith("net.gstreamer.Insanity.Test.Test"):
            return
        # extract uuid
        uuid = name.rsplit('.Test', 1)[-1]
        if newowner == "":
            self.emit("removed-remote-test", uuid)
        elif oldowner == "":
            self.emit("new-remote-test", uuid)

    def _collectEnvironment(self):
        """
        Collect the environment settings, parameters, variables,...
        """
        environment.collectEnvironment(self._env, self._gotEnvironment)

    def _gotEnvironment(self, resdict):
        info("Got environment %r", resdict)
        self._environment = resdict
        self.emit("start")
        self._starttime = int(time.time())
        self._storage.startNewTestRun(self, self._clientid)
        self._runNextBatch()

    def _singleTestStart(self, test, iteration):
        info("test %r started (%d)", test, iteration)
        self.emit("single-test-start", test, iteration)
        self._storage.newTestStarted(self, test, iteration)

    def _singleTestStop(self, test, iteration):
        info("test %r stopped (%d)", test, iteration)
        self.emit("single-test-stop", test, iteration)
        self._storage.newTestStopped(self, test, iteration)

    def _singleTestDone(self, test):
        info("test %r done, success rate %02f%%",
             test, test.getSuccessPercentage())
        self.emit("single-test-done", test)
        # FIXME : Improvement : disconnect all signals from that test
        if test in self._runninginstances:
            self._runninginstances.remove(test)
        self._storage.newTestFinished(self, test)
        self._runNextBatch()

    def _singleTestCheck(self, test, check, validate):
        pass

    def _runNext(self):
        """ Run the next test+arg+monitor combination """
        if len(self._runninginstances) >= self._maxnbtests:
            warning("We were already running the max number of tests")
            return False

        # grab the next arguments
        testclass = self._currenttest
        monitors = self._currentmonitors
        kwargs= self._currentkwargs

        # create test with arguments
        debug("Creating test %r with arguments %r" % (testclass, kwargs))
        test = PythonDBusTest(testrun=self, bus=self._bus,
                         bus_address=self._bus_address,
                         metadata = testclass,
                         test_arguments = self._currentarguments,
                         **kwargs)
#        test = testclass(testrun=self, bus=self._bus,
#                         bus_address=self._bus_address,
#                         **kwargs)
        if monitors:
            for monitor in monitors:
                test.addMonitor(*monitor)

        test.connect("start", self._singleTestStart)
        test.connect("stop", self._singleTestStop)
        test.connect("done", self._singleTestDone)
        test.connect("check", self._singleTestCheck)

        # start test
        allok = test.run()
        if allok:
            # add instance to running tests
            self._runninginstances.append(test)

        warning("Just added a test %d/%d", len(self._runninginstances), self._maxnbtests)
        # if we can still create a new test, call ourself again
        if len(self._runninginstances) < self._maxnbtests:
            warning("still more test to run (current:%d/max:%d)",
                    len(self._runninginstances), self._maxnbtests)
            gobject.idle_add(self._runNextBatch)
        return False

    def _runNextBatch(self):
        """ Runs the next test batch """
        if len(self._tests) == 0:
            # if nothing left, stop
            info("No more tests batch to run, we're done")
            self._stoptime = int(time.time())
            self._storage.endTestRun(self)
            self._running = False
            self.emit("done")
            return False

        info("Getting next test batch")
        # pop out the next batch
        test, args, monitors, kwargs = self._tests.pop(0)
        self._currenttest = test
        self._currentmonitors = monitors
        self._currentarguments = args
        self._currentkwargs = kwargs

        info("Current test : %r" % test)
        info("Current monitors : %r" % monitors)
        info("Current arguments : %r" % args)

        # and run the first one of that batch
        self._runNext()
        return False

    def getCurrentBatchPosition(self):
        """
        Returns the position (index) in the current batch.
        """
        if self._currentarguments:
            return self._currentarguments.current()
        return 0

    def getCurrentBatchLength(self):
        """
        Returns the size of the current batch.
        """
        if self._currentarguments:
            return len(self._currentarguments)
        return 0

    def getWorkingDirectory(self):
        """
        Returns the currently configured working directory for this
        TestRun.
        """
        return self._workingdir

    def setWorkingDirectory(self, workdir):
        """
        Change the working directory. This can only be called when the
        TestRun isn't running.
        Creates the directories if they are not present.

        Returns True if the working directory was properly changed.
        Returns False if self is running.
        """
        if self._running:
            return False
        debug("Changing workdir to %s", workdir)
        self._workingdir = workdir
        self._outputdir = os.path.join(self._workingdir, "outputfiles")
        # ensure directories exist
        if not os.path.exists(self._outputdir):
            os.makedirs(self._outputdir)
        return True

    def get_temp_file(self, nameid='', suffix='', category="insanity-output"):
        """
        Creates a new temporary file in a secure fashion, guaranteeing
        it will be unique and only accessible from this user.

        If specified, the nameid will be inserted in the unique name.
        If specified, the suffix will be used

        The returned file will NEVER be removed or closed, the caller
        should take care of that.

        Return (filepath, fileobject) for the newly created file
        """
        # we create temporary files in a specified directory
        prefix = "%s-%s" % (category, nameid)
        return tempfile.mkstemp(prefix=prefix,
                                suffix=suffix,
                                dir=self._outputdir)


gobject.type_register(TestRun)


class ListTestRun(TestRun):
    """
    Convenience class to specify a list of tests that will be run
    with the same arguments/generator and monitor(s).

    Parameters:
    * fatal-failure : boolean (default:False)
    If set to True, a test will only be run if the previous test for
    the same argument has completed successfully.
    """

    def __init__(self, tests, arguments, monitors=None, *args, **kwargs):
        TestRun.__init__(self, *args, **kwargs)
        for test in tests:
            self.addTest(test, arguments, monitors)


class XmlTestRun(TestRun):
    """
    Convenience class to create a list of tests from an xml file.

    Example of an xml file content:

    <insanity-tests>
        <monitors>
          <monitor name="gdb-monitor" type="GDBMonitor" args="'gdb-script' : '$gdbscriptfile'" />
        </monitors>
        <test name="exmple-test">
            <occurrence>
                <argument name="argument-name" type="GeneratorClasseName" args="List of argument to pass to the GeneratorClasseName constructor">
                <argument name="decoder-name" type="ConstantGenerator" args="constant='theoradec'"/>
            </occurrence>
            <occurrence>
              <argument name="location" type="ExternalGenerator" args="command='find $basedir -xtype f -name *Vorbis*', max_length=30" />
              <argument name="decoder-name" type="ConstantGenerator" args="constant='vorbisdec'" />
            </occurrence>
        </test>
        <test name="another-test">
            <!-- Some other tests -->
        </test>
    </insanity-tests>
    """

    def __init__(self, xmlpath, workingdir, substitutes={}):
        """
        Creates a testrun base on the content of @xmlpath
        """
        TestRun.__init__(self, maxnbtests=1, workingdir=workingdir)
        self.substitutes = substitutes
        self._root = parse(xmlpath)
        self._fillTestRunFromXml()

    def _applySubstitutes(self, string):
        for old, new in self.substitutes.iteritems():
            if old in string:
                string = string.replace(old, new)
        return string

    def _getGenerator(self, node):
        str_instantiator = node.attrib["type"] + "(" + node.attrib["args"] + ")"
        str_instantiator = self._applySubstitutes(str_instantiator)
        try:
            debug ("Creating %s", str_instantiator)
            gen = eval (str_instantiator)
        except Exception, e:
            error("Could not instantiate %s, reason: %s",
                    str_instantiator, e)
            return None

        if not isinstance(gen, Generator):
            error("%s is not a generator type", arg.attrib["type"])
            return None

        return gen

    def _fillTestRunFromXml(self):

        standard_monitor = []
        monitorsn = self._root.find("monitors")
        if monitorsn is not None:
            for monitor in monitorsn.findall("monitor"):
                standard_monitor.append((getMonitorClass(monitor.attrib["type"]),
                            eval('{' + monitor.attrib["args"] + '}')))

        for testn in self._root.findall("test"):
            monitors = [mon for mon in standard_monitor]
            monitorsn = testn.find("monitors")
            if monitorsn is not None:
                for monitor in monitorsn.findall("monitor"):
                    monitors.append((getMonitorClass(self._applySubstitutes (monitor.attrib["type"])),
                                eval('{' + self._applySubstitutes (monitor.attrib["args"]) + '}')))

            for occ in testn.findall("occurrence"):
                test_args = []
                test = get_test_metadata(testn.attrib["name"])
                test_arguments = {}
                test_kwargs = {}
                for arg in occ.findall("argument"):
                    gen = self._getGenerator(arg)
                    if not gen:
                        break

                    test_arguments[arg.attrib["name"]] = gen

                e_failures = []
                for expected_failure in occ.findall("expected-failures"):
                    checkitems = expected_failure.findall("checkitem")
                    efail = {}
                    results = {}
                    for item in checkitems:
                        results[item.attrib["name"]] = item.attrib['values']

                    efail["results"] = results

                    args = expected_failure.findall("arguments")
                    if args:
                        arguments = {}
                        for arg in args:
                            gen = self._getGenerator(arg)
                            vals = gen.generate()
                            arguments[item.attrib['name']] = vals
                        efail["arguments"] = results

                    e_failures.append(efail)

                if e_failures:
                    test_kwargs['expected-failures'] = e_failures
                try:
                    self.addTest(test, arguments=test_arguments, monitors=monitors, kwargs=test_kwargs)
                except Exception, e:
                    warning("Could not add %s with arguments %s and montors %s. Reason %s",
                        test, test_arguments, monitors, e)


def single_test_run(test, arguments=[], monitors=None):
    """
    Convenience function to create a TestRun for a single test
    """
    tr = TestRun()
    tr.addTest(test, arguments, monitors)
    return tr
