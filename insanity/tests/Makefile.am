# All tests MUST start with "insanity-test-". Failure to do so
# will cause failure to be considered by Insanity. Reason is
# to avoid inadvertently running random binaries when probing
# for tests in the wrong place. Only works for mistakes.

LIBTOOLFLAGS=--silent

AM_CPPFLAGS=-I $(top_srcdir)/lib

common_cflags=$(GLIB_CFLAGS) $(GOBJECT_CFLAGS) $(DBUS_CFLAGS)
common_ldadd=$(GLIB_LIBS) $(GOBJECT_LIBS) $(DBUS_LIBS)

insanity_test_blank_SOURCES=insanity-test-blank.c
insanity_test_blank_CFLAGS=$(common_cflags)
insanity_test_blank_LDADD=../../lib/libinsanity.la $(common_ldadd)

noinst_PROGRAMS=insanity-test-blank
