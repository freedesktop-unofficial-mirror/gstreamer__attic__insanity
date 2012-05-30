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
import re

class DBusTest(Test, dbus.service.Object):
    """
    Class for tests being run in a separate process

    DBus is the ONLY IPC system used for getting results from remote
    tests.
    """

    __test_name__ = """dbus-test"""

    __test_description__ = """Base class for distributed tests using DBUS"""

    __test_checklist__ = {
    "dbus-process-spawned": {
        "description": "The DBus child process spawned itself"
    },
    "dbus-process-connected": {
        "description": "The DBus child process connected properly to the private Bus"
    },
    "subprocess-exited-normally": {
        "description": "The subprocess returned a null exit code (success)"
    }
    }

    __test_extra_infos__ = {
    "subprocess-return-code":"The exit value returned by the subprocess",
    "subprocess-spawn-time":"How long it took to spawn the subprocess (in milliseconds)",
    "cpu-load" : "CPU load in percent (can exceed 100% on multi core systems)" # TODO: move to C
    }

    __test_arguments__ = {
    "bus_address": {
        "global": True,
        "description": "The private DBus bus address",
        "type": "s"
    }
    }

    __async_setup__ = True
    ## Needed for dbus
    __metaclass__ = dbus.gobject_service.ExportedGObjectType

    def _parse_test_arguments(self, test_arguments):
        parsed_arguments = {}
        metadata_arguments = self.getFullArgumentList()

        for (k, v) in test_arguments.items():
            if not k in metadata_arguments:
                continue
            t = metadata_arguments[k]["type"]

            if t == "i":
                parsed_arguments[k] = dbus.Int32(int(v))
            elif t == "I":
                parsed_arguments[k] = dbus.Int64(int(v))
            elif t == "u":
                parsed_arguments[k] = dbus.UInt32(int(v))
            elif t == "U":
                parsed_arguments[k] = dbus.UInt64(int(v))
            elif t == "s":
                parsed_arguments[k] = v
            elif t == "d":
                parsed_arguments[k] = float(v)
            elif t == "b":
                parsed_arguments[k] = (v == "True" or v == "true" or v == "TRUE" or v == "1")

        return parsed_arguments

    def __init__(self, bus=None, bus_address="", metadata = None,
                 test_arguments = None, env=None, *args, **kwargs):
        """
        bus is the private DBusConnection used for testing.
        bus_address is the address of the private DBusConnection used for testing.

        You need to provide at least bus or bus_address.
        """
        if (metadata == None):
            raise Exception("You need to provide test metadata")
        self._metadata = metadata
        self._test_arguments = test_arguments

        Test.__init__(self, bus_address=bus_address,
                      *args, **kwargs)
        if (bus == None) and (bus_address == ""):
            raise Exception("You need to provide at least a bus or bus_address")
        self._bus = bus
        self._bus_address = bus_address

        self._remote_tearing_down = False

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
        
    # Test class overrides

    def test(self):
        pass

    def setUp(self):
        info("uuid:%s", self.uuid)
        if Test.setUp(self) == False:
            return False

        # get the remote launcher
        pargs = self._preargs
        pargs.extend(self.get_remote_launcher_args())
        shell = isinstance (pargs, basestring)

        cwd = self._testrun.getWorkingDirectory()

        self._environ["PRIVATE_DBUS_ADDRESS"] = self._bus_address
        info("Setting PRIVATE_DBUS_ADDRESS : %r" % self._bus_address)
        info("bus:%r" % self._bus)

        self._prepareArguments()

        if False: # useful to allow some time to run dbus-monitor on the private bus
            print("Setting PRIVATE_DBUS_ADDRESS : %r" % self._bus_address)
            time.sleep(5)

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
                                             shell = shell,
                                             cwd=cwd)
            self._pid = self._process.pid
        except:
            exception("Error starting the subprocess command ! %r", pargs)
            self.validateChecklistItem("dbus-process-spawned", False)
            return False
        debug("Subprocess created successfully [pid:%d]", self._pid)

        self.validateChecklistItem("dbus-process-spawned")
        # add a poller for the proces
        self._processpollid = gobject.timeout_add(500, self._pollSubProcess)
        # Don't forget to set a timeout for waiting for the connection
        return True

    def start(self):
        info("uuid:%s", self.uuid)
        if Test.start(self) == False:
            return False
        return self.callRemoteStart()

    def tearDown(self):
        info("uuid:%s", self.uuid)
        # FIXME : tear down the other process gracefully
        #    by first sending it the termination remote signal
        #    and then checking it's killed
        try:
            self.callRemoteTearDown()
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
                if self._returncode is None:
                    self._returncode = utils.kill_process (self._process)
                self._process = None
            if not self._returncode is None:
                info("Process returned %d", self._returncode)
                self.extraInfo("subprocess-return-code", self._returncode)
            self.validateChecklistItem("subprocess-exited-normally", self._returncode == 0)

        Test.tearDown(self)

    def stop(self):
        info("uuid:%s", self.uuid)
        self.callRemoteStop()
        # Chaining up to the parent class happens after
        # the DBus method reply arrived

    def ping(self):
        Test.ping(self)

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

    def _voidRemoteSetUpCallBackHandler(self, success):
        if success:
            self.ping()
            self.start()
        else:
            error("FATAL : Failed to setup test")
            self.tearDown()

    def _voidRemoteStartCallBackHandler(self, success):
        if not success:
            error("FATAL : Failed to start test")
            self.tearDown()

    def _voidRemoteStopCallBackHandler(self):
        info("%s", self.uuid)

        self.validateChecklistItem("subprocess-exited-normally")
        self._prepareArguments()
        Test.stop(self)

        self.ping()
        # Check if we have new arguments and
        # have to run another time
        if self.args:
            self.start()
        else:
            self.tearDown()

    def _voidRemoteErrBackHandler(self, exc, caller=None, fatal=True):
        error("%r : %s", caller, exc)
        if fatal:
            warning("FATAL : aborting test")
            # a fatal error happened, DIVE DIVE DIVE !
            self.tearDown()

    def _voidRemoteSetUpErrBackHandler(self, exc):
        self._voidRemoteErrBackHandler(exc, "remoteSetUp")

    def _voidRemoteStartErrBackHandler(self, exc):
        self._voidRemoteErrBackHandler(exc, "remoteStart")

    def _voidRemoteStopErrBackHandler(self, exc):
        self._voidRemoteErrBackHandler(exc, "remoteStop", fatal=False)

    def _voidRemoteTearDownErrBackHandler(self, exc):
        self._voidRemoteErrBackHandler(exc, "remoteTearDown", fatal=False)


    ## Proxies for remote DBUS calls
    def callRemoteSetUp(self):
        # call remote instance "remoteSetUp()"
        if not self._remoteinstance:
            return

        args = dict((k, v) for k, v in self.args.items() if (k in self.getFullArgumentList() and self.getFullArgumentList()[k]["global"] == True))
        args = self._parse_test_arguments(args)

        self._remoteinstance.remoteSetUp(args, self.getOutputFiles(),
                                         reply_handler=self._voidRemoteSetUpCallBackHandler,
                                         error_handler=self._voidRemoteSetUpErrBackHandler)

    def callRemoteStart(self):
        # call remote instance "remoteStart()"
        if not self._remoteinstance:
            return

        self.args = self._parse_test_arguments(self.args)
        self._remoteinstance.remoteStart(self.args, self.getOutputFiles(),
                                         reply_handler=self._voidRemoteStartCallBackHandler,
                                         error_handler=self._voidRemoteStartErrBackHandler)

    def callRemoteStop(self):
        # call remote instance "remoteStop()"
        if not self._remoteinstance:
            return
        self._remoteinstance.remoteStop(reply_handler=self._voidRemoteStopCallBackHandler,
                                        error_handler=self._voidRemoteStopErrBackHandler)

    def callRemoteTearDown(self):
        # call remote instance "remoteTearDown()"
        if not self._remoteinstance:
            return
        self._remoteinstance.remoteTearDown(reply_handler=self._voidRemoteCallBackHandler,
                                            error_handler=self._voidRemoteTearDownErrBackHandler)

    def _prepareArguments(self):
        try:
            self.args = self._test_arguments.next().copy()
            self.args["bus_address"] = self._bus_address
            self.prepareIteration(self.args)
        except:
            self.args = None

    ## callbacks from remote signals
    def _remoteDoneCb(self):
        info("%s", self.uuid)
        self.ping()
        self.stop()

    def _remoteValidateChecklistItemCb(self, item, validate, desc):
        info("%s checklist item:%s : %r", self.uuid, item, validate)
        self.ping()
        self.validateChecklistItem(unwrap(item), validate, desc)

    def _remoteExtraInfoCb(self, key, value):
        info("%s key:%s value:%r", self.uuid, key, value)
        self.ping()
        self.extraInfo(unwrap(key), unwrap(value))

    def _remotePingCb(self):
        info("%s", self.uuid)
        self.ping()

    ## DBUS Signals for proxies

    def _newRemoteTest(self, testrun, uuid):
        if not uuid == self.uuid:
            return

        info("%s our remote counterpart has started", self.uuid)
        self.validateChecklistItem("dbus-process-connected")
        self._subprocessconnecttime = time.time()
        delay = self._subprocessconnecttime - self._subprocessspawntime
        self.extraInfo("subprocess-spawn-time", int(delay * 1000))
        # we need to give the remote process the following information:
        # * filename where the Test class is located (self.get_file())
        # * class name (self.__class__.__name__)
        # * the arguments (self.arguments)
        rname = "net.gstreamer.Insanity.Test.Test%s" % self.uuid
        rpath = "/net/gstreamer/Insanity/Test/Test%s" % self.uuid
        # get the proxy object to our counterpart
        remoteobj = self._bus.get_object(rname, rpath)
        debug("Got remote runner object %r" % remoteobj)
        # call createTestInstance()
        remoterunner = dbus.Interface(remoteobj,
                                      "net.gstreamer.Insanity.Test")
        debug("Got remote iface %r" % remoterunner)
        try:
            delay = time.time() - self._subprocessconnecttime
            self._remoteinstance = dbus.Interface(remoteobj,
                                                  "net.gstreamer.Insanity.Test")
            info ('Listening to signals from %s' % self._remoteinstance)
            self._remoteinstance.connect_to_signal("remoteDoneSignal",
                                                   self._remoteDoneCb)
            self._remoteinstance.connect_to_signal("remoteValidateChecklistItemSignal",
                                                   self._remoteValidateChecklistItemCb)
            self._remoteinstance.connect_to_signal("remoteExtraInfoSignal",
                                                   self._remoteExtraInfoCb)
            self._remoteinstance.connect_to_signal("remotePingSignal",
                                                   self._remotePingCb)
            self.callRemoteSetUp()
        except:
            exception("Exception raised when creating remote instance !")
            self.stop()

    def _removedRemoteTest(self, testrun, uuid):
        if not uuid == self.uuid:
            return

        info("%s our remote counterpart has left", self.uuid)
        # abort if the test hasn't actually finished
        self._remoteinstance = None
        if not self._stopping:
            self.stop()

    def getFullCheckList(self):
        return self._metadata.getFullCheckList()

    def getFullArgumentList(self):
        return self._metadata.getFullArgumentList()

    def getFullExtraInfoList(self):
        return self._metadata.getFullExtraInfoList()

    def getFullOutputFilesList(self):
        return self._metadata.getFullOutputFilesList()

    def getTestName(self):
        return self._metadata.__test_name__

    def getTestDescription(self):
        return self._metadata.__test_description__

    def getTestFullDescription(self):
        return self._metadata.__test_full_description__

class PythonDBusTest(DBusTest):
    """
    Convenience class for python-based tests being run in a separate process
    """
    __test_name__ = """python-dbus-test"""
    __test_description__ = """Base Class for Python DBUS tests"""
    __test_extra_infos__ = {
        "python-exception" : """Python unhandled exception information"""}

    def __init__(self, *args, **kwargs):
        self.__exception_handled = False
        self.__orig_excepthook = None
        DBusTest.__init__(self, *args, **kwargs)

    def get_remote_launcher_args(self):
        # FIXME : add proper arguments
        rootdir = os.path.split(os.path.dirname(os.path.abspath(__file__)))[0]
        path = self._metadata.__test_filename__
        return [path, "--run", "--dbus-uuid="+self.uuid]

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

