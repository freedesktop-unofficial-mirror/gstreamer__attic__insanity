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
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

"""
DBus Test Class
"""

import os
import sys
import subprocess
import resource
import signal
import time
import dbus
import dbus.gobject_service
from insanity.test import Test
from insanity.dbustools import unwrap
from insanity.log import error, warning, debug, info, exception
import insanity.utils as utils
import gobject

class DBusTest(Test, dbus.service.Object):
    """
    Class for tests being run in a separate process

    DBus is the ONLY IPC system used for getting results from remote
    tests.
    """

    __test_name__ = """dbus-test"""

    __test_description__ = """Base class for distributed tests using DBUS"""

    __test_checklist__ = {
    "dbus-process-spawned":
    "The DBus child process spawned itself",
    "dbus-process-connected":
    "The DBus child process connected properly to the private Bus",
    "remote-instance-created":
    "The remote version of this test was created properly",
    "subprocess-exited-normally":
    "The subprocess returned a null exit code (success)"
    }

    __test_extra_infos__ = {
    "subprocess-return-code":"The exit value returned by the subprocess",
    "subprocess-spawn-time":"How long it took to spawn the subprocess (in milliseconds)",
    "remote-instance-creation-delay":"How long it took to create the remote instance (in milliseconds)",
    "cpu-load" : "CPU load in percent (can exceed 100% on multi core systems)"
    }

    __async_setup__ = True
    ## Needed for dbus
    __metaclass__ = dbus.gobject_service.ExportedGObjectType

    def __init__(self, bus=None, bus_address="", proxy=True,
                 env=None, *args, **kwargs):
        """
        bus is the private DBusConnection used for testing.
        bus_address is the address of the private DBusConnection used for testing.

        You need to provide at least bus or bus_address.

        If proxy is set to True, this instance will be the proxy to
        the remote DBus test.
        If proxy is set to False, this instance will be the actual test
        to be run.
        """
        Test.__init__(self, bus_address=bus_address,
                      proxy=proxy, *args, **kwargs)
        self._isproxy = proxy
        if (bus == None) and (bus_address == ""):
            raise Exception("You need to provide at least a bus or bus_address")
        self._bus = bus
        self._bus_address = bus_address

        self._remote_tearing_down = False

        if self._isproxy:
            if self._testrun:
                sid = self._testrun.connect("new-remote-test",
                                            self._newRemoteTest)
                self._newremotetestsid = sid
                sid = self._testrun.connect("removed-remote-test",
                                            self._removedRemoteTest)
                self._testrunremovedtestsigid = sid
            self._process = None
            self._processpollid = 0
            self._remoteinstance = None
            # return code from subprocess
            self._returncode = None
            # variables for remote launching, can be modified by monitors
            self._stdin = None
            self._stdout = None
            self._stderr = None
            self._preargs = []
            self._environ = env or {}
            self._environ.update(os.environ.copy())
            self._subprocessspawntime = 0
            self._subprocessconnecttime = 0
            self._pid = 0
        else:
            self.rusage_start = None
            self._remotetimeoutid = 0
            self._remotetimedout = False
            # connect to bus
            self.objectpath = "/net/gstreamer/Insanity/Test/Test%s" % self.uuid
            dbus.service.Object.__init__(self, conn=self._bus,
                                         object_path=self.objectpath)
    # Test class overrides

    def test(self):
        info("uuid:%s proxy:%r", self.uuid, self._isproxy)
        if self._isproxy:
            self.callRemoteTest()
        else:
            # really do the test
            raise Exception("I shouldn't be called ! I am the remote test !")

    def validateStep(self, checkitem, validate=True):
        info("uuid:%s proxy:%r checkitem:%s : %r", self.uuid,
             self._isproxy, checkitem, validate)
        if self._isproxy:
            Test.validateStep(self, checkitem, validate)
        else:
            self.remoteValidateStepSignal(checkitem, validate)

    def extraInfo(self, key, value):
        info("uuid:%s proxy:%r", self.uuid, self._isproxy)
        if self._isproxy:
            Test.extraInfo(self, key, value)
        else:
            try:
                self.remoteExtraInfoSignal(key, value)
            except:
                error("Error signaling extra info %r : %r", key, value)


    def setUp(self):
        info("uuid:%s proxy:%r", self.uuid, self._isproxy)
        if Test.setUp(self) == False:
            return False

        if self._isproxy:
            # get the remote launcher
            pargs = self._preargs
            pargs.extend(self.get_remote_launcher_args())

            cwd = self._testrun.getWorkingDirectory()

            self._environ["PRIVATE_DBUS_ADDRESS"] = self._bus_address
            info("Setting PRIVATE_DBUS_ADDRESS : %r" % self._bus_address)
            info("bus:%r" % self._bus)

            # spawn the other process
            info("opening %r" % pargs)
            info("cwd %s" % cwd)
            try:
                self._subprocessspawntime = time.time()
                self._process = subprocess.Popen(pargs,
                                                 stdin = self._stdin,
                                                 stdout = self._stdout,
                                                 stderr = self._stderr,
                                                 env=self._environ,
                                                 cwd=cwd)
                self._pid = self._process.pid
            except:
                exception("Error starting the subprocess command ! %r", pargs)
                self.validateStep("dbus-process-spawned", False)
                return False
            debug("Subprocess created successfully [pid:%d]", self._pid)

            self.validateStep("dbus-process-spawned")
            # add a poller for the proces
            self._processpollid = gobject.timeout_add(500, self._pollSubProcess)
            # Don't forget to set a timeout for waiting for the connection
        else:
            # remote instance setup
            # self.remoteSetUp()
            pass
        return True

    def tearDown(self):
        info("uuid:%s proxy:%r", self.uuid, self._isproxy)
        if self._isproxy:
            # FIXME : tear down the other process gracefully
            #    by first sending it the termination remote signal
            #    and then checking it's killed
            try:
                self.callRemoteStop()
            finally:
                if self._testrun:
                    if self._newremotetestsid:
                        self._testrun.disconnect(self._newremotetestsid)
                        self._newremotetestsid = 0
                    if self._testrunremovedtestsigid:
                        self._testrun.disconnect(self._testrunremovedtestsigid)
                        self._testrunremovedtestsigid = 0
                if self._processpollid:
                    gobject.source_remove(self._processpollid)
                    self._processpollid = 0
                if self._process:
                    # double check it hasn't actually exited
                    # give the test up to one second to exit
                    tries = 10
                    while self._returncode is None and not tries == 0:
                        time.sleep(0.1)
                        self._returncode = self._process.poll()
                        tries -= 1
                    if self._returncode is None:
                        info("Process isn't done yet, terminating it")
                        os.kill(self._process.pid, signal.SIGTERM)
                        time.sleep(1)
                        self._returncode = self._process.poll()
                    if self._returncode is None:
                        info("Process did not terminate, killing it")
                        os.kill(self._process.pid, signal.SIGKILL)
                        time.sleep(1)
                        self._returncode = self._process.poll()
                    if self._returncode is None:
                        # Probably turned into zombie process, something is
                        # really broken...
                        info("Process did not exit after SIGKILL")
                    self._process = None
                if not self._returncode is None:
                    info("Process returned %d", self._returncode)
                    self.validateStep("subprocess-exited-normally", self._returncode == 0)
                    self.extraInfo("subprocess-return-code", self._returncode)
        else:
            self.remoteTearDown()
        Test.tearDown(self)

    def stop(self):
        info("uuid:%s proxy:%r", self.uuid, self._isproxy)
        if self._isproxy:
            Test.stop(self)
        else:
            self.tearDown()
            self.remoteStopSignal()

    def get_remote_launcher_args(self):
        """
        Subclasses should return the name and arguments of the remote
        process
        Ex : [ "/path/to/myapp", "--thisoption" ]
        """
        raise NotImplementedError

    ## Subprocess polling
    def _pollSubProcess(self):
        info("polling subprocess %r", self.uuid)
        if not self._process:
            info("process left, stopping looping")
            return False
        res = self._process.poll()
        # None means the process hasn't terminated yet
        if res == None:
            info("process hasn't stopped yet")
            return True
        # Positive value is the return code of the terminated
        #   process
        # Negative values means the process was killed by signal
        info("subprocess returned %r" % res)
        self._returncode = res
        self._process = None
        self._processpollid = 0
        self.stop()
        return False


    ## void handlers for remote DBUS calls
    def _voidRemoteCallBackHandler(self):
        pass

    def _voidRemoteErrBackHandler(self, exc, caller=None, fatal=True):
        warning("%r : %s", caller, exc)
        if fatal:
            warning("FATAL : aborting test")
            # a fatal error happened, DIVE DIVE DIVE !
            self.stop()

    def _voidRemoteTestErrBackHandler(self, exc):
        self._voidRemoteErrBackHandler(exc, "remoteTest")

    def _voidRemoteSetUpErrBackHandler(self, exc):
        self._voidRemoteErrBackHandler(exc, "remoteSetUp")

    def _voidRemoteStopErrBackHandler(self, exc):
        self._voidRemoteErrBackHandler(exc, "remoteStop", fatal=False)

    def _voidRemoteTearDownErrBackHandler(self, exc):
        self._voidRemoteErrBackHandler(exc, "remoteTearDown", fatal=False)

    ## Proxies for remote DBUS calls
    def callRemoteTest(self):
        # call remote instance "remoteTest()"
        if not self._remoteinstance:
            return
        self._remoteinstance.remoteTest(reply_handler=self._voidRemoteCallBackHandler,
                                        error_handler=self._voidRemoteTestErrBackHandler)

    def callRemoteSetUp(self):
        # call remote instance "remoteSetUp()"
        if not self._remoteinstance:
            return
        rephandler = self._voidRemoteCallBackHandler
        errhandler = self._voidRemoteSetUpErrBackHandler
        self._remoteinstance.remoteSetUp(reply_handler=rephandler,
                                         error_handler=errhandler)

    def callRemoteStop(self):
        # call remote instance "remoteStop()"
        if not self._remoteinstance:
            return
        self._remoteinstance.remoteStop(reply_handler=self._voidRemoteCallBackHandler,
                                        error_handler=self._voidRemoteStopErrBackHandler)

    def callRemoteTearDown(self):
        # call remote instance "remoteTearDown()"
        if not self._remoteinstance:
            return
        rephandler = self._voidRemoteCallBackHandler
        errhandler = self._voidRemoteTearDownErrBackHandler
        self._remoteinstance.remoteTearDown(reply_handler=rephandler,
                                            error_handler=errhandler)

    ## callbacks from remote signals
    def _remoteReadyCb(self):
        info("%s", self.uuid)
        # increment proxy timeout by 5s
        self._timeout += 5
        self.start()

    def _remoteStopCb(self):
        info("%s", self.uuid)
        self.stop()

    def _remoteValidateStepCb(self, step, validate):
        info("%s step:%s : %r", self.uuid, step, validate)
        self.validateStep(unwrap(step), validate)

    def _remoteExtraInfoCb(self, key, value):
        info("%s key:%s value:%r", self.uuid, key, value)
        self.extraInfo(unwrap(key), unwrap(value))

    ## Remote DBUS calls
    def _remoteTestTimeoutCb(self):
        debug("%s", self.uuid)
        self.validateStep("no-timeout", False)
        self.remoteTearDown()
        self._remotetimeoutid = 0
        return False

    @dbus.service.method(dbus_interface="net.gstreamer.Insanity.Test",
                         in_signature='', out_signature='')
    def remoteTest(self):
        """
        Remote-side test() method.

        Subclasses should implement this method and chain up to the parent
        remoteTest() method at the *beginning* of their implementation.
        """
        info("%s", self.uuid)
        # add a timeout
        self._remotetimeoutid = gobject.timeout_add(self._timeout * 1000,
                                                    self._remoteTestTimeoutCb)

    @dbus.service.method(dbus_interface="net.gstreamer.Insanity.Test",
                         in_signature='', out_signature='')
    def remoteSetUp(self):
        """
        Remote-side setUp() method.

        Subclasses should implement this method and chain up to the parent
        remoteSetUp() method at the *end* of their implementation.
        """
        info("%s", self.uuid)

        usage = resource.getrusage (resource.RUSAGE_SELF)
        self.rusage_start = (time.time (), usage.ru_utime, usage.ru_stime,)

        # if not overriden, we just emit the "ready" signal
        self.remoteReadySignal()

    @dbus.service.method(dbus_interface="net.gstreamer.Insanity.Test",
                         in_signature='', out_signature='')
    def remoteStop(self):
        info("%s", self.uuid)
        # because of being asynchronous, we call remoteTearDown first
        self.tearDown()
        Test.stop(self)

    @dbus.service.method(dbus_interface="net.gstreamer.Insanity.Test",
                         in_signature='', out_signature='')
    def remoteTearDown(self):
        """
        Remote-side tearDown() method.

        Subclasses wishing to clean up their tests or collect information to
        send at the end, should implement this in their subclass and chain up
        to the parent remoteTearDown() at the *beginning of their
        implementation.

        If the parent method returns False, return False straight-away
        """
        if self._remote_tearing_down:
            return False
        self._remote_tearing_down = True
        info("%s remoteTimeoutId:%r", self.uuid, self._remotetimeoutid)

        if self.rusage_start:
            usage = resource.getrusage (resource.RUSAGE_SELF)
            rusage_end = (time.time (), usage.ru_utime, usage.ru_stime,)
            rusage_diffs = [end - start for start, end in zip(self.rusage_start, rusage_end)]
            real_time, user_time, system_time = rusage_diffs
            if real_time:
                cpu_load = float(user_time + system_time) / real_time * 100.
                self.extraInfo("cpu-load", int(cpu_load))

        # remote the timeout
        if self._remotetimeoutid:
            gobject.source_remove(self._remotetimeoutid)
            self._remotetimedout = False
            self._remotetimeoutid = 0
        self.validateStep("no-timeout", not self._remotetimedout)
        return True

    ## Remote DBUS signals
    @dbus.service.signal(dbus_interface="net.gstreamer.Insanity.Test",
                         signature='')
    def remoteReadySignal(self):
        info("%s", self.uuid)

    @dbus.service.signal(dbus_interface="net.gstreamer.Insanity.Test",
                         signature='')
    def remoteStopSignal(self):
        info("%s", self.uuid)

    @dbus.service.signal(dbus_interface="net.gstreamer.Insanity.Test",
                         signature='')
    def remoteStartSignal(self):
        info("%s", self.uuid)

    @dbus.service.signal(dbus_interface="net.gstreamer.Insanity.Test",
                         signature='sb')
    def remoteValidateStepSignal(self, step, validate):
        info("%s %s %s", self.uuid, step, validate)

    @dbus.service.signal(dbus_interface="net.gstreamer.Insanity.Test",
                         signature='sv')
    def remoteExtraInfoSignal(self, name, data):
        info("%s %s : %r", self.uuid, name, data)

    ## DBUS Signals for proxies

    def _newRemoteTest(self, testrun, uuid):
        if not uuid == self.uuid:
            return

        info("%s our remote counterpart has started", self.uuid)
        self.validateStep("dbus-process-connected")
        self._subprocessconnecttime = time.time()
        delay = self._subprocessconnecttime - self._subprocessspawntime
        self.extraInfo("subprocess-spawn-time", int(delay * 1000))
        # we need to give the remote process the following information:
        # * filename where the Test class is located (self.get_file())
        # * class name (self.__class__.__name__)
        # * the arguments (self.arguments) + proxy=True
        rname = "net.gstreamer.Insanity.Test.Test%s" % self.uuid
        rpath = "/net/gstreamer/Insanity/Test/RemotePythonRunner%s" % self.uuid
        # get the proxy object to our counterpart
        remoteobj = self._bus.get_object(rname, rpath)
        debug("Got remote runner object %r" % remoteobj)
        # call createTestInstance()
        remoterunner = dbus.Interface(remoteobj,
                                      "net.gstreamer.Insanity.RemotePythonRunner")
        debug("Got remote iface %r" % remoterunner)
        args = self.arguments.copy()
        args["bus_address"] = self._bus_address
        args["timeout"] = self._timeout
        if self._outputfiles:
            args["outputfiles"] = self.getOutputFiles()
        debug("Creating remote instance with arguments %s %s %s %r", self.get_file(),
              self.__module__, self.__class__.__name__, args)
        try:
            remoterunner.createTestInstance(self.get_file(),
                                            self.__module__,
                                            self.__class__.__name__,
                                            args,
                                            reply_handler=self._createTestInstanceCallBack,
                                            error_handler=self._voidRemoteErrBackHandler)
        except:
            exception("Exception raised when creating remote instance !")
            self.validateStep("remote-instanced-created", False)
            self.stop()

    def _createTestInstanceCallBack(self, retval):
        debug("%s retval:%r", self.uuid, retval)
        if retval:
            delay = time.time() - self._subprocessconnecttime
            rname = "net.gstreamer.Insanity.Test.Test%s" % self.uuid
            rpath = "/net/gstreamer/Insanity/Test/Test%s" % self.uuid
            # remote instance was successfully created, let's get it
            try:
                remoteobj = self._bus.get_object(rname, rpath)
            except:
                warning("Couldn't get the remote instance for test %r", self.uuid)
                self.stop()
                return
            self.extraInfo("remote-instance-creation-delay", int(delay * 1000))
            self.validateStep("remote-instance-created")
            self._remoteinstance = dbus.Interface(remoteobj,
                                                  "net.gstreamer.Insanity.Test")
            self._remoteinstance.connect_to_signal("remoteReadySignal",
                                                   self._remoteReadyCb)
            self._remoteinstance.connect_to_signal("remoteStopSignal",
                                                   self._remoteStopCb)
            self._remoteinstance.connect_to_signal("remoteValidateStepSignal",
                                                   self._remoteValidateStepCb)
            self._remoteinstance.connect_to_signal("remoteExtraInfoSignal",
                                                   self._remoteExtraInfoCb)
            self.callRemoteSetUp()
        else:
            self.stop()

    def _removedRemoteTest(self, testrun, uuid):
        if not uuid == self.uuid:
            return

        info("%s our remote counterpart has left", self.uuid)
        # abort if the test hasn't actually finished
        self._remoteinstance = None
        if not self._stopping:
            self.stop()

class PythonDBusTest(DBusTest):
    """
    Convenience class for python-based tests being run in a separate process
    """
    __test_name__ = """python-dbus-test"""
    __test_description__ = """Base Class for Python DBUS tests"""
    __test_extra_infos__ = {
        "python-exception" : """Python unhandled exception information"""}

    def __init__(self, proxy=True, *args, **kwargs):
        self.__exception_handled = False
        self.__orig_excepthook = None
        DBusTest.__init__(self, proxy=proxy, *args, **kwargs)

        if not proxy:
            self.__setup_excepthook()

    def get_remote_launcher_args(self):
        # FIXME : add proper arguments
        # locate the python dbus runner
        # HACK : take top-level-dir/bin/pythondbusrunner.py
        rootdir = os.path.split(os.path.dirname(os.path.abspath(__file__)))[0]
        path = os.path.join(rootdir, "bin", "insanity-pythondbusrunner")
        if not os.path.isfile(path):
            path = "/usr/share/insanity/libexec/insanity-pythondbusrunner"
        return [sys.executable, path, self.uuid]

    def __excepthook(self, exc_type, exc_value, exc_traceback):

        import traceback

        if not self.__exception_handled:

            self.__exception_handled = True
            exc_format = traceback.format_exception(exc_type, exc_value, exc_traceback)
            self.extraInfo("python-exception", "".join(exc_format))

            self.stop()

            self.__orig_excepthook(exc_type, exc_value, exc_traceback)

        sys.exit(1)

    def __setup_excepthook(self):

        try:
            if sys.excepthook == self.__excepthook:
                return
        except AttributeError:
            return
        self.__exception_handled = False
        self.__orig_excepthook = sys.excepthook
        sys.excepthook = self.__excepthook

class CmdLineTest(PythonDBusTest):
    """
    Tests that run a command line application/script.
    """
    # TODO : fill with command line generic stuff
    pass
