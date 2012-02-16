AC_INIT([insanity],[0.0.1])

AC_CONFIG_SRCDIR([insanity/dbustest.py])

AC_PREREQ(2.53)

AC_CANONICAL_TARGET

AM_INIT_AUTOMAKE([-Wall -Werror foreign subdir-objects])
AC_CONFIG_HEADERS([lib/config.h])

ifdef([AM_SILENT_RULES],[AM_SILENT_RULES])

dnl  3. If the library source code has changed at all since the last
dnl     update, then increment REVISION (`C:R:A' becomes `C:r+1:A').
dnl
dnl  4. If any interfaces have been added, removed, or changed since the
dnl     last update, increment CURRENT, and set REVISION to 0.
dnl
dnl  5. If any interfaces have been added since the last public release,
dnl     then increment AGE.
dnl
dnl  6. If any interfaces have been removed since the last public release,
dnl     then set AGE to 0.

LIBINSANITY_SHARED_VERSION="0:0:0"

AC_PROG_CC_C_O
AC_PROG_LIBTOOL
AC_PROG_GREP

AC_C_CONST

AM_PATH_PYTHON(,HAVE_PYTHON=yes, HAVE_PYTHON=no)
AM_CONDITIONAL(HAVE_PYTHON,test "${HAVE_PYTHON}" = "yes")

# headers

AC_HEADER_STDC
AC_CHECK_HEADERS([unistd.h time.h])

AC_TYPE_SIZE_T

AC_CHECK_PROG(HAVE_PKG_CONFIG,pkg-config,yes)

PKG_CHECK_MODULES(GOBJECT, gobject-2.0)
PKG_CHECK_MODULES(GLIB, glib-2.0)
PKG_CHECK_MODULES(DBUS, dbus-1)

AC_CONFIG_FILES(
  [Makefile]
  [lib/Makefile]
  [insanity/Makefile]
  [web/Makefile]
  [insanity/tests/Makefile]
  [lib/insanity.pc]
  [lib/insanity-uninstalled.pc]
)
AC_OUTPUT

