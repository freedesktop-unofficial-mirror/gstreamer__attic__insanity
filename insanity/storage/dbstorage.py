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
from insanity.scenario import Scenario
from insanity.test import Test
from insanity.monitor import Monitor
from insanity.utils import reverse_dict, map_dict, map_list
from insanity.storage.storage import DataStorage
from insanity.storage.async import AsyncStorage, queuemethod

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
            self._updateTables(version, DB_SCHEME_VERSION)
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
        res = self._FetchAll(liststr, (testrunid, ))
        if len(res) == 0:
            debug("Testrun not available in DB")
            return (None, None, None)
        if len(res) > 1:
            warning("More than one testrun with the same id ! Fix DB !!")
            return (None, None, None)
        return res[0]

    def getTestsForTestRun(self, testrunid, withscenarios=True):
        debug("testrunid:%d", testrunid)
        liststr = "SELECT id FROM test WHERE testrunid=?"
        res = self._FetchAll(liststr, (testrunid, ))
        if not res:
            return []
        tmp = list(zip(*res)[0])
        if not withscenarios:
            scenarios = self.getScenariosForTestRun(testrunid)
            for sc in scenarios.keys():
                tmp.remove(sc)
        return tmp

    def getScenariosForTestRun(self, testrunid):
        debug("testrunid:%d", testrunid)
        liststr = """
        SELECT test.id,subtests.testid
        FROM test
        INNER JOIN subtests
        ON test.id=subtests.scenarioid
        WHERE test.testrunid=?"""
        res = self._FetchAll(liststr, (testrunid, ))
        if not res:
            return {}
        # make list unique
        dc = {}
        for scenarioid, subtestid in res:
            if not scenarioid in dc.keys():
                dc[scenarioid] = [subtestid]
            else:
                dc[scenarioid].append(subtestid)
        return dc

    def getClientInfoForTestRun(self, testrunid):
        debug("testrunid:%d", testrunid)
        liststr = """
        SELECT client.software,client.name,client.user
        FROM client,testrun
        WHERE client.id=testrun.clientid AND testrun.id=?"""
        res = self._FetchAll(liststr, (testrunid,))
        return res[0]

    def getEnvironmentForTestRun(self, testrunid):
        debug("testrunid", testrunid)
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

    def getFullTestInfo(self, testid, rawinfo=False):
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
            return (None, None, None, None, None, None, None)
        testrunid, ttype, resperc = res
        args = self.__getDict("test_arguments_dict", testid)
        results = self.__getList("test_checklist_list", testid, intonly=True)
        extras = self.__getDict("test_extrainfo_dict", testid)
        ofs = self.__getDict("test_outputfiles_dict", testid, txtonly=True)
        if not rawinfo:
            args = map_dict(args,
                            reverse_dict(self.__getTestClassArgumentMapping(ttype)))
            results = map_list(results,
                               reverse_dict(self.__getTestClassCheckListMapping(ttype)))
            extras = map_dict(extras,
                              reverse_dict(self.__getTestClassExtraInfoMapping(ttype)))
            ofs = map_dict(ofs,
                           reverse_dict(self.__getTestClassOutputFileMapping(ttype)))
        return (testrunid, ttype, args, results, resperc, extras, ofs)

    def getTestClassInfo(self, testtype):
        searchstr = """SELECT id,parent,description,fulldescription
        FROM testclassinfo WHERE type=?"""
        res = self._FetchOne(searchstr, (testtype, ))
        if not res:
            return (None, None)
        tcid, rp, desc, fulldesc = res
        args = self.__getDict("testclassinfo_arguments_dict", tcid, blobonly=True)
        checks = self.__getDict("testclassinfo_checklist_dict", tcid, txtonly=True)
        extras = self.__getDict("testclassinfo_extrainfo_dict", tcid, txtonly=True)
        outputfiles = self.__getDict("testclassinfo_outputfiles_dict",
                                    tcid, txtonly=True)
        while rp:
            ptcid, prp = self._FetchOne(searchstr, (rp, ))[:2]
            args.update(self.__getDict("testclassinfo_arguments_dict",
                                      ptcid, blobonly=True))
            checks.update(self.__getDict("testclassinfo_checklist_dict",
                                        ptcid, txtonly=True))
            extras.update(self.__getDict("testclassinfo_extrainfo_dict",
                                        ptcid, txtonly=True))
            outputfiles.update(self.__getDict("testclassinfo_outputfiles_dict",
                                             ptcid, txtonly=True))
            rp = prp

        return (desc, fulldesc, args, checks, extras, outputfiles)

    def getMonitorsIDForTest(self, testid):
        """
        Returns a list of monitorid for the given test
        """
        searchstr = "SELECT id FROM monitor WHERE testid=?"
        res = self._FetchAll(searchstr, (testid, ))
        if not res:
            return []
        return list(zip(*res)[0])

    def getFullMonitorInfo(self, monitorid):
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
        res = self.getMonitorInfo(monitorid)
        if res == (None, None, None):
            return (None, None, None, None, None, None, None)
        testid, mtype, resperc = res
        args = map_dict(self.__getDict("monitor_arguments_dict", monitorid),
                        reverse_dict(self.__getMonitorClassArgumentMapping(mtype)))
        results = map_dict(self.__getDict("monitor_checklist_dict",
                                         monitorid, intonly=True),
                           reverse_dict(self.__getMonitorClassCheckListMapping(mtype)))
        extras = map_dict(self.__getDict("monitor_extrainfo_dict", monitorid),
                          reverse_dict(self.__getMonitorClassExtraInfoMapping(mtype)))
        outputfiles = map_dict(self.__getDict("monitor_outputfiles_dict",
                                             monitorid, txtonly=True),
                               reverse_dict(self.__getMonitorClassOutputFileMapping(mtype)))
        return (testid, mtype, args, results, resperc, extras, outputfiles)

    def getMonitorInfo(self, monitorid):
        """
        Returns a tuple with the following info:
        * the ID of the test on which the monitor was applied
        * the type of the monitor
        * the result percentage
        """
        searchstr = """
        SELECT monitor.testid,monitorclassinfo.type,monitor.resultpercentage
        FROM monitor,monitorclassinfo
        WHERE monitor.id=? AND monitorclassinfo.id=monitor.type"""
        res = self._FetchOne(searchstr, (monitorid, ))
        if not res:
            return (None, None, None)
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

    def _updateTables(self, fromversion, toversion):
        """
        Update the tables from <toversion> to <toversion> database
        scheme.
        """
        # FIXME : This could most likely have a default implementation
        if fromversion < 2:
            self.__updateDatabaseFrom1To2()

        # finally update the db version
        cmstr = "UPDATE version SET version=?,modificationtime=? WHERE version=?"
        self._ExecuteCommit(cmstr, (DB_SCHEME_VERSION, int (time.time()), fromversion))
        return True

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
        self._ExecuteCommit(instructions, *args, **kwargs)

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

    def _FetchAll(self, instruction, *args, **kwargs):
        """
        Executes the given SQL query and returns a list
        of tuples of the results

        Threadsafe
        """
        self._lock.acquire()
        try:
            cur = self.con.cursor()
            cur.execute(instruction, *args, **kwargs)
            res = cur.fetchall()
        finally:
            self._lock.release()
        return res

    def _FetchOne(self, instruction, *args, **kwargs):
        """
        Executes the given SQL query and returns a unique
        tuple of result

        Threadsafe
        """
        self._lock.acquire()
        try:
            cur = self.con.cursor()
            cur.execute(instruction, *args, **kwargs)
            res = cur.fetchone()
        finally:
            self._lock.release()
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
        res = self._FetchOne("SELECT id FROM monitorclassinfo WHERE type=?",
                             (monitortype, ))
        if res == None:
            return None
        return res[0]




    # PRIVATE METHODS

    def __closedb(self, callback, *args, **kwargs):
        self._shutDown()
        callback(*args, **kwargs)

    def __updateDatabaseFrom1To2(self):
        create1to2 = """
        CREATE INDEX test_type_idx ON test (type);
        """
        # Add usedtests_testrun table and index
        self.con.executescript(create1to2)
        self.con.commit()

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
        insertstr = """
        INSERT INTO testrun (clientid, starttime) VALUES (?, ?)
        """
        testrunid = self._ExecuteCommit(insertstr,
                                        (clientid,
                                         testrun._starttime))
        envdict = testrun.getEnvironment()
        if envdict:
            self._storeEnvironmentDict(testrunid, envdict)
        self.__testruns[testrun] = testrunid
        debug("Got testrun id %d", testrunid)
        return testrunid

    def __endTestRun(self, testrun):
        debug("testrun:%r", testrun)
        if not testrun in self.__testruns.keys():
            # add the testrun since it wasn't done before
            self.__startNewTestRun(testrun, None)
        updatestr = "UPDATE testrun SET stoptime=? WHERE id=?"
        self._ExecuteCommit(updatestr, (testrun._stoptime, self.__testruns[testrun]))
        debug("updated")

    def __newTestStarted(self, testrun, test, commit=True):
        if not isinstance(test, Test):
            raise TypeError("test isn't a Test instance !")
        if not testrun in self.__testruns.keys():
            self.__startNewTestRun(testrun, None)
        debug("test:%r", test)
        self.__storeTestClassInfo(test)
        testtid = self._getTestTypeID(test.__test_name__)
        insertstr = "INSERT INTO test (testrunid, type) VALUES (?, ?)"
        testid = self._ExecuteCommit(insertstr,
                                     (self.__testruns[testrun], testtid),
                                     commit=commit)
        debug("got testid %d", testid)
        self.__tests[test] = testid


    def __storeMonitor(self, monitor, testid):
        insertstr = """
        INSERT INTO monitor (testid, type, resultpercentage)
        VALUES (?, ?, ?)
        """
        debug("monitor:%r:%d", monitor, testid)
        # store monitor
        self.__storeMonitorClassInfo(monitor)

        monitortype = self._getMonitorTypeID(monitor.__monitor_name__)
        mid = self._ExecuteCommit(insertstr, (testid, monitortype,
                                              monitor.getSuccessPercentage()))
        # store related dictionnaries
        self.__storeMonitorArgumentsDict(mid, monitor.getArguments(),
                                        monitor.__monitor_name__)
        self.__storeMonitorCheckListDict(mid, monitor.getCheckList(),
                                        monitor.__monitor_name__)
        self.__storeMonitorExtraInfoDict(mid, monitor.getExtraInfo(),
                                        monitor.__monitor_name__)
        self.__storeMonitorOutputFileDict(mid, monitor.getOutputFiles(),
                                         monitor.__monitor_name__)

    def __newTestFinished(self, testrun, test):
        debug("testrun:%r, test:%r", testrun, test)
        if not testrun in self.__testruns.keys():
            debug("different testrun, starting new one")
            self.__startNewTestRun(testrun, None)
        if not self.__tests.has_key(test):
            debug("we don't have test yet, starting that one")
            self.__newTestStarted(testrun, test, commit=False)
        tid = self.__tests[test]
        debug("test:%r:%d", test, tid)
        # if it's a scenario, fill up the subtests
        if isinstance(test, Scenario):
            debug("test is a scenario, adding subtests")
            for sub in test.tests:
                self.__newTestFinished(testrun, sub)
            # now add those to the subtests table
            insertstr = "INSERT INTO subtests (testid, scenarioid) VALUES (?,?)"
            for sub in test.tests:
                self._ExecuteCommit(insertstr, (self.__tests[sub],
                                                self.__tests[test]))
            debug("done adding subtests")

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
        updatestr = "UPDATE test SET resultpercentage=? WHERE id=?"
        resultpercentage = test.getSuccessPercentage()
        self._ExecuteCommit(updatestr, (resultpercentage, tid))

        # and on to the monitors
        for monitor in test._monitorinstances:
            self.__storeMonitor(monitor, tid)
        debug("done adding information for test %d", tid)


    def __getTestClassMapping(self, testtype, dictname):
        return self.__getClassMapping(self.__tcmapping,
                                      "testclassinfo",
                                      testtype, dictname)

    def __getMonitorClassMapping(self, monitortype, dictname):
        return self.__getClassMapping(self.__mcmapping,
                                      "monitorclassinfo",
                                      monitortype, dictname)

    def __getClassMapping(self, mapping, classtable, classtype, dictname):
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
                                            "monitorclassinfo_arguments_dict")
    def __getMonitorClassCheckListMapping(self, monitortype):
        return self.__getMonitorClassMapping(monitortype,
                                            "monitorclassinfo_checklist_dict")
    def __getMonitorClassExtraInfoMapping(self, monitortype):
        return self.__getMonitorClassMapping(monitortype,
                                            "monitorclassinfo_extrainfo_dict")
    def __getMonitorClassOutputFileMapping(self, monitortype):
        return self.__getMonitorClassMapping(monitortype,
                                            "monitorclassinfo_outputfiles_dict")
    def __storeDict(self, dicttable, containerid, pdict):
        if not pdict:
            # empty dictionnary
            debug("Empty dictionnary, returning")
            return
        self.__storeList(dicttable, containerid, tuple(pdict.iteritems()))

    def __storeList(self, dicttable, containerid, pdict):
        if not pdict:
            # empty dictionnary
            debug("Empty list, returning")
            return

        self._lock.acquire()
        try:
            cur = self.con.cursor()
            insertstr = """INSERT INTO %s (containerid, name, %s)
            VALUES (?, ?, ?)"""
            for key, value in pdict:
                debug("Adding key:%s , value:%r", key, value)
                val = value
                if isinstance(value, int):
                    valstr = "intvalue"
                elif isinstance(value, basestring):
                    valstr = "txtvalue"
                else:
                    valstr = "blobvalue"
                    val = str(dumps(value))
                comstr = insertstr % (dicttable, valstr)
                #debug("instruction:%s", comstr)
                #debug("%s, %s, %s", containerid, key, val)
                self._ExecuteCommit(comstr, (containerid, key, val),
                                    commit=False, threadsafe=True)
        finally:
            self._lock.release()

    def __getDict(self, tablename, containerid, blobonly=False, txtonly=False,
                 intonly=False):
        return dict(self.__getList(tablename, containerid, blobonly,
                                   txtonly, intonly))

    def __getList(self, tablename, containerid, blobonly=False, txtonly=False,
                 intonly=False):
        # returns a list object
        # get all the key, value for that dictid
        searchstr = "SELECT * FROM %s WHERE containerid=?" % tablename
        res = self._FetchAll(searchstr, (containerid, ))

        dc = []
        for row in res:
            containerid, name = row[1:3]
            if intonly or txtonly:
                val = row[3]
            elif blobonly:
                val = loads(str(row[3]))
            else:
                # we need to figure it out
                ival, tval, bval = row[3:]
                if not ival == None:
                    val = ival
                elif not tval == None:
                    val = str(tval)
                else:
                    val = loads(str(bval))
            dc.append((name, val))
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
        return self.__storeDict("monitor_arguments_dict",
                               monitorid, map_dict(dic, maps))

    def __storeMonitorCheckListDict(self, monitorid, dic, monitortype):
        maps = self.__getMonitorClassCheckListMapping(monitortype)
        return self.__storeDict("monitor_checklist_dict",
                               monitorid, map_dict(dic, maps))

    def __storeMonitorExtraInfoDict(self, monitorid, dic, monitortype):
        maps = self.__getMonitorClassExtraInfoMapping(monitortype)
        return self.__storeDict("monitor_extrainfo_dict",
                               monitorid, map_dict(dic, maps))

    def __storeMonitorOutputFileDict(self, monitorid, dic, monitortype):
        maps = self.__getMonitorClassOutputFileMapping(monitortype)
        return self.__storeDict("monitor_outputfiles_dict",
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
        return self.__storeDict("monitorclassinfo_arguments_dict",
                               monitorclassinfoid, dic)

    def __storeMonitorClassCheckListDict(self, monitorclassinfoid, dic):
        return self.__storeDict("monitorclassinfo_checklist_dict",
                               monitorclassinfoid, dic)

    def __storeMonitorClassExtraInfoDict(self, monitorclassinfoid, dic):
        return self.__storeDict("monitorclassinfo_extrainfo_dict",
                               monitorclassinfoid, dic)

    def __storeMonitorClassOutputFileDict(self, monitorclassinfoid, dic):
        return self.__storeDict("monitorclassinfo_outputfiles_dict",
                               monitorclassinfoid, dic)

    def _storeEnvironmentDict(self, testrunid, dic):
        return self.__storeDict("testrun_environment_dict",
                               testrunid, dic)

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
        checklist = tclass.__dict__.get("__test_checklist__")
        extrainfo = tclass.__dict__.get("__test_extra_infos__")
        outputfiles = tclass.__dict__.get("__test_output_files__")
        if tclass == Test:
            parent = None
        else:
            parent = tclass.__base__.__dict__.get("__test_name__").strip()

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
        debug("done adding class info for %s [%d]", ctype, tcid)
        return True

    def __storeTestClassInfo(self, testinstance):
        # check if we don't already have info for this class
        debug("test name: %s", testinstance.__test_name__)
        existstr = "SELECT * FROM testclassinfo WHERE type=?"
        res = self._FetchAll(existstr, (testinstance.__test_name__, ))
        if len(res) > 0:
            # type already exists, returning
            return
        # we need an inverted mro (so we can know the parent class)
        for cl in testinstance.__class__.mro():
            if not self.__insertTestClassInfo(cl):
                break
            if cl == Test:
                break

    def __insertMonitorClassInfo(self, tclass):
        ctype = tclass.__dict__.get("__monitor_name__").strip()
        searchstr = "SELECT * FROM monitorclassinfo WHERE type=?"
        if len(self._FetchAll(searchstr, (ctype, ))) >= 1:
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

        # insert into db
        insertstr = """
        INSERT INTO monitorclassinfo (type, parent, description) VALUES (?, ?, ?)
        """
        tcid = self._ExecuteCommit(insertstr, (ctype, parent, desc))

        # store the dicts
        self.__storeMonitorClassArgumentsDict(tcid, args)
        self.__storeMonitorClassCheckListDict(tcid, checklist)
        self.__storeMonitorClassExtraInfoDict(tcid, extrainfo)
        self.__storeMonitorClassOutputFileDict(tcid, outputfiles)
        return True

    def __storeMonitorClassInfo(self, monitorinstance):
        # check if we don't already have info for this class
        existstr = "SELECT * FROM monitorclassinfo WHERE type=?"
        res = self._FetchAll(existstr, (monitorinstance.__monitor_name__, ))
        if len(res) >= 1:
            # type already exists, returning
            return
        # we need an inverted mro (so we can now the parent class)
        for cl in monitorinstance.__class__.mro():
            if not self.__insertMonitorClassInfo(cl):
                break
            if cl == Monitor:
                break




DB_SCHEME_VERSION = 2