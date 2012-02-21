# GStreamer QA system
#
#       testmetadata.py
#
# Copyright (c) 2012, Vincent Penquerc'h <vincent@collabora.co.uk>
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
Test metadata class
"""

import os
import sys
import subprocess
import json
from insanity.log import error, warning, debug, info, exception

class TestMetadata():
    """
    Gathers metadata from a test binary, which can then be used
    by other code without instanciating the test object.
    """

    def __init__(self, filename, *args, **kwargs):
        if not self.probe_test (filename):
            raise Exception ('Not a test')

    def probe_test(self, filename):
        if not "insanity-test-" in filename:
            return False
        info ('Running %s, which might be a test', filename)
        try:
            process = subprocess.Popen([filename, '--insanity-metadata'],
                stdin = None, stdout = subprocess.PIPE, stderr = subprocess.PIPE,
                universal_newlines=True)
        except Exception,e:
            info('Exception running process (%s), not a test', e)
            return False
        if process == None:
            info('Failed to create process, not a test')
            return False
        if process.stdin:
            process.stdin.close()
        if process.stderr:
            process.stderr.close()

        lines=""
        line=process.stdout.readline()
        if not line or not 'Insanity test metadata:\n' in line:
             info('No magic, not a test')
             process.stdout.close()
             return False
        line=process.stdout.readline()
        while line:
            lines = lines + line
            line = process.stdout.readline()
        process.stdout.close()

        try:
            metadata = json.loads(lines);
        except Exception,e:
            info('Exception loading JSON metadata (%s), not a test', e)
            return False
        if not metadata:
            info('Empty metadata, not a test')
            return False
        if not "__name__" in metadata or not "__description__" in metadata:
            info('Partial metadata, probably a broken or obsolete test')
            return False

        # TODO: need to wait at most a second or so, then kill any process that's not dead yet
        #kill_process(process)
        self.__test_filename__ = os.path.abspath(filename)
        self.__test_name__ = self.get_metadata (metadata, "__name__")
        self.__test_description__ = self.get_metadata (metadata, "__description__")
        self.__test_full_description__ = self.get_metadata (metadata, "__full_description__")
        self.__test_arguments__ = self.get_metadata (metadata, "__arguments__")
        self.__test_output_files__ = self.get_metadata (metadata, "__output_files__")
        self.__test_checklist__ = self.get_metadata (metadata, "__checklist__")
        self.__test_extra_infos__ = self.get_metadata (metadata, "__extra_infos__")
        info('It is a valid test')

        mod = sys.modules["insanity.dbustest"]
        debug("Got module %r", mod)
        # get class
        cls = mod.__dict__.get("DBusTest")
        self.__test_class__ = cls
        return True

    def get_metadata(self, metadata, key):
        if not key in metadata:
            return None
        return metadata[key]

    def getFullCheckList(self):
        """
        Returns the full test checklist. This is used to know all the
        possible check items for this instance, along with their description.
        """
        dc = self.__test_class__.getClassFullCheckList()
        if self.__test_checklist__ != None:
            dc.update(self.__test_checklist__)
        return dc

    def getFullArgumentList(self):
        """
        Returns the full list of arguments with descriptions.

        The format of the returned argument dictionnary is:
        key : argument name
        value : tuple of :
            * short description
            * default value
            * extended description (Can be None)
        """
        dc = self.__test_class__.getClassFullArgumentList()
        if self.__test_arguments__ != None:
            dc.update(self.__test_arguments__)
        return dc

    def getFullExtraInfoList(self):
        """
        Returns the full list of extra info with descriptions.
        """
        dc = self.__test_class__.getClassFullExtraInfoList()
        if self.__test_extra_infos__ != None:
            dc.update(self.__test_extra_infos__)
        return dc

    def getFullOutputFilesList(self):
        """
        Returns the full list of output files with descriptions.
        """
        dc = self.__test_class__.getClassFullOutputFilesList()
        if self.__test_output_files__ != None:
            dc.update(self.__test_output_files__)
        return dc

