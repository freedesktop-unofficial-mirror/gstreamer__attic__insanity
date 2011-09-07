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

if os.path.exists('/usr/share/samplemedia'):
    INSANITY_TEST_FOLDERS['/usr/share/samplemedia'] = {
      'name': 'http://samplemedia.linaro.org test media',
      'extra-arguments': {
        'expected-failures': [
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_AMR_1Channel_8k_7.4K.AMR',
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_AC3_6Channel_48k_448K.AC3',
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_AC3_2Channel_48k_384K.AC3',
              ],
            },
            'results': {'duration-available': ['0']},
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/BigBuckBunnyAttribution.txt',
                'file:///usr/share/samplemedia/sampleinfo.csv',
              ],
            },
            'results': {
              'is-media-type': ['0'],
              'no-errors-seen': ['0'],
              'reached-initial-state': ['None'],
              'duration-available': ['None'],
              'stream-duration-identical': ['None'],
              'available-demuxer': ['None'],
              'all-fixed-caps-streams': ['None'],
              'all-streams-decodable': ['None'],
            },
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_FLAC_2Channel_48k_561K.FLAC',
              ],
            },
            'results': {
              'no-errors-seen': ['0'],
              'reached-initial-state': ['None'],
              'correct-final-buffer': ['None'],
              'correct-initial-buffer': ['None'],
              'correct-newsegment-format': ['None'],
              'correct-newsegment-position': ['None'],
              'correct-newsegment-start': ['None'],
              'correct-newsegment-stop': ['None'],
              'first-buffer-after-newsegment': ['None'],
            },
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/H264/big_buck_bunny_1080p_H264_AAC_25fps_7200K.MP4',
                'file:///usr/share/samplemedia/H264/big_buck_bunny_720p_H264_AAC_25fps_3400K.MP4',
                'file:///usr/share/samplemedia/H264/big_buck_bunny_480p_H264_AAC_25fps_1800K.MP4',
              ],
              'instance-name': ['stream1.from_near_end'],
            },
            'results': {'correct-newsegment-stop': ['0']},
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/VC1/big_buck_bunny_480p_VC1_WMA3_25fps_2100K.WMV',
                'file:///usr/share/samplemedia/VC1/big_buck_bunny_720p_VC1_WMA3_25fps_4200K.WMV',
              ],
              'instance-name': ['stream1.from_near_end',
                'stream2.from_near_end'],
            },
            'results': {
              'correct-final-buffer': ['None'],
              'correct-initial-buffer': ['None'],
              'correct-newsegment-format': ['None'],
              'correct-newsegment-position': ['None'],
              'correct-newsegment-start': ['None'],
              'correct-newsegment-stop': ['None'],
              'first-buffer-after-newsegment': ['None'],
            },
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_AAC_2Channel_44.1k_128K.AAC',
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_AAC_2Channel_48k_165K.AAC',
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_AAC_6Channel_48k_253K.AAC',
              ],
              'instance-name': ['stream1.from_near_end'],
            },
            'results': {
              'correct-final-buffer': ['None'],
              'correct-initial-buffer': ['None'],
              'first-buffer-after-newsegment': ['None'],
            },
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/MPEG2/big_buck_bunny_480p_MPEG2_MP2_25fps_1800K.MPG',
                'file:///usr/share/samplemedia/MPEG2/big_buck_bunny_720p_MPEG2_MP2_25fps_3600K.MPG',
              ],
              'instance-name': ['stream2.from_middle'],
            },
            'results': {
              'correct-final-buffer': ['None'],
              'correct-initial-buffer': ['None'],
              'first-buffer-after-newsegment': ['None'],
            },
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/MPEG2/big_buck_bunny_480p_MPEG2_MP2_25fps_1800K.MPG',
              ],
              'instance-name': ['stream2.from_near_end'],
            },
            'results': {
              'correct-final-buffer': ['None'],
              'correct-initial-buffer': ['None'],
              'first-buffer-after-newsegment': ['None'],
            },
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/VP8/big_buck_bunny_1080p_VP8_VORBIS_25fps_7800K.WebM',
                'file:///usr/share/samplemedia/VP8/big_buck_bunny_480p_VP8_VORBIS_25fps_1900K.WebM',
                'file:///usr/share/samplemedia/VP8/big_buck_bunny_720p_VP8_VORBIS_25fps_3900K.WebM',
              ],
              'instance-name': [
                'stream1.from_start',
              ],
            },
            'results': {'correct-initial-buffer': ['0']},
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/MPEG2/big_buck_bunny_1080p_MPEG2_MP2_25fps_6600K.MPG',
                'file:///usr/share/samplemedia/MPEG2/big_buck_bunny_480p_MPEG2_MP2_25fps_1800K.MPG',
                'file:///usr/share/samplemedia/MPEG2/big_buck_bunny_720p_MPEG2_MP2_25fps_3600K.MPG',
              ],
              # All instances fail this check.
            },
            'results': {'correct-initial-buffer': ['0']},
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_WMA2_2Channel_44.1k_128K.WMA',
                'file:///usr/share/samplemedia/VC1/big_buck_bunny_720p_VC1_WMA3_25fps_4200K.WMV',
                'file:///usr/share/samplemedia/VC1/big_buck_bunny_1080p_VC1_WMA3_25fps_8600K.WMV',
                'file:///usr/share/samplemedia/VC1/big_buck_bunny_480p_VC1_WMA3_25fps_2100K.WMV',
              ],
              'instance-name': ['stream1.from_middle'],
            },
            'results': {'correct-initial-buffer': ['0']},
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_WMA2_2Channel_44.1k_128K.WMA',
              ],
              'instance-name': ['stream1.from_near_end'],
            },
            'results': {
              'correct-initial-buffer': ['0'],
              'correct-final-buffer': ['0'],
            },
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/H264/big_buck_bunny_1080p_H264_AAC_25fps_7200K.MP4',
                'file:///usr/share/samplemedia/H264/big_buck_bunny_480p_H264_AAC_25fps_1800K.MP4',
                'file:///usr/share/samplemedia/H264/big_buck_bunny_720p_H264_AAC_25fps_3400K.MP4',
                'file:///usr/share/samplemedia/MPEG4/big_buck_bunny_720p_MPEG4_MP3_25fps_3300K.AVI',
                'file:///usr/share/samplemedia/MPEG4/big_buck_bunny_1080p_MPEG4_MP3_25fps_7600K.AVI',
                'file:///usr/share/samplemedia/MPEG4/big_buck_bunny_480p_MPEG4_MP3_25fps_1600K.AVI',
                '',
              ],
              'instance-name': ['stream1.from_start', 'stream1.from_middle', 'stream1.from_near_end'],
            },
            'results': {'correct-final-buffer': ['0']},
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/Audio/big_buck_bunny_MP3_2Channel_44.1k_128K.MP3',
                'file:///usr/share/samplemedia/MPEG4/big_buck_bunny_1080p_MPEG4_MP3_25fps_7600K.AVI',
                'file:///usr/share/samplemedia/VP8/big_buck_bunny_720p_VP8_VORBIS_25fps_3900K.WebM',
                'file:///usr/share/samplemedia/VP8/big_buck_bunny_480p_VP8_VORBIS_25fps_1900K.WebM',
              ],
              'instance-name': ['stream1.from_near_end'],
            },
            'results': {'correct-final-buffer': ['0']},
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/VP8/big_buck_bunny_720p_VP8_VORBIS_25fps_3900K.WebM',
                'file:///usr/share/samplemedia/VP8/big_buck_bunny_480p_VP8_VORBIS_25fps_1900K.WebM',
                'file:///usr/share/samplemedia/VP8/big_buck_bunny_1080p_VP8_VORBIS_25fps_7800K.WebM',
                'file:///usr/share/samplemedia/MPEG4/big_buck_bunny_1080p_MPEG4_MP3_25fps_7600K.AVI',
              ],
              'instance-name': ['stream2.from_near_end'],
            },
            'results': {'correct-final-buffer': ['0']},
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/MPEG2/big_buck_bunny_1080p_MPEG2_MP2_25fps_6600K.MPG',
                'file:///usr/share/samplemedia/MPEG2/big_buck_bunny_480p_MPEG2_MP2_25fps_1800K.MPG',
                'file:///usr/share/samplemedia/MPEG2/big_buck_bunny_720p_MPEG2_MP2_25fps_3600K.MPG',
              ],
              'instance-name': ['stream1.from_start', 'stream2.from_start'],
            },
            'results': {'correct-newsegment-position': ['0'],
              'correct-newsegment-start': ['0']},
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/VC1/big_buck_bunny_1080p_VC1_WMA3_25fps_8600K.WMV',
              ],
              'instance-name': ['stream1.from_near_end'],
            },
            'results': {
              'correct-initial-buffer': ['0'],
              'correct-final-buffer': ['0'],
            },
          },
          {
            'arguments': {
              'uri': [
                'file:///usr/share/samplemedia/VC1/big_buck_bunny_1080p_VC1_WMA3_25fps_8600K.WMV',
              ],
              'instance-name': ['stream1.from_start', 'stream2.from_start'],
            },
            'results': {
              'no-timeout': ['0', '1'],
              'reached-initial-state': ['None', '1'],
              'correct-final-buffer': ['None', '1'],
            },
          },
        ],
      },
    }
