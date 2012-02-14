# GStreamer QA system
#
#       tests/blank.py
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
Blank QA test for development purposes only
"""

from insanity.test import PythonDBusTest

class BlankCTest(PythonDBusTest):
    __test_name__ = "blank-c-test"
    __test_description__ = """Blank C QA test"""
    __test_object__ = "blankc"
    __test_arguments__ = {
        "data" : ( "Data passed to see if that works", None, None)
        }
    __test_output_files__ = {
        "dummy-output-file":"Output file, for testing"
        }

