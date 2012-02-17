LIBTOOLFLAGS=--silent

AM_CPPFLAGS=-I $(top_srcdir)/lib

insanityincdir=$(includedir)/insanity

lib_LTLIBRARIES=libinsanity.la

libinsanity_la_SOURCES=\
  insanitytest.c \
  insanitythreadedtest.c

insanityinc_HEADERS=\
  insanitytest.h \
  insanitythreadedtest.h

libinsanity_la_LIBADD=$(GLIB_LIBS) $(GOBJECT_LIBS) $(GTHREAD_LIBS) $(DBUS_LIBS)
libinsanity_la_CFLAGS=$(GLIB_CFLAGS) $(GOBJECT_CFLAGS) $(GTHREAD_CFLAGS) $(DBUS_CFLAGS)

