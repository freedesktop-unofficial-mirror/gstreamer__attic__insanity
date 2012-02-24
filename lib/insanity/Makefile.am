LIBTOOLFLAGS=--silent

AM_CPPFLAGS=-I $(top_srcdir)/lib

insanityincdir=$(includedir)/insanity-@LIBINSANITY_API_VERSION@/insanity

lib_LTLIBRARIES=libinsanity-@LIBINSANITY_API_VERSION@.la

libinsanity_@LIBINSANITY_API_VERSION@_la_SOURCES=\
  insanitytest.c \
  insanitythreadedtest.c

insanityinc_HEADERS=\
  insanity.h \
  insanitydefs.h \
  insanitytest.h \
  insanitythreadedtest.h

noinst_HEADERS =\
  insanityprivate.h

libinsanity_@LIBINSANITY_API_VERSION@_la_LDFLAGS = -version-info @LIBINSANITY_SHARED_VERSION@ -no-undefined -export-symbols-regex \^insanity_.*
libinsanity_@LIBINSANITY_API_VERSION@_la_LIBADD=$(GLIB_LIBS) $(GOBJECT_LIBS) $(GTHREAD_LIBS) $(DBUS_LIBS)
libinsanity_@LIBINSANITY_API_VERSION@_la_CFLAGS=$(GLIB_CFLAGS) $(GOBJECT_CFLAGS) $(GTHREAD_CFLAGS) $(DBUS_CFLAGS)

if HAVE_INTROSPECTION
BUILT_GIRSOURCES = Insanity-@LIBINSANITY_API_VERSION@.gir

gir_headers=$(patsubst %,$(srcdir)/%, $(insanityinc_HEADERS))
gir_sources=$(patsubst %,$(srcdir)/%, $(libinsanity_@LIBINSANITY_API_VERSION@_la_SOURCES))

Insanity-@LIBINSANITY_API_VERSION@.gir: $(INTROSPECTION_SCANNER) libinsanity.la
	$(AM_V_GEN) $(INTROSPECTION_SCANNER) -v --namespace Insanity \
		--nsversion=@LIBINSANITY_API_VERSION@ \
		--warn-all \
		-I$(top_srcdir)/lib \
		-I$(top_builddir) \
		-DIN_GOBJECT_INTROSPECTION=1 \
		--c-include='insanity/insanity.h' \
		--library=libinsanity-@LIBINSANITY_API_VERSION@.la \
		--include=GLib-2.0 \
		--include=GObject-2.0 \
		--libtool="$(top_builddir)/libtool" \
		--pkg glib-2.0 \
		--pkg gobject-2.0 \
		--pkg gmodule-no-export-2.0 \
		--pkg gthread-2.0 \
		--pkg-export insanity-1.0 \
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

