import os, sys
from django.core.wsgi import get_wsgi_application

# Must point to where insanity web has been installed
PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
PYTHON_VERSION = str(sys.version_info[0]) + '.' + str(sys.version_info[1])
sys.path.append(os.path.join(PROJECT_PATH))
sys.path.append(os.path.abspath(os.path.join(PROJECT_PATH, '..')))
sys.path.append(os.path.join(PROJECT_PATH, 'insanityweb'))
sys.path.append(os.path.abspath(os.path.join(PROJECT_PATH, '../../..',
            'lib/python' + PYTHON_VERSION + '/site-packages')))
sys.path.append(os.path.abspath(os.path.join(PROJECT_PATH, '../../..',
            'lib64/python' + PYTHON_VERSION + '/site-packages')))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

# This application object is used by the development server
# as well as any WSGI server configured to use this file.
application = get_wsgi_application()
