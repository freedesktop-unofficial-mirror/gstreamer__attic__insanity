LIBTOOLFLAGS=--silent

AM_CPPFLAGS=-I $(top_srcdir)/lib

insanityincdir=$(includedir)
insanitypcdir=$(libdir)/pkgconfig

lib_LTLIBRARIES=libinsanity.la

libinsanity_la_SOURCES=\
  insanity.c

insanityinc_HEADERS=\
  insanity.h

insanitypc_DATA=insanity.pc
noinst_DATA=insanity-uninstalled.pc

libinsanity_la_LIBADD=@GLIB_LIBS@ @GOBJECT_LIBS@ @DBUS_LIBS@
libinsanity_la_CFLAGS=@GLIB_CFLAGS@ @GOBJECT_CFLAGS@ @DBUS_CFLAGS@
#libinsanity_la_LDFLAGS=@GLIB_LDFLAGS@ @DBUS_LDFLAGS@

