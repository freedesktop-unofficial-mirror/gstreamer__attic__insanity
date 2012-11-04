# GStreamer QA system
#
#       generators/external.py
#
# Copyright (c) 2012, Collabora Ltd <vincent@collabora.co.uk>
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
External process generator
"""

import random
import subprocess
import signal

from insanity.generator import Generator
from insanity.log import debug, info, exception

class ExternalGenerator(Generator):
    """
    Arguments:
    * path to binary (could be a shell)
    * arguments to binary (could be shell exec command)
    * directory to run in

    Returns:
    * the process' stdout
    """

    __args__ = {
        "command":"Command line to run",
        "cwd":"Directory to run on",
        }

    # We don't know any semantics, derived classes are welcome to add some
    __produces__ = None

    def __init__(self, command="", cwd=None, max_length=0, randomize=False, seed=5,
                 *args,
                 **kwargs):
        """
        command: Command line to run
        cwd: Directory where to run the program
        max_length: The maximum size of the generated list
        randomize: Wether the result list will be randomized or not.
        seed: The seed to us to shuffle the list. 0 means no seed. default: 5
        """
        Generator.__init__(self, *args, **kwargs)
        self.command = command
        self.cwd = cwd
        self._max_length = max_length
        self._randomize = randomize
        self._seed = seed
        info ("randomize %s", randomize)
        info ("Seed used %i", seed)
        info("command:%r, cwd:%r" % (command, cwd))

    def _generate(self):
        debug("Running generator command line in %r: %r" % (self.cwd, self.command))
        try:
            process = subprocess.Popen([self.command],
                                       stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       cwd=self.cwd, shell=True, universal_newlines=True)
        except Exception, e:
            exception("Error running external generator: %r: %s", self.command, e)
            return []

        if process == None:
            exception("Failed to create external generator process: %r", self.command)
            return []

        if process.stdin:
            process.stdin.close()
        if process.stderr:
            process.stderr.close()

        def timeout_handler(signum, frame):
            raise Exception()

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)

        lines=[]
        try:
            line=process.stdout.readline()
            while line:
                lines.append(line.replace("\n", ''))
                line=process.stdout.readline()
        except:
            exception("Timeout running external generator '%r'", self.command)
            pass
        finally:
            signal.signal(signal.SIGALRM, old_handler)
        signal.alarm(0)
        process.stdout.close()

        if self._randomize:
            debug ("Randomizing list")
            if self._seed:
                random.seed(self._seed)
            random.shuffle(lines)

        if self._max_length != 0:
            lines = lines[:self._max_length]

        info("Returning %d lines" % len(lines))

        return lines

