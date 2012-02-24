LIBTOOLFLAGS=--silent

AM_CPPFLAGS=-I $(top_srcdir)/lib

insanityincdir=$(includedir)/insanity

lib_LTLIBRARIES=libinsanity.la

libinsanity_la_SOURCES=\
  insanitytest.c \
  insanitythreadedtest.c

insanityinc_HEADERS=\
  insanity.h \
  insanitydefs.h \
  insanitytest.h \
  insanitythreadedtest.h

libinsanity_la_LDFLAGS = -no-undefined -export-symbols-regex \^insanity_.*
libinsanity_la_LIBADD=$(GLIB_LIBS) $(GOBJECT_LIBS) $(GTHREAD_LIBS) $(DBUS_LIBS)
libinsanity_la_CFLAGS=$(GLIB_CFLAGS) $(GOBJECT_CFLAGS) $(GTHREAD_CFLAGS) $(DBUS_CFLAGS)

if HAVE_INTROSPECTION
BUILT_GIRSOURCES = Insanity-1.0.gir

gir_headers=$(patsubst %,$(srcdir)/%, $(insanityinc_HEADERS))
gir_sources=$(patsubst %,$(srcdir)/%, $(libinsanity_la_SOURCES))

Insanity-1.0.gir: $(INTROSPECTION_SCANNER) libinsanity.la
	$(AM_V_GEN) $(INTROSPECTION_SCANNER) -v --namespace Insanity \
		--nsversion=0.0.1 \
		--warn-all \
		-I$(top_srcdir)/lib \
		-I$(top_builddir) \
		-DIN_GOBJECT_INTROSPECTION=1 \
		--c-include='insanity/insanity.h' \
		--library=libinsanity.la \
		--include=GLib-2.0 \
		--include=GObject-2.0 \
		--libtool="$(top_builddir)/libtool" \
		--pkg glib-2.0 \
		--pkg gobject-2.0 \
		--pkg gmodule-no-export-2.0 \
		--pkg gthread-2.0 \
		--pkg-export insanity \
		--output $@ \
		$(gir_headers) \
		$(gir_sources)

# INTROSPECTION_GIRDIR/INTROSPECTION_TYPELIBDIR aren't the right place to
# install anything - we need to install inside our prefix.
girdir = $(datadir)/gir-1.0
gir_DATA = $(BUILT_GIRSOURCES)

typelibsdir = $(libdir)/girepository-1.0/

typelibs_DATA = $(BUILT_GIRSOURCES:.gir=.typelib)

%.typelib: %.gir $(INTROSPECTION_COMPILER)
	$(AM_V_GEN)$(INTROSPECTION_COMPILER) --includedir=$(srcdir) --includedir=$(builddir) $(INTROSPECTION_COMPILER_OPTS) $< -o $(@F)

CLEANFILES = $(BUILT_GIRSOURCES) $(typelibs_DATA)
endif

