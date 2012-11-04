# GStreamer QA system
#
#       storage/mysql.py
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
MySQL based DBStorage

Requires the mysql-python module
http://mysql-python.sourceforge.net/
"""

from insanity.log import error, warning, debug
from insanity.storage.dbstorage import DBStorage

try:
    import MySQLdb

    class MySQLStorage(DBStorage):
        """
        MySQL based DBStorage
        """

        _default_host = "localhost"
        _default_user = "insanity"
        _default_pass = "madness"
        _default_port = 3306
        _default_db = "insanity"

        @classmethod
        def parse_uri(cls, uri):
            """
            Parse a given string of format

              mysql://username:password@hostname:port/database

            into a dictionary {"hostname":...} suitable for passing as kwargs to
            MySQLStorage(**kwargs).

            Omitted fields will be filled with default values from

              mysql://insanity:madness@localhost:3306/insanity
            """
            username=cls._default_user
            passwd=cls._default_pass
            port=cls._default_port
            host=cls._default_host
            dbname=cls._default_db

            if uri.startswith("mysql://"):
                uri = uri[8:]

            if '@' in uri:
                userpass, uri = uri.split('@', 1)
                if ':' in userpass:
                    username, passwd = userpass.split(':', 1)
                else:
                    username = userpass
            if '/' in uri:
                uri, dbname = uri.rsplit('/', 1)
            if ':' in uri:
                host, port = uri.split(':', 1)
                port = int(port)
            else:
                host = uri

            return {"username":username,
                    "passwd":passwd,
                    "port":port,
                    "host":host,
                    "dbname":dbname}

        def __init__(self, host=_default_host, username=_default_user,
                     passwd=_default_pass, port=_default_port,
                     dbname=_default_db,
                     *args, **kwargs):

            self.__host = host
            self.__port = port
            self.__username = username
            self.__passwd = passwd
            self.__dbname = dbname
            DBStorage.__init__(self, *args, **kwargs)

        def __repr__(self):
            return "<%s %s@%s:%d>" % (type(self),
                                      self.__dbname,
                                      self.__host,
                                      self.__port)

        def _openDatabase(self):
            con = MySQLdb.connect(host=self.__host,
                                  port=self.__port,
                                  user=self.__username,
                                  passwd=self.__passwd,
                                  db=self.__dbname)
            return con

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
            SHOW TABLES;
            """
            cursor = self.con.cursor()
            cursor.execute(checktables)
            res = cursor.fetchall()
            if not res:
                return []
            res = list(zip(*res)[0])
            return res

        def _ExecuteCommit(self, instruction, *args, **kwargs):
            """
            Calls .execute(instruction, *args, **kwargs) and .commit()

            Returns the last row id

            Threadsafe
            """
            instruction = instruction.replace('?', '%s')
            return DBStorage._ExecuteCommit(self, instruction, *args, **kwargs)

        def _ExecuteMany(self, instruction, *args, **kwargs):
            instruction = instruction.replace('?', '%s')
            return DBStorage._ExecuteMany(self, instruction, *args, **kwargs)

        def _FetchAll(self, instruction, *args, **kwargs):
            """
            Executes the given SQL query and returns a list
            of tuples of the results

            Threadsafe
            """
            instruction = instruction.replace('?', '%s')
            return DBStorage._FetchAll(self, instruction, *args, **kwargs)

        def _FetchOne(self, instruction, *args, **kwargs):
            """
            Executes the given SQL query and returns a unique
            tuple of result

            Threadsafe
            """
            instruction = instruction.replace('?', '%s')
            return DBStorage._FetchOne(self, instruction, *args, **kwargs)

        def _getDBScheme(self):
            return DB_SCHEME


    DB_SCHEME = """
    CREATE TABLE version (
       version integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       modificationtime INTEGER
    );

    CREATE TABLE testrun (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       clientid INTEGER,
       starttime INTEGER,
       stoptime INTEGER
    );

    CREATE TABLE client (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       software TEXT,
       name TEXT,
       user TEXT
    );

    CREATE TABLE test (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       testrunid INTEGER,
       type INTEGER,
       resultpercentage FLOAT,
       parentid INTEGER,
       ismonitor TINYINT(1) DEFAULT 0,
       isscenario TINYINT(1) DEFAULT 0
    );

    CREATE TABLE testclassinfo (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       type TEXT,
       parent VARCHAR(255),
       description TEXT,
       fulldescription TEXT
    );

    CREATE TABLE testrun_environment_dict (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       containerid INTEGER,
       name TEXT,
       intvalue INTEGER,
       txtvalue TEXT
    );

    CREATE TABLE test_arguments_dict (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       containerid INTEGER,
       name INTEGER,
       intvalue INTEGER,
       txtvalue TEXT
    );

    CREATE TABLE test_checklist_list (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       containerid INTEGER,
       name INTEGER,
       intvalue INTEGER
    );

    CREATE TABLE test_extrainfo_dict (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       containerid INTEGER,
       name INTEGER,
       intvalue INTEGER,
       txtvalue TEXT
    );

    CREATE TABLE test_outputfiles_dict (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       containerid INTEGER,
       name INTEGER,
       txtvalue TEXT
    );

    CREATE TABLE testclassinfo_arguments_dict (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       containerid VARCHAR(255),
       name TEXT,
       txtvalue TEXT
    );

    CREATE TABLE testclassinfo_checklist_dict (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       containerid VARCHAR(255),
       name TEXT,
       txtvalue TEXT
    );

    CREATE TABLE testclassinfo_extrainfo_dict (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       containerid VARCHAR(255),
       name TEXT,
       txtvalue TEXT
    );

    CREATE TABLE testclassinfo_outputfiles_dict (
       id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
       containerid VARCHAR(255),
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

    CREATE INDEX tc_a_dict_c_idx ON testclassinfo_arguments_dict (containerid);
    CREATE INDEX tc_c_dict_c_idx ON testclassinfo_checklist_dict (containerid);
    CREATE INDEX tc_ei_dict_c_idx ON testclassinfo_extrainfo_dict (containerid);
    CREATE INDEX tc_of_dict_c_idx ON testclassinfo_outputfiles_dict (containerid);

    CREATE INDEX test_type_idx ON test (type);
    """
except ImportError:
    print "mysql-python (http://mysql-python.sourceforge.net/) is needed" \
        " to use the MySQLStorage DBStorage backend"
