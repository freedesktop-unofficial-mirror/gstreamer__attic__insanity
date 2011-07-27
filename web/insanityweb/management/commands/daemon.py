from django.core.management.base import BaseCommand, CommandError
from django.core.management.commands.runserver import BaseRunserverCommand

from django.core.handlers.wsgi import WSGIHandler
from django.core.servers.basehttp import WSGIRequestHandler, WSGIServer, AdminMediaHandler, WSGIServerException

import gtk
import gobject

import sys
import os

# Need to initialise it immediately because insanity.Client runs its
# own mainloop, creates DBus service, etc. We also need to properly
# quit it before exiting
from insanityweb.runner import runner

class Command(BaseRunserverCommand):
    args = ''
    help = 'Start the Insanity integrated web + test runner'

    def run(self, *args, **options):
        try:
            server = WSGIServer((self.addr, int(self.port)), WSGIRequestHandler)
        except WSGIServerException, e:
            sys.stderr.write("ERROR: " + str(e) + "\n")
            runner.quit()
            return

        # alidate models
        sys.stdout.write("Validating models...\n")
        self.validate(display_num_errors=True)

        handler = AdminMediaHandler(WSGIHandler())
        server.set_app(handler)
        server.timeout = 0.1

        orig_handle_timeout = server.handle_timeout
        timeout_happened = [False]

        def handle_timeout(*args, **kwargs):
            orig_handle_timeout(*args, **kwargs)
            timeout_happened[0] = True

        server.handle_timeout = handle_timeout

        def django_driver():
            timeout_happened[0] = False
            while not timeout_happened[0]:
                try:
                    server.handle_request()
                except KeyboardInterrupt:
                    sys.stdout.write("Stopping the server...\n")
                    runner.quit()
                    gtk.main_quit()
                    return False
                except Exception, e:
                    sys.stderr.write("ERROR: " + str(e) + "\n")
                    return True
            return True

        gobject.idle_add(django_driver)

        sys.stdout.write("Running the server...\n")
        gtk.main()
