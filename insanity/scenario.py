# GStreamer QA system
#
#       scenario.py
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

from copy import copy

import gobject
from insanity.test import Test
from insanity.log import debug, exception

class Scenario(Test):
    """
    Test that runs other tests with optional programmatic decisions
    and result processing.
    """
    __test_name__ = "scenario"
    __test_description__ = """Base class for scenarios"""
    __test_timeout__ = 600 # 10 minutes because the subtests will handle themselves
    __test_extra_infos__ = {"subtest-names":
            "The instance-name argument for all subtests started."}

    # TODO :
    #  auto-aggregation of arguments, checklists and extra-info
    #  Scenario might want to add some arguments, checks, extra-info ?
    #  arg/checklist/extra-info names might need to be prefixed ?
    #    Ex : <test-name>-<nb>-<name>
    #  Override timeout !

    # implement methods to:
    # * decide which test should be run first
    # * what should be done when a test is done

    # Test methods overrides

    def setUp(self):
        if not Test.setUp(self):
            return False
        self._tests = [] # list of (test, args, monitors)
        self.tests = [] # executed tests
        self._subtest_names = []

        # FIXME : asynchronous starts ???
        return True

    def _setUpMonitors(self):
        # we don't need monitors, our subclass do
        return True

    def tearDown(self):
        # FIXME : implement this for the case where we are aborted !
        self.extraInfo("subtest-names", repr(self._subtest_names))
        pass

    def test(self):
        # get the first test to run
        if len(self._tests) > 0:
            self._startNextSubTest()

    def getSuccessPercentage(self):
        if not self.tests:
            return 0.0
        res = reduce(lambda x, y: x+y, [z.getSuccessPercentage() for z in self.tests]) / len(self.tests)
        return res

    # private methods

    def _startNextSubTest(self):
        try:
            testclass, args, monitors, instance_name = self._tests.pop(0)
            if not 'bus' in args.keys():
                args["bus"] = self.arguments.get("bus")
            if not 'bus_address' in args.keys():
                args["bus_address"] = self.arguments.get("bus_address")
            debug("About to create subtest %r (instance_name=%r) "
                  "with arguments %r", testclass, instance_name, args)
            args["instance-name"] = instance_name
            instance = testclass(testrun=self._testrun,
                                 **args)
            if monitors:
                for monitor in monitors:
                    instance.addMonitor(*monitor)
        except Exception, e:
            exception("Failed to create instance of class %r : %r", testclass, e)
            self.stop()
            return
        # connect to signals
        self.tests.append(instance)
        instance.connect("done", self._subTestDoneCb)
        for monitor in self._monitors:
            instance.addMonitor(*monitor)
        instance.run()
        # returning False so that idle_add() doesn't call us again
        return False

    # sub-test callbacks
    def _subTestDoneCb(self, subtest):
        debug("Done with subtest %r", subtest)
        carryon = self.subTestDone(subtest)
        debug("carryon:%r , len(self._tests):%d",
              carryon, len(self._tests))
        if carryon and len(self._tests) > 0:
            # startup the next test !
            debug("Carrying on with next test")
            gobject.idle_add(self._startNextSubTest)
        else:
            debug("No more subtests to run, stopping")
            self.stop()

    # overridable methods

    def addSubTest(self, testclass, arguments, monitors=None, position=-1,
            instance_name=None):
        """
        testclass : a testclass to run next, can be a Scenario
        arguments : dictionnary of arguments
        monitors : list of (Monitor, monitorargs) to run the test with
        position : the position to insert the test in (-1 for last)
        instance_name : a human-readable name for the test.

        This method can be called several times in a row at any moment.
        """
        if instance_name is None:
            instance_name = "%u.%s" % (len(self._subtest_names),
                                       testclass.__test_name__)
        # filter out unused arguments in arguments for non-scenarios
        if not issubclass(testclass, Scenario):
            args = {}
            for validkey in testclass.getFullArgumentList():
                if validkey in arguments.keys():
                    args[validkey] = arguments[validkey]
        else:
            args = copy(arguments)

        debug("Appending subtest %r args:%r", testclass, args)
        if position == -1:
            self._tests.append((testclass, args, monitors, instance_name))
        else:
            self._tests.insert(position,
                                (testclass, args, monitors, instance_name))
        self._subtest_names.append(instance_name)

    def subTestDone(self, subtest):
        """
        subclass should implement this method to know when a subtest is
        done. This is the right place to call setNextSubTest().

        Return True (default) if we should carry on with the next subtest (if any).
        Return False if we should not carry on with further tests.
        """
        return True

    # implement Test methods

    def _getRecursiveArgumentList(self):
        """
        Like Test.getFullArgumentsList(), but takes subtests into account,
        which would not be possible with a classmethod.
        """
        validkeys = self.getFullArgumentList()
        for sub in self.tests:
            if isinstance(sub, Scenario):
                validkeys.update(sub._getRecursiveArgumentList())
            else:
                validkeys.update(sub.getFullArgumentList())

        return validkeys

    def getArguments(self):
        """
        Returns the list of valid arguments for this scenario.
        """
        validkeys = self._getRecursiveArgumentList()
        # Hide expected-failures from the storage backend.
        validkeys.pop("expected-failures", [])
        res = {}
        for key in self.arguments.iterkeys():
            if key in validkeys:
                res[key] = self.arguments[key]
        return res

    def getCheckList(self):
        checklist = dict(super(Scenario, self).getCheckList())
        for sub in self.tests:
            n_u_failures = \
                dict(sub.getCheckList()).get("no-unexpected-failures")
            if n_u_failures == 0:
                checklist["no-unexpected-failures"] = 0
        return checklist.items()

    def addMonitor(self, monitor, monitorargs=None):
        # the subtests will do the check for validity
        self._monitors.append((monitor, monitorargs))

class ListScenario(Scenario):
    """
    Scenario that will run each test one after the other on the same
    arguments.
    """

    __test_name__ = """list-scenario"""
    __test_arguments__ = {
        "subtest-list" : ( "List of Testclass to run sequentially",
                           [], None ),
        "fatal-subtest-failure" : ( "Do not carry on with next subtest if previous failed",
                                    True, None )
        }
    __test_description__ = """
    This scenario will execute the given tests one after the other.
    """
    __test_full_description__ = """
    This scenario will execute the given tests one after the other.
    If fata-subtest-failure is set to True, then it will stop whenever
    one test hasn't succeeded fully (all checklist items validated).
    """

    def setUp(self):
        if not Scenario.setUp(self):
            return False
        # add the tests
        if self.arguments and "subtest-list" in self.arguments:
          for subtest in self.arguments["subtest-list"]:
            self.addSubTest(subtest,
                            self.arguments,
                            [])
        return True

    def subTestDone(self, test):
        # if we don't have fatal-subtest-failure, carry on if any
        if self.arguments["fatal-subtest-failure"] == False:
            return True
        # else we only carry on if the test was 100% succesfull
        if test.getSuccessPercentage() == 100.0:
            return True
        return False
