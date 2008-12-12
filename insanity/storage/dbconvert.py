# GStreamer QA system
#
#       storage/dbconvert.py
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
Conversion scripts for DBStorage
"""

import time
from cPickle import dumps, loads
from insanity.log import error, warning, debug

def _updateTables(storage, fromversion, toversion):
    """
    Update the tables from <toversion> to <toversion> database
    scheme.
    """
    if fromversion < 2:
        __updateDatabaseFrom1To2(storage)
    if fromversion < 3:
        __updateDatabaseFrom2To3(storage)

    # finally update the db version
    cmstr = "UPDATE version SET version=?,modificationtime=? WHERE version=?"
    storage._ExecuteCommit(cmstr, (toversion, int (time.time()), fromversion))
    return True



def __updateDatabaseFrom1To2(storage):
    create1to2 = """
    CREATE INDEX test_type_idx ON test (type);
    """
    # Add usedtests_testrun table and index
    storage._ExecuteScript(create1to2)
    storage.con.commit()

def testrun_env_2to3(storage):
    # go over all testrun environment and convert them accordingly
    envs = storage._FetchAll("""SELECT id, name, containerid, intvalue, txtvalue, blobvalue FROM testrun_environment_dict""")
    for eid, name, container, intvalue, txtvalue, blobvalue in envs:
        drop = False
        update = False
        add = None # list of new (name, intvalue, txtvalue)
        print name, intvalue, txtvalue, blobvalue
        if name == "uname" and blobvalue != None:
            update = True
            txtvalue = ' '.join(loads(blobvalue))
        elif name == "env-variables" and blobvalue != None:
            drop = True
            add = [(k, None, v) for k,v in loads(blobvalue).iteritems()]
        elif name == "gst-registry" and blobvalue != None:
            drop = True
            d = loads(blobvalue)
            add = []
            for k in d.keys():
                filename, date, version, features = d[k]
                print k, filename, date, version, features
                add.append(("gst-registry.%s.filename"%k, None, filename))
                add.append(("gst-registry.%s.date"%k, None, date))
                add.append(("gst-registry.%s.version"%k, None, version))
                add.append(("gst-registry.%s.features"%k, None, ','.join(features)))
        print drop, update
        if add:
            print "Adding", add
        if update == True:
            storage._ExecuteCommit("""UPDATE testrun_environment_dict SET intvalue=?,txtvalue=? WHERE id=?""",
                                   (intvalue, txtvalue, eid))
        if drop == True:
            storage._ExecuteCommit("""DELETE FROM testrun_environment_dict WHERE id=?""",
                                   (eid, ))
        if add != None:
            storage._ExecuteMany("""INSERT INTO testrun_environment_dict (containerid, name, intvalue, txtvalue) VALUES (?, ?, ?, ?)""",
                                 [(container, a, b, c) for a,b,c in add])

def __updateDatabaseFrom2To3(storage):
    def convert_extrainfo_data(name, intvalue, txtvalue, blobvalue):
        """ Converts the extrainfo data to remove blobvalues
        Returns a tuple of :
        * name
        * intvalue
        * txtvalue"""
        if name in ["subprocess-spawn-time", "remote-instance-creation-delay",
                    "test-setup-duration", "test-total-duration"]:
            val = loads(blobvalue)
            return (name, intvalue, txtvalue, int(val * 1000))
        return (name, intvalue, txtvalue)
    create2to3 = """
    ALTER TABLE testclassinfo_arguments_dict CHANGE containerid containerid VARCHAR(255);
    ALTER TABLE testclassinfo_arguments_dict CHANGE blobvalue txtvalue TEXT;
    ALTER TABLE testclassinfo_checklist_dict CHANGE containerid containerid VARCHAR(255);
    ALTER TABLE testclassinfo_extrainfo_dict CHANGE containerid containerid VARCHAR(255);
    ALTER TABLE testclassinfo_outputfiles_dict CHANGE containerid containerid VARCHAR(255);

    DROP INDEX mc_a_dict_c_idx ON monitorclassinfo_arguments_dict;
    DROP INDEX mc_c_dict_c_idx ON monitorclassinfo_checklist_dict;
    DROP INDEX mc_ei_dict_c_idx ON monitorclassinfo_extrainfo_dict;
    DROP INDEX mc_of_dict_c_idx ON monitorclassinfo_outputfiles_dict;

    DROP TABLE monitorclassinfo_arguments_dict;
    DROP TABLE monitorclassinfo_checklist_dict;
    DROP TABLE monitorclassinfo_extrainfo_dict;
    DROP TABLE monitorclassinfo_outputfiles_dict;

    ALTER TABLE test ADD COLUMN parentid INTEGER;
    ALTER TABLE test ADD COLUMN ismonitor TINYINT(1) DEFAULT 0;
    ALTER TABLE test ADD COLUMN isscenario TINYINT(1) DEFAULT 0;

    ALTER TABLE testrun_environment_dict DROP COLUMN blobvalue;
    ALTER TABLE test_arguments_dict DROP COLUMN blobvalue;
    ALTER TABLE test_extrainfo_dict DROP COLUMN blobvalue;

    DROP INDEX subtests_scenarioid_idx ON subtests;
    DROP INDEX monitor_testid_idx ON monitor;
    DROP INDEX monitorclassinfo_parent_idx ON monitorclassinfo;
    DROP INDEX m_a_dict_containerid_idx ON monitor_arguments_dict;
    DROP INDEX m_c_dict_containerid_idx ON monitor_checklist_dict;
    DROP INDEX m_ei_dict_containerid_idx ON monitor_extrainfo_dict;
    DROP INDEX m_of_dict_containerid_idx ON monitor_outputfiles_dict;

    DROP TABLE subtests;
    DROP TABLE monitor;
    DROP TABLE monitorclassinfo;
    DROP TABLE monitor_arguments_dict;
    DROP TABLE monitor_checklist_dict;
    DROP TABLE monitor_extrainfo_dict;
    DROP TABLE monitor_outputfiles_dict;
    """
    # Change testclassinfo_*_dict.container from INTEGER to VARCHAR
    #
    # We need to:
    # 1. Get all available (id, containerid)
    # 2. Alter the column type
    # 3. Replace the containerid with the testclassinfo.type
    print("Getting original testclassinfo_*_ values")
    args = storage._FetchAll("""SELECT id, containerid, blobvalue FROM testclassinfo_arguments_dict""")
    checks = storage._FetchAll("""SELECT id, containerid FROM testclassinfo_checklist_dict""")
    extras = storage._FetchAll("""SELECT id, containerid FROM testclassinfo_extrainfo_dict""")
    outputs = storage._FetchAll("""SELECT id, containerid FROM testclassinfo_outputfiles_dict""")
    classes = dict(storage._FetchAll("""SELECT id, type FROM testclassinfo"""))

    print("Getting monitorclassinfo_*_ values")
    margs = storage._FetchAll("""SELECT id, containerid, name, txtvalue FROM monitorclassinfo_arguments_dict""")
    mchecks = storage._FetchAll("""SELECT id, containerid, name, txtvalue FROM monitorclassinfo_checklist_dict""")
    mextras = storage._FetchAll("""SELECT id, containerid, name, txtvalue FROM monitorclassinfo_extrainfo_dict""")
    moutputs = storage._FetchAll("""SELECT id, containerid, name, txtvalue FROM monitorclassinfo_outputfiles_dict""")
    mclasses = dict(storage._FetchAll("""SELECT id, type FROM monitorclassinfo"""))

    print("Getting subtests contents")
    # subtests will be a dictionnary of:
    # * key : test id
    # * value : container id
    subtests = storage._FetchAll("""SELECT testid, scenarioid FROM subtests""")

    print("Getting monitor contents")
    # id, testid, type, resperc, testrunid
    monitors = storage._FetchAll("""SELECT monitor.id, monitor.testid, monitor.type, monitor.resultpercentage, test.testrunid FROM monitor,test WHERE monitor.testid=test.id""")
    monclassinfo = storage._FetchAll("""SELECT id, type, parent, description FROM monitorclassinfo""")
    monargs = storage._FetchAll("""SELECT id, containerid, name, intvalue, txtvalue FROM monitor_arguments_dict""")
    monchecks = storage._FetchAll("""SELECT id, containerid, name, intvalue FROM monitor_checklist_dict""")
    monextras = storage._FetchAll("""SELECT id, containerid, name, intvalue, txtvalue FROM monitor_extrainfo_dict""")
    monoutputs = storage._FetchAll("""SELECT id, containerid, name, txtvalue FROM monitor_outputfiles_dict""")

    print("Going over testrun_environment_dict to convert blob values to non-blob values")
    testrun_env_2to3(storage)

    try:
        print("Converting 'containerid' columns from INT to TEXT")
        storage._ExecuteScript(create2to3)
        storage.con.commit()
    except:
        error("Can't upgrade DB scheme !")
        raise

    # STEP 1 : Move monitorclassinfo to testclassinfo and remember the mapping
    # of monitorclassinfo.id to testclassinfo.id
    print("Moving old monitorclassinfo contents to testclassinfo")
    mci_mapping = {}
    for mid, mtype, parent, description in monclassinfo:
        mci_mapping[mid] = storage._ExecuteCommit("""INSERT INTO testclassinfo (type, parent, description) VALUES (?, ?, ?)""",
                                                  (mtype, parent, description))

    # STEP 2 : Move monitor to test, using the mci_mapping and remember the
    # mapping of monitor.id to test.id
    print("Moving old monitor contents to test")
    monitor_mapping = {}
    for mid, testid, mtype, resultpercentage, testrunid in monitors:
        monitor_mapping[mid] = storage._ExecuteCommit("""INSERT INTO test (testrunid, type, resultpercentage, parentid, ismonitor) VALUES (?, ?, ?, ?, 1)""",
                                                      (testrunid, mci_mapping[mtype], resultpercentage, testid))

    # STEP 2b : Convert testclassinfo_*_dict.containerid from int to txt
    print("Updating converted TestClassInfo* columns")
    storage._ExecuteMany("""UPDATE testclassinfo_arguments_dict SET containerid=? , txtvalue=? WHERE id=?""",
                      [(classes[int(b)],loads(c)[0],a) for a,b,c in args])
    storage._ExecuteMany("""UPDATE testclassinfo_checklist_dict SET containerid=? WHERE id=?""",
                      [(classes[int(b)],a) for a,b in checks])
    storage._ExecuteMany("""UPDATE testclassinfo_extrainfo_dict SET containerid=? WHERE id=?""",
                      [(classes[int(b)],a) for a,b in extras])
    storage._ExecuteMany("""UPDATE testclassinfo_outputfiles_dict SET containerid=? WHERE id=?""",
                      [(classes[int(b)],a) for a,b in outputs])

    # STEP 3 : Move monitorclassinfo_*_dict to testclassinfo_*_dict and remember
    # the mapping of monitorclassinfo_*_dict.id to testclassinfo_*_dict.id for
    # each of the tables.
    # Also, be careful to now use the classinfo name
    print("Moving old monitorclassinfo_arguments_dict to testclassinfo_arguments_dict")
    mcia_mapping = {}
    for id, containerid, name, value in margs:
        mcia_mapping[id] = storage._ExecuteCommit("""INSERT INTO testclassinfo_arguments_dict (containerid, name, txtvalue) VALUES (?, ?, ?)""",
                                               (mclasses[containerid], name, value))
    print("Moving old monitorclassinfo_checklist_dict to testclassinfo_checklist_dict")
    mcic_mapping = {}
    for id, containerid, name, value in mchecks:
        mcic_mapping[id] = storage._ExecuteCommit("""INSERT INTO testclassinfo_checklist_dict (containerid, name, txtvalue) VALUES (?, ?, ?)""",
                                               (mclasses[containerid], name, value))

    print("Moving old monitorclassinfo_extrainfo_dict to testclassinfo_extrainfo_dict")
    mcie_mapping = {}
    for id, containerid, name, value in mextras:
        mcie_mapping[id] = storage._ExecuteCommit("""INSERT INTO testclassinfo_extrainfo_dict (containerid, name, txtvalue) VALUES (?, ?, ?)""",
                                               (mclasses[containerid], name, value))

    print("Moving old monitorclassinfo_outputfiles_dict to testclassinfo_outputfiles_dict")
    mcio_mapping = {}
    for id, containerid, name, value in moutputs:
        mcio_mapping[id] = storage._ExecuteCommit("""INSERT INTO testclassinfo_outputfiles_dict (containerid, name, txtvalue) VALUES (?, ?, ?)""",
                                               (mclasses[containerid], name, value))

    # STEP 4 : Move all monitor_*_dict to test_*_dict using the mci_mapping and the
    # mci*_mapping
    print("Moving monitor_arguments_dict to test_arguments_dict")
    for id, containerid, name, intvalue, txtvalue in monargs:
        storage._ExecuteCommit("""INSERT into test_arguments_dict (containerid, name, intvalue, txtvalue) VALUES (?, ?, ?, ?)""",
                            (monitor_mapping[containerid], mcia_mapping[name], intvalue, txtvalue))

    print("Moving monitor_checklist_dict to test_checklist_list")
    for id, containerid, name, intvalue in monchecks:
        storage._ExecuteCommit("""INSERT into test_checklist_list (containerid, name, intvalue) VALUES (?, ?, ?)""",
                            (monitor_mapping[containerid], mcic_mapping[name], intvalue))

    print("Moving monitor_extrainfo_dict to test_extrainfo_dict")
    for id, containerid, name, intvalue, txtvalue in monextras:
        storage._ExecuteCommit("""INSERT into test_extrainfo_dict (containerid, name, intvalue, txtvalue) VALUES (?, ?, ?, ?)""",
                            (monitor_mapping[containerid], mcie_mapping[name], intvalue, txtvalue))

    print("Moving monitor_outputfiles_dict to test_outputfiles_dict")
    for id, containerid, name, txtvalue in monoutputs:
        storage._ExecuteCommit("""INSERT into test_outputfiles_dict (containerid, name, txtvalue) VALUES (?, ?, ?)""",
                            (monitor_mapping[containerid], mcio_mapping[name], txtvalue))

    # STEP 5 : Transfer information from subtests to test
    # subtests.testid => test.ismonitor = 0
    # test.parentid = subtests.scenarioid
    print("Moving old subtests data to test (parentid, ismonitor)")
    for testid, scenarioid in subtests:
        storage._ExecuteCommit("""UPDATE test SET test.parentid=?,test.ismonitor=0 WHERE test.id=?""",
                            (scenarioid, testid))
        storage._ExecuteCommit("""UPDATE test SET test.ismonitor=0,test.isscenario=1 WHERE test.id=?""", (scenarioid, ))

    print("done")
