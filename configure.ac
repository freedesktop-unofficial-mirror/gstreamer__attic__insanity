AC_INIT([insanity],[0.0.1])

AC_CONFIG_SRCDIR([insanity/dbustest.py])

AC_PREREQ(2.53)

AC_CANONICAL_TARGET

AM_INIT_AUTOMAKE([-Wall -Werror foreign subdir-objects])
AM_MAINTAINER_MODE

AC_CONFIG_HEADERS([lib/insanity/config.h])

m4_ifdef([AM_SILENT_RULES],[AM_SILENT_RULES([yes])],
  [AM_DEFAULT_VERBOSITY=1
   AC_SUBST(AM_DEFAULT_VERBOSITY)])

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
AC_SUBST(LIBINSANITY_SHARED_VERSION)
LIBINSANITY_API_VERSION=1.0
AC_SUBST(LIBINSANITY_API_VERSION)

AC_PROG_CC
AC_PROG_CC_STDC
AC_PROG_CC_C_O
AC_PROG_LIBTOOL
AC_PROG_GREP

AC_C_CONST

# Check compiler warning flags
WARNING_CFLAGS=""
for i in -Wall -Wdeclaration-after-statement -Wvla -Wpointer-arith -Wmissing-declarations -Wmissing-prototypes -Wredundant-decls -Wundef -Wwrite-strings -Wformat-nonliteral -Wformat-security -Wold-style-definition -Winit-self -Wmissing-include-dirs -Waddress -Waggregate-return -Wno-multichar -Wnested-externs; do
    AS_COMPILER_FLAG($i, WARNING_CFLAGS="$WARNING_CFLAGS $i")
done

AC_SUBST(WARNING_CFLAGS)

AM_PATH_PYTHON(,HAVE_PYTHON=yes, HAVE_PYTHON=no)
AM_CONDITIONAL(HAVE_PYTHON,test "${HAVE_PYTHON}" = "yes")

dnl Add parameters for aclocal
AC_SUBST(ACLOCAL_AMFLAGS, "-I m4 -I common/m4")

# headers

AC_HEADER_STDC

# Check if we can collect CPU usage information
AC_CHECK_FUNCS([getrusage], HAVE_GETRUSAGE=yes, HAVE_GETRUSAGE=no)
AC_CHECK_FUNCS([gettimeofday], HAVE_GETTIMEOFDAY=yes, HAVE_GETTIMEOFDAY=no)
AC_CHECK_HEADER([sys/time.h], HAVE_SYS_TIME_H=yes, HAVE_SYS_TIME_H=no)
AC_CHECK_HEADER([sys/resource.h], HAVE_SYS_RESOURCE_H=yes, HAVE_SYS_RESOURCE_H=no)
if test x$HAVE_GETRUSAGE = "xyes" -a x$HAVE_GETTIMEOFDAY = "xyes" -a x$HAVE_SYS_TIME_H = "xyes" -a x$HAVE_SYS_RESOURCE_H = "xyes"; then
    AC_DEFINE(USE_CPU_LOAD, 1, [Defined if CPU usage information can be collected])
fi

AC_CHECK_PROG(HAVE_PKG_CONFIG,pkg-config,yes)

PKG_CHECK_MODULES(GLIB, glib-2.0)
PKG_CHECK_MODULES(GOBJECT, gobject-2.0)
PKG_CHECK_MODULES(GTHREAD, gthread-2.0)
PKG_CHECK_MODULES(DBUS, dbus-1)

dnl check for gobject-introspection
GOBJECT_INTROSPECTION_CHECK([1.31.1])

dnl check for gtk-doc
GTK_DOC_CHECK([1.3])

dnl Check for documentation xrefs
GLIB_PREFIX="`$PKG_CONFIG --variable=prefix glib-2.0`"
AC_SUBST(GLIB_PREFIX)

AC_CONFIG_FILES(
  [Makefile]
  [common/Makefile]
  [common/m4/Makefile]
  [lib/Makefile]
  [lib/insanity/Makefile]
  [insanity/Makefile]
  [insanity/generators/Makefile]
  [insanity/storage/Makefile]
  [web/Makefile]
  [tests/Makefile]
  [docs/Makefile]
  [docs/insanity/Makefile]
  [docs/insanity/version.xml]
  [docs/random/Makefile]
  [lib/insanity.pc]
  [lib/insanity-uninstalled.pc]
)
AC_OUTPUT

