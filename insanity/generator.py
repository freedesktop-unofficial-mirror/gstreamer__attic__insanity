# GStreamer QA system
#
#       generator.py
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
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA 02110-1301, USA.

"""
Generator classes

Generators expand some arguments into a dictionnary of arguments.
"""

# TODO
#  introspection
#
# We should be able to do something like:
# * chaining generators output
#   i.e. pass the output of FileSystemGenerator to PlaylistGenerator

class Generator(object):
    """
    Expands some arguments into a list of arguments.

    Base class, should not be used directly.
    """

    __args__ = {}
    __produces__ = None

    def __init__(self, *args, **kwargs):
        """
        Subclasses should call their parent __init__ will ALL arguments
        """
        self.args = args
        self.kwargs = kwargs
        self.generated = []
        self._length = None

    def copy(self):
        return self.__class__(*self.args, **self.kwargs)

    def generate(self):
        """
        Returns the full combination of results
        """
        if not self.generated:
            self.generated = self._generate()
        return self.generated

    def _generate(self):
        """
        Return the full list of results
        to be implemented by subclasses
        """
        raise NotImplementedError

    def __iter__(self):
        return iter(self.generate()[:])

    def __len__(self):
        if self._length == None:
            self._length = len(self.generate())
        return self._length

    def __getitem__(self, idx):
        return self.generate()[idx]
