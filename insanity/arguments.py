# GStreamer QA system
#
#       arguments.py
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
Arguments classes for tests
"""

from insanity.log import debug, info
from insanity.generator import Generator

class Arguments(object):
    """
    Iterable argument lists.

    Takes a list of named arguments and can be iterated to return
    dictionnaries of all the combinations.

    Those arguments can either be :
    * static arguments (ex: int, list, string, etc...), or
    * dynamic arguments (currently only generators).

    If a dynamic arguments produces multiple return values, you need
    to name that argument as the coma-separated concatenation of the
    individual arguments. Ex : "arg1,arg2,arg3". These multiple values
    may be either a python list, or a comma separated string.
    """

    def __init__(self, **kwargs):
        self.args = kwargs
        # split out static args from generators
        # generators : (generator, curidx, length)
        self.generators = {}
        self.statics = {}
        for key, value in self.args.iteritems():
            info("key:%s, type:%r" % (key, value))
            if isinstance(value, Generator):
                try:
                    # Checking that the generator is not empty, which can
                    # happen easily if you mistype the filename passed to the
                    # filesystemgenerator for example.
                    iter(value).next()
                except StopIteration:
                    raise ValueError("generator %r for argument %r produced no items" % \
                                     (value, key,))
                self.generators[key] = [value, 0, 0]
            else:
                self.statics[key] = value
        self.genlist = self.generators.keys()
        self._initialized = False
        self.combinations = 1
        self.globalidx = 0

    ## Iterable interface
    def __iter__(self):
        # return a copy
        return Arguments(**self.args)

    def next(self):
        if not self._initialized:
            self._initialize()
        if not self.globalidx < self.combinations:
            raise StopIteration
        # return the next dict of arguments
        # contains a copy of all static arguments
        # plus the next combination of generators
        res = self.statics.copy()
        if self.generators:
            info("we have generators")
            # extend with current generator values
            for key in self.genlist:
                info("key")
                gen, idx = self.generators[key][:2]
                # split generator name
                keys = key.split(",")
                if len(keys) > 1:
                    if isinstance(gen[idx],list):
                      gens = gen[idx]
                    else:
                      gens = gen[idx].split(",")
                    for i in range(len(keys)):
                        res[keys[i]] = gens[i]
                else:
                    res[keys[0]] = gen[idx]
            # update values
            self._updateGeneratorsPosition()
        # update global idx
        self.globalidx += 1
        return res

    def _updateGeneratorsPosition(self):
        for key in self.genlist:
            # update the position of this generator
            apos = (self.generators[key][1] + 1) % self.generators[key][2]
            self.generators[key][1] = apos
            # if we didn't go over, break, else continue to update next one
            if self.generators[key][1]:
                break

    def _initialize(self):
        # figure out the length of all generators
        debug("initializing")
        cpy = {}
        for key, value in self.generators.iteritems():
            gen, idx, nb = value
            nb = len(gen)
            if nb:
                self.combinations *= nb
            cpy[key] = [gen, idx, nb]
        debug("self.combinations: %d" % self.combinations)
        self.generators = cpy
        self._initialized = True

    def __len__(self):
        if not self._initialized:
            self._initialize()
        return self.combinations

    def current(self):
        """ Returns the current position """
        return self.globalidx

    ## EXTRA METHODS
    ## NOT IMPLEMENTED YET

    def isValidWithTest(self, testclass):
        """
        Checks if all arguments are valid with given test
        """
        raise NotImplementedError
