SUBDIRS=insanity

insanitypcdir=$(libdir)/pkgconfig
 
pcfiles=insanity-@LIBINSANITY_API_VERSION@.pc
pcfiles_uninstalled=insanity-@LIBINSANITY_API_VERSION@-uninstalled.pc

insanitypc_DATA=$(pcfiles)
noinst_DATA=$(pcfiles_uninstalled)

all-local: $(pcfiles) $(pcfiles_uninstalled)

cp_verbose = $(cp_verbose_$(V))
cp_verbose_ = $(cp_verbose_$(AM_DEFAULT_VERBOSITY))
cp_verbose_0 = @echo "  CP     $@";

%-@LIBINSANITY_API_VERSION@.pc: %.pc
	$(cp_verbose_0)cp $< $@
%-@LIBINSANITY_API_VERSION@-uninstalled.pc: %-uninstalled.pc
	$(cp_verbose_0)cp $< $@

EXTRA_DIST=insanity.pc.in insanity-uninstalled.pc.in
