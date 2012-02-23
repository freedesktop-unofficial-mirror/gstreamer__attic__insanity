modules = __init__ filesystem playlist external

# dummy - this is just for automake to copy py-compile, as it won't do it
# if it doesn't see anything in a PYTHON variable. KateDJ is Python, but
# is installed as a normal script manually. This works as automake doesn't
# do anything for Python sources at build time, only at install time.
noinst_PYTHON=Makefile.am

install-exec-local:
	${mkinstalldirs} "$(DESTDIR)$(pythondir)/insanity/generators"
	for module in $(modules); do \
	  $(INSTALL_DATA) "${top_srcdir}/insanity/generators/$$module.py" "$(DESTDIR)$(pythondir)/insanity/generators"; \
	  if test -z "${DESTDIR}"; then \
	    ${top_srcdir}/py-compile --basedir "${pythondir}/insanity/generators" "$$module.py"; \
	  else \
	    ${top_srcdir}/py-compile --destdir "$(DESTDIR)" --basedir "${pythondir}/insanity/generators" "$$module.py"; \
	  fi \
	done
	${mkinstalldirs} "$(DESTDIR)$(bindir)"

uninstall-local:
	for module in $(modules); do \
	  rm "$(DESTDIR)$(pythondir)/insanity/generators/$$module.py"; \
	  rm "$(DESTDIR)$(pythondir)/insanity/generators/$$module.pyc"; \
	  rm "$(DESTDIR)$(pythondir)/insanity/generators/$$module.pyo"; \
	done
	rmdir "$(DESTDIR)$(pythondir)/insanity/generators"

EXTRA_DIST=$(foreach module, $(modules), $(module).py)

