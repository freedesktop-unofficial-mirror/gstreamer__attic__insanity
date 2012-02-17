LIBTOOLFLAGS=--silent

AM_CPPFLAGS=-I $(top_srcdir)/lib

insanityincdir=$(includedir)
insanitypcdir=$(libdir)/pkgconfig

lib_LTLIBRARIES=libinsanity.la

libinsanity_la_SOURCES=\
  insanity.c \
  insanitythreadedtest.c

insanityinc_HEADERS=\
  insanity.h \
  insanitythreadedtest.h

insanitypc_DATA=insanity.pc
noinst_DATA=insanity-uninstalled.pc

libinsanity_la_LIBADD=$(GLIB_LIBS) $(GOBJECT_LIBS) $(GTHREAD_LIBS) $(DBUS_LIBS)
libinsanity_la_CFLAGS=$(GLIB_CFLAGS) $(GOBJECT_CFLAGS) $(GTHREAD_CFLAGS) $(DBUS_CFLAGS)

