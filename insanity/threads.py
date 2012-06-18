# GStreamer QA system
#
#       threads.py
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
Convenience methods and classes for multi-threading
"""

# code from pitivi/threads.py

import Queue
import threading
import gobject
import traceback
from insanity.log import error, warning, debug

class Thread(threading.Thread, gobject.GObject):
    """
    GObject-powered thread
    """

    __gsignals__ = {
        "done" : ( gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   ( ))
        }

    def __init__(self):
        threading.Thread.__init__(self)
        gobject.GObject.__init__(self)

    def stop(self):
        """ stop the thread, do not override """
        self.abort()
        self.emit("done")

    def run(self):
        """ thread processing """
        self.process()
        gobject.idle_add(self.emit, "done")

    def process(self):
        """ Implement this in subclasses """
        raise NotImplementedError

    def abort(self):
        """ Abort the thread. Subclass have to implement this method ! """
        pass

gobject.type_register(Thread)

class CallbackThread(Thread):

    def __init__(self, callback, *args, **kwargs):
        Thread.__init__(self)
        self.callback = callback
        self.args = args
        self.kwargs = kwargs

    def process(self):
        self.callback(*self.args, **self.kwargs)

gobject.type_register(CallbackThread)

class ActionQueueThread(threading.Thread):
    """
    Thread for serializing actions.

    Actions can be added in queueAction()

    If you no longer wish to use this thread, add a
    notifier callback by using queueFinalAction().
    The thread will exit after calling that final action.

    If you wish to abort the thread, just call abort() and
    the Thread will return as soon as possible.
    """

    def __init__(self):
        threading.Thread.__init__(self)
        self._lock = threading.Condition()
        # if set to True, the thread will exit even though
        # there are remaining actions
        self._abort = False
        # if set to True, the thread will exit when there's
        # no longer any actions in the queue.
        self._exit = False
        # list of callables with arguments/kwargs
        self._queue = []

    def run(self):
        # do something
        debug("Starting in process...")
        self._lock.acquire()
        while True:
            debug("queue:%d _exit:%r _abort:%r",
                    len(self._queue), self._exit,
                    self._abort)
            if self._abort:
                debug("aborting")
                self._lock.release()
                return

            while len(self._queue) == 0:
                debug("queue:%d _exit:%r _abort:%r",
                        len(self._queue), self._exit,
                        self._abort)
                if self._exit:
                    self._lock.release()
                    return
                debug("waiting for cond")
                self._lock.wait()
                debug("cond was triggered")
                if self._abort:
                    self._lock.release()
                    return
            method, args, kwargs = self._queue.pop(0)
            self._lock.release()
            try:
                debug("about to call %r", method)
                method(*args, **kwargs)
            except:
                error("There was a problem calling %r", method)
                error(traceback.format_exc())
            finally:
                debug("Finished calling %r, re-acquiring lock",
                      method)
            self._lock.acquire()

    def abort(self):
        self._lock.acquire()
        self._abort = True
        self._lock.notify()
        self._lock.release()

    def queueAction(self, method, *args, **kwargs):
        """
        Queue an action.
        Returns True if the action was queued, else False.
        """
        res = False
        debug("about to queue %r", method)
        self._lock.acquire()
        debug("Got lock to queue, _abort:%r, _exit:%r",
                self._abort, self._exit)
        if not self._abort and not self._exit:
            self._queue.append((method, args, kwargs))
            self._lock.notify()
            res = True
        debug("about to release lock")
        self._lock.release()
        debug("lock released, result:%r", res)
        return res

    def queueFinalAction(self, method, *args, **kwargs):
        """
        Set a last action to be called.
        """
        res = False
        debug("about to queue %r", method)
        self._lock.acquire()
        debug("Got lock to queue, _abort:%r, _exit:%r",
                self._abort, self._exit)
        if not self._abort and not self._exit:
            self._queue.append((method, args, kwargs))
            res = True
        self._exit = True
        self._lock.notify()
        debug("about to release lock")
        self._lock.release()
        debug("lock released, result:%r", res)
        return res

class FileReadingThread(threading.Thread):
    """
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    """

    def __init__(self, fd, queue):
        threading.Thread.__init__(self)
        self._fd = fd
        self._queue = queue

    def setQueue(self, queue):
        old_q = self._queue
        old_q.mutex.acquire()
        self._queue = queue
        old_q.mutex.release()

    def run(self):
        '''The body of the tread: read lines and put them on the queue.'''
        while True:
            line =  self._fd.readline()
            self._queue.put(line)
            if not line:
                break

class RedirectTerminalOuputThread(threading.Thread):
    """
    Class implementing terminal stderr/stdout redirection to a file
    allowing the redirection to be changed during the lifetime of the
    subprocess.

    This needs to be done in separate threads to avoid deadlocks
    """

    def __init__(self, process, outfile_path, errfile_path):
        threading.Thread.__init__(self)
        self._lock = threading.Lock()
        # if set to True, the thread will exit even though
        # there are remaining actions
        self._abort = False
        # if set to True, the thread will exit
        self._exit = False
        # list of callables with arguments/kwargs
        self._process = process

        # The only way to avoid deadlocks is to have one thread for each of
        # stdout and stderr (Queue is thread safe)
        self.stdout_queue = Queue.Queue()
        self.stdout_reader = FileReadingThread(process.stdout, self.stdout_queue)
        self.stdout_reader.start()
        self.stderr_queue = Queue.Queue()
        self.stderr_reader = FileReadingThread(process.stderr, self.stderr_queue)
        self.stderr_reader.start()

        # We are working with the paths here because the file descriptor
        # are not shared between the various threads
        self.setStdoutFile(outfile_path)
        self.setStderrFile(outfile_path)

    def setStderrFile(self, errfile_path):
        self._lock.acquire()

        # We change the reader queue as we want to empty the current one
        n_queue = Queue.Queue()
        self.stderr_reader.setQueue(n_queue)
        self._emptyErrQueue()
        self.stderr_queue = n_queue
        self._stderrfile = open(errfile_path, "a")
        self._lock.release()

    def setStdoutFile(self, outfile_path):
        self._lock.acquire()

        # We change the reader queue as we want to empty the current one
        n_queue = Queue.Queue()
        self.stdout_reader.setQueue(n_queue)
        self._emptyOutQueue()
        self.stdout_queue = n_queue

        self._stdoutfile = open(outfile_path, "a")
        self._lock.release()

    def _emptyErrQueue(self):
        while not self.stderr_queue.empty():
            self._write_err(self.stderr_queue.get())

    def _emptyOutQueue(self):
        while not self.stdout_queue.empty():
            self._write_out(self.stdout_queue.get())

    def _finalize(self):
        #Empty all the queue and make sure the reader thread are done
        self._emptyErrQueue()
        self._emptyOutQueue()
        self.stdout_reader.join()
        self.stderr_reader.join()


    def run(self):
        debug("Starting in process...")

        while True:
            self._lock.acquire()
            if self._exit:
                self._lock.release()

                debug("exiting %s", self.stdout_queue)
                self._finalize()
                return

            if not self.stderr_queue.empty():
                self._write_err(self.stderr_queue.get())

            if not self.stdout_queue.empty():
                self._write_out(self.stdout_queue.get())

            if self._abort:
                self._lock.release()
                debug("aborting")
                self._finalize()
                return

            self._lock.release()

    def _write_err(self, data):
        if data and self._stderrfile:
            self._stderrfile.writelines(data)

    def _write_out(self, data):
        if data and self._stderrfile:
            self._stdoutfile.writelines(data)

    def exit(self):
        self._lock.acquire()
        self._exit = True
        self._lock.release()

    def abort(self):
        self._lock.acquire()
        self._abort = True
        self._lock.release()


class ThreadMaster(gobject.GObject):
    """
    Controls all thread
    """

    def __init__(self):
        gobject.GObject.__init__(self)
        self.threads = []

    def addThread(self, threadclass, *args):
        # IDEA : We might need a limit of concurrent threads ?
        # ... or some priorities ?
        # FIXME : we should only accept subclasses of our Thread class
        debug("Adding thread of type %r" % threadclass)
        thread = threadclass(*args)
        thread.connect("done", self._threadDoneCb)
        self.threads.append(thread)
        debug("starting it...")
        thread.start()
        debug("started !")

    def _threadDoneCb(self, thread):
        debug("thread %r is done" % thread)
        self.threads.remove(thread)

    def stopAllThreads(self):
        debug("stopping all threads")
        joinedthreads = 0
        while(joinedthreads < len(self.threads)):
            for thread in self.threads:
                debug("Trying to stop thread %r" % thread)
                try:
                    thread.join()
                    joinedthreads += 1
                except:
                    warning("what happened ??")


