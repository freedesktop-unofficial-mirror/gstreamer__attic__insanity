# GStreamer QA system
#
#       storage/dbstorage.py
#
# Copyright (c) 2008, Edward Hervey <bilboed@bilboed.com>
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
Database DataStorage for python modules supporting the DB-API v2.0
"""

import time
import threading
from cPickle import dumps, loads
from weakref import WeakKeyDictionary
from insanity.log import error, warning, debug
from insanity.utils import reverse_dict, map_dict, map_list
from insanity.storage.storage import DataStorage
from insanity.storage.async import AsyncStorage, queuemethod

class BlobException(Exception):
    pass

class DBStorage(DataStorage, AsyncStorage):
    """
    Stores data in a database
    (anyone recognized by Python DB-API (PEP 249))

    Don't use this class directly, but one of its subclasses
    """

    def __init__(self, async=True, *args, **kwargs):

        # public
        # db-api Connection
        self.con = None

        # protected
        # threading lock
        self._lock = threading.Lock()

        # private
        # key: testrun, value: testrunid
        self.__testruns = WeakKeyDictionary()
        self.__tests = WeakKeyDictionary()
        self.__clients = WeakKeyDictionary()

        # cache of mappings for testclassinfo
        # { 'testtype' : { 'dictname' : mapping } }
        self.__tcmapping = {}
        # cache of mappings for testclassinfo
        # { 'testtype' : { 'dictname' : mapping } }
        self.__mcmapping = {}

        DataStorage.__init__(self, *args, **kwargs)
        AsyncStorage.__init__(self, async)

    def merge(self, otherdb, testruns=None):
        """
        Merges the contents of 'otherdb' into ourselves.

        If no list of testrun id from otherdb are specified, then all testruns
        from otherdb are merged into ourselves.

        Currently only supports DBStorage as other database.
        """
        # FIXME : Add option to only merge some testruns
        if not isinstance(otherdb, DBStorage):
            raise TypeError("otherdb is not a DBStorage !")
        # testruns needs to be a list or tuple
        if not testruns == None:
            if not isinstance(testruns, list) and not isinstance(testruns, tuple):
                raise TypeError("testruns needs to be a list of testrun id")
        if self.async:
            raise Exception("Can not merge into an Asynchronous DBStorage, use async=False")
        self.__merge(otherdb, testruns=testruns)

    # DataStorage methods implementation

    def _setUp(self):
        # open database
        con = self._openDatabase()
        if not con:
            error("Could not open database !")
            return
        self.con = con

        # check if we have an existing database with valid
        # tables.
        version = self._getDatabaseSchemeVersion()
        if version == DB_SCHEME_VERSION:
            return
        if version == None:
            # createTables if needed
            debug("No valid tables seem to exist, creating them")
            self._createTables()
        elif version < DB_SCHEME_VERSION:
            from insanity.storage.dbconvert import _updateTables
            _updateTables(self, version, DB_SCHEME_VERSION)
        else:
            warning("database uses a more recent version (%d) than we support (%d)",
                    version, DB_SCHEME_VERSION)

    def close(self, callback=None, *args, **kwargs):
        """
        Shut down the database, the callback will be called when it's finished
        processing pending actions.

        Subclasses wishing to do something as final action (closing connections,
        etc...) should implement/chain-to the _shutDown() method.
        """
        if callback == None or not callable(callback):
            debug("No callback provided or not callable")
            return
        self.queueFinalAction(self.__closedb, callback, *args, **kwargs)

    def setClientInfo(self, softwarename, clientname, user):
        debug("softwarename:%s, clientname:%s, user:%s",
              softwarename, clientname, user)
        existstr = "SELECT id FROM client WHERE software=? AND name=? AND user=?"
        res = self._FetchAll(existstr, (softwarename, clientname, user))
        if len(res) == 1 :
            debug("Entry already present !")
            key = res[0][0]
        elif len(res) > 1:
            warning("More than one similar entry ???")
            raise Exception("Several client entries with the same information, fix db!")
        else:
            insertstr = """
            INSERT INTO client (software, name, user) VALUES (?,?,?)
            """
            key = self._ExecuteCommit(insertstr, (softwarename, clientname, user))
        debug("got id %d", key)
        # cache the key
        return key

    @queuemethod
    def startNewTestRun(self, testrun, clientid):
        self.__startNewTestRun(testrun, clientid)

    @queuemethod
    def endTestRun(self, testrun):
        self.__endTestRun(testrun)

    @queuemethod
    def newTestStarted(self, testrun, test, commit=True):
        self.__newTestStarted(testrun, test, commit)

    @queuemethod
    def newTestFinished(self, testrun, test):
        self.__newTestFinished(testrun, test)

    def listTestRuns(self):
        liststr = "SELECT id FROM testrun"
        res = self._FetchAll(liststr)
        debug("Got %d testruns", len(res))
        if len(res):
            return list(zip(*res)[0])
        return []

    ## Retrieval API

    def getTestRun(self, testrunid):
        debug("testrunid:%d", testrunid)
        liststr = """
        SELECT clientid,starttime,stoptime
        FROM testrun WHERE id=?"""
        res = self._FetchOne(liststr, (testrunid, ))
        if len(res) == 0:
            debug("Testrun not available in DB")
            return (None, None, None)
        return res

    def getNbTestsForTestrun(self, testrunid, withscenarios=True, failedonly=False):
        debug("testrunid:%d", testrunid)
        liststr = "SELECT COUNT(*) FROM test WHERE testrunid=?"
        if failedonly:
            liststr += " AND resultpercentage <> 100.0"
        if withscenarios == False:
            liststr += " AND isscenario=0"
        res = self._FetchOne(liststr, (testrunid, ))
        if not res:
            return 0
        return res[0]

    def getTestsForTestRun(self, testrunid, withscenarios=True, failedonly=False):
        debug("testrunid:%d", testrunid)
        liststr = "SELECT test.id  FROM test WHERE test.testrunid=? AND ismonitor<>1"
        if failedonly:
            liststr += " AND test.resultpercentage <> 100.0"
        if withscenarios == False:
            liststr += " AND test.isscenario=0"
        res = self._FetchAll(liststr, (testrunid, ))
        if not res:
            return []
        tmp = list(zip(*res)[0])
        return tmp

    def getScenariosForTestRun(self, testrunid):
        debug("testrunid:%d", testrunid)
        liststr = """
        SELECT test.parentid, test.id FROM test
        WHERE test.parentid IN (
        SELECT test.id FROM test
        WHERE test.testrunid=?
        AND test.isscenario=1)"""
        res = self._FetchAll(liststr, (testrunid, ))
        if not res:
            return {}
        return dict(res)

    def getClientInfoForTestRun(self, testrunid):
        debug("testrunid:%d", testrunid)
        liststr = """
        SELECT client.software,client.name,client.user
        FROM client,testrun
        WHERE client.id=testrun.clientid AND testrun.id=?"""
        res = self._FetchOne(liststr, (testrunid,))
        return res

    def getEnvironmentForTestRun(self, testrunid):
        debug("testrunid:%d", testrunid)
        return self.__getDict("testrun_environment_dict", testrunid)

    def getFailedTestsForTestRun(self, testrunid):
        debug("testrunid:%d", testrunid)
        liststr = """
        SELECT id
        FROM test
        WHERE testrunid=? AND resultpercentage<>100.0"""
        res = self._FetchAll(liststr, (testrunid, ))
        if not res:
            return []
        return list(zip(*res)[0])

    def getSucceededTestsForTestRun(self, testrunid):
        debug("testrunid:%d", testrunid)
        liststr = """
        SELECT id
        FROM test
        WHERE testrunid=? AND resultpercentage=100.0"""
        res = self._FetchAll(liststr, (testrunid, ))
        if not res:
            return []
        return list(zip(*res)[0])

    def getTestInfo(self, testid, rawinfo=False):
        if not rawinfo:
            searchstr = """
            SELECT test.testrunid,testclassinfo.type,test.resultpercentage
            FROM test,testclassinfo
            WHERE test.id=? AND test.type=testclassinfo.id"""
        else:
            searchstr = """
            SELECT test.testrunid,test.type,test.resultpercentage
            FROM test
            WHERE test.id=?"""
        res = self._FetchOne(searchstr, (testid, ))
        if not res:
            return (None, None, None)
        return res

    def getFullTestInfo(self, testid, rawinfo=False, onlyargs=False):
        """
        Returns a tuple with the following info:
        * the testrun id in which it was executed
        * the type of the test
        * the arguments (dictionnary)
        * the results (checklist list)
        * the result percentage
        * the extra information (dictionnary)
        * the output files (dictionnary)

        If rawinfo is set to True, then the keys of the following
        dictionnaries will be integer identifiers (and not strings):
        * arguments, results, extra information, output files
        Also, the testtype will be the testclass ID (and not a string)
        """
        testrunid, ttype, resperc = self.getTestInfo(testid, rawinfo)
        if testrunid == None:
            return (None, None, None, None, None, None, None)

        # Query should be done differently for rawinfo or not
        # WE SHOULD NOT DO SEVERAL QUERIES !
        args = self.__getArguments(testid, rawinfo)
        if onlyargs:
            results, extras, ofs = [], [], {}
        else:
            results = self.__getCheckList(testid, rawinfo)
            extras = self.__getExtraInfo(testid, rawinfo)
            ofs = self.__getOutputFiles(testid, rawinfo)
        return (testrunid, ttype, args, results, resperc, extras, ofs)

    def getTestClassInfoFull(self, testtype, withparents=True):
        searchstr = """SELECT id,parent,description,fulldescription
        FROM testclassinfo WHERE type=?"""
        res = self._FetchOne(searchstr, (testtype, ))
        if not res:
            return (None, None, None, None, None, None)
        tcid, parent, desc, fulldesc = res
        args = self.__getDict("testclassinfo_arguments_dict", tcid, txtonly=True)
        checks = self.__getDict("testclassinfo_checklist_dict", tcid, txtonly=True)
        extras = self.__getDict("testclassinfo_extrainfo_dict", tcid, txtonly=True)
        outputfiles = self.__getDict("testclassinfo_outputfiles_dict",
                                    tcid, txtonly=True)
        if withparents:
            rp = parent
            while rp:
                ptcid, prp = self._FetchOne(searchstr, (rp, ))[:2]
                args.update(self.__getDict("testclassinfo_arguments_dict",
                                          ptcid, txtonly=True))
                checks.update(self.__getDict("testclassinfo_checklist_dict",
                                            ptcid, txtonly=True))
                extras.update(self.__getDict("testclassinfo_extrainfo_dict",
                                            ptcid, txtonly=True))
                outputfiles.update(self.__getDict("testclassinfo_outputfiles_dict",
                                                 ptcid, txtonly=True))
                rp = prp

        return (desc, fulldesc, args, checks, extras, outputfiles, parent)

    def getTestClassInfo(self, testtype, withparents=True):
        fargs = self.getTestClassInfoFull(testtype, withparents)
        desc, fulldesc, args, checks, extras, outputfiles, parent = fargs

        return (desc, fulldesc, args, checks, extras, outputfiles)

    def getMonitorClassInfoFull(self, monitortype, withparents=True):
        searchstr = """SELECT parent,description
        FROM testclassinfo WHERE type=?"""
        res = self._FetchOne(searchstr, (monitortype, ))
        if not res:
            return (None, None, None, None, None, None)
        parent, desc = res
        args = self.__getDict("testclassinfo_arguments_dict",
                              monitortype, txtonly=True)
        checks = self.__getDict("testclassinfo_checklist_dict",
                                monitortype, txtonly=True)
        extras = self.__getDict("testclassinfo_extrainfo_dict",
                                monitortype, txtonly=True)
        outputfiles = self.__getDict("testclassinfo_outputfiles_dict",
                                     monitortype, txtonly=True)
        if withparents:
            rp = parent
            while rp:
                prp = self._FetchOne(searchstr, (rp, ))[0]
                args.update(self.__getDict("testclassinfo_arguments_dict",
                                           prp, txtonly=True))
                checks.update(self.__getDict("testclassinfo_checklist_dict",
                                             prp, txtonly=True))
                extras.update(self.__getDict("testclassinfo_extrainfo_dict",
                                             prp, txtonly=True))
                outputfiles.update(self.__getDict("testclassinfo_outputfiles_dict",
                                                  prp, txtonly=True))
                rp = prp

        return (desc, args, checks, extras, outputfiles, parent)

    def getMonitorsIDForTest(self, testid):
        """
        Returns a list of monitorid for the given test
        """
        searchstr = "SELECT test.id FROM test WHERE test.parentid=? AND test.ismonitor=1"
        res = self._FetchAll(searchstr, (testid, ))
        if not res:
            return []
        return list(zip(*res)[0])

    def getMonitorInfo(self, monitorid, rawinfo=False):
        """
        Returns a tuple with the following info:
        * the ID of the test on which the monitor was applied
        * the type of the monitor
        * the result percentage

        If rawinfo is True, the ID of the monitortype will be returned instead
        of the name of the monitortype.
        """
        if rawinfo == False:
            searchstr = """
            SELECT test.parentid, testclassinfo.type, test.resultpercentage
            FROM test,testclassinfo
            WHERE test.id=? AND testclassinfo.id=test.type"""
        else:
            searchstr = """
            SELECT test.testid,test.type,test.resultpercentage
            FROM test
            WHERE test.id=?"""
        res = self._FetchOne(searchstr, (monitorid, ))
        if not res:
            return (None, None, None)
        return res

    def __getExtendedMonitorInfo(self, monitorid, mtype=None, rawinfo=False, onlyargs=False):
        args = self.__getArguments(monitorid, rawinfo)
        if onlyargs:
            results = {}
            extras = {}
            outputfiles = {}
        else:
            results = self.__getCheckList(monitorid, rawinfo)
            extras = self.__getExtraInfo(monitorid, rawinfo)
            outputfiles = self.__getOutputFiles(monitorid, rawinfo)
        return (args, results, extras, outputfiles)

    def getFullMonitorInfo(self, monitorid, rawinfo=False):
        """
        Returns a tuple with the following info:
        * the ID of the test on which this monitor was applied
        * the type of the monitor
        * the arguments (dictionnary)
        * the results (dictionnary)
        * the result percentage
        * the extra information (dictionnary)
        * the output files (dictionnary)
        """
        res = self.getMonitorInfo(monitorid, rawinfo)
        if res == (None, None, None):
            return (None, None, None, None, None, None, None)
        testid, mtype, resperc = res
        args, results, extras, outputfiles = self.__getExtendedMonitorInfo(monitorid, mtype, rawinfo)
        return (testid, mtype, args, results, resperc, extras, outputfiles)

    def getFullMonitorsInfoForTest(self, testid, rawinfo=False, onlyargs=False):
        if rawinfo == False:
            searchstr = """
            SELECT monitor.id,monitorclassinfo.type,monitor.resultpercentage
            FROM monitor,monitorclassinfo
            WHERE monitor.testid=? AND monitorclassinfo.id=monitor.type"""
        else:
            searchstr = """
            SELECT monitor.id,monitor.type,monitor.resultpercentage
            FROM monitor
            WHERE monitor.testid=?"""
        res1 = self._FetchAll(searchstr, (testid, ))
        if not res1:
            return []
        res = []
        for mid,mtype,mperc in res1:
            args, results, extras, outputfiles = self.__getExtendedMonitorInfo(mid, mtype, rawinfo, onlyargs=onlyargs)
            res.append((mid, mtype, mperc, args, results, extras, outputfiles))
        return res

    def findTestsByArgument(self, testtype, arguments, testrunid=None, monitorids=None, previd=None):
        searchstr = """
        SELECT DISTINCT test.id
        FROM test, test_arguments_dict
        WHERE test.id=test_arguments_dict.containerid """
        initialsearchargs = []

        # the following are only needed for the first query (or the most nested queries)
        initialsearchstr = searchstr
        if not testrunid == None:
            initialsearchstr += "AND test.testrunid=? "
            initialsearchargs.append(testrunid)
        initialsearchstr += "AND test.type=? "
        initialsearchargs.append(testtype)

        # we'll now recursively search for the compatible tests
        # we first start to look for all tests matching the first argument
        # then from those tests, find those that match the second,...
        # Break out from the loop whenever there's nothing more matching

        firsttime = True

        # build the query using nested queries

        fullquery = initialsearchstr
        args = initialsearchargs[:]

        for key, val in arguments.iteritems():
            value = val
            if isinstance(val, int):
                valstr = "intvalue"
            elif isinstance(val, basestring):
                valstr = "txtvalue"
            else:
                raise BlobException
            tmpsearch = "AND test_arguments_dict.name=? AND test_arguments_dict.%s=? " % valstr
            if firsttime:
                tmpargs = initialsearchargs[:]
                tmpargs.extend([key, value])
                fullquery = initialsearchstr + tmpsearch
                args = tmpargs
                firsttime = False
            else:
                # nest the previous query
                fullquery = searchstr + tmpsearch + "AND test.id IN (" + fullquery + ")"
                args = [key, value] + args

        # do the query
        try:
            res = [x[0] for x in self._FetchAll(fullquery, tuple(args))]
        except:
            res = []

        # finally... make sure that for the monitors that both test
        # share, they have the same arguments
        if res != [] and (previd != None or monitorids != None):
            tmp = []
            if previd and not monitorids:
                monitors = self.getFullMonitorsInfoForTest(previd,
                                                           rawinfo=True,
                                                           onlyargs=True)
            else:
                monitors = [self.getFullMonitorInfo(x) for x in monitorids]

            for pid in res:
                similar = True
                pm = self.getFullMonitorsInfoForTest(pid, rawinfo=True,
                                                     onlyargs=True)

                samemons = []
                # for each candidate monitors
                for tid, mtype, margs, mres, mresperc, mextra, mout in pm:
                    # for each original monitor
                    for mon in monitors:
                        if mon[1] == mtype:
                            # same type of monitor, now check arguments
                            samemons.append((margs, mon[2]))
                if not samemons == []:
                    for cand, mon in samemons:
                        if not cand == mon:
                            similar = False
                if similar:
                    tmp.append(pid)
            res = tmp
        return res

    # Methods to be implemented in subclasses
    # DBAPI implementation specific

    def _getDBScheme(self):
        """
        Returns the DB Scheme used for the given class
        """
        raise NotImplementedError

    def _openDatabase(self):
        """
        Open the database

        Subclasses should implement this and return the Connection object.
        """
        raise NotImplementedError

    def _getDatabaseSchemeVersion(self):
        """
        Returns the scheme version of the currently loaded databse

        Returns None if there's no properly configured scheme, else
        returns the version
        """
        raise NotImplementedError

    # Optional overrides

    def _createTables(self):
        """Makes sure the tables are properly created"""
        debug("Calling db creation script")
        #self.con.executescript(DB_SCHEME)
        self._ExecuteScript(self._getDBScheme())
        # add database version
        cmstr = "INSERT INTO version (version, modificationtime) VALUES (?, ?)"
        self._ExecuteCommit(cmstr, (DB_SCHEME_VERSION, int(time.time())))
        debug("Tables properly created")

    def _shutDown(self):
        """
        Subclasses should implement this method for specific closing/cleanup.
        """
        if self.con:
            debug("Closing database Connection")
            self.con.close()

    # PROTECTED METHODS
    # Usable by subclasses

    def _ExecuteScript(self, instructions, *args, **kwargs):
        """
        Executes the given script.
        """
        self._ExecuteCommit(instructions, commit=False, *args, **kwargs)

    def _ExecuteCommit(self, instruction, *args, **kwargs):
        """
        Calls .execute(instruction, *args, **kwargs) and .commit()

        Returns the last row id

        Threadsafe
        """
        commit = kwargs.pop("commit", True)
        threadsafe = kwargs.pop("threadsafe", False)
        debug("%s args:%r kwargs:%r", instruction, args, kwargs)
        if not threadsafe:
            self._lock.acquire()
        try:
            cur = self.con.cursor()
            cur.execute(instruction, *args, **kwargs)
            if commit:
                self.con.commit()
        finally:
            if not threadsafe:
                self._lock.release()
        return cur.lastrowid

    def _ExecuteMany(self, instruction, *args, **kwargs):
        commit = kwargs.pop("commit", True)
        threadsafe = kwargs.pop("threadsafe", False)
        debug("%s args:%r, kwargs:%r", instruction, args, kwargs)
        if not threadsafe:
            self._lock.acquire()
        try:
            cur = self.con.cursor()
            cur.executemany(instruction, *args, **kwargs)
            if commit:
                self.con.commit()
        finally:
            if not threadsafe:
                self._lock.release()

    def _FetchAll(self, instruction, *args, **kwargs):
        """
        Executes the given SQL query and returns a list
        of tuples of the results

        Threadsafe
        """
        debug("instruction %s", instruction)
        debug("args: %r", args)
        debug("kwargs: %r", kwargs)
        self._lock.acquire()
        try:
            cur = self.con.cursor()
            cur.execute(instruction, *args, **kwargs)
            res = cur.fetchall()
        finally:
            self._lock.release()
        debug("returning %r", res)
        return list(res)

    def _FetchOne(self, instruction, *args, **kwargs):
        """
        Executes the given SQL query and returns a unique
        tuple of result

        Threadsafe
        """
        debug("instruction %s", instruction)
        debug("args: %r", args)
        debug("kwargs: %r", kwargs)
        self._lock.acquire()
        try:
            cur = self.con.cursor()
            cur.execute(instruction, *args, **kwargs)
            res = cur.fetchone()
        finally:
            self._lock.release()
        debug("returning %r", res)
        return res

    def _getTestTypeID(self, testtype):
        """
        Returns the test.id for the given testtype

        Returns None if there is no information regarding the given testtype
        """
        res = self._FetchOne("SELECT id FROM testclassinfo WHERE type=?",
                             (testtype, ))
        if res == None:
            return None
        return res[0]

    def _getMonitorTypeID(self, monitortype):
        """
        Returns the monitor.id for the given monitortype

        Returns None if there is no information regarding the given monitortype
        """
        res = self._FetchOne("SELECT id FROM testclassinfo WHERE type=?",
                             (monitortype, ))
        if res == None:
            return None
        return res[0]


    def getTestTypeUsed(self, testrunid):
        """
        Returns a list of test type names being used in the given testrunid
        """
        getstr = """SELECT DISTINCT testclassinfo.type
        FROM test,testclassinfo
        WHERE test.type=testclassinfo.id AND test.testrunid=?"""
        res = self._FetchAll(getstr, (testrunid, ))
        if len(res):
            return list(zip(*res)[0])
        return []

    def getMonitorTypesUsed(self, testrunid):
        """
        Returns a list of monitor type names being used in the given testrunid
        """
        getstr = """SELECT DISTINCT testclassinfo.type
        FROM test,testclassinfo
        WHERE test.type=testclassinfo.id
        AND test.testrunid=? AND test.ismonitor=1"""
        res = self._FetchAll(getstr, (testrunid, ))
        if len(res):
            return list(zip(*res)[0])
        return []


    # PRIVATE METHODS

    def __closedb(self, callback, *args, **kwargs):
        self._shutDown()
        callback(*args, **kwargs)


    def __merge(self, otherdb, testruns=None):
        # FIXME : This is a straight-forward method that could be optimized
        # We just :
        # * Get some data from otherdb
        # * Save it into self (modifying key id on the fly)
        debug("otherdb : %r", otherdb)
        debug("testruns : %r", testruns)
        if testruns == None:
            testruns = otherdb.listTestRuns()
        for trid in testruns:
            self.__mergeTestRun(otherdb, trid)

    def __mergeTestRun(self, otherdb, othertrid):
        debug("othertrid:%d", othertrid)
        # FIXME : Try to figure out (by some way) if we're not merging an
        # existing testrun (same client, dates, etc...)

        debug("Merging client info")
        # 1. Client info
        # if it already exists, don't insert but get back the new clientid
        oclsoft, oclname, ocluser = otherdb.getClientInfoForTestRun(othertrid)
        clid = self.setClientInfo(oclsoft, oclname, ocluser)

        debug("Creating TestRun Entry")
        # 2. Create the TestRun entry, and get the id back for further usage
        unused_clid, starttime, stoptime = otherdb.getTestRun(othertrid)
        trid = self.__rawStartNewTestRun(clid, starttime)
        self.__rawEndTestRun(trid, stoptime)

        debug("copying over Environment")
        # 3. Environment
        env = otherdb.getEnvironmentForTestRun(othertrid)
        if env:
            self._storeEnvironmentDict(trid, env)

        debug("Ensuring all TestClassInfo are present in self")
        # We need to figure out which test and monitor types are being used
        # in this testrun.
        testclasses = otherdb.getTestTypeUsed(othertrid)
        for tclass in testclasses:
            if not self.__hasTestClassInfo(tclass):
                self.__mergeTestClassInfo(tclass, otherdb)

        debug("Ensuring all MonitorClassInfo are present in self")
        monitorclasses = otherdb.getMonitorTypesUsed(othertrid)
        for mclass in monitorclasses:
            if not self.__hasMonitorClassInfo(mclass):
                self.__mergeMonitorClassInfo(mclass, otherdb)

        debug("Getting Class/Monitor mappings")
        testclassmap = self.__getTestClassRemoteMapping(otherdb)
        monitorclassmap = self.__getMonitorClassRemoteMapping(otherdb)
        testmapping = {}

        debug("Inserting tests")
        for othertestid in otherdb.getTestsForTestRun(othertrid):
            # this includes both tests and scenarios
            # to properly re-map subtests we need to have the mapping of
            # oldtestid => newtestid
            newtestid = self.__mergeTest(otherdb, othertestid, trid,
                                         testclassmap, monitorclassmap)
            testmapping[othertestid] = newtestid

        debug("Merging subtest table")
        # Finnally move all subtests using the testmapping
        selectstr = """
        SELECT testid, scenarioid FROM subtests
        WHERE testid IN ( %s )""" % ','.join([str(x) for x in testmapping.keys()])
        insertstr = """
        INSERT INTO subtests (testid, scenarioid) VALUES (?, ?)"""
        subtests = otherdb._FetchAll(selectstr, ())
        # convert the subtests from old testid to new testid
        tocommit = []
        for testid, scenarioid in subtests:
            tocommit.append((testmapping[testid], testmapping[scenarioid]))
        self._ExecuteMany(insertstr, tocommit)

        debug("done merging testrun")

    def __mergeTest(self, otherdb, otid, testrunid, testclassmap,
                    monitorclassmap):
        """
        Copy all information about test 'otid' from otherdb into self, including monitor.

        Returns the id of the new test entry
        """
        debug("otid:%d, testrunid:%d", otid, testrunid)
        insertstr = """
        INSERT INTO test (testrunid, type, resultpercentage)
        VALUES (?, ?, ?)
        """

        oldtr, testname, args, checks, resperc, extras, outputfiles = otherdb.getFullTestInfo(otid)
        # convert testname (str) to testtype (int)
        debug("testname %s", testname)
        tmp = testclassmap[testname]
        ttype = tmp[0]

        newtid = self._ExecuteCommit(insertstr, (testrunid, ttype, resperc))

        # store the dictionnaries
        self.__storeTestArgumentsDict(newtid, args, testname)
        self.__storeTestCheckListList(newtid, checks, testname)
        self.__storeTestExtraInfoDict(newtid, extras, testname)
        self.__storeTestOutputFileDict(newtid, outputfiles, testname)

        # and on to the monitors
        monitorids = otherdb.getMonitorsIDForTest(otid)
        for oldmid in monitorids:
            un_tid, omtype, margs, mres, mresperc, mextras, moutputs = otherdb.getFullMonitorInfo(oldmid)
            # convert omtype to self
            debug("omtype:%r", omtype)
            debug("monitorclassmap:%r", monitorclassmap)
            monitorname = None
            for mname,mtypes in monitorclassmap.iteritems():
                if omtype == mname:
                    id_self, id_other = mtypes
                    mtype = id_self
                    break
            self.__rawStoreMonitor(newtid, mtype, omtype,
                                   mresperc, margs, mres, mextras, moutputs)
        return newtid

    def __mergeTestClassInfo(self, ttype, otherdb):
        """
        Copy all information about ttype from otherdb into self

        Returns the new TestClassInfo ID in self for the given test type.
        """
        debug("ttype:%s", ttype)
        res = None
        fargs = otherdb.getTestClassInfoFull(ttype, withparents=False)
        desc, fdesc, args, checks, extras, outputfiles, ptype = fargs

        # figure out if we have ttype's parent already in self
        if ptype and not self.__hasTestClassInfo(ptype):
            self.__mergeTestClassInfo(ptype, otherdb)

        self.__rawInsertTestClassInfo(ttype, desc, fdesc, args, checks, extras,
                                      outputfiles, ptype)

    def __mergeMonitorClassInfo(self, ttype, otherdb):
        """
        Copy all information about ttype from otherdb into self

        Returns the new MonitorClassInfo ID in self for the given monitor type.
        """
        res = None
        fargs = otherdb.getMonitorClassInfoFull(ttype, withparents=False)
        desc, args, checks, extras, outputfiles, ptype = fargs

        # figure out if we have ttype's parent already in self
        if ptype and not self.__hasMonitorClassInfo(ptype):
            self.__mergeMonitorClassInfo(ptype, otherdb)

        self.__rawInsertMonitorClassInfo(ttype, ptype, desc, args, checks, extras,
                                         outputfiles)

    def __getRemoteMapping(self, tablename, otherdb, field1='type', field2='id'):
        # field1 is the common field
        # field2 is the one that varies
        getstr = """SELECT %s, %s FROM %s""" % (field1, field2, tablename)
        selfcl = dict(self._FetchAll(getstr, ( )))
        othercl = dict(otherdb._FetchAll(getstr, ( )))
        # we now have two dicts with name:id
        res = {}
        for selftype, selfid in selfcl.iteritems():
            if othercl.has_key(selftype):
                res[selftype] = (selfid, othercl[selftype])
        debug("returning mapping %r", res)
        return res

    def __getTestClassRemoteMapping(self, otherdb):
        """
        Returns the mapping of all common testclassinfo between self and otherdb

        Key : testname
        Value : (id in selfdb, id in otherdb)
        """
        return self.__getRemoteMapping("testclassinfo", otherdb)
        # now that we have the class mappings, we can get the maps for 

    def __getMonitorClassRemoteMapping(self, otherdb):
        """
        Returns a mapping of all common monitorclassinfo between self and otherdb.

        Key : monitorname
        Value : (id in selfdb, id in otherdb)
        """
        return self.__getRemoteMapping("testclassinfo", otherdb)

    def __rawStartNewTestRun(self, clientid, starttime):
        insertstr = """
        INSERT INTO testrun (clientid, starttime) VALUES (?, ?)
        """
        return self._ExecuteCommit(insertstr,(clientid, starttime))

    def __startNewTestRun(self, testrun, clientid):
        # create new testrun entry with client entry
        debug("testrun:%r", testrun)
        if testrun in self.__testruns.keys():
            warning("Testrun already started !")
            return
        if clientid:
            self.__clients[testrun] = clientid
        else:
            clientid = self.__clients.get(testrun, 0)
        testrunid = self.__rawStartNewTestRun(clientid, testrun._starttime)
        envdict = testrun.getEnvironment()
        if envdict:
            self._storeEnvironmentDict(testrunid, envdict)
        self.__testruns[testrun] = testrunid
        debug("Got testrun id %d", testrunid)
        return testrunid

    def __rawEndTestRun(self, testrunid, stoptime):
        updatestr = "UPDATE testrun SET stoptime=? WHERE id=?"
        self._ExecuteCommit(updatestr, (stoptime, testrunid))

    def __endTestRun(self, testrun):
        debug("testrun:%r", testrun)
        if not testrun in self.__testruns.keys():
            # add the testrun since it wasn't done before
            self.__startNewTestRun(testrun, None)
        self.__rawEndTestRun(self.__testruns[testrun],
                             testrun._stoptime)
        debug("updated")

    def __rawNewTestStarted(self, testrunid, testtype, commit=True):
        debug("testrunid: %d, testtype: %r, commit: %r",
              testrunid, testtype, commit)
        insertstr = "INSERT INTO test (testrunid, type) VALUES (?, ?)"
        return self._ExecuteCommit(insertstr,
                                   (testrunid, testtype),
                                   commit=commit)

    def __newTestStarted(self, testrun, test, commit=True):
        from insanity.test import Test
        if not isinstance(test, Test):
            raise TypeError("test isn't a Test instance !")
        if not testrun in self.__testruns.keys():
            self.__startNewTestRun(testrun, None)
        debug("test:%r", test)
        self.__storeTestClassInfo(test)
        testtid = self._getTestTypeID(test.__test_name__)
        testid = self.__rawNewTestStarted(self.__testruns[testrun],
                                          testtid, commit)
        debug("got testid %d", testid)
        self.__tests[test] = testid


    def __rawStoreMonitor(self, testid, monitortype, monitorname,
                          resperc, args, checks, extras, outputfiles,
                          testrunid):
        insertstr = """
        INSERT INTO test (parentid, type, resultpercentage, ismonitor, testrunid)
        VALUES (?, ?, ?, 1, ?)
        """
        debug("testid:%d, monitortype:%s, monitorname:%s, resperc:%f",
              testid, monitortype, monitorname, resperc)
        mid = self._ExecuteCommit(insertstr, (testid, monitortype,
                                              resperc, testrunid))
        debug("args:%r", args)
        debug("checks:%r", checks)
        debug("extras:%r", extras)
        debug("outputfiles:%r", outputfiles)
        # store related dictionnaries
        self.__storeMonitorArgumentsDict(mid, args, monitorname)
        self.__storeMonitorCheckListDict(mid, checks, monitorname)
        self.__storeMonitorExtraInfoDict(mid, extras, monitorname)
        self.__storeMonitorOutputFileDict(mid, outputfiles, monitorname)

    def __storeMonitor(self, monitor, testid, testrunid):
        debug("monitor:%r:%d", monitor, testid)
        # store monitor
        self.__storeMonitorClassInfo(monitor)

        monitortype = self._getMonitorTypeID(monitor.__monitor_name__)
        self.__rawStoreMonitor(testid, monitortype, monitor.__monitor_name__,
                               monitor.getSuccessPercentage(),
                               monitor.getArguments(),
                               monitor.getCheckList(),
                               monitor.getExtraInfo(),
                               monitor.getOutputFiles(),
                               testrunid)

    def __newTestFinished(self, testrun, test, parentid=None):
        debug("testrun:%r, test:%r", testrun, test)
        if not testrun in self.__testruns.keys():
            debug("different testrun, starting new one")
            self.__startNewTestRun(testrun, None)

        if not self.__tests.has_key(test):
            debug("we don't have test yet, starting that one")
            self.__newTestStarted(testrun, test, commit=False)

        tid = self.__tests[test]
        debug("test:%r:%d", test, tid)

        from insanity.scenario import Scenario
        # if it's a scenario, fill up the subtests
        if isinstance(test, Scenario):
            debug("test is a scenario, adding subtests")
            for sub in test.tests:
                self.__newTestFinished(testrun, sub, parentid=tid)
            debug("done adding subtests")
            self._ExecuteCommit("""UPDATE test SET test.isscenario=1 WHERE test.id=?""", (tid, ))

        # store the dictionnaries
        self.__storeTestArgumentsDict(tid, test.getArguments(),
                                     test.__test_name__)
        self.__storeTestCheckListList(tid, test.getCheckList(),
                                     test.__test_name__)
        self.__storeTestExtraInfoDict(tid, test.getExtraInfo(),
                                     test.__test_name__)
        self.__storeTestOutputFileDict(tid, test.getOutputFiles(),
                                      test.__test_name__)

        # finally update the test
        updatestr = "UPDATE test SET resultpercentage=?, parentid=? WHERE id=?"
        resultpercentage = test.getSuccessPercentage()
        self._ExecuteCommit(updatestr, (resultpercentage, parentid, tid))

        # and on to the monitors
        for monitor in test._monitorinstances:
            self.__storeMonitor(monitor, tid, self.__testruns[testrun])
        debug("done adding information for test %d", tid)


    def __getTestClassMapping(self, testtype, dictname):
        return self.__getClassMapping(self.__tcmapping,
                                      "testclassinfo",
                                      testtype, dictname)

    def __getMonitorClassMapping(self, monitortype, dictname):
        return self.__getClassMapping(self.__mcmapping,
                                      "testclassinfo",
                                      monitortype, dictname)

    def __getClassMapping(self, mapping, classtable, classtype, dictname,
                          vals=None):
        """
        Returns a dictionnary of mappings for the given class/table.

        mapping : cache of all mappings
        classtable : name of the table for the given container class (*classinfo)
        classtype : id of the class in the classtable
        dictname : name of the table (*classinfo_*_dict)
        vals : (optional) dict of all values we wish to store.

        If 'vals' is provided, then we will ensure that all keys of vals are
        present in 'dictname' for the provided 'classtype'
        """

        # Search in cache first
        if classtype in mapping:
            if dictname in mapping[classtype]:
                return mapping[classtype][dictname]

        # returns a dictionnary of name : id mapping for a test's
        # arguments, including the parent class mapping
        searchstr = "SELECT parent,id FROM %s WHERE type=?" % classtable
        res = self._FetchOne(searchstr, (classtype, ))
        if not res:
            return {}
        rp, tcid = res
        mapsearch = """
        SELECT name,id
        FROM %s
        WHERE containerid=?""" % dictname
        maps = self._FetchAll(mapsearch, (tcid, ))
        while rp:
            res = self._FetchOne(searchstr, (rp, ))
            rp, tcid = res
            vals = self._FetchAll(mapsearch, (tcid, ))
            maps.extend(vals)

        if not classtype in mapping:
            mapping[classtype] = {}
        mapping[classtype][dictname] = dict(maps)
        return mapping[classtype][dictname]


    def __getTestClassArgumentMapping(self, testtype):
        return self.__getTestClassMapping(testtype, "testclassinfo_arguments_dict")
    def __getTestClassCheckListMapping(self, testtype):
        return self.__getTestClassMapping(testtype, "testclassinfo_checklist_dict")
    def __getTestClassExtraInfoMapping(self, testtype):
        return self.__getTestClassMapping(testtype, "testclassinfo_extrainfo_dict")
    def __getTestClassOutputFileMapping(self, testtype):
        return self.__getTestClassMapping(testtype, "testclassinfo_outputfiles_dict")

    def __getMonitorClassArgumentMapping(self, monitortype):
        return self.__getMonitorClassMapping(monitortype,
                                            "testclassinfo_arguments_dict")
    def __getMonitorClassCheckListMapping(self, monitortype):
        return self.__getMonitorClassMapping(monitortype,
                                            "testclassinfo_checklist_dict")
    def __getMonitorClassExtraInfoMapping(self, monitortype):
        return self.__getMonitorClassMapping(monitortype,
                                            "testclassinfo_extrainfo_dict")
    def __getMonitorClassOutputFileMapping(self, monitortype):
        return self.__getMonitorClassMapping(monitortype,
                                            "testclassinfo_outputfiles_dict")
    def __storeDict(self, dicttable, containerid, pdict):
        if not pdict:
            # empty dictionnary
            debug("Empty dictionnary, returning")
            return
        # let's sort the dictionnary by keys, just for the sake of it
        keys = pdict.keys()
        keys.sort()
        self.__storeList(dicttable, containerid, [(k,pdict[k]) for k in keys])

    def __storeList(self, dicttable, containerid, pdict):
        if not pdict:
            # empty dictionnary
            debug("Empty list, returning")
            return

        def flatten_tuple(atup):
            if not atup:
                return atup
            res = []
            for k,v in atup:
                if isinstance(v, list):
                    for i in v:
                        res.append((k,i))
                elif isinstance(v, dict):
                    for s,u in v.iteritems():
                        res.append((str(k)+"."+str(s), u))
                else:
                    res.append((k,v))
            return res

        pdict = flatten_tuple(pdict)

        self._lock.acquire()
        try:
            cur = self.con.cursor()
            insertstr = """INSERT INTO %s (containerid, name, %s)
            VALUES (?, ?, ?)"""
            for key, value in pdict:
                debug("Adding key:%s , value:%r", key, value)
                if value == None:
                    self._ExecuteCommit("""INSERT INTO %s (containerid, name) VALUES (?, ?)""" % dicttable,
                                        (containerid, key), commit=False, threadsafe=True)
                    continue
                val = value
                if isinstance(value, int):
                    valstr = "intvalue"
                elif isinstance(value, basestring):
                    valstr = "txtvalue"
                else:
                    valstr = "txtvalue"
                    val = repr(value)
                comstr = insertstr % (dicttable, valstr)
                #debug("instruction:%s", comstr)
                #debug("%s, %s, %s", containerid, key, val)
                self._ExecuteCommit(comstr, (containerid, key, val),
                                    commit=False, threadsafe=True)
        finally:
            self._lock.release()

    def __getArguments(self, containerid, rawinfo=False):
        fullsearch = """SELECT testclassinfo_arguments_dict.name,
        test_arguments_dict.intvalue, test_arguments_dict.txtvalue
        FROM test_arguments_dict, testclassinfo_arguments_dict
        WHERE test_arguments_dict.containerid=? AND
        test_arguments_dict.name=testclassinfo_arguments_dict.id"""

        normalsearch = """SELECT test_arguments_dict.name,
        test_arguments_dict.intvalue, test_arguments_dict.txtvalue
        FROM test_arguments_dict
        WHERE test_arguments_dict.containerid=?"""

        if rawinfo == False:
            res = self._FetchAll(fullsearch, (containerid, ))
        else:
            res = self._FetchAll(normalsearch, (containerid, ))
        d = {}
        for n, iv, tv in res:
            if iv != None:
                d[n] = iv
            else:
                d[n] = tv
        return d

    def __getExtraInfo(self, containerid, rawinfo=False):
        fullsearch = """SELECT testclassinfo_extrainfo_dict.name,
        test_extrainfo_dict.intvalue, test_extrainfo_dict.txtvalue
        FROM test_extrainfo_dict, testclassinfo_extrainfo_dict
        WHERE test_extrainfo_dict.containerid=? AND
        test_extrainfo_dict.name=testclassinfo_extrainfo_dict.id"""

        normalsearch = """SELECT test_extrainfo_dict.name,
        test_extrainfo_dict.intvalue, test_extrainfo_dict.txtvalue
        FROM test_extrainfo_dict
        WHERE test_extrainfo_dict.containerid=?"""

        if rawinfo == False:
            res = self._FetchAll(fullsearch, (containerid, ))
        else:
            res = self._FetchAll(normalsearch, (containerid, ))
        d = {}
        for n, iv, tv in res:
            if iv != None:
                d[n] = iv
            else:
                d[n] = tv
        return d

    def __getCheckList(self, containerid, rawinfo=False):
        fullsearch = """SELECT testclassinfo_checklist_dict.name,
        test_checklist_list.intvalue
        FROM test_checklist_list, testclassinfo_checklist_dict
        WHERE test_checklist_list.containerid=? AND
        test_checklist_list.name=testclassinfo_checklist_dict.id"""

        normalsearch = """SELECT test_checklist_list.name,
        test_checklist_list.intvalue
        FROM test_checklist_list
        WHERE test_checklist_list.containerid=?"""

        if rawinfo == False:
            res = self._FetchAll(fullsearch, (containerid, ))
        else:
            res = self._FetchAll(normalsearch, (containerid, ))
        return list(res)

    def __getOutputFiles(self, containerid, rawinfo=False):
        fullsearch = """SELECT testclassinfo_outputfiles_dict.name,
        test_outputfiles_dict.txtvalue
        FROM test_outputfiles_dict, testclassinfo_outputfiles_dict
        WHERE test_outputfiles_dict.containerid=? AND
        test_outputfiles_dict.name=testclassinfo_outputfiles_dict.id"""

        normalsearch = """SELECT test_outputfiles_dict.name,
        test_outputfiles_dict.txtvalue
        FROM test_outputfiles_dict
        WHERE test_outputfiles_dict.containerid=?"""

        if rawinfo == False:
            res = self._FetchAll(fullsearch, (containerid, ))
        else:
            res = self._FetchAll(normalsearch, (containerid, ))
        return dict(res)

    def __getDict(self, tablename, containerid, txtonly=False,
                 intonly=False):
        return dict(self.__getList(tablename, containerid,
                                   txtonly, intonly))

    def __getList(self, tablename, containerid, txtonly=False,
                 intonly=False):
        # returns a list object
        # get all the key, value for that dictid
        searchstr = "SELECT * FROM %s WHERE containerid=?" % tablename
        res = self._FetchAll(searchstr, (containerid, ))

        dc = []
        for row in res:
            if intonly or txtonly:
                val = row[3]
            else:
                # we need to figure it out
                ival, tval = row[3:]
                if not ival == None:
                    val = ival
                elif not tval == None:
                    val = str(tval)
                else:
                    val = None
            dc.append((row[2], val))
        return dc

    def __storeTestArgumentsDict(self, testid, dic, testtype):
        # transform the dictionnary from names to ids
        maps = self.__getTestClassArgumentMapping(testtype)
        return self.__storeDict("test_arguments_dict",
                               testid, map_dict(dic, maps))

    def __storeTestCheckListList(self, testid, dic, testtype):
        maps = self.__getTestClassCheckListMapping(testtype)
        return self.__storeList("test_checklist_list",
                               testid, map_list(dic, maps))

    def __storeTestExtraInfoDict(self, testid, dic, testtype):
        maps = self.__getTestClassExtraInfoMapping(testtype)
        return self.__storeDict("test_extrainfo_dict",
                               testid, map_dict(dic, maps))

    def __storeTestOutputFileDict(self, testid, dic, testtype):
        maps = self.__getTestClassOutputFileMapping(testtype)
        return self.__storeDict("test_outputfiles_dict",
                               testid, map_dict(dic, maps))

    def __storeMonitorArgumentsDict(self, monitorid, dic, monitortype):
        maps = self.__getMonitorClassArgumentMapping(monitortype)
        return self.__storeDict("test_arguments_dict",
                               monitorid, map_dict(dic, maps))

    def __storeMonitorCheckListDict(self, monitorid, dic, monitortype):
        maps = self.__getMonitorClassCheckListMapping(monitortype)
        return self.__storeDict("test_checklist_list",
                               monitorid, map_dict(dic, maps))

    def __storeMonitorExtraInfoDict(self, monitorid, dic, monitortype):
        maps = self.__getMonitorClassExtraInfoMapping(monitortype)
        return self.__storeDict("test_extrainfo_dict",
                               monitorid, map_dict(dic, maps))

    def __storeMonitorOutputFileDict(self, monitorid, dic, monitortype):
        maps = self.__getMonitorClassOutputFileMapping(monitortype)
        return self.__storeDict("test_outputfiles_dict",
                               monitorid, map_dict(dic, maps))

    def __storeTestClassArgumentsDict(self, testclassinfoid, dic):
        return self.__storeDict("testclassinfo_arguments_dict",
                               testclassinfoid, dic)

    def __storeTestClassCheckListDict(self, testclassinfoid, dic):
        return self.__storeDict("testclassinfo_checklist_dict",
                               testclassinfoid, dic)

    def __storeTestClassExtraInfoDict(self, testclassinfoid, dic):
        return self.__storeDict("testclassinfo_extrainfo_dict",
                               testclassinfoid, dic)

    def __storeTestClassOutputFileDict(self, testclassinfoid, dic):
        return self.__storeDict("testclassinfo_outputfiles_dict",
                               testclassinfoid, dic)

    def __storeMonitorClassArgumentsDict(self, monitorclassinfoid, dic):
        return self.__storeDict("testclassinfo_arguments_dict",
                               monitorclassinfoid, dic)

    def __storeMonitorClassCheckListDict(self, monitorclassinfoid, dic):
        return self.__storeDict("testclassinfo_checklist_dict",
                               monitorclassinfoid, dic)

    def __storeMonitorClassExtraInfoDict(self, monitorclassinfoid, dic):
        return self.__storeDict("testclassinfo_extrainfo_dict",
                               monitorclassinfoid, dic)

    def __storeMonitorClassOutputFileDict(self, monitorclassinfoid, dic):
        return self.__storeDict("testclassinfo_outputfiles_dict",
                               monitorclassinfoid, dic)

    def _storeEnvironmentDict(self, testrunid, dic):
        return self.__storeDict("testrun_environment_dict",
                               testrunid, dic)

    def __rawInsertTestClassInfo(self, ctype, desc, fdesc, args, checklist,
                                 extrainfo, outputfiles, parent):
        # insert into db
        insertstr = """INSERT INTO testclassinfo
        (type, parent, description, fulldescription)
        VALUES (?, ?, ?, ?)"""
        tcid = self._ExecuteCommit(insertstr, (ctype, parent, desc, fdesc))

        # store the dicts
        self.__storeTestClassArgumentsDict(tcid, args)
        self.__storeTestClassCheckListDict(tcid, checklist)
        self.__storeTestClassExtraInfoDict(tcid, extrainfo)
        self.__storeTestClassOutputFileDict(tcid, outputfiles)


    def __insertTestClassInfo(self, tclass):
        ctype = tclass.__dict__.get("__test_name__").strip()
        searchstr = "SELECT * FROM testclassinfo WHERE type=?"
        if len(self._FetchAll(searchstr, (ctype, ))) >= 1:
            return False
        # get info
        desc = tclass.__dict__.get("__test_description__").strip()
        fdesc = tclass.__dict__.get("__test_full_description__")
        if fdesc:
            fdesc.strip()
        args = tclass.__dict__.get("__test_arguments__")
        if args:
            args = dict([(key, val[0]) for key,val in args.iteritems()])
        checklist = tclass.__dict__.get("__test_checklist__")
        extrainfo = tclass.__dict__.get("__test_extra_infos__")
        outputfiles = tclass.__dict__.get("__test_output_files__")
        from insanity.test import Test
        if tclass == Test:
            parent = None
        else:
            parent = tclass.__base__.__dict__.get("__test_name__").strip()

        self.__rawInsertTestClassInfo(ctype, desc, fdesc, args, checklist,
                                      extrainfo, outputfiles, parent)
        debug("done adding class info for %s", ctype)
        return True

    def __hasTestClassInfo(self, testtype):
        existstr = "SELECT * FROM testclassinfo WHERE type=?"
        res = self._FetchAll(existstr, (testtype, ))
        if len(res) > 0:
            # type already exists, returning
            return True
        return False

    def __storeTestClassInfo(self, testinstance):
        from insanity.test import Test
        # check if we don't already have info for this class
        debug("test name: %s", testinstance.__test_name__)
        if self.__hasTestClassInfo(testinstance.__test_name__):
            return
        # we need an inverted mro (so we can know the parent class)
        for cl in testinstance.__class__.mro():
            if not self.__insertTestClassInfo(cl):
                break
            if cl == Test:
                break

    def __hasMonitorClassInfo(self, monitortype):
        existstr = "SELECT * FROM testclassinfo WHERE type=?"
        res = self._FetchAll(existstr, (monitortype, ))
        if len(res) > 0:
            # type already exists, returning
            return True
        return False

    def __rawInsertMonitorClassInfo(self, ctype, parent, desc, args, checklist,
                                    extrainfo, outputfiles):
        # insert into db
        debug("ctype:%r, parent:%r, desc:%r", ctype, parent, desc)
        insertstr = """
        INSERT INTO testclassinfo (type, parent, description) VALUES (?, ?, ?)
        """
        tcid = self._ExecuteCommit(insertstr, (ctype, parent, desc))

        # store the dicts
        self.__storeMonitorClassArgumentsDict(tcid, args)
        self.__storeMonitorClassCheckListDict(tcid, checklist)
        self.__storeMonitorClassExtraInfoDict(tcid, extrainfo)
        self.__storeMonitorClassOutputFileDict(tcid, outputfiles)

    def __insertMonitorClassInfo(self, tclass):
        from insanity.monitor import Monitor
        ctype = tclass.__dict__.get("__monitor_name__").strip()
        if self.__hasMonitorClassInfo(ctype):
            return False
        # get info
        desc = tclass.__dict__.get("__monitor_description__").strip()
        args = tclass.__dict__.get("__monitor_arguments__")
        checklist = tclass.__dict__.get("__monitor_checklist__")
        extrainfo = tclass.__dict__.get("__monitor_extra_infos__")
        outputfiles = tclass.__dict__.get("__monitor_output_files__")
        if tclass == Monitor:
            parent = None
        else:
            parent = tclass.__base__.__dict__.get("__monitor_name__").strip()
        self.__rawInsertMonitorClassInfo(ctype, parent, desc, args, checklist,
                                         extrainfo, outputfiles)
        return True

    def __storeMonitorClassInfo(self, monitorinstance):
        from insanity.monitor import Monitor
        # check if we don't already have info for this class
        if self.__hasMonitorClassInfo(monitorinstance.__monitor_name__):
            return
        # we need an inverted mro (so we can now the parent class)
        for cl in monitorinstance.__class__.mro():
            if not self.__insertMonitorClassInfo(cl):
                break
            if cl == Monitor:
                break




DB_SCHEME_VERSION = 3
