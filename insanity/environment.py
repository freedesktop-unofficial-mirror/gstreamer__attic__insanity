#!/usr/bin/env python

# GStreamer QA system
#
#       environment.py
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
Environment-related methods and classes
"""

import cPickle
import subprocess
import os
import tempfile
import sys
import imp
import gobject
gobject.threads_init()
from insanity.log import debug, exception

# TODO : methods/classes to retrieve/process environment
#
# examples:
#   env variablse
#   pluggable env retrievers
#   Application should be able to add information of its own
def _pollSubProcess(process, resfile, callback):
    res = process.poll()
    if res == None:
        return True
    # get dictionnary from resultfile
    try:
        wmf = open(resfile, "rb")
        resdict = cPickle.load(wmf)
        wmf.close()
        os.remove(resfile)
    except:
        exception("Couldn't get pickle from file %s", resfile)
        resdict = {}
    # call callback with dictionnary
    callback(resdict)
    return False

def collectEnvironment(environ, callback):
    """
    Using the given environment variables, spawn a new process to collect
    various environment information.

    Returns a dictionnary of information.

    When the information collection is done, the given callback will be called
    with the dictionnary of information as it's sole argument.
    """
    resfile, respath = tempfile.mkstemp()
    os.close(resfile)
    thispath = os.path.abspath(__file__)
    # The compiled module suffix can be ".pyc" or ".pyo":
    suffixes = [s[0] for s in imp.get_suffixes()
                if s[2] == imp.PY_COMPILED]
    for suffix in suffixes:
        if thispath.endswith(suffix):
            thispath = thispath[:-len(suffix)] + ".py"
            break
    pargs = [sys.executable, thispath, respath]

    try:
        debug("spawning subprocess %r", pargs)
        proc = subprocess.Popen(pargs, env=environ)
    except:
        exception("Spawning remote process (%s) failed" % (" ".join(pargs),))
        os.remove(respath)
        callback({})
    else:
        gobject.timeout_add(500, _pollSubProcess, proc, respath, callback)

def _privateCollectEnvironment():
    d = {}
    return d

if __name__ == "__main__":
    # args : <outputfile>
    d = _privateCollectEnvironment()
    mf = open(sys.argv[1], "wb+")
    cPickle.dump(d, mf)
    mf.close()
