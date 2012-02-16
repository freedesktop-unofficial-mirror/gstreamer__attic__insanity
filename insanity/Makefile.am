modules = __init__ arguments client dbustest dbustools environment generator log monitor profile scenario test testrun threads type utils

# dummy - this is just for automake to copy py-compile, as it won't do it
# if it doesn't see anything in a PYTHON variable. KateDJ is Python, but
# is installed as a normal script manually. This works as automake doesn't
# do anything for Python sources at build time, only at install time.
noinst_PYTHON=Makefile.am

install-exec-local:
	${mkinstalldirs} "$(DESTDIR)$(pythondir)/insanity"
	for module in $(modules); do \
	  $(INSTALL_DATA) "${top_srcdir}/insanity/$$module.py" "$(DESTDIR)$(pythondir)/insanity"; \
	  if test -z "${DESTDIR}"; then \
	    ${top_srcdir}/py-compile --basedir "${pythondir}/insanity" "$$module.py"; \
	  else \
	    ${top_srcdir}/py-compile --destdir "$(DESTDIR)" --basedir "${pythondir}/insanity" "$$module.py"; \
	  fi \
	done
	${mkinstalldirs} "$(DESTDIR)$(bindir)"

uninstall-local:
	for module in $(modules); do \
	  rm "$(DESTDIR)$(pythondir)/insanity/$$module.py"; \
	  rm "$(DESTDIR)$(pythondir)/insanity/$$module.pyc"; \
	  rm "$(DESTDIR)$(pythondir)/insanity/$$module.pyo"; \
	done
	rmdir "$(DESTDIR)$(pythondir)/insanity"

EXTRA_DIST=$(foreach module, $(modules), $(module).py)

