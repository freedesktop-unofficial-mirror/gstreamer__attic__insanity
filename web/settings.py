import os
import sys

PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
DATA_PATH = os.path.join(PROJECT_PATH, '..')

if not os.access(DATA_PATH, os.W_OK):
    sys.stderr.write("%s is not writable. Trying xdg-data-path.\n" %
            DATA_PATH)
    try:
        import xdg.BaseDirectory
        DATA_PATH = xdg.BaseDirectory.save_data_path("insanity")
    except (ImportError, OSError):
        sys.stderr.write("xdg.BaseDirectory doesn't exist or doesn't work.\n")
        DATA_PATH = os.getcwd()
    sys.stderr.write("Data will be saved to %s.\n" % DATA_PATH)

# Django settings for web project.

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(DATA_PATH, 'testrun.db'),
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': ''
    }
}

# Local time zone for this installation. Choices can be found here:
# http://www.postgresql.org/docs/8.1/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
# although not all variations may be possible on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Madrid'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(PROJECT_PATH, 'site_media')

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = '/media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/admin/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'vma@9ngdk2_csfj890u234e0q-ps-lc36f#5c0j8e4hx%r'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
)

ROOT_URLCONF = 'web.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(PROJECT_PATH, 'templates')
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'insanityweb'
)

# A map of folders that the tests can be run in, with any extra arguments that
# need to be passed to the tests:
#
INSANITY_TEST_FOLDERS = {
#     '/path/to/test-media/': {
#         'name': 'Test Media Folder',
#         'extra-arguments': {
#             'expected-failures': [ # patterns of checkitem/arguments to match
#                 {
#                     'arguments': {
#                         'uri': [
#                             'file:///path/to/test/media/not-a-media-file.zip',
#                             'file:///path/to/test/media/also-not-a-media-file.zip',
#                         ]
#                     }
#                     'results': {'is-media-type': ['0']}
#                 }
#             ]
#         }
#     }
}
