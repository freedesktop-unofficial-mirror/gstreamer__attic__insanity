# GStreamer QA system
#
#       utils.py
#
# Copyright (c) 2007, Edward Hervey <bilboed@bilboed.com>
# Copyright (C) 2004 Johan Dahlin <johan at gnome dot org>
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
Miscellaneous utility functions and classes
"""

import os
import time
import signal
import subprocess
import imp
import urllib
from random import randint
import gzip
from insanity.log import info, exception
from insanity.testmetadata import TestMetadata

__uuids = []
__tests = []

def randuuid():
    """
    Generates a random uuid, not guaranteed to be unique.
    """
    return "%032x" % randint(0, 2**128)

def acquire_uuid():
    """
    Returns a guaranted unique identifier.
    When the user of that UUID is done with it, it should call
    release_uuid(uuid) with that identifier.
    """
    global __uuids
    uuid = randuuid()
    while uuid in __uuids:
        uuid = randuuid()
    __uuids.append(uuid)
    return uuid

def release_uuid(uuid):
    """
    Releases the use of a unique identifier.
    """
    global __uuids
    if not uuid in __uuids:
        return
    __uuids.remove(uuid)

def list_available_tests():
    """
    Returns the list of available tests containing for each:
    * the test name
    * the test description
    * the test class
    """
    global __tests
    return __tests

def list_available_scenarios():
    """
    Returns the list of available scenarios containing for each:
    * the scenario name
    * the scenario description
    * the scenario class
    """
    from insanity.test import Test, DBusTest, PythonDBusTest
    from insanity.scenario import Scenario

    #def get_valid_subclasses(cls):
    #    res = []
    #    if not cls == Scenario:
    #        res.append((cls.__test_name__.strip(), cls.__test_description__.strip(), cls))
    #    for i in cls.__subclasses__():
    #        res.extend(get_valid_subclasses(i))
    #    return res
    #return get_valid_subclasses(Scenario)
    return [] # hmm, need to look up how a scenario is different from a large test

def kill_process(process):
    tries = 10
    returncode = None
    while returncode is None and not tries == 0:
        time.sleep(0.1)
        returncode = process.poll()
        tries -= 1
        if returncode is None:
            info("Process isn't done yet, terminating it")
            os.kill(process.pid, signal.SIGTERM)
            time.sleep(1)
            returncode = process.poll()
        if returncode is None:
            info("Process did not terminate, killing it")
            os.kill(process.pid, signal.SIGKILL)
            time.sleep(1)
            returncode = process.poll()
        if returncode is None:
            # Probably turned into zombie process, something is
            # really broken...
            info("Process did not exit after SIGKILL")
    return returncode


def scan_directory_for_tests(directory):

    source_ext = [t[0] for t in imp.get_suffixes() if t[2] == imp.PY_SOURCE]
    import_names = []

    for dirpath, dirnames, filenames in os.walk(directory):

        for filename in filenames:
            fullname = os.path.join(dirpath, filename)
            try:
                tm = TestMetadata (fullname)
                import_names.append(tm)
            except Exception, e:
                info ( 'Exception: %s' % e)
                pass

        #for dirname in dirnames:
        #    for ext in source_ext:
        #        if os.path.exists(os.path.join(dirpath, dirname, "__init__%s" % (ext,))):
        #            import_names.append(dirname)

        # Don't descent to subdirectories:
        break

    return import_names

def scan_for_tests(directory = None):
    if directory == None:
        directory = 'tests' # TODO
    global __tests
    __tests = scan_directory_for_tests (directory)

def get_test_metadata(testname):
    """
    Returns the Test metadata corresponding to the given testname
    """
    tests = list_available_tests()
    tests.extend(list_available_scenarios())
    testname = testname.strip()
    for test in tests:
        if test.__test_name__ == testname:
            return test
    raise ValueError("No Test metadata available for %s" % testname)

def reverse_dict(adict):
    """
    Returns a dictionnary where keys and values are inverted.

    Uniqueness of keys/values isn't checked !
    """
    d = {}
    if not adict:
        return d
    for k, v in adict.iteritems():
        d[v] = k
    return d

def map_dict_full(adict, mapdict):
    """
    Switches the keys of adict using the mapping (oldkey:newkey) from
    mapdict.

    Returns:
    * a dictionnary where the keys from adict are replaced
    by the value mapped in mapdict.
    * a list of unmapped keys
    """
    d = {}
    unk = []
    if not mapdict:
        return d, unk
    for k, v in adict.iteritems():
        if k in mapdict:
            d[mapdict[k]] = v
        else:
            unk.append(k)
    return d, unk

def map_dict(adict, mapdict):
    """
    Switches the keys of adict using the mapping (oldkey:newkey) from
    mapdict.

    Returns:
    * a dictionnary where the keys from adict are replaced
    by the value mapped in mapdict.
    """
    d, unk = map_dict_full(adict, mapdict)
    return d

def map_list(alist, mapdict):
    """
    Same as map_dict, except the first argument and return value are
    the flattened out tuple-list version : [(key1,val1), (key2, val2)..]
    """
    r = []
    if not mapdict:
        return r
    for k, v in alist:
        if k in mapdict:
            r.append((mapdict[k], v))
    return r

def compress_file(original, compfile):
    """
    Takes the contents of 'original' and compresses it into the new file
    'compfile' using gzip methods.
    """
    f = open(original, "r")
    out = gzip.GzipFile(compfile, "w")
    # reading 8kbytes at a time, might want to increase it later
    buf = f.read(8192)
    while buf:
        out.write(buf)
        buf = f.read(8192)

    f.close()
    out.close()

def unicode_dict(adict):
    """
    Returns a copy on the given dictionary where all string values
    are validated as proper unicode
    """
    res = {}
    for key, val in adict.iteritems():
        if isinstance(val, str) and key != 'uri':
            try:
                res[key] = unicode(val)
            except:
                try:
                    res[key] = unicode(val, 'iso8859_1')
                except:
                    exception("Argument [%s] is not valid UTF8 (%r)",
                              key, val)
        else:
            res[key] = val
    return res
