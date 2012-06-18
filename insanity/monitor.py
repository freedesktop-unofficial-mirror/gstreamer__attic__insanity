# GStreamer QA system
#
#       monitor.py
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
Monitors

Monitors are objects that can be attached to tests to collect extra
information, run extra analysis, etc...
"""

# TODO
#
# Add default monitor (spawn process, crash, timeout, IPC)
#    maybe in a different file...

# Design
#
# Monitors can do one or more of the following:
# * set/add/change Environment variables
# * wrap the test (ex : valgrind)
#   Ex : sometool --with -some -option [regularlauncher args]...
# * redirect Standard I/O to some files or functions
#   => Requires being able to create temporary files
# * postprocess output
# * has a checklist like tests
# * can modify timeout (i.e. with valgrind)

import os
import subprocess
from insanity.test import Test, DBusTest
from insanity.log import warning, debug, info, exception
from insanity.utils import compress_file

class Monitor(object):
    """
    Monitors a test

    Base class
    """
    __monitor_name__ = "monitor"
    """The searchable name of the monitor, should be unique"""

    __monitor_description__ = "Base Monitor class"
    """A short description of the monitor"""

    __monitor_arguments__ = {}
    """
    The possible arguments of the monitors.
    Dictionnary of:
    * key : Argument name
    * value : Description of the argument
    """

    __monitor_output_files__ = {}
    """
    List of the files that the monitor generates
    Dictionnary of:
    * key : Output file name
    * value : Description of the output file
    """

    __monitor_checklist__ = {}
    """
    List of the checkitem:
    Dictionnary of:
    * key : Check item name
    * value : Check item description
    """

    __monitor_extra_infos__ = {}
    """
    List of extra information which the monitor generates
    Dictionnary of:
    * key : Extra information name
    * value : Description of the extra information
    """

    __applies_on__ = Test
    """
    Class of Test this monitor can be applied on.
    """

    def __init__(self, testrun, instance, **kwargs):
        self.testrun = testrun
        self.test = instance
        self.arguments = kwargs
        self._checklist = {}
        self._extraInfo = {}
        self._outputfiles = {}
        self._iteration = 0
        self._iteration_outputfiles = {}

    def setUp(self):
        """
        Prepare the monitor.

        Returns True if everything went well, else False.

        Sub-classes should call their parent-class setUp() before
        their implementation.
        """
        return True

    def start(self, iteration):
        """
        Prepare the monitor.

        Returns True if everything went well, else False.

        Sub-classes should call their parent-class start() before
        their implementation.
        """
        self._iteration = iteration
        return True

    def stop(self):
        """
        Stop the monitor.

        Sub-classes should call their parent-class stop() before
        their implementation.
        """
        return True

    def tearDown(self):
        """
        Clean up the monitor.

        Sub-classes should call their parent-class tearDown() before
        their implementation.
        """
        pass

    def _processResults(self):
        pass

    def _populateChecklist(self):
        """ fill the instance checklist with default values """
        ckl = self.getFullCheckList()
        for key in ckl.keys():
            self._checklist[key] = False

    ## Methods for tests to return information

    def validateChecklistItem(self, checkitem):
        """
        Validate a checklist item in the checklist.
        checkitem is one of the keys of __test_checklist__

        Called by the test itself
        """
        info("checklist item %s for item %r" % (checkitem, self))
        if not checkitem in self._checklist:
            return
        self._checklist[checkitem] = True

    def extraInfo(self, key, value):
        """
        Give extra information obtained while running the tests.

        If key was already given, the new value will override the value
        previously given for the same key.

        Called by the test itself
        """
        debug("%s : %r", key, value)
        self._extraInfo[key] = value

    def addIterationOutputFile(self, key, value):
        """
        Report the location of an output file for a specific iteration
        """
        debug("%s : %s", key, value)
        try:
            self._iteration_outputfiles[self._iteration][key] = value
        except KeyError:
            kv = {}
            kv[key] = value
            self._iteration_outputfiles[self._iteration] = kv

    def getIterationOutputFiles(self, iteration):
        """
        Return a dictionnary containing the outputfiles in the form of
        {outputfile-name: /path/to/file} for a specific iteration
        """
        try:
            return self._iteration_outputfiles[iteration]
        except KeyError:
            debug("No outputfile for iteration %s", iteration)
            return None

    def setOutputFile(self, key, value):
        """
        Report the location of an output file
        """
        debug("%s : %s", key, value)
        self._outputfiles[key] = value

    # getters

    def getCheckList(self):
        """
        Returns the instance checklist.
        """
        return self._checklist

    def getArguments(self):
        """
        Returns the list of arguments for the given test
        """
        validkeys = self.getFullArgumentList()
        # Hide expected-failures from the storage backend.
        validkeys.pop("expected-failures", [])
        res = {}
        for key in self.arguments:
            if key in validkeys:
                res[key] = self.arguments[key]
        return res

    def getExtraInfo(self):
        """
        Returns the extra-information dictionnary
        """
        return self._extraInfo

    def getOutputFiles(self):
        """
        Returns the output files generated by the monitor
        """
        return self._outputfiles

    def getSuccessPercentage(self):
        """
        Returns the success rate of this instance as a float
        """
        ckl = self.getCheckList()
        nbitems = len(ckl)
        if nbitems:
            nbsucc = len([x for x in ckl if ckl[x] == True])
            return (100.0 * nbsucc) / nbitems
        # yes, no check items means 100% success for monitors
        return 100.0

    ## Class methods

    @classmethod
    def getFullCheckList(cls):
        """
        Returns the full monitor checklist. This is used to know all the
        possible check items for this instance, along with their description.
        """
        d = {}
        for cl in cls.mro():
            if "__monitor_checklist__" in cl.__dict__:
                d.update(cl.__monitor_checklist__)
            if cl == Monitor:
                break
        return d

    @classmethod
    def getFullArgumentList(cls):
        """
        Returns the full list of arguments with descriptions.
        """
        d = {}
        for cl in cls.mro():
            if "__monitor_arguments__" in cls.__dict__:
                d.update(cl.__monitor_arguments__)
            if cl == Monitor:
                break
        return d

    @classmethod
    def getFullExtraInfoList(cls):
        """
        Returns the full list of extra info with descriptions.
        """
        d = {}
        for cl in cls.mro():
            if "__monitor_extra_infos__" in cls.__dict__:
                d.update(cl.__monitor_extra_infos__)
            if cl == Monitor:
                break
        return d

    @classmethod
    def getFullOutputFilesList(cls):
        """
        Returns the full list of output files with descriptions.
        """
        d = {}
        for cl in cls.mro():
            if "__monitor_output_files__" in cls.__dict__:
                d.update(cl.__monitor_output_files__)
            if cl == Monitor:
                break
        return d


class ValgrindMemCheckMonitor(Monitor):
    """
    Runs the test within a valgrind --tool=memcheck environment
    """
    __monitor_name__ = "valgrind-memcheck-monitor"
    __monitor_description__ = "Checks for memory leaks using valgrind memcheck"
    __monitor_arguments__ = {
        "suppression-files":"coma separated list of suppression files, or list of suppression files"
        }
    __monitor_output_files__ = {
        "memcheck-log" : "Full log from valgrind memcheck"
        }

    __applies_on__ = DBusTest

    def setUp(self):
        Monitor.setUp(self)
        self._logfile, self._logfilepath = self.testrun.get_temp_file(nameid="valgrind-memcheck")
        # prepend valgrind options
        ourargs = ["valgrind", "--tool=memcheck",
                   "--leak-check=full", "--trace-children=yes",
                   "--leak-resolution=med", "--num-callers=20",
                   "--log-file=%s" % self._logfilepath]
        # add the suppression files
        sups = self.arguments.get("suppression-files")
        if sups:
            if isinstance(sups,list):
                for sup in sups:
                    ourargs.append("--suppressions=%s" % sup)
            else:
                for sup in sups.split(','):
                    ourargs.append("--suppressions=%s" % sup)
        ourargs.extend(self.test._preargs)
        self.test._preargs = ourargs
        # set some env variables
        self.test._environ["G_SLICE"] = "always-malloc"
        # multiply timeout by 4
        if not self.test.setTimeout(self.test.getTimeout() * 4):
            warning("Couldn't change the timeout !")
            return False
        # multiply async-setup-timeout by 4 !
        if not self.test.setAsyncSetupTimeout(self.test.getAsyncSetupTimeout() * 4):
            warning("Couldn't change the asynchronous setup timeout !")
            return False
        return True

    def tearDown(self):
        print 'Tearing down memcheck monitor'
        Monitor.tearDown(self)
        if self._logfile:
            os.close(self._logfile)
        if not os.path.getsize(self._logfilepath):
            # if log file is empty remove it
            debug("log file is empty, removing it")
            os.remove(self._logfilepath)
        else:
            # else report it
            print 'Reporting memcheck monitor log: ', self._logfilepath
            self.setOutputFile("memcheck-log", self._logfilepath)

class GDBMonitor(Monitor):
    """
    Sets up the environment in order to collect core dumps and
    get backtraces.

    This monitor will NOT run the test under gdb

    For this monitor to work, you need to have the two following
    kernel values set properly:

    /proc/sys/kernel/core_uses_pid = 1
    /proc/sys/kernel/core_pattern = core
    """
    __monitor_name__ = "gdb-monitor"
    __monitor_description__ = """
    Sets up the environment in order to collect core dumps of subprocesses
    that failed. If possible, it will also get the backtrace of those
    core dumps.
    """
    __monitor_arguments__ = {
        "save-core-dumps":"Save core dump files (default: False)",
        "generate-back-traces":"Generate back traces from core dumps (default True)",
        "gdb-script":"Script to use to generate gdb backtraces (default : gdb.instructions"
        }
    __monitor_output_files__ = {
        "core-dump":"The core dump file",
        "backtrace-file":"The backtrace file"
        }
    __applies_on__ = DBusTest

    # doesn't need to do any redirections
    # setup 'ulimit -c unlimited'
    # when the test is done, check whether it crashed, if so:
    #  * run a gdb script to collect a backtrace
    #  * remove core file

    def setUp(self):
        Monitor.setUp(self)
        self._saveCoreDumps = self.arguments.get("save-core-dumps", False)
        self._generateBackTraces = self.arguments.get("generate-back-traces", True)
        self._GDBScript = self.arguments.get("gdb-script", "gdb.instructions")
        # add some env variables
        self.test._environ["G_DEBUG"] = "fatal_warnings"
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CORE, (-1, -1))
        except:
            exception("Couldn't change core limit")
            return False
        return True

    def tearDown(self):
        Monitor.tearDown(self)
        # if the return value of the subprocess is non-null, we most
        # likely have a crasher and core dump
        if not self.test._returncode == 0:
            debug("non-null returncode [%d] for pid %d",
                  self.test._returncode,
                  self.test._pid)
            # try to find the core file
            core = self._findCoreFile()
            if core:
                debug("Got core file %s", core)
                if self._generateBackTraces:
                    # output file for backtrace
                    backtracefd, backtracepath = self.testrun.get_temp_file(nameid="gdb-back-trace")
                    backtracefile = open(backtracepath, "a+")

                    # run the backtrace script
                    # This blocks, which is acceptable since we're tearing down
                    subprocess.Popen(["libtool", "--mode=execute",
                                     "gdb", "--batch", "-x", self._GDBScript,
                                     self.test._metadata.__test_filename__, core],
                                     stdout = backtracefile,
                                     stderr = backtracefile).wait()

                    # cleanup
                    os.close(backtracefd)
                    backtracefile.close()

                    # notify of backtrace file
                    self.setOutputFile("backtrace-file", backtracepath)
                if self._saveCoreDumps:
                    # copy over the core dump
                    corefd, corepath = self.testrun.get_temp_file(nameid="core-dump")
                    # copy core dump to that file
                    # FIXME : THIS MIGHT NOT WORK ON WINDOWS (see os.rename docs)
                    try:
                        os.rename(core, corepath)
                        self.setOutputFile("core-dump", corepath)
                    except:
                        exception("Couldn't rename core dump file !!!")
                        os.remove(core)
                    finally:
                        os.close(corefd)
                else:
                    os.remove(core)

    def _findCoreFile(self):
        cwd = self.testrun.getWorkingDirectory()
        files = os.listdir(cwd)
        debug("files : %r", files)
        for fname in files:
            if fname == "core":
                return os.path.join(cwd, fname)
            if fname == "core.%d" % self.test._pid:
                return os.path.join(cwd, fname)
        return None

class TerminalRedirectionMonitor(Monitor):
    """
    Redirects stderr and stdout of a given test to a file
    """
    __monitor_name__ = "output-redirection-monitor"
    __monitor_description__ = """
    Redirects stderr and stdout of a given test to a file
    """
    __monitor_arguments__ = {
        "desc":"How to save stderr/stdout. Possible values are 'stderr', only"
        " is saved in the stderr-file, 'stdout', only stdout is saved in the"
        " stdout-file outptufile, 'stderr,stdout' both files are saved."
        " Note that by default both are saved in the stdout-and-stderr-file"
        " output file",
        "outputfile-basename":"The category of outputfiles (default='')",
        "category":"The category of outputfiles (default='insanity-output')",
        "compress-outputfiles":"Whether the resulting output should be compressed (default:True)"
        }
    __monitor_output_files__ = {
        "stdout-and-stderr-file":"File with both stderr and stdout",
        "stdout-file":"File with stdout only",
        "stderr-file":"File with stderr only",
        }
    __applies_on__ = DBusTest

    def setUp(self):
        Monitor.setUp(self)
        desc = self.arguments.get("desc", 'stderrstdout')
        basename = self.arguments.get("outputfile-basename")
        category = self.arguments.get("category")

        self._files = []
        self._paths = {}
        if desc:
            info("No path set, trying to use stdout and stding specific files")
            if not 'stderr' in desc and not 'stdout' in desc:
                warning("Neither of stdout-path, stderr-path and path specified"
                        "Can not use the monitor")
                return False

            if 'stderr' in desc:
                if basename is None:
                    nameid = "stderr"
                else:
                    nameid = basename

                if category:
                    stderr_file, stderr_path = self.testrun.get_temp_file(nameid=nameid, category=category)
                else:
                    stderr_file, stderr_path = self.testrun.get_temp_file(nameid=nameid)

                self.test.setStderr(stderr_file)
                self._files.append(stderr_file)
                self._paths["stderr-file"] = stderr_path

            if 'stdout' in desc:
                if basename is None:
                    nameid = "stdout"
                else:
                    nameid = basename
                if category:
                    stdout_file, stdout_path = self.testrun.get_temp_file(nameid=nameid, category=category)
                else:
                    stdout_file, stdout_path = self.testrun.get_temp_file(nameid=nameid)

                self.test.setStdout(stdout_file)
                self._files.append(stdout_file)
                self._paths["stdout-file"] = stdout_path
        else:
            if basename is None:
                nameid = "stdoutanderr"
            else:
                nameid = basename

            if category:
                _file, path = self.testrun.get_temp_file(nameid=nameid, category=category)
            else:
                _file, path = self.testrun.get_temp_file(nameid=nameid)

            self.test.setStdOutAndErr(_file)
            self._files.append(_file)
            self._paths["stdout-and-stderr-file"] = path

        return True

    def tearDown(self):
        Monitor.tearDown(self)
        for f in self._files:
            os.close(f)

        for output, path in self._paths.iteritems():
            if not os.path.getsize(path):
                # if log file is empty remove it
                debug("log file is empty, removing it")
                os.remove(path)
            else:
                if self.arguments.get("compress", True):
                    res = path + ".gz"
                    debug("compressing debug log to %s", res)
                    compress_file(path, res)
                    os.remove(path)
                    path = res
                # else report it
                print "SETTING", output, path
                self.setOutputFile(output, path)

def getMonitorClass(classname):
    return eval(classname)
