SUBDIRS=common lib insanity web tests docs

bin_SCRIPTS=\
  bin/insanity-compare \
  bin/insanity-dbmerge \
  bin/insanity-dumpresults \
  bin/insanity-dumpresults-json \
  bin/insanity-grouper \
  bin/insanity-gtk \
  bin/insanity-run \
  bin/insanity-inspect

insanitygtkdir = $(datadir)/applications
insanitygtk_DATA = insanity-gtk.desktop

insanitysharedir = $(datadir)/insanity
insanityshare_DATA = bin/gdb.instructions

EXTRA_DIST=README $(bin_SCRIPTS) $(insanitygtk_DATA) $(insanityshare_DATA)
