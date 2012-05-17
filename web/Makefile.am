webdir = $(datadir)/insanity/web

install-data-local:
	${mkinstalldirs} "$(DESTDIR)$(webdir)"
#for dir in $(top_srcdir)/web; do \
#  if test -d "$$dir"; then \
#    b=`basename $$dir`; \
#    echo "Found dir: $$dir, to install to $(DESTDIR)$(webdir)/$$b"; \
#    $(mkinstalldirs) $(DESTDIR)$(webdir)/$$b; \
#    for f in "$$dir/"*; do \
#      $(INSTALL_DATA) "$$f" "$(DESTDIR)$(webdir)/$$b"; \
       #    done \
#  fi \
#done
	cp -a $(top_srcdir)/web/* $(DESTDIR)$(webdir)

uninstall-local:
	rm -rf $(DESTDIR)$(webdir)

#EXTRA_DIST = $(wildcard *.py */*.py */*/*.py */*/*/*.py)
