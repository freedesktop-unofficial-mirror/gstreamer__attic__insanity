# GStreamer QA system
#
#       storage/sqlite.py
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
SQLite based DataStorage
"""

import time
import string
from weakref import WeakKeyDictionary
from insanity.log import critical, error, warning, debug, info
from insanity.storage.storage import DBStorage
from insanity.scenario import Scenario
from insanity.test import Test
from insanity.monitor import Monitor
from insanity.utils import reverse_dict, map_dict, map_list
try:
    # In Python 2.5, this is part of the standard library:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    # Previous versions have this as external dependency...
    from pysqlite2 import dbapi2 as sqlite
from cPickle import dumps, loads

# New dictionnaries table have the following name
# <container name>_<dictionnary name>_dict

TABLECREATION = """
CREATE TABLE version (
   version INTEGER,
   modificationtime INTEGER
);

CREATE TABLE testrun (
   id INTEGER PRIMARY KEY,
   clientid INTEGER,
   starttime INTEGER,
   stoptime INTEGER
);

CREATE TABLE client (
   id INTEGER PRIMARY KEY,
   software TEXT,
   name TEXT,
   user TEXT
);

CREATE TABLE test (
   id INTEGER PRIMARY KEY,
   testrunid INTEGER,
   type INTEGER,
   resultpercentage FLOAT
);

CREATE TABLE subtests (
   testid INTEGER PRIMARY KEY,
   scenarioid INTEGER
);

CREATE TABLE monitor (
   id INTEGER PRIMARY KEY,
   testid INTEGER,
   type INTEGER,
   resultpercentage FLOAT
);

CREATE TABLE testclassinfo (
   id INTEGER PRIMARY KEY,
   type TEXT,
   parent TEXT,
   description TEXT,
   fulldescription TEXT
);

CREATE TABLE monitorclassinfo (
   id INTEGER PRIMARY KEY,
   type TEXT,
   parent TEXT,
   description TEXT
);

CREATE TABLE testrun_environment_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   intvalue INTEGER,
   txtvalue TEXT,
   blobvalue BLOB
);

CREATE TABLE test_arguments_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   intvalue INTEGER,
   txtvalue TEXT,
   blobvalue BLOB
);

CREATE TABLE test_checklist_list (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   intvalue INTEGER
);

CREATE TABLE test_extrainfo_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   intvalue INTEGER,
   txtvalue TEXT,
   blobvalue BLOB
);

CREATE TABLE test_outputfiles_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   txtvalue TEXT
);

CREATE TABLE monitor_arguments_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   intvalue INTEGER,
   txtvalue TEXT,
   blobvalue BLOB
);

CREATE TABLE monitor_checklist_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   intvalue INTEGER
);

CREATE TABLE monitor_extrainfo_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   intvalue INTEGER,
   txtvalue TEXT,
   blobvalue BLOB
);

CREATE TABLE monitor_outputfiles_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   txtvalue TEXT
);

CREATE TABLE testclassinfo_arguments_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   blobvalue BLOB
);

CREATE TABLE testclassinfo_checklist_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   txtvalue TEXT
);

CREATE TABLE testclassinfo_extrainfo_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   txtvalue TEXT
);

CREATE TABLE testclassinfo_outputfiles_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   txtvalue TEXT
);

CREATE TABLE monitorclassinfo_arguments_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   txtvalue TEXT
);

CREATE TABLE monitorclassinfo_checklist_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   txtvalue TEXT
);

CREATE TABLE monitorclassinfo_extrainfo_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   txtvalue TEXT
);

CREATE TABLE monitorclassinfo_outputfiles_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   txtvalue TEXT
);

CREATE INDEX test_testrunid_idx ON test(testrunid);
CREATE INDEX subtests_scenarioid_idx ON subtests(scenarioid);
CREATE INDEX monitor_testid_idx ON monitor(testid);
CREATE INDEX testclassinfo_parent_idx ON testclassinfo (parent);
CREATE INDEX monitorclassinfo_parent_idx ON monitorclassinfo (parent);
CREATE INDEX testrun_env_dict_container_idx ON testrun_environment_dict (containerid);

CREATE INDEX t_a_dict_containerid_idx ON test_arguments_dict (containerid);
CREATE INDEX t_c_list_containerid_idx ON test_checklist_list (containerid);
CREATE INDEX t_ei_dict_containerid_idx ON test_extrainfo_dict (containerid);
CREATE INDEX t_of_dict_containerid_idx ON test_outputfiles_dict (containerid);

CREATE INDEX m_a_dict_containerid_idx ON monitor_arguments_dict (containerid);
CREATE INDEX m_c_dict_containerid_idx ON monitor_checklist_dict (containerid);
CREATE INDEX m_ei_dict_containerid_idx ON monitor_extrainfo_dict (containerid);
CREATE INDEX m_of_dict_containerid_idx ON monitor_outputfiles_dict (containerid);

CREATE INDEX tc_a_dict_c_idx ON testclassinfo_arguments_dict (containerid);
CREATE INDEX tc_c_dict_c_idx ON testclassinfo_checklist_dict (containerid);
CREATE INDEX tc_ei_dict_c_idx ON testclassinfo_extrainfo_dict (containerid);
CREATE INDEX tc_of_dict_c_idx ON testclassinfo_outputfiles_dict (containerid);

CREATE INDEX mc_a_dict_c_idx ON monitorclassinfo_arguments_dict (containerid);
CREATE INDEX mc_c_dict_c_idx ON monitorclassinfo_checklist_dict (containerid);
CREATE INDEX mc_ei_dict_c_idx ON monitorclassinfo_extrainfo_dict (containerid);
CREATE INDEX mc_of_dict_c_idx ON monitorclassinfo_outputfiles_dict (containerid);
"""

# Current database version
DATABASE_VERSION = 1

DATA_TYPE_INT = 0
DATA_TYPE_STR = 1
DATA_TYPE_BLOB = 2

#
# FIXME / WARNING
# The current implementation only supports handling of one testrun at a time !
#

class SQLiteStorage(DBStorage):
    """
    Stores data in a sqlite db
    """

    def __init__(self, *args, **kwargs):
        DBStorage.__init__(self, *args, **kwargs)
        self.__clientid = None
        self.__testrunid = None
        self.__testrun = None
        self.__tests = WeakKeyDictionary()
        # cache of mappings for testclassinfo
        # { 'testtype' : { 'dictname' : mapping } }
        self.__tcmapping = {}
        # cache of mappings for testclassinfo
        # { 'testtype' : { 'dictname' : mapping } }
        self.__mcmapping = {}

    def openDatabase(self):
        debug("opening sqlite db for path '%s'", self.path)
        self.con = sqlite.connect(self.path, check_same_thread=False)

    def createTables(self):
        # check if tables aren't already created
        if self._checkForTables():
            return
        debug("Calling db creation script")
        self.con.executescript(TABLECREATION)
        self.con.commit()
        if self._checkForTables() == False:
            error("Tables were not created properly !!")
        # add database version
        self._ExecuteCommit("INSERT INTO version (version, modificationtime) VALUES (?, ?)",
                            (DATABASE_VERSION, int(time.time())))
        debug("Tables properly created")

    def _checkForTables(self):
        # return False if the tables aren't created
        tables = self._getAllTables()
        if len(tables) == 0 or not "version" in tables:
            return False

        # FIXME : if ver != DATABASE_VERSION, then update the database
        ver = self._getDatabaseSchemeVersion()
        if not ver or ver != DATABASE_VERSION:
            return False
        return True

    def _ExecuteCommit(self, instruction, *args, **kwargs):
        # Convenience function to call execute and commit in one line
        # returns the last row id
        commit = kwargs.pop("commit", True)
        debug("%s args:%r kwargs:%r", instruction, args, kwargs)
        cur = self.con.cursor()
        cur.execute(instruction, *args, **kwargs)
        if commit:
            self.con.commit()
        return cur.lastrowid

    def _FetchAll(self, instruction, *args, **kwargs):
        # Convenience function to fetch all results
        cur = self.con.cursor()
        cur.execute(instruction, *args, **kwargs)
        return cur.fetchall()

    def _FetchOne(self, instruction, *args, **kwargs):
        # Convenience function to fetch all results
        cur = self.con.cursor()
        cur.execute(instruction, *args, **kwargs)
        return cur.fetchone()

    def _getAllTables(self):
        """
        Returns the name of all the available tables in the currently
        loaded database.
        """
        CHECKTABLES = """
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name;
        """
        return [x[0] for x in self.con.execute(CHECKTABLES).fetchall()]

    def _getDatabaseSchemeVersion(self):
        """
        Returns the scheme version of the currently loaded databse

        Returns None if there's no properly configured scheme, else
        returns the version
        """
        tables = self._getAllTables()
        if not "version" in tables:
            return None
        # check if the version is the same as the current one
        res = self._FetchOne("SELECT version FROM version")
        if res == None:
            return None
        return res[0]

    # dictionnary storage methods
    def _conformDict(self, pdict):
        # transforms the dictionnary values to types compatible with
        # the DB storage format
        if pdict == None:
            return None
        res = {}
        for key,value in pdict.iteritems():
            res[key] = value
        return res

    def _storeDict(self, dicttable, containerid, pdict):
        pdict = self._conformDict(pdict)

        if not pdict:
            # empty dictionnary
            debug("Empty dictionnary, returning")
            return

        insertstr = """INSERT INTO %s (id, containerid, name, %s)
        VALUES (NULL, ?, ?, ?)"""
        cur = self.con.cursor()
        for key,value in pdict.iteritems():
            debug("Adding key:%s , value:%r", key, value)
            val = value
            if isinstance(value, int):
                valstr = "intvalue"
            elif isinstance(value, basestring):
                valstr = "txtvalue"
            else:
                valstr = "blobvalue"
                val = sqlite.Binary(dumps(value))
            comstr = insertstr % (dicttable, valstr)
            cur.execute(comstr, (containerid, key, val))

    def _storeList(self, dicttable, containerid, pdict):
        if not pdict:
            # empty dictionnary
            debug("Empty list, returning")
            return

        cur = self.con.cursor()
        insertstr = """INSERT INTO %s (id, containerid, name, %s)
        VALUES (NULL, ?, ?, ?)"""
        for key,value in pdict:
            debug("Adding key:%s , value:%r", key, value)
            val = value
            if isinstance(value, int):
                valstr = "intvalue"
            elif isinstance(value, basestring):
                valstr = "txtvalue"
            else:
                valstr = "blobvalue"
                val = sqlite.Binary(dumps(value))
            comstr = insertstr % (dicttable, valstr)
            cur.execute(comstr, (containerid, key, val))

    def _storeList(self, dicttable, containerid, pdict):
        if not pdict:
            # empty dictionnary
            debug("Empty list, returning")
            return

        cur = self.con.cursor()
        insertstr = """INSERT INTO %s (id, containerid, name, %s)
        VALUES (NULL, ?, ?, ?)"""
        for key,value in pdict:
            debug("Adding key:%s , value:%r", key, value)
            val = value
            if isinstance(value, int):
                valstr = "intvalue"
            elif isinstance(value, basestring):
                valstr = "txtvalue"
            else:
                valstr = "blobvalue"
                val = sqlite.Binary(dumps(value))
            comstr = insertstr % (dicttable, valstr)
            cur.execute(comstr, (containerid, key, val))

    def _storeTestArgumentsDict(self, testid, dict, testtype):
        # transform the dictionnary from names to ids
        maps = self._getTestClassArgumentMapping(testtype)
        return self._storeDict("test_arguments_dict",
                               testid, map_dict(dict, maps))

    def _storeTestCheckListList(self, testid, dict, testtype):
        maps = self._getTestClassCheckListMapping(testtype)
        return self._storeList("test_checklist_list",
                               testid, map_list(dict, maps))

    def _storeTestExtraInfoDict(self, testid, dict, testtype):
        maps = self._getTestClassExtraInfoMapping(testtype)
        return self._storeDict("test_extrainfo_dict",
                               testid, map_dict(dict, maps))

    def _storeTestOutputFileDict(self, testid, dict, testtype):
        maps = self._getTestClassOutputFileMapping(testtype)
        return self._storeDict("test_outputfiles_dict",
                               testid, map_dict(dict, maps))

    def _storeMonitorArgumentsDict(self, monitorid, dict, monitortype):
        maps = self._getMonitorClassArgumentMapping(monitortype)
        return self._storeDict("monitor_arguments_dict",
                               monitorid, map_dict(dict, maps))

    def _storeMonitorCheckListDict(self, monitorid, dict, monitortype):
        maps = self._getMonitorClassCheckListMapping(monitortype)
        return self._storeDict("monitor_checklist_dict",
                               monitorid, map_dict(dict, maps))

    def _storeMonitorExtraInfoDict(self, monitorid, dict, monitortype):
        maps = self._getMonitorClassExtraInfoMapping(monitortype)
        return self._storeDict("monitor_extrainfo_dict",
                               monitorid, map_dict(dict, maps))

    def _storeMonitorOutputFileDict(self, monitorid, dict, monitortype):
        maps = self._getMonitorClassOutputFileMapping(monitortype)
        return self._storeDict("monitor_outputfiles_dict",
                               monitorid, map_dict(dict, maps))

    def _storeTestClassArgumentsDict(self, testclassinfoid, dict):
        return self._storeDict("testclassinfo_arguments_dict", testclassinfoid, dict)

    def _storeTestClassCheckListDict(self, testclassinfoid, dict):
        return self._storeDict("testclassinfo_checklist_dict", testclassinfoid, dict)

    def _storeTestClassExtraInfoDict(self, testclassinfoid, dict):
        return self._storeDict("testclassinfo_extrainfo_dict", testclassinfoid, dict)

    def _storeTestClassOutputFileDict(self, testclassinfoid, dict):
        return self._storeDict("testclassinfo_outputfiles_dict", testclassinfoid, dict)

    def _storeMonitorClassArgumentsDict(self, monitorclassinfoid, dict):
        return self._storeDict("monitorclassinfo_arguments_dict", monitorclassinfoid, dict)

    def _storeMonitorClassCheckListDict(self, monitorclassinfoid, dict):
        return self._storeDict("monitorclassinfo_checklist_dict", monitorclassinfoid, dict)

    def _storeMonitorClassExtraInfoDict(self, monitorclassinfoid, dict):
        return self._storeDict("monitorclassinfo_extrainfo_dict", monitorclassinfoid, dict)

    def _storeMonitorClassOutputFileDict(self, monitorclassinfoid, dict):
        return self._storeDict("monitorclassinfo_outputfiles_dict", monitorclassinfoid, dict)

    def _storeEnvironmentDict(self, testrunid, dict):
        return self._storeDict("testrun_environment_dict", testrunid, dict)

    def _insertTestClassInfo(self, tclass):
        ctype = tclass.__dict__.get("__test_name__")
        searchstr = "SELECT * FROM testclassinfo WHERE type=?"
        if len(self._FetchAll(searchstr, (ctype, ))) >= 1:
            return False
        # get info
        desc = tclass.__dict__.get("__test_description__")
        fdesc = tclass.__dict__.get("__test_full_description__")
        args = tclass.__dict__.get("__test_arguments__")
        checklist = tclass.__dict__.get("__test_checklist__")
        extrainfo = tclass.__dict__.get("__test_extra_infos__")
        outputfiles = tclass.__dict__.get("__test_output_files__")
        if tclass == Test:
            parent = None
        else:
            parent = tclass.__base__.__dict__.get("__test_name__")

        # insert into db
        insertstr = """INSERT INTO testclassinfo
        (id, type, parent, description, fulldescription)
        VALUES (NULL, ?, ?, ?, ?)"""
        tcid = self._ExecuteCommit(insertstr, (ctype, parent, desc, fdesc))

        # store the dicts
        self._storeTestClassArgumentsDict(tcid, args)
        self._storeTestClassCheckListDict(tcid, checklist)
        self._storeTestClassExtraInfoDict(tcid, extrainfo)
        self._storeTestClassOutputFileDict(tcid, outputfiles)
        self.con.commit()
        return True

    def _storeTestClassInfo(self, testinstance):
        # check if we don't already have info for this class
        existstr = "SELECT * FROM testclassinfo WHERE type=?"
        res = self._FetchAll(existstr, (testinstance.__test_name__, ))
        if len(res) >= 1:
            # type already exists, returning
            return
        # we need an inverted mro (so we can now the parent class)
        for cl in testinstance.__class__.mro():
            if not self._insertTestClassInfo(cl):
                break
            if cl == Test:
                break

    def _insertMonitorClassInfo(self, tclass):
        ctype = tclass.__dict__.get("__monitor_name__")
        searchstr = "SELECT * FROM monitorclassinfo WHERE type=?"
        if len(self._FetchAll(searchstr, (ctype, ))) >= 1:
            return False
        # get info
        desc = tclass.__dict__.get("__monitor_description__")
        args = tclass.__dict__.get("__monitor_arguments__")
        checklist = tclass.__dict__.get("__monitor_checklist__")
        extrainfo = tclass.__dict__.get("__monitor_extra_infos__")
        outputfiles = tclass.__dict__.get("__monitor_output_files__")
        if tclass == Monitor:
            parent = None
        else:
            parent = tclass.__base__.__dict__.get("__monitor_name__")

        # insert into db
        insertstr = "INSERT INTO monitorclassinfo (type, parent, description) VALUES (?, ?, ?)"
        tcid = self._ExecuteCommit(insertstr, (ctype, parent, desc))

        # store the dicts
        self._storeMonitorClassArgumentsDict(tcid, args)
        self._storeMonitorClassCheckListDict(tcid, checklist)
        self._storeMonitorClassExtraInfoDict(tcid, extrainfo)
        self._storeMonitorClassOutputFileDict(tcid, outputfiles)
        self.con.commit()
        return True

    def _storeMonitorClassInfo(self, monitorinstance):
        # check if we don't already have info for this class
        existstr = "SELECT * FROM monitorclassinfo WHERE type=?"
        res = self._FetchAll(existstr, (monitorinstance.__monitor_name__, ))
        if len(res) >= 1:
            # type already exists, returning
            return
        # we need an inverted mro (so we can now the parent class)
        for cl in monitorinstance.__class__.mro():
            if not self._insertMonitorClassInfo(cl):
                break
            if cl == Monitor:
                break



    # public storage API

    def _setClientInfo(self, softwarename, clientname, user, id=None):
        # check if that triplet is already present
        debug("softwarename:%s, clientname:%s, user:%s", softwarename, clientname, user)
        existstr = "SELECT id FROM client WHERE software=? AND name=? AND user=?"
        res = self._FetchAll(existstr, (softwarename, clientname, user))
        if len(res) == 1 :
            debug("Entry already present !")
            key = res[0][0]
        elif len(res) > 1:
            warning("More than one similar entry ???")
            raise Exception("There are more than one client entry with the same information, fix database !")
        else:
            insertstr = "INSERT INTO client (id, software, name, user) VALUES (NULL, ?,?,?)"
            key = self._ExecuteCommit(insertstr, (softwarename, clientname, user))
        debug("got id %d", key)
        # cache the key
        self.__clientid = key
        return key

    def setClientInfo(self, softwarename, clientname, user, id=None):
        self._lock.acquire()
        try:
            self._setClientInfo(softwarename, clientname, user)
        finally:
            self._lock.release()

    def startNewTestRun(self, testrun):
        self._lock.acquire()
        try:
            self._startNewTestRun(testrun)
        finally:
            self._lock.release()

    def _startNewTestRun(self, testrun):
        # create new testrun entry with client entry
        debug("testrun:%r", testrun)
        if not self.__clientid:
            raise Exception("Please specify client information before starting the testruns")
        if self.__testrun:
            warning("Apparently the previous testrun didn't exit successfully")
        insertstr = "INSERT INTO testrun (id, clientid, starttime, stoptime) VALUES (NULL, ?, ?, NULL)"
        self.__testrunid = self._ExecuteCommit(insertstr, (self.__clientid, testrun._starttime))
        envdict = testrun.getEnvironment()
        if envdict:
            self._storeEnvironmentDict(self.__testrunid, envdict)
        self.__testrun = testrun
        debug("Got testrun id %d", self.__testrunid)

    def endTestRun(self, testrun):
        self._lock.acquire()
        try:
            self._endTestRun(testrun)
        finally:
            self._lock.release()

    def _endTestRun(self, testrun):
        debug("testrun:%r", testrun)
        if not self.__testrun == testrun:
            # add the testrun since it wasn't done before
            self._startNewTestRun(testrun)
        updatestr = "UPDATE testrun SET stoptime=? WHERE id=?"
        self._ExecuteCommit(updatestr, (testrun._stoptime, self.__testrunid))
        debug("updated")

    def _getTestTypeID(self, testtype):
        """
        Returns the test.id for the given testtype

        Returns None if there is no information regarding the given testtype
        """
        res = self._FetchOne("SELECT id FROM testclassinfo WHERE type=?", (testtype, ))
        if res == None:
            return None
        return res[0]

    def _getMonitorTypeID(self, monitortype):
        """
        Returns the monitor.id for the given monitortype

        Returns None if there is no information regarding the given monitortype
        """
        res = self._FetchOne("SELECT id FROM monitorclassinfo WHERE type=?", (monitortype, ))
        if res == None:
            return None
        return res[0]

    def newTestStarted(self, testrun, test, commit=True):
        self._lock.acquire()
        try:
            self._newTestStarted(testrun, test, commit)
        finally:
            self._lock.release()

    def _newTestStarted(self, testrun, test, commit=True):
        if not isinstance(test, Test):
            raise TypeError("test isn't a Test instance !")
        if not self.__testrun == testrun:
            self._startNewTestRun(testrun)
        debug("test:%r", test)
        self._storeTestClassInfo(test)
        testtid = self._getTestTypeID(test.__test_name__)
        insertstr = "INSERT INTO test (id, testrunid, type) VALUES (NULL, ?, ?)"
        testid = self._ExecuteCommit(insertstr,
                                     (self.__testrunid, testtid),
                                     commit=commit)
        debug("got testid %d", testid)
        self.__tests[test] = testid


    def newTestFinished(self, testrun, test):
        self._lock.acquire()
        try:
            self._newTestFinished(testrun, test)
        finally:
            self._lock.release()

    def _newTestFinished(self, testrun, test):
        if not self.__testrun == testrun:
            self._startNewTestRun(testrun)
        if not self.__tests.has_key(test):
            self._newTestStarted(testrun, test, commit=False)
        tid = self.__tests[test]
        debug("test:%r:%d", test, tid)
        # if it's a scenario, fill up the subtests
        if isinstance(test, Scenario):
            sublist = []
            for sub in test.tests:
                self._newTestFinished(testrun, sub)
            # now add those to the subtests table
            insertstr = "INSERT INTO subtests (testid, scenarioid) VALUES (?,?)"
            for sub in test.tests:
                self._ExecuteCommit(insertstr, (self.__tests[sub],
                                                self.__tests[test]))

        # store the dictionnaries
        self._storeTestArgumentsDict(tid, test.getArguments(),
                                     test.__test_name__)
        self._storeTestCheckListList(tid, test.getCheckList(),
                                     test.__test_name__)
        self._storeTestExtraInfoDict(tid, test.getExtraInfo(),
                                     test.__test_name__)
        self._storeTestOutputFileDict(tid, test.getOutputFiles(),
                                      test.__test_name__)
        self.con.commit()

        # finally update the test
        updatestr = "UPDATE test SET resultpercentage=? WHERE id=?"
        resultpercentage = test.getSuccessPercentage()
        self._ExecuteCommit(updatestr, (resultpercentage, tid))

        # and on to the monitors
        for monitor in test._monitorinstances:
            self._storeMonitor(monitor, tid)

    def _storeMonitor(self, monitor, testid):
        insertstr = """
        INSERT INTO monitor (id, testid, type, resultpercentage)
        VALUES (NULL, ?, ?, ?)
        """
        # store monitor
        self._storeMonitorClassInfo(monitor)

        monitortype = self._getMonitorTypeID(monitor.__monitor_name__)
        mid = self._ExecuteCommit(insertstr, (testid, monitortype,
                                              monitor.getSuccessPercentage()))
        # store related dictionnaries
        self._storeMonitorArgumentsDict(mid, monitor.getArguments(),
                                        monitor.__monitor_name__)
        self._storeMonitorCheckListDict(mid, monitor.getCheckList(),
                                        monitor.__monitor_name__)
        self._storeMonitorExtraInfoDict(mid, monitor.getExtraInfo(),
                                        monitor.__monitor_name__)
        self._storeMonitorOutputFileDict(mid, monitor.getOutputFiles(),
                                         monitor.__monitor_name__)
        self.con.commit()

    # public retrieval API

    def _getDict(self, tablename, containerid, blobonly=False, txtonly=False, intonly=False):
        # returns a dict object
        # get all the key/type for that dictid
        searchstr = "SELECT * FROM %s WHERE containerid=?" % tablename
        res = self._FetchAll(searchstr, (containerid, ))

        d = {}
        for row in res:
            id, containerid, name = row[:3]
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
            d[name] = val
        return d

    def _getList(self, tablename, containerid, blobonly=False, txtonly=False, intonly=False):
        # returns a list object
        # get all the key, value for that dictid
        searchstr = "SELECT * FROM %s WHERE containerid=?" % tablename
        res = self._FetchAll(searchstr, (containerid, ))

        d = []
        for row in res:
            id, containerid, name = row[:3]
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
            d.append((name, val))
        return d


    def getClientInfoForTestRun(self, testrunid):
        debug("testrunid:%d", testrunid)
        liststr = """
        SELECT client.software,client.name,client.user
        FROM client,testrun
        WHERE client.id=testrun.clientid AND testrun.id=?"""
        res = self._FetchAll(liststr, (testrunid,))
        return res[0]

    def listTestRuns(self):
        liststr = "SELECT id FROM testrun"
        res = self._FetchAll(liststr)
        debug("Got %d testruns", len(res))
        if len(res):
            return list(zip(*res)[0])
        return []

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

    def getEnvironmentForTestRun(self, testrunid):
        debug("testrunid", testrunid)
        return self._getDict("testrun_environment_dict", testrunid)

    def getTestsForTestRun(self, testrunid, withscenarios=True):
        debug("testrunid:%d", testrunid)
        liststr = "SELECT id FROM test WHERE testrunid=?"
        res = self._FetchAll(liststr, (testrunid, ))
        if not res:
            return []
        tmp = list(zip(*res)[0])
        if not withscenarios:
            scenarios = self.getScenariosForTestRun(testrunid)
            for x in scenarios.keys():
                tmp.remove(x)
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
            return []
        # make list unique
        d = {}
        for scenarioid, subtestid in res:
            if not scenarioid in d.keys():
                d[scenarioid] = [subtestid]
            else:
                d[scenarioid].append(subtestid)
        return d

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

    def getFullTestInfo(self, testid):
        """
        Returns a tuple with the following info:
        * the testrun id in which it was executed
        * the type of the test
        * the arguments (dictionnary)
        * the results (checklist list)
        * the result percentage
        * the extra information (dictionnary)
        * the output files (dictionnary)
        """
        searchstr = """
        SELECT test.testrunid,testclassinfo.type,test.resultpercentage
        FROM test,testclassinfo
        WHERE test.id=? AND test.type=testclassinfo.id"""
        res = self._FetchOne(searchstr, (testid, ))
        if not res:
            return (None, None, None, None, None, None, None)
        testrunid,ttype,resperc = res
        args = map_dict(self._getDict("test_arguments_dict", testid),
                        reverse_dict(self._getTestClassArgumentMapping(ttype)))
        results = map_list(self._getList("test_checklist_list", testid, intonly=True),
                           reverse_dict(self._getTestClassCheckListMapping(ttype)))
        extras = map_dict(self._getDict("test_extrainfo_dict", testid),
                          reverse_dict(self._getTestClassExtraInfoMapping(ttype)))
        outputfiles = map_dict(self._getDict("test_outputfiles_dict", testid, txtonly=True),
                               reverse_dict(self._getTestClassOutputFileMapping(ttype)))
        return (testrunid, ttype, args, results, resperc, extras, outputfiles)

    def getTestClassInfo(self, testtype):
        searchstr = """SELECT id,parent,description,fulldescription
        FROM testclassinfo WHERE type=?"""
        res = self._FetchOne(searchstr, (testtype, ))
        if not res:
            return (None, None)
        tcid, rp, desc, fulldesc = res
        args = self._getDict("testclassinfo_arguments_dict", tcid, blobonly=True)
        checks = self._getDict("testclassinfo_checklist_dict", tcid, txtonly=True)
        extras = self._getDict("testclassinfo_extrainfo_dict", tcid, txtonly=True)
        outputfiles = self._getDict("testclassinfo_outputfiles_dict", tcid, txtonly=True)
        while rp:
            ptcid, prp, pd, pfd = self._FetchOne(searchstr, (rp, ))
            args.update(self._getDict("testclassinfo_arguments_dict", ptcid, blobonly=True))
            checks.update(self._getDict("testclassinfo_checklist_dict", ptcid, txtonly=True))
            extras.update(self._getDict("testclassinfo_extrainfo_dict", ptcid, txtonly=True))
            outputfiles.update(self._getDict("testclassinfo_outputfiles_dict", ptcid, txtonly=True))
            rp = prp

        return (desc, fulldesc, args, checks, extras, outputfiles)

    def _getClassMapping(self, classtable, classtype, dictname):
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

        return dict(maps)

    def _getTestClassMapping(self, testtype, dictname):
        # Search in the cache first
        if testtype in self.__tcmapping:
            if dictname in self.__tcmapping[testtype]:
                return self.__tcmapping[testtype][dictname]
        maps = self._getClassMapping("testclassinfo", testtype, dictname)
        if not testtype in self.__tcmapping:
            self.__tcmapping[testtype] = {}
        self.__tcmapping[testtype][dictname] = dict(maps)

    def _getMonitorClassMapping(self, monitortype, dictname):
        # Search in the cache first
        if monitortype in self.__mcmapping:
            if dictname in self.__mcmapping[monitortype]:
                return self.__mcmapping[monitortype][dictname]
        maps = self._getClassMapping("monitorclassinfo", monitortype, dictname)
        if not monitortype in self.__mcmapping:
            self.__mcmapping[monitortype] = {}
        self.__mcmapping[monitortype][dictname] = dict(maps)

    def _getTestClassArgumentMapping(self, testtype):
        return self._getTestClassMapping(testtype, "testclassinfo_arguments_dict")

    def _getTestClassCheckListMapping(self, testtype):
        return self._getTestClassMapping(testtype, "testclassinfo_checklist_dict")

    def _getTestClassExtraInfoMapping(self, testtype):
        return self._getTestClassMapping(testtype, "testclassinfo_extrainfo_dict")

    def _getTestClassOutputFileMapping(self, testtype):
        return self._getTestClassMapping(testtype, "testclassinfo_outputfiles_dict")

    def _getMonitorClassArgumentMapping(self, monitortype):
        return self._getMonitorClassMapping(monitortype, "monitorclassinfo_arguments_dict")

    def _getMonitorClassCheckListMapping(self, monitortype):
        return self._getMonitorClassMapping(monitortype, "monitorclassinfo_checklist_dict")

    def _getMonitorClassExtraInfoMapping(self, monitortype):
        return self._getMonitorClassMapping(monitortype, "monitorclassinfo_extrainfo_dict")

    def _getMonitorClassOutputFileMapping(self, monitortype):
        return self._getMonitorClassMapping(monitortype, "monitorclassinfo_outputfiles_dict")


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
        testid,mtype,resperc = res
        args = map_dict(self._getDict("monitor_arguments_dict", monitorid),
                        reverse_dict(self._getMonitorClassArgumentMapping(mtype)))
        results = map_dict(self._getDict("monitor_checklist_dict", monitorid, intonly=True),
                           reverse_dict(self._getMonitorClassCheckListMapping(mtype)))
        extras = map_dict(self._getDict("monitor_extrainfo_dict", monitorid),
                          reverse_dict(self._getMonitorClassExtraInfoMapping(mtype)))
        outputfiles = map_dict(self._getDict("monitor_outputfiles_dict", monitorid, txtonly=True),
                               reverse_dict(self._getMonitorClassOutputFileMapping(mtype)))
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


    def findTestsByArgument(self, testtype, arguments, testrunid=None, monitorids=[]):
        searchstr = """
        SELECT test.id
        FROM test, test_arguments_dict
        WHERE test.id=test_arguments_dict.containerid """
        searchargs = []
        if not testrunid == None:
            searchstr += "AND test.testrunid=? "
            searchargs.append(testrunid)
        searchstr += "AND test.type=? "
        searchargs.append(testtype)

        # we'll now recursively search for the compatible tests
        # we first start to look for all tests matching the first argument
        # then from those tests, find those that match the second,...
        # Break out from the loop whenever there's nothing more matching

        res = []

        for key,val in arguments.iteritems():
            if not res == []:
                tmpsearch = "AND test.id in (%s) " % string.join([str(x) for x in res], ', ')
            else:
                tmpsearch = ""
            value = val
            if isinstance(val, int):
                valstr = "intvalue"
            elif isinstance(val, basestring):
                valstr = "txtvalue"
            else:
                valstr = "blobvalue"
                value = sqlite.Binary(dumps(val))
            tmpsearch += "AND test_arguments_dict.name=? AND test_arguments_dict.%s=?" % valstr
            tmpargs = searchargs[:]
            tmpargs.extend([key, value])
            tmpres = self._FetchAll(searchstr + tmpsearch, tuple(tmpargs))
            res = []
            if tmpres == []:
                break
            tmp2 = list(zip(*tmpres)[0])
            # transform this into a unique list
            for i in tmp2:
                if not i in res:
                    res.append(i)

        # finally... make sure that for the monitors that both test
        # share, they have the same arguments
        if not monitorids == []:
            tmp = []
            monitors = [self.getFullMonitorInfo(x) for x in monitorids]
            for p in res:
                similar = True
                pm = [self.getFullMonitorInfo(x) for x in self.getMonitorsIDForTest(p)]

                samemons = []
                # for each candidate monitors
                for tid, mtype, margs, mres, mresperc, mextra, mout in pm:
                    # for each original monitor
                    for mon in monitors:
                        if mon[1] == mtype:
                            # same type of monitor, now check arguments
                            samemons.append(((tid, mtype, margs, mres, mresperc, mextra, mout), mon))
                if not samemons == []:
                    for cand, mon in samemons:
                        if not cand[2] ==  mon[2]:
                            similar = False
                if similar:
                    tmp.append(p)
            res = tmp
        return res
