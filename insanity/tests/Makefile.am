LIBTOOLFLAGS=--silent

AM_CPPFLAGS=-I $(top_srcdir)/lib

common_cflags=$(GLIB_CFLAGS) $(GOBJECT_CFLAGS) $(DBUS_CFLAGS)
common_ldadd=$(GLIB_LIBS) $(GOBJECT_LIBS) $(DBUS_LIBS)

blankc_SOURCES=blankc.c
blankc_CFLAGS=$(common_cflags)
blankc_LDADD=../../lib/libinsanity.la $(common_ldadd)

noinst_PROGRAMS=blankc
