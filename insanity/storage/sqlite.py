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
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA 02110-1301, USA.

"""
SQLite based DBStorage
"""

from insanity.log import error, warning, debug
from insanity.storage.dbstorage import DBStorage

try:
    # In Python 2.5, this is part of the standard library:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    # Previous versions have this as external dependency...
    from pysqlite2 import dbapi2 as sqlite

class SQLiteStorage(DBStorage):
    """
    Stores data in a sqlite db

    The 'async' setting will allow all writes to be serialized in a separate thread,
    allowing the testing to carry on.

    If you are only using the database for reading information, you should use
    async=False and only use the storage object from one thread.
    """

    def __init__(self, path, *args, **kwargs):
        self.path = path
        DBStorage.__init__(self, *args, **kwargs)

    def __repr__(self):
        return "<%s %s>" % (type(self), self.path)

    # DBStorage methods implementation
    def _openDatabase(self):
        debug("opening sqlite db for path '%s'", self.path)
        con = sqlite.connect(self.path, check_same_thread=False)
        # we do this so that we can store UTF8 strings in the database
        con.text_factory = str
        return con

    def _ExecuteScript(self, instructions, *args, **kwargs):
        """
        Executes the given script.
        """
        commit = kwargs.pop("commit", True)
        threadsafe = kwargs.pop("threadsafe", False)
        debug("%s args:%r kwargs:%r", instructions, args, kwargs)
        if not threadsafe:
            self._lock.acquire()
        try:
            cur = self.con.cursor()
            cur.executescript(instructions, *args, **kwargs)
            if commit:
                self.con.commit()
        finally:
            if not threadsafe:
                self._lock.release()
        return cur.lastrowid


    def _getDatabaseSchemeVersion(self):
        """
        Returns the scheme version of the currently loaded databse

        Returns None if there's no properly configured scheme, else
        returns the version
        """
        tables = self.__getAllTables()
        if not "version" in tables:
            return None
        # check if the version is the same as the current one
        res = self._FetchOne("SELECT version FROM version")
        if res == None:
            return None
        return res[0]

    def __getAllTables(self):
        """
        Returns the name of all the available tables in the currently
        loaded database.
        """
        checktables = """
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name;
        """
        return [x[0] for x in self.con.execute(checktables).fetchall()]


    def _getDBScheme(self):
        return DB_SCHEME

DB_SCHEME = """
CREATE TABLE version (
   version INTEGER AUTO_INCREMENT PRIMARY KEY,
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
   resultpercentage FLOAT,
   parentid INTEGER,
   ismonitor INTEGER NOT NULL DEFAULT 0,
   isscenario INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE testclassinfo (
   id INTEGER PRIMARY KEY,
   type TEXT,
   parent TEXT,
   description TEXT,
   fulldescription TEXT
);

CREATE TABLE testrun_environment_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name TEXT,
   intvalue INTEGER,
   txtvalue TEXT
);

CREATE TABLE test_arguments_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   intvalue INTEGER,
   txtvalue TEXT
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
   txtvalue TEXT
);

CREATE TABLE test_error_explanation_dict (
  id INTEGER PRIMARY KEY,
  containerid INTEGER,
  name INTEGER,
  txtvalue TEXT
);

CREATE TABLE test_outputfiles_dict (
   id INTEGER PRIMARY KEY,
   containerid INTEGER,
   name INTEGER,
   txtvalue TEXT
);

CREATE TABLE testclassinfo_arguments_dict (
   id INTEGER PRIMARY KEY,
   containerid TEXT,
   name TEXT,
   txtvalue TEXT
);

CREATE TABLE testclassinfo_checklist_dict (
   id INTEGER PRIMARY KEY,
   containerid TEXT,
   name TEXT,
   txtvalue TEXT
);

CREATE TABLE testclassinfo_extrainfo_dict (
   id INTEGER PRIMARY KEY,
   containerid TEXT,
   name TEXT,
   txtvalue TEXT
);

CREATE TABLE testclassinfo_outputfiles_dict (
   id INTEGER PRIMARY KEY,
   containerid TEXT,
   name TEXT,
   txtvalue TEXT
);

CREATE INDEX test_testrunid_idx ON test(testrunid, resultpercentage);
CREATE INDEX testclassinfo_parent_idx ON testclassinfo (parent);
CREATE INDEX testrun_env_dict_container_idx ON testrun_environment_dict (containerid);

CREATE INDEX t_a_dict_containerid_idx ON test_arguments_dict (containerid, name);
CREATE INDEX t_a_dict_txtname_idx ON test_arguments_dict (txtvalue, name);
CREATE INDEX t_c_list_containerid_idx ON test_checklist_list (containerid, name);
CREATE INDEX t_ei_dict_containerid_idx ON test_extrainfo_dict (containerid, name);
CREATE INDEX t_of_dict_containerid_idx ON test_outputfiles_dict (containerid, name);

CREATE INDEX tc_a_dict_c_idx ON testclassinfo_arguments_dict (containerid, name);
CREATE INDEX tc_c_dict_c_idx ON testclassinfo_checklist_dict (containerid, name);
CREATE INDEX tc_ei_dict_c_idx ON testclassinfo_extrainfo_dict (containerid, name);
CREATE INDEX tc_of_dict_c_idx ON testclassinfo_outputfiles_dict (containerid, name);

CREATE INDEX test_type_idx ON test (type);
"""
