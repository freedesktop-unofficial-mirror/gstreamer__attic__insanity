/* Insanity QA system

       insanitytest.c

 Copyright (c) 2012, Collabora Ltd <vincent@collabora.co.uk>

 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU Lesser General Public
 License as published by the Free Software Foundation; either
 version 2.1 of the License, or (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 Lesser General Public License for more details.

 You should have received a copy of the GNU Lesser General Public
 License along with this program; if not, write to the
 Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
 Boston, MA 02110-1301, USA.
*/

/**
 * SECTION:insanitytest
 * @short_description: Basic Test
 * @see_also: #InsanityThreadedTest
 *
 * %TODO.
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include "insanitytest.h"
#include "insanityprivate.h"

#include <glib/gstdio.h>
#include <dbus/dbus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <errno.h>

/* TODO:
  - logs ?
  - gather timings at every checklist item validated ?
*/

#ifdef USE_CPU_LOAD
#include <sys/time.h>
#include <sys/resource.h>
#endif

#define TEST_TIMEOUT (15)

enum
{
  PROP_0,
  PROP_NAME,
  PROP_DESCRIPTION,
  PROP_FULL_DESCRIPTION,
  N_PROPERTIES
};

/* if global vars are good enough for gstreamer, it's good enough for insanity */
static guint setup_signal;
static guint start_signal;
static guint stop_signal;
static guint teardown_signal;
static GParamSpec *properties[N_PROPERTIES] = { NULL, };

/* Taken and adapted from GStreamer */
#define SECOND ((guint64)1000000)
#define TIME_FORMAT "u:%02u:%02u.%09u"
#define TIME_ARGS(t) \
        (guint) (((guint64)(t)) / (SECOND * 60 * 60)), \
        (guint) ((((guint64)(t)) / (SECOND * 60)) % 60), \
        (guint) ((((guint64)(t)) / SECOND) % 60), \
        (guint) (((guint64)(t)) % SECOND)

static const char *const log_level_names[] = {
  "none", "info", "debug", "spam"
};

#if GLIB_CHECK_VERSION(2,31,0)
#define USE_NEW_GLIB_MUTEX_API
#endif

typedef enum RunLevel
{
  rl_idle,
  rl_setup,
  rl_started
} RunLevel;

struct _InsanityTestPrivateData
{
  DBusConnection *conn;
#ifdef USE_CPU_LOAD
  struct timeval start;
  struct rusage rusage;
#endif
  char *name;
  GHashTable *args;
  int cpu_load;
  gboolean exit;
  GHashTable *filename_cache;
  char *tmpdir;
  gboolean keep_unnamed_output_files;
#ifdef USE_NEW_GLIB_MUTEX_API
  GMutex lock;

  GMutex signal_lock;
  GCond cond;
#else
  GMutex *lock;

  GMutex *signal_lock;
  GCond *cond;
#endif
  gboolean standalone;
  GHashTable *checklist_results;
  RunLevel runlevel;
  gint iteration;
  InsanityLogLevel default_log_level;
  GHashTable *log_levels;
  guint64 start_time;

  /* test metadata */
  char *test_name;
  char *test_desc;
  char *test_full_desc;
  GHashTable *test_checklist;
  GHashTable *test_arguments;
  GHashTable *test_extra_infos;
  GHashTable *test_output_files;

  /* timeout for standalone mode */
  gint timeout;
  gint64 timeout_end_time;
};

#ifdef USE_NEW_GLIB_MUTEX_API
#define LOCK(test) g_mutex_lock(&(test)->priv->lock)
#define UNLOCK(test) g_mutex_unlock(&(test)->priv->lock)

#define LOCK_SIGNAL(test) g_mutex_lock(&(test)->priv->signal_lock)
#define UNLOCK_SIGNAL(test) g_mutex_unlock(&(test)->priv->signal_lock)
#define SIGNAL(test) g_cond_signal(&(test)->priv->cond)

static inline gboolean
WAIT_TIMEOUT (InsanityTest * test)
{
  if (test->priv->timeout > 0) {
    gint64 current_time;
    gboolean signalled;

    do {
      test->priv->timeout_end_time =
          g_get_monotonic_time () + test->priv->timeout * G_TIME_SPAN_SECOND;
      signalled =
          g_cond_wait_until (&test->priv->cond, &test->priv->signal_lock,
          test->priv->timeout_end_time);
      current_time = g_get_monotonic_time ();
    } while (!signalled && current_time < test->priv->timeout_end_time);

    return !signalled;
  } else {
    g_cond_wait (&test->priv->cond, &test->priv->signal_lock);
    return FALSE;
  }
}
#else
#define LOCK(test) g_mutex_lock((test)->priv->lock)
#define UNLOCK(test) g_mutex_unlock((test)->priv->lock)

#define LOCK_SIGNAL(test) g_mutex_lock((test)->priv->signal_lock)
#define UNLOCK_SIGNAL(test) g_mutex_unlock((test)->priv->signal_lock)
#define SIGNAL(test) g_cond_signal((test)->priv->cond)

static inline gboolean
WAIT_TIMEOUT (InsanityTest * test)
{
  if (test->priv->timeout > 0) {
    gint64 current_time;
    GTimeVal tmp;
    gboolean signalled;

    do {
      test->priv->timeout_end_time =
          g_get_monotonic_time () + test->priv->timeout * G_TIME_SPAN_SECOND;
      tmp.tv_sec = test->priv->timeout_end_time / G_USEC_PER_SEC;
      tmp.tv_usec = test->priv->timeout_end_time % G_USEC_PER_SEC;
      signalled =
          g_cond_timed_wait (test->priv->cond, test->priv->signal_lock, &tmp);
      current_time = g_get_monotonic_time ();
    } while (!signalled && current_time < test->priv->timeout_end_time);

    return !signalled;
  } else {
    g_cond_wait (test->priv->cond, test->priv->signal_lock);
    return FALSE;
  }
}
#endif

typedef struct _Argument
{
  gboolean global;
  char *description;
  GValue default_value;
  char *full_description;
} Argument;

typedef struct _ChecklistItem
{
  gboolean global;
  char *label;
  char *description;
  char *likely_error;
} ChecklistItem;

typedef struct _OutputFileItem
{
  char *description;
  gboolean global;
} OutputFileItem;

static void
free_output_file_item (void *ptr)
{
  OutputFileItem *of = ptr;

  g_free (of->description);

  g_slice_free1 (sizeof (OutputFileItem), ptr);
}

static void
free_checklist_item (void *ptr)
{
  ChecklistItem *i = ptr;

  g_free (i->label);
  g_free (i->description);
  g_free (i->likely_error);

  g_slice_free1 (sizeof (ChecklistItem), ptr);
}

static void
free_argument (void *ptr)
{
  Argument *arg = (Argument *) ptr;

  g_free (arg->description);
  g_value_unset (&arg->default_value);
  g_free (arg->full_description);
  g_slice_free1 (sizeof (Argument), ptr);
}

static gboolean
insanity_test_setup (InsanityTest * test)
{
  (void) test;
  return TRUE;
}

static gboolean
insanity_test_start (InsanityTest * test)
{
  (void) test;
  return TRUE;
}

static void
insanity_test_stop (InsanityTest * test)
{
  (void) test;
}

static void
insanity_test_teardown (InsanityTest * test)
{
  (void) test;
}

static void
insanity_test_connect (InsanityTest * test, DBusConnection * conn,
    const char *uuid)
{
  LOCK (test);
  test->priv->standalone = FALSE;
  if (test->priv->conn)
    dbus_connection_unref (test->priv->conn);
  test->priv->conn = dbus_connection_ref (conn);
  if (test->priv->name)
    g_free (test->priv->name);
  test->priv->name =
      g_strdup_printf ("/net/gstreamer/Insanity/Test/Test%s", uuid);
  UNLOCK (test);
}

static void
insanity_test_record_start_time (InsanityTest * test)
{
#ifdef USE_CPU_LOAD
  gettimeofday (&test->priv->start, NULL);
  getrusage (RUSAGE_SELF, &test->priv->rusage);
#endif
}

#ifdef USE_CPU_LOAD
static long
tv_us_diff (const struct timeval *t0, const struct timeval *t1)
{
  return (t1->tv_sec - t0->tv_sec) * 1000000 + t1->tv_usec - t0->tv_usec;
}
#endif

static void
insanity_test_record_stop_time (InsanityTest * test)
{
#ifdef USE_CPU_LOAD
  struct rusage rusage;
  struct timeval end;
  unsigned long us;

  getrusage (RUSAGE_SELF, &rusage);
  gettimeofday (&end, NULL);
  us = tv_us_diff (&test->priv->rusage.ru_utime, &rusage.ru_utime)
      + tv_us_diff (&test->priv->rusage.ru_stime, &rusage.ru_stime);
  test->priv->cpu_load = 100 * us / tv_us_diff (&test->priv->start, &end);
#endif
}

#define INSANITY_TEST_INTERFACE "net.gstreamer.Insanity.Test"
#define INTROSPECT_RESPONSE_TEMPLATE \
  "<!DOCTYPE node PUBLIC \"-//freedesktop//DTD D-BUS Object Introspection 1.0//EN\" " \
  "\"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd\">\n" \
  "<node name=\"/net/gstreamer/Insanity/Test/Test%s\">\n" \
  "  <interface name=\"org.freedesktop.DBus.Introspectable\">\n" \
  "    <method name=\"Introspect\">\n" \
  "      <arg name=\"xml_data\" direction=\"out\" type=\"s\" />\n" \
  "    </method>\n" \
  "  </interface>\n" \
  "  <interface name=\"" INSANITY_TEST_INTERFACE "\">\n" \
  "    <method name=\"remoteSetUp\">\n" \
  "      <arg name=\"success\" direction=\"out\" type=\"b\" />\n" \
  "      <arg name=\"arguments\" direction=\"in\" type=\"a{sv}\" />\n" \
  "      <arg name=\"outputfiles\" direction=\"in\" type=\"a{ss}\" />\n" \
  "    </method>\n" \
  "    <method name=\"remoteStart\">\n" \
  "      <arg name=\"success\" direction=\"out\" type=\"b\" />\n" \
  "      <arg name=\"arguments\" direction=\"in\" type=\"a{sv}\" />\n" \
  "      <arg name=\"outputfiles\" direction=\"in\" type=\"a{ss}\" />\n" \
  "    </method>\n" \
  "    <method name=\"remoteStop\">\n" \
  "    </method>\n" \
  "    <method name=\"remoteTearDown\">\n" \
  "    </method>\n" \
  "    <signal name=\"remoteDoneSignal\">\n" \
  "    </signal>\n" \
  "    <signal name=\"remoteValidateChecklistItemSignal\">\n" \
  "      <arg name=\"name\" type=\"s\" />\n" \
  "      <arg name=\"success\" type=\"b\" />\n" \
  "      <arg name=\"description\" type=\"s\" />\n" \
  "    </signal>\n" \
  "    <signal name=\"remoteExtraInfoSignal\">\n" \
  "      <arg name=\"name\" type=\"s\" />\n" \
  "      <arg name=\"value\" type=\"v\" />\n" \
  "    </signal>\n" \
  "    <signal name=\"remotePingSignal\">\n" \
  "    </signal>\n" \
  "  </interface>\n" \
  "</node>\n"

static gboolean
send_signal (DBusConnection * conn, const char *signal_name,
    const char *path_name, int type, ...)
{
  DBusMessage *msg;
  dbus_uint32_t serial = 0;
  va_list ap;

  msg =
      dbus_message_new_signal (path_name, INSANITY_TEST_INTERFACE, signal_name);
  if (NULL == msg) {
    g_error ("Message Null\n");
    return FALSE;
  }

  if (type != DBUS_TYPE_INVALID) {
    int iter_type = type;
    DBusMessageIter iter;

    va_start (ap, type);

    dbus_message_iter_init_append (msg, &iter);

    while (iter_type != DBUS_TYPE_INVALID) {
      if (dbus_type_is_basic (iter_type)) {
        const void *value;

        value = va_arg (ap, const void *);
        if (!dbus_message_iter_append_basic (&iter, iter_type, value)) {
          g_error ("Out Of Memory!\n");
          va_end (ap);
          goto fail;
        }
      } else if (iter_type == DBUS_TYPE_VARIANT) {
        DBusMessageIter sub;
        DBusSignatureIter siter;
        const char *variant_type;
        int variant_type_id;
        const void *value;

        variant_type = va_arg (ap, const char *);
        value = va_arg (ap, const void *);

        if (!dbus_signature_validate_single (variant_type, NULL)) {
          g_critical ("Invalid or unsupported DBus type \'%s\'\n",
              variant_type);
          va_end (ap);
          goto fail;
        }

        dbus_signature_iter_init (&siter, variant_type);
        variant_type_id = dbus_signature_iter_get_current_type (&siter);

        if (!dbus_type_is_basic (variant_type_id)) {
          g_critical ("Invalid or unsupported DBus type \'%s\'\n",
              variant_type);
          va_end (ap);
          goto fail;
        }

        if (!dbus_message_iter_open_container (&iter, DBUS_TYPE_VARIANT,
                variant_type, &sub)) {
          g_error ("Out Of Memory!\n");
          va_end (ap);
          goto fail;
        }

        if (!dbus_message_iter_append_basic (&sub, variant_type_id, value)) {
          g_error ("Out Of Memory!\n");
          dbus_message_iter_close_container (&iter, &sub);
          va_end (ap);
          goto fail;
        }

        if (!dbus_message_iter_close_container (&iter, &sub)) {
          g_error ("Out Of Memory!\n");
          va_end (ap);
          goto fail;
        }
      } else {
        g_critical ("Invalid or unsupported DBus type %d\n", type);
        va_end (ap);
        goto fail;
      }

      iter_type = va_arg (ap, int);
    }
    va_end (ap);
  }

  if (!dbus_connection_send (conn, msg, &serial)) {
    g_error ("Out Of Memory!\n");
    dbus_message_unref (msg);
    return FALSE;
  }
  dbus_connection_flush (conn);

  dbus_message_unref (msg);

  return TRUE;

fail:

  dbus_message_unref (msg);
  return FALSE;
}

/* Only allow alphanumeric characters and dash */
gboolean
check_valid_label (const char *label)
{
  const gchar *p;

  if (!label)
    return FALSE;

  if ((label[0] < 'A' || label[0] > 'Z') && (label[0] < 'a' || label[0] > 'z'))
    return FALSE;

  for (p = label; *p != 0; p++) {
    gchar c = *p;

    if (c != '-' && c != '.' &&
        (c < '0' || c > '9') && (c < 'A' || c > 'Z') && (c < 'a' || c > 'z'))
      return FALSE;
  }

  return TRUE;
}

static gboolean
check_valid_type (GType type)
{
  return (type == G_TYPE_STRING ||
      type == G_TYPE_INT ||
      type == G_TYPE_UINT ||
      type == G_TYPE_INT64 ||
      type == G_TYPE_UINT64 || type == G_TYPE_DOUBLE || type == G_TYPE_BOOLEAN);
}

static void
insanity_test_ping_unlocked (InsanityTest * test)
{
  if (!test->priv->standalone) {
    send_signal (test->priv->conn, "remotePingSignal", test->priv->name,
        DBUS_TYPE_INVALID);
  } else {
    test->priv->timeout_end_time =
        g_get_monotonic_time () + test->priv->timeout * G_TIME_SPAN_SECOND;
  }
}

/**
 * insanity_test_checklist_item_set_global:
 * @test: a #InsanityTest to operate on
 * @label: the label of the checklist item
 * @global: the new value for global
 *
 * Sets whether a given checklist item is global.
 *
 * Returns: TRUE if the item was found, FALSE otherwise.
 */
gboolean
insanity_test_checklist_item_set_global (InsanityTest * test, const char *label,
    gboolean global)
{
  ChecklistItem *item;
  gboolean ret = FALSE;

  g_return_val_if_fail (INSANITY_IS_TEST (test), FALSE);
  g_return_val_if_fail (test->priv->runlevel == rl_idle, FALSE);
  g_return_val_if_fail (label != NULL, FALSE);
  g_return_val_if_fail (check_valid_label (label), FALSE);
  g_return_val_if_fail (g_hash_table_lookup (test->priv->test_checklist,
          label) != NULL, FALSE);

  LOCK (test);

  item = g_hash_table_lookup (test->priv->test_checklist, label);
  if (!item)
    goto done;

  item->global = global;
  ret = TRUE;

done:
  UNLOCK (test);
  return ret;
}

/**
 * insanity_test_validate_checklist_item:
 * @test: a #InsanityTest to operate on
 * @label: the label of the checklist item
 * @success: whether the checklist item passed, or failed
 * @description: (allow-none): optional description string
 *
 * Declares a given checklist item as either passed, or failed.
 * An optional description may be given to supply more information
 * about the reason for a particular failure.
 */
void
insanity_test_validate_checklist_item (InsanityTest * test, const char *label,
    gboolean success, const char *description)
{
  const ChecklistItem *item;
  gpointer cur_success;

  g_return_if_fail (INSANITY_IS_TEST (test));
  g_return_if_fail (label != NULL);
  g_return_if_fail (check_valid_label (label));
  g_return_if_fail (g_hash_table_lookup (test->priv->test_checklist,
          label) != NULL);

  LOCK (test);

  item = g_hash_table_lookup (test->priv->test_checklist, label);
  if (!item->global &&test->priv->runlevel != rl_started
      && test->priv->runlevel != rl_setup) {
    g_critical ("Non-global checklist item '%s' requested to validate but "
        "not set up yet\n", label);
    goto done;
  }

  insanity_test_ping_unlocked (test);

  /* if the item has already been invalidated, then we do nothing.
     This ends up doing a AND operation on all booleans
     passed for that checklist item (ie, a checklist item succeeds only if all calls to
     validate for that item succeed, and fails if any call to validate for that item fails). */
  if ((cur_success =
          g_hash_table_lookup (test->priv->checklist_results, label)) != NULL) {
    if (!GPOINTER_TO_UINT (cur_success)) {
      UNLOCK (test);
      return;
    }
  }

  if (test->priv->standalone) {
    if (description) {
      insanity_test_printf (test, "checklist item: %s: %s (%s)\n", label,
          success ? "PASS" : "FAIL", description);
    } else {
      insanity_test_printf (test, "checklist item: %s: %s\n", label,
          success ? "PASS" : "FAIL");
    }
  } else {
    const char *desc = description ? description : "";
    send_signal (test->priv->conn, "remoteValidateChecklistItemSignal",
        test->priv->name, DBUS_TYPE_STRING, &label, DBUS_TYPE_BOOLEAN, &success,
        DBUS_TYPE_STRING, &desc, DBUS_TYPE_INVALID);
  }

  g_hash_table_insert (test->priv->checklist_results, g_strdup (label),
      (success ? GUINT_TO_POINTER (1) : GUINT_TO_POINTER (0)));

done:
  UNLOCK (test);
}

static void
insanity_test_set_extra_info_internal (InsanityTest * test, const char *label,
    const GValue * data, gboolean locked)
{
  GType glib_type;
  const char *dbus_type;
  dbus_int32_t int32_value;
  dbus_uint32_t uint32_value;
  dbus_int64_t int64_value;
  dbus_uint64_t uint64_value;
  dbus_bool_t bool_value;
  double double_value;
  const char *string_value;
  void *dataptr = NULL;

  if (!locked)
    LOCK (test);

  if (test->priv->standalone) {
    char *s = g_strdup_value_contents (data);
    insanity_test_printf (test, "Extra info: %s: %s\n", label, s);
    g_free (s);
    if (!locked)
      UNLOCK (test);
    return;
  }

  glib_type = G_VALUE_TYPE (data);
  if (glib_type == G_TYPE_INT) {
    int32_value = g_value_get_int (data);
    dbus_type = "i";
    dataptr = &int32_value;
  } else if (glib_type == G_TYPE_UINT) {
    uint32_value = g_value_get_uint (data);
    dbus_type = "u";
    dataptr = &uint32_value;
  } else if (glib_type == G_TYPE_INT64) {
    int64_value = g_value_get_int64 (data);
    dbus_type = "x";
    dataptr = &int64_value;
  } else if (glib_type == G_TYPE_UINT64) {
    uint64_value = g_value_get_uint64 (data);
    dbus_type = "t";
    dataptr = &uint64_value;
  } else if (glib_type == G_TYPE_DOUBLE) {
    double_value = g_value_get_double (data);
    dbus_type = "d";
    dataptr = &double_value;
  } else if (glib_type == G_TYPE_BOOLEAN) {
    bool_value = g_value_get_boolean (data) ? 0 : 1;
    dbus_type = "b";
    dataptr = &bool_value;
  } else if (glib_type == G_TYPE_STRING) {
    string_value = g_value_get_string (data);
    dbus_type = "s";
    dataptr = &string_value;
  } else {
    /* Add more if needed, there doesn't seem to be a glib "glib to dbus" conversion public API,
       but if I missed one, it could replace the above. */
  }

  if (dataptr) {
    send_signal (test->priv->conn, "remoteExtraInfoSignal", test->priv->name,
        DBUS_TYPE_STRING, &label, DBUS_TYPE_VARIANT, dbus_type, dataptr,
        DBUS_TYPE_INVALID);
  } else {
    char *s = g_strdup_value_contents (data);
    g_critical ("Unsupported extra info: %s\n", s);
    g_free (s);
  }

  if (!locked)
    UNLOCK (test);
}

/**
 * insanity_test_set_extra_info:
 * @test: a #InsanityTest to operate on
 * @label: a label for the extra information
 * @data: the extra information
 *
 * Allows a test to supply any relevant information of interest.
 * As an example, Insanity uses this system to record the CPU load
 * used by a given test, the data here being an integer.
 */
void
insanity_test_set_extra_info (InsanityTest * test, const char *label,
    const GValue * data)
{
  g_return_if_fail (INSANITY_IS_TEST (test));
  g_return_if_fail (label != NULL);
  g_return_if_fail (check_valid_label (label));
  g_return_if_fail (G_IS_VALUE (data));
  g_return_if_fail (check_valid_type (G_VALUE_TYPE (data)));

  insanity_test_ping (test);
  insanity_test_set_extra_info_internal (test, label, data, FALSE);
}

void
insanity_test_ping (InsanityTest * test)
{
  g_return_if_fail (INSANITY_IS_TEST (test));

  LOCK (test);
  insanity_test_ping_unlocked (test);
  UNLOCK (test);
}

static void
gather_end_of_test_info (InsanityTest * test)
{
  GValue value = { 0 };

  if (test->priv->cpu_load >= 0)
    return;

  insanity_test_record_stop_time (test);

  g_value_init (&value, G_TYPE_INT);
  g_value_set_int (&value, test->priv->cpu_load);
  insanity_test_set_extra_info_internal (test, "cpu-load", &value, TRUE);
  g_value_unset (&value);
}

/**
 * insanity_test_done:
 * @test: a #InsanityTest to operate on
 *
 * This function MUST be called when each test is finished.
 */
void
insanity_test_done (InsanityTest * test)
{
  g_return_if_fail (INSANITY_IS_TEST (test));

  LOCK (test);
  if (!test->priv->standalone) {
    send_signal (test->priv->conn, "remoteDoneSignal", test->priv->name,
        DBUS_TYPE_INVALID);
  }
  UNLOCK (test);

  LOCK_SIGNAL (test);
  SIGNAL (test);
  UNLOCK_SIGNAL (test);
}

static gboolean
on_setup (InsanityTest * test)
{
  gboolean ret = TRUE;
  const gchar *ptr;
  gchar *log_level;

  LOCK (test);
  if (test->priv->runlevel != rl_idle) {
    UNLOCK (test);
    return FALSE;
  }
  UNLOCK (test);

  insanity_test_get_string_argument (test, "log-level", &log_level);
  LOCK (test);
  for (ptr = log_level; *ptr;) {
    const char *colon, *end, *slev;
    char *category = NULL, *lptr = NULL;
    unsigned long level;

    end = strchr (ptr, ',');
    if (!end)
      end = strchr (ptr, 0);
    colon = memchr (ptr, ':', end - ptr + 1);
    slev = ptr;
    if (colon) {
      slev = colon + 1;
      category = g_strndup (ptr, colon - ptr);
      if (!check_valid_label (category)) {
        g_error ("Invalid category name: %s - ignored\n", category);
        g_free (category);
        goto ignore;
      }
    }

    errno = 0;
    level = strtoul (slev, &lptr, 10);
    if ((*lptr && lptr < end) || (level == ULONG_MAX && errno) || end == slev) {
      g_error ("Invalid log level: %*.*s - ignored\n", (int) (end - slev),
          (int) (end - slev), slev);
      if (category)
        g_free (category);
      goto ignore;
    }

    if (colon) {
      g_hash_table_insert (test->priv->log_levels, category, (gpointer) level);
    } else {
      test->priv->default_log_level = level;
    }

  ignore:
    ptr = *end ? end + 1 : end;
  }
  UNLOCK (test);

  g_signal_emit (test, setup_signal, 0, &ret);

  LOCK (test);

  insanity_test_record_start_time (test);
  test->priv->runlevel = rl_setup;
  test->priv->iteration = 0;
  UNLOCK (test);
  return ret;
}

static gboolean
on_start (InsanityTest * test)
{
  gboolean ret = TRUE;

  if (test->priv->runlevel != rl_setup)
    return FALSE;

  g_signal_emit (test, start_signal, 0, &ret);
  test->priv->runlevel = rl_started;
  return ret;
}

static void
on_stop (InsanityTest * test)
{
  if (test->priv->runlevel != rl_started)
    return;

  g_signal_emit (test, stop_signal, 0, NULL);

  LOCK (test);
  test->priv->runlevel = rl_setup;
  test->priv->iteration++;
  UNLOCK (test);
}

static void
on_teardown (InsanityTest * test)
{
  if (test->priv->runlevel != rl_setup)
    return;

  LOCK (test);
  gather_end_of_test_info (test);
  UNLOCK (test);

  g_signal_emit (test, teardown_signal, 0, NULL);

  LOCK (test);
  test->priv->runlevel = rl_idle;
  test->priv->exit = TRUE;
  UNLOCK (test);
}

static int
foreach_dbus_array (DBusMessageIter * iter, int (*f) (const char *key,
        const GValue * value, guintptr userdata), guintptr userdata)
{
  DBusMessageIter subiter, subsubiter, subsubsubiter;
  const char *key;
  const char *string_value;
  dbus_uint32_t uint32_value;
  dbus_int32_t int32_value;
  int boolean_value;
  dbus_uint64_t uint64_value;
  dbus_int64_t int64_value;
  double double_value;
  GValue value = { 0 };
  int type;
  int ret;

  type = dbus_message_iter_get_arg_type (iter);
  if (type != DBUS_TYPE_ARRAY) {
    g_critical ("Expected array, got %c\n", type);
    return -1;
  }
  dbus_message_iter_recurse (iter, &subiter);
  do {
    type = dbus_message_iter_get_arg_type (&subiter);
    if (type != DBUS_TYPE_DICT_ENTRY) {
      g_critical ("Expected dict entry, got %c\n", type);
      return -1;
    }
    dbus_message_iter_recurse (&subiter, &subsubiter);

    type = dbus_message_iter_get_arg_type (&subsubiter);
    if (type != DBUS_TYPE_STRING) {
      g_critical ("Expected string, got %c\n", type);
      return -1;
    }
    dbus_message_iter_get_basic (&subsubiter, &key);
    if (!dbus_message_iter_next (&subsubiter)) {
      g_critical ("Value not present\n");
      return -1;
    }
    type = dbus_message_iter_get_arg_type (&subsubiter);
    if (type == DBUS_TYPE_STRING) {
      dbus_message_iter_get_basic (&subsubiter, &string_value);
      g_value_init (&value, G_TYPE_STRING);
      g_value_set_string (&value, string_value);
    } else if (type == DBUS_TYPE_VARIANT) {
      dbus_message_iter_recurse (&subsubiter, &subsubsubiter);

      type = dbus_message_iter_get_arg_type (&subsubsubiter);

      switch (type) {
        case DBUS_TYPE_STRING:
          dbus_message_iter_get_basic (&subsubsubiter, &string_value);
          g_value_init (&value, G_TYPE_STRING);
          g_value_set_string (&value, string_value);
          break;
        case DBUS_TYPE_INT32:
          dbus_message_iter_get_basic (&subsubsubiter, &int32_value);
          g_value_init (&value, G_TYPE_INT);
          g_value_set_int (&value, int32_value);
          break;
        case DBUS_TYPE_UINT32:
          dbus_message_iter_get_basic (&subsubsubiter, &uint32_value);
          g_value_init (&value, G_TYPE_UINT);
          g_value_set_uint (&value, uint32_value);
          break;
        case DBUS_TYPE_INT64:
          dbus_message_iter_get_basic (&subsubsubiter, &int64_value);
          g_value_init (&value, G_TYPE_INT64);
          g_value_set_int64 (&value, int64_value);
          break;
        case DBUS_TYPE_UINT64:
          dbus_message_iter_get_basic (&subsubsubiter, &uint64_value);
          g_value_init (&value, G_TYPE_UINT64);
          g_value_set_uint64 (&value, uint64_value);
          break;
        case DBUS_TYPE_DOUBLE:
          dbus_message_iter_get_basic (&subsubsubiter, &double_value);
          g_value_init (&value, G_TYPE_DOUBLE);
          g_value_set_double (&value, double_value);
          break;
        case DBUS_TYPE_BOOLEAN:
          dbus_message_iter_get_basic (&subsubsubiter, &boolean_value);
          g_value_init (&value, G_TYPE_BOOLEAN);
          g_value_set_boolean (&value, boolean_value);
          break;
        case DBUS_TYPE_ARRAY:
          g_value_init (&value, G_TYPE_POINTER);
          g_value_set_pointer (&value, &subsubsubiter);
          break;
        default:
          g_critical ("Unsupported type: %c\n", type);
          return -1;
          break;
      }
    } else {
      g_critical ("Expected variant, got %c\n", type);
      return -1;
    }

    /* < 0 -> error, 0 -> continue, > 0 -> stop */
    ret = (*f) (key, &value, userdata);
    g_value_unset (&value);
    if (ret)
      return ret;

  } while (dbus_message_iter_next (&subiter));

  return 0;
}

static int
output_filename_converter (const char *label, const GValue * value,
    guintptr userdata)
{
  InsanityTest *test = (InsanityTest *) userdata;

  if (G_VALUE_TYPE (value) != G_TYPE_STRING) {
    g_critical ("Output filename %s is not a string, ignored\n", label);
    return 0;
  }

  g_hash_table_insert (test->priv->filename_cache, g_strdup (label),
      g_value_dup_string (value));
  return 0;
}

static int
arg_converter (const char *label, const GValue * value, guintptr userdata)
{
  InsanityTest *test = (InsanityTest *) userdata;
  const Argument *arg;
  GValue *v;

  arg = g_hash_table_lookup (test->priv->test_arguments, label);
  if (!arg) {
    /* fprintf (stderr, "Key '%s' is not a declared argument, ignored\n", label); */
    return 0;
  }
  if (G_VALUE_TYPE (value) != G_VALUE_TYPE (&arg->default_value)) {
    g_critical ("Key '%s' does not have the expected type\n", label);
    return -1;
  }

  v = g_slice_alloc0 (sizeof (GValue));
  g_value_init (v, G_VALUE_TYPE (value));
  g_value_copy (value, v);      /* src first */
  g_hash_table_insert (test->priv->args, g_strdup (label), v);
  return 0;
}

static void
free_gvalue (void *ptr)
{
  GValue *v = (GValue *) ptr;

  g_value_unset (v);
  g_slice_free1 (sizeof (GValue), v);
}

static void
insanity_test_set_args (InsanityTest * test, DBusMessage * msg)
{
  LOCK (test);

  if (test->priv->args) {
    g_hash_table_destroy (test->priv->args);
    test->priv->args = NULL;
  }

  g_hash_table_remove_all (test->priv->filename_cache);

  if (msg) {
    int ret;
    DBusMessageIter iter;

    dbus_message_iter_init (msg, &iter);

    /* arguments */
    test->priv->args =
        g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free,
        &free_gvalue);
    ret = foreach_dbus_array (&iter, &arg_converter, (guintptr) test);
    if (ret < 0) {
      UNLOCK (test);
      return;
    }

    /* output files */
    if (!dbus_message_iter_next (&iter)) {
      UNLOCK (test);
      return;
    }

    ret =
        foreach_dbus_array (&iter, &output_filename_converter, (guintptr) test);
    if (ret < 0) {
      UNLOCK (test);
      return;
    }
  }

  UNLOCK (test);
}

/**
 * insanity_test_get_argument:
 * @test: a #InsanityTest to operate on
 * @label: the label of the argument to retrieve
 * @value: (out caller-allocates): a pointer to a value to receive the contents of the argument
 *
 * Returns: TRUE if the argument was found (in which case the value
 * is initialized and contains its value), FALSE otherwise (in which
 * case the value is left untouched).
 */
gboolean
insanity_test_get_argument (InsanityTest * test, const char *label,
    GValue * value)
{
  const Argument *arg;
  const GValue *v;
  gboolean ret = FALSE;

  g_return_val_if_fail (INSANITY_IS_TEST (test), FALSE);
  g_return_val_if_fail (label != NULL, FALSE);
  g_return_val_if_fail (check_valid_label (label), FALSE);
  g_return_val_if_fail (g_hash_table_lookup (test->priv->test_arguments,
          label) != NULL, FALSE);
  g_return_val_if_fail (value != NULL, FALSE);

  LOCK (test);

  arg = g_hash_table_lookup (test->priv->test_arguments, label);

  if (!arg->global &&test->priv->runlevel != rl_started
      && test->priv->runlevel != rl_setup) {
    g_critical ("Non-global argument \'%s' requested but not set up yet\n",
        label);
    goto done;
  }

  if (test->priv->args) {
    v = g_hash_table_lookup (test->priv->args, label);
    if (v) {
      g_value_init (value, G_VALUE_TYPE (v));
      g_value_copy (v, value);
      ret = TRUE;
    }
  }

  if (!ret) {
    if (arg) {
      g_value_init (value, G_VALUE_TYPE (&arg->default_value));
      g_value_copy (&arg->default_value, value);
      ret = TRUE;
    }
  }

  if (!ret) {
    g_critical ("Argument %s not found\n", label);
  }

done:
  UNLOCK (test);

  return ret;
}

/**
 * insanity_test_get_output_filename:
 * @test: a #InsanityTest to operate on
 * @label: the label of the filename to retrieve
 *
 * Returns: the filename associated to the label, or NULL if none.
 */
const char *
insanity_test_get_output_filename (InsanityTest * test, const char *label)
{
  gpointer ptr;
  char *fn = NULL;
  OutputFileItem *of;

  g_return_val_if_fail (INSANITY_IS_TEST (test), NULL);
  g_return_val_if_fail (label != NULL, NULL);
  g_return_val_if_fail (check_valid_label (label), NULL);
  g_return_val_if_fail (g_hash_table_lookup (test->priv->test_output_files,
          label) != NULL, NULL);

  LOCK (test);

  of = g_hash_table_lookup (test->priv->test_output_files, label);
  if (!of->global &&test->priv->runlevel != rl_started
      && test->priv->runlevel != rl_setup) {
    g_critical
        ("Non-global output filename \'%s' requested but not set up yet\n",
        label);
    goto done;
  }

  ptr = g_hash_table_lookup (test->priv->filename_cache, label);
  if (ptr) {
    fn = ptr;
  }

  else if (test->priv->standalone) {
    if (!test->priv->tmpdir) {
      GError *error = NULL;
      test->priv->tmpdir = g_dir_make_tmp ("insanity-XXXXXX", &error);
      if (error)
        g_error_free (error);
      if (!test->priv->tmpdir) {
        g_error ("Failed to create temporary directory\n");
        UNLOCK (test);
        return NULL;
      }
    }

    if (of->global) {
      fn = g_build_filename (test->priv->tmpdir, label, NULL);
    } else {
      gchar *filename;

      filename = g_strdup_printf ("%s-%d", label, test->priv->iteration);
      fn = g_build_filename (test->priv->tmpdir, filename, NULL);
      g_free (filename);
    }
    g_hash_table_insert (test->priv->filename_cache, g_strdup (label), fn);
  }

done:
  UNLOCK (test);

  return fn;
}

static void
insanity_test_dbus_handler_remoteSetup (InsanityTest * test, DBusMessage * msg,
    DBusMessage * reply)
{
  DBusMessageIter iter;
  gboolean ret;

  insanity_test_set_args (test, msg);
  ret = on_setup (test);

  dbus_message_iter_init_append (reply, &iter);
  if (!dbus_message_iter_append_basic (&iter, DBUS_TYPE_BOOLEAN, &ret)) {
    g_error ("Out Of Memory!\n");
  }
}

static void
insanity_test_dbus_handler_remoteStart (InsanityTest * test, DBusMessage * msg,
    DBusMessage * reply)
{
  DBusMessageIter iter;
  gboolean ret;

  insanity_test_set_args (test, msg);
  ret = on_start (test);

  dbus_message_iter_init_append (reply, &iter);
  if (!dbus_message_iter_append_basic (&iter, DBUS_TYPE_BOOLEAN, &ret)) {
    g_error ("Out Of Memory!\n");
  }
}

static void
insanity_test_dbus_handler_remoteStop (InsanityTest * test, DBusMessage * msg,
    DBusMessage * reply)
{
  (void) msg;
  on_stop (test);
}

static void
insanity_test_dbus_handler_remoteTearDown (InsanityTest * test,
    DBusMessage * msg, DBusMessage * reply)
{
  (void) msg;
  on_teardown (test);
}

static const struct
{
  const char *method;
  void (*handler) (InsanityTest *, DBusMessage *, DBusMessage *);
} dbus_test_handlers[] = {
  {
  "remoteSetUp", &insanity_test_dbus_handler_remoteSetup}, {
  "remoteStart", &insanity_test_dbus_handler_remoteStart}, {
  "remoteStop", &insanity_test_dbus_handler_remoteStop}, {
"remoteTearDown", &insanity_test_dbus_handler_remoteTearDown},};

static gboolean
insanity_call_interface (InsanityTest * test, DBusMessage * msg)
{
  size_t n;
  const char *method = dbus_message_get_member (msg);

  for (n = 0; n < sizeof (dbus_test_handlers) / sizeof (dbus_test_handlers[0]);
      ++n) {
    if (!strcmp (method, dbus_test_handlers[n].method)) {
      dbus_uint32_t serial = 0;
      DBusMessage *reply = dbus_message_new_method_return (msg);

      if (dbus_test_handlers[n].handler)
        (*dbus_test_handlers[n].handler) (test, msg, reply);

      LOCK (test);
      if (!dbus_connection_send (test->priv->conn, reply, &serial)) {
        g_error ("Out Of Memory!\n");
      } else {
        dbus_connection_flush (test->priv->conn);
      }
      UNLOCK (test);
      dbus_message_unref (reply);

      return TRUE;
    }
  }
  return FALSE;
}

static gboolean
listen (InsanityTest * test, const char *bus_address, const char *uuid)
{
  DBusMessage *msg;
  DBusMessage *reply;
  DBusMessageIter args;
  DBusConnection *conn;
  DBusError err;
  int ret;
  char *object_name;
  dbus_uint32_t serial = 0;

  test->priv->standalone = FALSE;

  dbus_error_init (&err);

  /* connect to the bus and check for errors */
  conn = dbus_connection_open (bus_address, &err);
  if (dbus_error_is_set (&err)) {
    g_error ("Connection Error (%s)\n", err.message);
    dbus_error_free (&err);
    return FALSE;
  }
  if (NULL == conn) {
    g_error ("Connection Null\n");
    return FALSE;
  }

  ret = dbus_bus_register (conn, &err);
  if (dbus_error_is_set (&err)) {
    g_error ("Failed to register bus (%s)\n", err.message);
    dbus_error_free (&err);
    /* Is this supposed to be fatal ? */
  }
  /* request our name on the bus and check for errors */
  object_name = g_strdup_printf (INSANITY_TEST_INTERFACE ".Test%s", uuid);
  ret =
      dbus_bus_request_name (conn, object_name, DBUS_NAME_FLAG_REPLACE_EXISTING,
      &err);
  if (dbus_error_is_set (&err)) {
    g_error ("Name Error (%s)\n", err.message);
    dbus_error_free (&err);
    /* Is this supposed to be fatal ? */
  }
  if (DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER != ret) {
    g_error ("Not Primary Owner (%d)\n", ret);
    return FALSE;
  }

  insanity_test_connect (test, conn, uuid);

  /* loop, testing for new messages */
  test->priv->exit = FALSE;
  while (1) {
    LOCK (test);
    /* barely blocking update of dbus */
    dbus_connection_read_write (conn, 1);

    if (test->priv->exit) {
      UNLOCK (test);
      break;
    }

    /* see if we have a message to handle */
    msg = dbus_connection_pop_message (conn);
    UNLOCK (test);
    if (NULL == msg) {
      g_usleep (10000);         /* Not good */
      continue;
    }
#if 0
    printf ("Got message:\n");
    printf ("  type %d\n", dbus_message_get_type (msg));
    printf ("  path %s\n", dbus_message_get_path (msg));
    printf ("  interface %s\n", dbus_message_get_interface (msg));
    printf ("  member %s\n", dbus_message_get_member (msg));
    printf ("  sender %s\n", dbus_message_get_sender (msg));
    printf ("  destination %s\n", dbus_message_get_destination (msg));
    printf ("  signature %s\n", dbus_message_get_signature (msg));
#endif

    /* check this is a method call for the right interface & method */
    if (dbus_message_is_method_call (msg, "org.freedesktop.DBus.Introspectable",
            "Introspect")) {
      char *introspect_response =
          g_strdup_printf (INTROSPECT_RESPONSE_TEMPLATE, uuid);
      reply = dbus_message_new_method_return (msg);
      dbus_message_iter_init_append (reply, &args);
      if (!dbus_message_iter_append_basic (&args, DBUS_TYPE_STRING,
              &introspect_response)) {
        g_error ("Out Of Memory!\n");
        dbus_message_unref (reply);
        goto msg_error;
      }
      g_free (introspect_response);
      LOCK (test);
      if (!dbus_connection_send (conn, reply, &serial)) {
        UNLOCK (test);
        g_error ("Out Of Memory!\n");
        dbus_message_unref (reply);
        goto msg_error;
      }
      dbus_connection_flush (conn);
      UNLOCK (test);
      dbus_message_unref (reply);
    } else if (!strcmp (dbus_message_get_interface (msg),
            INSANITY_TEST_INTERFACE)) {
      insanity_call_interface (test, msg);
    } else {
      /*printf("Got unhandled method call: interface %s, method %s\n", dbus_message_get_interface(msg), dbus_message_get_member(msg)); */
    }

  msg_error:
    dbus_message_unref (msg);
  }

  dbus_connection_unref (conn);
  g_free (object_name);

  return TRUE;
}

static void
output_table (InsanityTest * test, FILE * f, GHashTable * table,
    const char *name, const char *(*getname) (void *))
{
  GHashTableIter it;
  const char *label, *comma = "";
  void *data;

  if (g_hash_table_size (table) == 0)
    return;

  fprintf (f, ",\n  \"%s\": {\n", name);
  g_hash_table_iter_init (&it, table);
  while (g_hash_table_iter_next (&it, (gpointer) & label, (gpointer) & data)) {
    const char *str_value = (*getname) (data);

    if (!str_value)
      continue;

    fprintf (f, "%s    \"%s\" : \"%s\"", comma, label, str_value);
    comma = ",\n";
  }
  fprintf (f, "\n  }");
}

static const char *
get_raw_string (void *ptr)
{
  return ptr;
}

static const char *
get_argument_type_char (const GValue * v)
{
  if (G_VALUE_HOLDS_STRING (v))
    return "s";
  else if (G_VALUE_HOLDS_INT (v))
    return "i";
  else if (G_VALUE_HOLDS_UINT (v))
    return "u";
  else if (G_VALUE_HOLDS_INT64 (v))
    return "I";
  else if (G_VALUE_HOLDS_UINT64 (v))
    return "U";
  else if (G_VALUE_HOLDS_DOUBLE (v))
    return "d";
  else if (G_VALUE_HOLDS_BOOLEAN (v))
    return "b";
  else
    g_assert_not_reached ();

  return NULL;
}

static void
output_checklist_table (InsanityTest * test, FILE * f)
{
  GHashTableIter it;
  const char *label, *comma = "";
  void *data;

  if (g_hash_table_size (test->priv->test_checklist) == 0)
    return;

  fprintf (f, ",\n  \"__checklist__\": {\n");
  g_hash_table_iter_init (&it, test->priv->test_checklist);
  while (g_hash_table_iter_next (&it, (gpointer) & label, (gpointer) & data)) {
    ChecklistItem *i = data;

    fprintf (f, "%s    \"%s\" : \n", comma, label);
    fprintf (f, "    {\n");
    fprintf (f, "        \"global\" : %s,\n", (i->global ? "true" : "false"));
    fprintf (f, "        \"description\" : \"%s\"", i->description);
    if (i->likely_error) {
      fprintf (f, ",\n        \"likely_error\" : \"%s\"", i->likely_error);
    }
    fprintf (f, "\n    }");

    comma = ",\n";
  }
  fprintf (f, "\n  }");
}

static void
output_arguments_table (InsanityTest * test, FILE * f)
{
  GHashTableIter it;
  const char *label, *comma = "";
  void *data;

  if (g_hash_table_size (test->priv->test_arguments) == 0)
    return;

  fprintf (f, ",\n  \"__arguments__\": {\n");
  g_hash_table_iter_init (&it, test->priv->test_arguments);
  while (g_hash_table_iter_next (&it, (gpointer) & label, (gpointer) & data)) {
    Argument *a = data;
    char *default_value;

    if (G_VALUE_HOLDS_STRING (&a->default_value))
      default_value = g_value_dup_string (&a->default_value);
    else
      default_value = g_strdup_value_contents (&a->default_value);

    fprintf (f, "%s    \"%s\" : \n", comma, label);
    fprintf (f, "    {\n");
    fprintf (f, "        \"global\" : %s,\n", (a->global ? "true" : "false"));
    fprintf (f, "        \"description\" : \"%s\",\n", a->description);
    fprintf (f, "        \"full_description\" : \"%s\",\n",
        a->full_description ? a->full_description : a->description);
    fprintf (f, "        \"type\" : \"%s\",\n",
        get_argument_type_char (&a->default_value));
    fprintf (f, "        \"default_value\" : \"%s\"\n", default_value);
    fprintf (f, "    }");
    g_free (default_value);

    comma = ",\n";
  }
  fprintf (f, "\n  }");
}

static void
output_output_files_table (InsanityTest * test, FILE * f)
{
  GHashTableIter it;
  const char *label, *comma = "";
  void *data;

  if (g_hash_table_size (test->priv->test_output_files) == 0)
    return;

  fprintf (f, ",\n  \"__output_files__\": {\n");
  g_hash_table_iter_init (&it, test->priv->test_output_files);
  while (g_hash_table_iter_next (&it, (gpointer) & label, (gpointer) & data)) {
    OutputFileItem *of = data;

    fprintf (f, "%s    \"%s\" : \n", comma, label);
    fprintf (f, "    {\n");
    fprintf (f, "        \"description\" : \"%s\",\n", of->description);
    fprintf (f, "        \"global\" : %s\n", (of->global ? "true" : "false"));
    fprintf (f, "    }");

    comma = ",\n";
  }
  fprintf (f, "\n  }");
}

static void
insanity_test_write_metadata (InsanityTest * test)
{
  FILE *f = stdout;
  char *name, *desc;

  g_object_get (G_OBJECT (test), "name", &name, NULL);
  g_object_get (G_OBJECT (test), "description", &desc, NULL);

  fprintf (f, "Insanity test metadata:\n");
  fprintf (f, "{\n");
  fprintf (f, "  \"__name__\": \"%s\",\n", name);
  fprintf (f, "  \"__description__\": \"%s\"", desc);
  output_checklist_table (test, f);
  output_arguments_table (test, f);
  output_table (test, f, test->priv->test_extra_infos, "__extra_infos__",
      &get_raw_string);
  output_output_files_table (test, f);
  fprintf (f, "\n}\n");

  g_free (name);
  g_free (desc);
}

static void
usage (const char *argv0)
{
  g_print
      ("Usage: %s [--insanity-metadata | --run [label=value]... | <uuid>]\n",
      argv0);
}

static gboolean
find_string (const char *string_value, const char *values[])
{
  int n;

  for (n = 0; values[n]; ++n) {
    if (!g_ascii_strcasecmp (string_value, values[n]))
      return TRUE;
  }
  return FALSE;
}

static gboolean
is_true (const char *string_value)
{
  static const char *true_values[] = { "1", "true", NULL };
  return find_string (string_value, true_values);
}

static gboolean
is_false (const char *string_value)
{
  static const char *false_values[] = { "0", "false", NULL };
  return find_string (string_value, false_values);
}

static gboolean
parse_value (InsanityTest * test, const char *label, const char *string_value,
    GValue * value)
{
  const Argument *arg;
  GType type;

  arg = g_hash_table_lookup (test->priv->test_arguments, label);
  if (arg) {
    type = G_VALUE_TYPE (&arg->default_value);
    if (type == G_TYPE_STRING) {
      g_value_init (value, G_TYPE_STRING);
      g_value_set_string (value, string_value);
      return TRUE;
    } else if (type == G_TYPE_INT) {
      char *ptr = NULL;
      long n = strtol (string_value, &ptr, 10);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_INT);
        g_value_set_int (value, n);
        return TRUE;
      }
    } else if (type == G_TYPE_UINT) {
      char *ptr = NULL;
      unsigned long n = strtoul (string_value, &ptr, 10);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_UINT);
        g_value_set_uint (value, n);
        return TRUE;
      }
    } else if (type == G_TYPE_INT64) {
      char *ptr = NULL;
      gint64 n = g_ascii_strtoll (string_value, &ptr, 10);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_INT64);
        g_value_set_int64 (value, n);
        return TRUE;
      }
    } else if (type == G_TYPE_UINT64) {
      char *ptr = NULL;
      guint64 n = g_ascii_strtoull (string_value, &ptr, 10);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_UINT64);
        g_value_set_uint64 (value, n);
        return TRUE;
      }
    } else if (type == G_TYPE_DOUBLE) {
      char *ptr = NULL;
      float f = strtof (string_value, &ptr);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_DOUBLE);
        g_value_set_float (value, f);
        return TRUE;
      }
    } else if (type == G_TYPE_BOOLEAN) {
      if (is_true (string_value)) {
        g_value_init (value, G_TYPE_BOOLEAN);
        g_value_set_boolean (value, TRUE);
        return TRUE;
      } else if (is_false (string_value)) {
        g_value_init (value, G_TYPE_BOOLEAN);
        g_value_set_boolean (value, FALSE);
        return TRUE;
      }
    }
    g_critical ("Unable to convert '%s' to the declared type\n", string_value);
    return FALSE;
  }

  return FALSE;
}

static unsigned int
insanity_report_failed_tests (InsanityTest * test, gboolean verbose)
{
  GHashTableIter i;
  gpointer label, value;
  unsigned int failed = 0;

  /* Get all checklist items that were passed or failed */
  g_hash_table_iter_init (&i, test->priv->checklist_results);
  while (g_hash_table_iter_next (&i, &label, &value)) {
    gboolean success = (value != NULL);
    if (verbose)
      insanity_test_report (test, "%s: %s\n", (const char *) label,
          success ? "PASS" : "FAIL");
    if (!success)
      failed++;
  }

  /* Get all checklist items that were not passed nor failed */
  g_hash_table_iter_init (&i, test->priv->test_checklist);
  while (g_hash_table_iter_next (&i, &label, &value)) {
    if (!g_hash_table_lookup_extended (test->priv->checklist_results, label,
            NULL, NULL)) {
      if (verbose)
        insanity_test_report (test, "%s: SKIP\n", (const char *) label);
      ++failed;
    }
  }

  if (verbose)
    insanity_test_report (test, "%u/%u failed tests\n", failed,
        g_hash_table_size (test->priv->test_checklist));

  return failed;
}

static gboolean
insanity_test_run_standalone (InsanityTest * test)
{
  gboolean timeout = FALSE, started;

  if (on_setup (test)) {
    LOCK_SIGNAL (test);
    started = on_start (test);
    if (started) {
      timeout = WAIT_TIMEOUT (test);
    }
    UNLOCK_SIGNAL (test);
    on_stop (test);
  }
  on_teardown (test);

  return (!timeout && insanity_report_failed_tests (test, TRUE) == 0);
}

/**
 * insanity_test_run:
 * @test: a #InsanityTest to operate on
 * @argc: (inout) (allow-none): pointer to application's argc
 * @argv: (inout) (array length=argc) (allow-none): pointer to application's argv
 *
 * This function runs the test after it was setup.
 * It will handle remote/standalone modes, command line handling, etc.
 *
 * Returns: %TRUE on success, FALSE on error.
 */
gboolean
insanity_test_run (InsanityTest * test, int *argc, char ***argv)
{
  const char *private_dbus_address;
  const char *opt_uuid = NULL;
  gboolean opt_run = FALSE;
  gboolean opt_metadata = FALSE;
  gint opt_timeout = TEST_TIMEOUT;
  const char *opt_output_directory = NULL;
  gboolean opt_keep_unnamed_output_files = FALSE;
  const GOptionEntry options[] = {
    {"run", 0, 0, G_OPTION_ARG_NONE, &opt_run, "Run the test standalone", NULL},
    {"insanity-metadata", 0, 0, G_OPTION_ARG_NONE, &opt_metadata,
        "Output test metadata", NULL},
    {"dbus-uuid", 0, 0, G_OPTION_ARG_STRING, &opt_uuid, "Set D-Bus uuid",
        "UUID"},
    {"timeout", 0, 0, G_OPTION_ARG_INT, &opt_timeout,
        "Test timeout in standalone mode (<= 0 to disable)", NULL},
    {"output-directory", 0, 0, G_OPTION_ARG_STRING, &opt_output_directory,
          "Set directory where to create output files(random by default)",
        NULL},
    {"keep-unnamed-output-files", 0, 0, G_OPTION_ARG_NONE,
          &opt_keep_unnamed_output_files,
          "Keep unnamed output files after program ends (by default, only named ones are kept)",
        NULL},
    {NULL}
  };
  GOptionContext *ctx;
  GError *err = NULL;
  gboolean ret = TRUE;
  gchar *prgname;

  g_return_val_if_fail (INSANITY_IS_TEST (test), FALSE);

  prgname = g_path_get_basename ((*argv)[0]);
  g_set_prgname (prgname);
  g_free (prgname);

  /* Make warnings/criticals fatal */
  g_log_set_always_fatal (G_LOG_LEVEL_ERROR | G_LOG_LEVEL_CRITICAL |
      G_LOG_LEVEL_WARNING);

  ctx = g_option_context_new (test->priv->test_desc);
  g_option_context_add_main_entries (ctx, options, NULL);
  if (!g_option_context_parse (ctx, argc, argv, &err)) {
    g_error ("Error initializing: %s\n", err->message);
    g_error_free (err);
    g_option_context_free (ctx);
    return FALSE;
  }

  if (opt_output_directory) {
    test->priv->tmpdir = g_strdup (opt_output_directory);
  }
  test->priv->keep_unnamed_output_files = opt_keep_unnamed_output_files;

  if (opt_metadata) {
    insanity_test_write_metadata (test);
    ret = TRUE;
  } else if (opt_run && !opt_uuid) {
    int n;

    test->priv->timeout = opt_timeout;

    /* Load any command line output files and arguments */
    test->priv->args =
        g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free,
        &free_gvalue);
    for (n = 1; n < *argc; ++n) {
      char *label;
      const char *equals;
      GValue value = { 0 }, *v;

      equals = strchr ((*argv)[n], '=');
      if (!equals) {
        usage ((*argv)[0]);
        return FALSE;
      }

      label = g_strndup ((*argv)[n], equals - (*argv)[n]);
      if (g_hash_table_lookup (test->priv->test_output_files, label)) {
        g_hash_table_insert (test->priv->filename_cache, label,
            g_strdup (equals + 1));
      } else {
        if (parse_value (test, label, equals + 1, &value)) {
          v = g_slice_alloc0 (sizeof (GValue));
          g_value_init (v, G_VALUE_TYPE (&value));
          g_value_copy (&value, v);     /* src first */
          g_hash_table_insert (test->priv->args, label, v);
          g_value_unset (&value);
        } else {
          g_free (label);
        }
      }
    }

    ret = insanity_test_run_standalone (test);
  }

  else if (opt_run && opt_uuid) {
    private_dbus_address = getenv ("PRIVATE_DBUS_ADDRESS");
    if (!private_dbus_address || !private_dbus_address[0]) {
      g_error ("The PRIVATE_DBUS_ADDRESS environment variable must be set\n");
      ret = FALSE;
    } else {
#if 0
      printf ("uuid: %s\n", opt_uuid);
      printf ("PRIVATE_DBUS_ADDRESS: %s\n", private_dbus_address);
#endif
      ret = listen (test, private_dbus_address, opt_uuid);
    }
  }

  else {
    g_print ("%s\n", g_option_context_get_help (ctx, FALSE, NULL));
    ret = FALSE;
  }

  g_option_context_free (ctx);

  return ret;
}

G_DEFINE_TYPE (InsanityTest, insanity_test, G_TYPE_OBJECT);

static void
insanity_test_finalize (GObject * gobject)
{
  InsanityTest *test = (InsanityTest *) gobject;
  InsanityTestPrivateData *priv = test->priv;

  if (priv->args)
    g_hash_table_destroy (priv->args);
  if (priv->conn)
    dbus_connection_unref (priv->conn);
  if (test->priv->name)
    g_free (test->priv->name);
  if (priv->filename_cache) {
    if (!priv->conn) {          /* unreffed, but value still set */
      if (!priv->keep_unnamed_output_files) {
        GHashTableIter i;
        gpointer label, value;
        g_hash_table_iter_init (&i, priv->filename_cache);
        while (g_hash_table_iter_next (&i, &label, &value)) {
          /* only unlink those random ones */
          if (test->priv->tmpdir
              && g_str_has_prefix (value, test->priv->tmpdir)) {
            g_unlink (value);
          }
        }
      }
    }
    g_hash_table_destroy (priv->filename_cache);
  }
  g_hash_table_destroy (priv->checklist_results);
  if (priv->tmpdir) {
    /* Will fail if there are files left, this is expected */
    g_rmdir (priv->tmpdir);
    g_free (priv->tmpdir);
  }

  g_free (test->priv->test_name);
  g_free (test->priv->test_desc);
  g_free (test->priv->test_full_desc);
  g_hash_table_destroy (priv->test_checklist);
  g_hash_table_destroy (priv->test_arguments);
  g_hash_table_destroy (priv->test_extra_infos);
  g_hash_table_destroy (priv->test_output_files);
#ifdef USE_NEW_GLIB_MUTEX_API
  g_mutex_clear (&priv->lock);
  g_mutex_clear (&priv->signal_lock);
  g_cond_clear (&priv->cond);
#else
  g_mutex_free (priv->lock);
  g_mutex_free (priv->signal_lock);
  g_cond_free (priv->cond);
#endif

  g_hash_table_destroy (test->priv->log_levels);

  G_OBJECT_CLASS (insanity_test_parent_class)->finalize (gobject);
}

static void
insanity_test_init (InsanityTest * test)
{
  InsanityTestPrivateData *priv = G_TYPE_INSTANCE_GET_PRIVATE (test,
      INSANITY_TYPE_TEST, InsanityTestPrivateData);
  GValue vdef = { 0 };

  priv->start_time = g_get_monotonic_time ();

#ifdef USE_NEW_GLIB_MUTEX_API
  g_mutex_init (&priv->lock);
  g_mutex_init (&priv->signal_lock);
  g_cond_init (&priv->cond);
#else
  priv->lock = g_mutex_new ();
  priv->signal_lock = g_mutex_new ();
  priv->cond = g_cond_new ();
#endif
  test->priv = priv;
  priv->conn = NULL;
  priv->name = NULL;
  priv->args = NULL;
  priv->cpu_load = -1;
  priv->standalone = TRUE;
  priv->tmpdir = NULL;
  priv->exit = FALSE;
  priv->runlevel = rl_idle;
  priv->filename_cache =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, g_free);
  priv->checklist_results =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, NULL);

  priv->test_name = NULL;
  priv->test_desc = NULL;
  priv->test_full_desc = NULL;
  priv->test_checklist =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free,
      &free_checklist_item);
  priv->test_arguments =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free,
      &free_argument);
  priv->test_extra_infos =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, g_free);
  priv->test_output_files =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free,
      &free_output_file_item);

  test->priv->log_levels = g_hash_table_new (&g_str_hash, &g_str_equal);

  priv->timeout = TEST_TIMEOUT;

  g_value_init (&vdef, G_TYPE_STRING);
  g_value_set_string (&vdef, "1");
  insanity_test_add_argument (test, "log-level",
      "Amount of extra information on stdout",
      "0: no output; 1: info; 2: debug; 3: verbose traces", TRUE, &vdef);
  g_value_unset (&vdef);
}

static gboolean
insanity_signal_stop_accumulator (GSignalInvocationHint * ihint,
    GValue * return_accu, const GValue * handler_return, gpointer data)
{
  gboolean v;

  (void) ihint;
  (void) data;
  v = g_value_get_boolean (handler_return);
  g_value_set_boolean (return_accu, v);
  return v;
}

static void
insanity_test_set_property (GObject * gobject,
    guint prop_id, const GValue * value, GParamSpec * pspec)
{
  InsanityTest *test = (InsanityTest *) gobject;

  LOCK (test);
  switch (prop_id) {
    case PROP_NAME:
      if (test->priv->test_name)
        g_free (test->priv->test_name);
      test->priv->test_name = g_strdup (g_value_get_string (value));
      break;
    case PROP_DESCRIPTION:
      if (test->priv->test_desc)
        g_free (test->priv->test_desc);
      test->priv->test_desc = g_strdup (g_value_get_string (value));
      break;
    case PROP_FULL_DESCRIPTION:
      if (test->priv->test_full_desc)
        g_free (test->priv->test_full_desc);
      test->priv->test_full_desc = g_strdup (g_value_get_string (value));
      break;
    default:
      g_assert_not_reached ();
  }
  UNLOCK (test);
}

static void
insanity_test_get_property (GObject * gobject,
    guint prop_id, GValue * value, GParamSpec * pspec)
{
  InsanityTest *test = (InsanityTest *) gobject;

  LOCK (test);
  switch (prop_id) {
    case PROP_NAME:
      g_value_set_string (value, test->priv->test_name);
      break;
    case PROP_DESCRIPTION:
      g_value_set_string (value, test->priv->test_desc);
      break;
    case PROP_FULL_DESCRIPTION:
      g_value_set_string (value, test->priv->test_full_desc);
      break;
    default:
      g_assert_not_reached ();
  }
  UNLOCK (test);
}

static void
insanity_test_class_init (InsanityTestClass * klass)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);

  gobject_class->finalize = insanity_test_finalize;

  klass->setup = &insanity_test_setup;
  klass->start = &insanity_test_start;
  klass->stop = &insanity_test_stop;
  klass->teardown = &insanity_test_teardown;

  gobject_class->get_property = &insanity_test_get_property;
  gobject_class->set_property = &insanity_test_set_property;

  g_type_class_add_private (klass, sizeof (InsanityTestPrivateData));

  properties[PROP_NAME] =
      g_param_spec_string ("name", "Name", "Name of the test", NULL,
      G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY | G_PARAM_STATIC_STRINGS);
  properties[PROP_DESCRIPTION] =
      g_param_spec_string ("description", "Description",
      "Description of the test", NULL,
      G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY | G_PARAM_STATIC_STRINGS);
  properties[PROP_FULL_DESCRIPTION] =
      g_param_spec_string ("full-description", "Full description",
      "Full description of the test", NULL,
      G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY | G_PARAM_STATIC_STRINGS);

  g_object_class_install_properties (gobject_class, N_PROPERTIES, properties);

  setup_signal = g_signal_new ("setup",
      G_TYPE_FROM_CLASS (gobject_class),
      G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS,
      G_STRUCT_OFFSET (InsanityTestClass, setup),
      &insanity_signal_stop_accumulator, NULL,
      NULL, G_TYPE_BOOLEAN /* return_type */ ,
      0, NULL);
  start_signal = g_signal_new ("start",
      G_TYPE_FROM_CLASS (gobject_class),
      G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS,
      G_STRUCT_OFFSET (InsanityTestClass, start),
      &insanity_signal_stop_accumulator, NULL,
      NULL, G_TYPE_BOOLEAN /* return_type */ ,
      0, NULL);
  stop_signal = g_signal_new ("stop",
      G_TYPE_FROM_CLASS (gobject_class),
      G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS,
      G_STRUCT_OFFSET (InsanityTestClass, stop),
      NULL, NULL, NULL, G_TYPE_NONE /* return_type */ ,
      0, NULL);
  teardown_signal = g_signal_new ("teardown",
      G_TYPE_FROM_CLASS (gobject_class),
      G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS,
      G_STRUCT_OFFSET (InsanityTestClass, teardown),
      NULL, NULL, NULL, G_TYPE_NONE /* return_type */ ,
      0, NULL);
}

/**
 * insanity_test_new:
 * @name: the short name of the test.
 * @description: a one line description of the test.
 * @full_description: (allow-none): an optional longer description of the test.
 *
 * This function creates a new test with the given properties.
 *
 * Returns: (transfer full): a new #InsanityTest instance.
 */
InsanityTest *
insanity_test_new (const char *name, const char *description,
    const char *full_description)
{
  InsanityTest *test;

  g_return_val_if_fail (name != NULL, NULL);
  g_return_val_if_fail (check_valid_label (name), NULL);
  g_return_val_if_fail (description != NULL, NULL);

  if (full_description)
    test = g_object_new (INSANITY_TYPE_TEST,
        "name", name, "description", description, "full-description",
        full_description, NULL);
  else
    test = g_object_new (INSANITY_TYPE_TEST,
        "name", name, "description", description, NULL);
  return test;
}

static void
insanity_add_metadata_entry (GHashTable * hash, const char *label,
    const char *description)
{
  g_hash_table_insert (hash, g_strdup (label), g_strdup (description));
}

/**
 * insanity_test_add_checklist_item:
 * @test: a #InsanityTest instance to operate on.
 * @label: the new checklist item's label
 * @description: a one line description of that item
 * @error_hint: (allow-none): an optional explanatory description of why this error may happen
 * @global: if this is a global item
 *
 * This function adds a checklist item declaration to the test.
 *
 * Checklist items are the individual checklist items that a test can pass or fail
 * using insanity_test_validate_checklist_item().
 */
void
insanity_test_add_checklist_item (InsanityTest * test, const char *label,
    const char *description, const char *error_hint, gboolean global)
{
  ChecklistItem *i;

  g_return_if_fail (INSANITY_IS_TEST (test));
  g_return_if_fail (test->priv->runlevel == rl_idle);
  g_return_if_fail (label != NULL);
  g_return_if_fail (check_valid_label (label));
  g_return_if_fail (description != NULL);
  g_return_if_fail (g_hash_table_lookup (test->priv->test_checklist,
          label) == NULL);

  i = g_slice_new (ChecklistItem);
  i->label = g_strdup (label);
  i->description = g_strdup (description);
  i->likely_error = g_strdup (error_hint);
  i->global = global;

  g_hash_table_insert (test->priv->test_checklist, g_strdup (label), i);
}

/**
 * insanity_test_add_argument:
 * @test: a #InsanityTest instance to operate on.
 * @label: the new argument's label
 * @description: a one line description of that argument
 * @full_description: (allow-none): an optional longer description of that argument
 * @global: if this is a global argument
 * @default_value: the default value for this parameter if not supplied at runtime
 *
 * This function adds an argument declaration to the test.
 *
 * Arguments are parameters which can be passed to the test, and which value
 * may be queried at runtime with insanity_test_get_argument. Arguments may
 * be changed every time a test is started, so should be inspected each time
 * the start function is called.
 *
 * If @global is %TRUE the argument is available in InsanityTest::setup and
 * between InsanityTest::start and InsanityTest::stop and will never change.
 * On the other hand if @global is %FALSE the argument is not available in
 * InsanityTest::setup but between InsanityTest::start and InsanityTest::stop
 * and can have a different value for every call of InsanityTest::start.
 */
void
insanity_test_add_argument (InsanityTest * test, const char *label,
    const char *description, const char *full_description,
    gboolean global, const GValue * default_value)
{
  Argument *arg;

  g_return_if_fail (INSANITY_IS_TEST (test));
  g_return_if_fail (test->priv->runlevel == rl_idle);
  g_return_if_fail (label != NULL);
  g_return_if_fail (check_valid_label (label));
  g_return_if_fail (g_hash_table_lookup (test->priv->test_arguments,
          label) == NULL);
  g_return_if_fail (g_hash_table_lookup (test->priv->test_output_files,
          label) == NULL);
  g_return_if_fail (description != NULL);
  g_return_if_fail (G_IS_VALUE (default_value));
  g_return_if_fail (check_valid_type (G_VALUE_TYPE (default_value)));

  arg = g_slice_alloc0 (sizeof (Argument));
  arg->global = global;
  arg->description = g_strdup (description);
  arg->full_description = full_description ? g_strdup (full_description) : NULL;
  g_value_init (&arg->default_value, G_VALUE_TYPE (default_value));
  g_value_copy (default_value, &arg->default_value);    /* Source is first */
  g_hash_table_insert (test->priv->test_arguments, g_strdup (label), arg);
}

/**
 * insanity_test_add_extra_info:
 * @test: a #InsanityTest instance to operate on.
 * @label: the new extra info's label
 * @description: a one line description of that extra info
 *
 * This function adds an extra info declaration to the test.
 *
 * Extra infos are test specific data that a test can signal to
 * the caller using insanity_test_add_extra_info.
 */
void
insanity_test_add_extra_info (InsanityTest * test, const char *label,
    const char *description)
{
  g_return_if_fail (INSANITY_IS_TEST (test));
  g_return_if_fail (label != NULL);
  g_return_if_fail (check_valid_label (label));
  g_return_if_fail (g_hash_table_lookup (test->priv->test_extra_infos,
          label) == NULL);
  g_return_if_fail (description != NULL);

  insanity_add_metadata_entry (test->priv->test_extra_infos, label,
      description);
}

/**
 * insanity_test_add_output_file:
 * @test: a #InsanityTest instance to operate on.
 * @label: the new output file's label
 * @description: a one line description of that file's purpose
 * @global: %TRUE if the filename should be shared among iterations, %FALSE otherwise
 *
 * This function adds an output file declaration to the test.
 *
 * Output files will be named automatically for the test's use.
 * A test can obtain the filename assigned to an output file
 * using insanity_test_get_output_filename, open it, and write
 * to it. After the test has finished, these files will be
 * either collected, deleted, or left for the user as requested.
 * A global output file will keep the same name for all invocations,
 * whereas a non global one will have a different name for each
 * invokation.
 */
void
insanity_test_add_output_file (InsanityTest * test, const char *label,
    const char *description, gboolean global)
{
  OutputFileItem *of;

  g_return_if_fail (INSANITY_IS_TEST (test));
  g_return_if_fail (label != NULL);
  g_return_if_fail (check_valid_label (label));
  g_return_if_fail (g_hash_table_lookup (test->priv->test_output_files,
          label) == NULL);
  g_return_if_fail (g_hash_table_lookup (test->priv->test_arguments,
          label) == NULL);
  g_return_if_fail (description != NULL);

  of = g_slice_new (OutputFileItem);
  of->description = g_strdup (description);
  of->global = global;

  g_hash_table_insert (test->priv->test_output_files, g_strdup (label), of);
}

/**
 * insanity_test_check:
 * @test: a #InsanityTest instance to operate on.
 * @label: a checklist item label
 * @expr: an expression which should evaluate to FALSE (failed) or TRUE (passed)
 * @msg: a printf(3) format string, followed by optional arguments as per printf(3)
 * @...: the parameters to insert into the format string
 *
 * This function checks whether an expression evaluates to 0 or not,
 * and, if false, invalidates the "insanity-check" checklist item.
 * If all checks pass, or not checks are done, this checklist item wil be
 * automatically validated at the end of a test.
 *
 * A checklist item label must specified, it must be one of the checklist items that were
 * predefined.
 *
 * There are macros (only one at the moment, INSANITY_TEST_CHECK) which are higher
 * level than this function, and may be more suited to call instead.
 *
 * Returns: the value of the expression, as a convenience.
 */
gboolean
insanity_test_check (InsanityTest * test, const char *label, gboolean expr,
    const char *msg, ...)
{
  char *fullmsg;
  va_list ap;

  g_return_val_if_fail (INSANITY_IS_TEST (test), FALSE);
  g_return_val_if_fail (label != NULL, FALSE);
  g_return_val_if_fail (check_valid_label (label), FALSE);
  g_return_val_if_fail (g_hash_table_lookup (test->priv->test_checklist,
          label) != NULL, FALSE);

  if (!expr) {
    va_start (ap, msg);
    fullmsg = g_strdup_vprintf (msg, ap);
    va_end (ap);
    insanity_test_validate_checklist_item (test, label, FALSE, fullmsg);
    g_free (fullmsg);
  }
  return expr;
}

static InsanityLogLevel
find_log_level (InsanityTest * test, const char *category)
{
  gpointer p;

  if (g_hash_table_lookup_extended (test->priv->log_levels, category, NULL, &p)) {
    printf ("category '%s' has log level %u\n", category, (InsanityLogLevel) p);
    return (InsanityLogLevel) p;
  }
  return test->priv->default_log_level;
}

/**
 * insanity_test_logv:
 * @test: a #InsanityTest instance to operate on.
 * @category: a debug category
 * @level: log level of this log
 * @file: the filename where the log call is located
 * @line: the line number in that file where the log call is located
 * @format: a printf(3) format string, followed by optional arguments as per printf(3)
 * @args: the parameters to insert into the format string
 *
 * This function outputs messages on stdout when some conditions are met.
 * The semantics of these messages may be debugging, or informative, but
 * which are not intended to be stored. If you want a message to be stored,
 * use a extra-info string for this.
 *
 * Currently, the output conditions are:
 *  - the test is running in standalone mode
 *  - the log-level property is set to higher or equal to the log's level
 *
 * These conditions may change to match a "when it makes sense" ideal.
 */
void
insanity_test_logv (InsanityTest * test, const char *category,
    InsanityLogLevel level, const char *file, unsigned int line,
    const char *format, va_list args)
{
  guint64 dt;
  gchar *msg;

  g_return_if_fail (INSANITY_IS_TEST (test));
  g_return_if_fail (check_valid_label (category));

  if (level == INSANITY_LOG_LEVEL_NONE)
    return;
  if (level > find_log_level (test, category))
    return;

  dt = g_get_monotonic_time () - test->priv->start_time;

  msg = g_strdup_vprintf (format, args);

  g_printerr ("%" TIME_FORMAT "\t%p\t%s\t%s\t%s:%u\t%s",
      TIME_ARGS (dt), g_thread_self (), log_level_names[level], category, file,
      line, msg);

  g_free (msg);
}

/**
 * insanity_test_log:
 * @test: a #InsanityTest instance to operate on.
 * @category: a debug category
 * @level: log level of this log
 * @file: the filename where the log call is located
 * @line: the line number in that file where the log call is located
 * @format: a printf(3) format string, followed by optional arguments as per printf(3)
 * @...: the parameters to insert into the format string
 *
 * This function outputs messages on stdout when some conditions are met.
 * The semantics of these messages may be debugging, or informative, but
 * which are not intended to be stored. If you want a message to be stored,
 * use a extra-info string for this.
 *
 * Currently, the output conditions are:
 *  - the test is running in standalone mode
 *  - the log-level property is set to higher or equal to the log's level
 *
 * These conditions may change to match a "when it makes sense" ideal.
 */
void
insanity_test_log (InsanityTest * test, const char *category,
    InsanityLogLevel level, const char *file, unsigned int line,
    const char *format, ...)
{
  va_list ap;

  va_start (ap, format);
  insanity_test_logv (test, category, level, file, line, format, ap);
  va_end (ap);
}

void
insanity_test_add_string_argument (InsanityTest * test, const char *label,
    const char *description, const char *full_description, gboolean global,
    const char *default_value)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_STRING);
  g_value_set_string (&v, default_value);
  insanity_test_add_argument (test, label, description, full_description,
      global, &v);
  g_value_unset (&v);
}

void
insanity_test_add_int_argument (InsanityTest * test, const char *label,
    const char *description, const char *full_description, gboolean global,
    gint default_value)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_INT);
  g_value_set_int (&v, default_value);
  insanity_test_add_argument (test, label, description, full_description,
      global, &v);
  g_value_unset (&v);
}

void
insanity_test_add_uint_argument (InsanityTest * test, const char *label,
    const char *description, const char *full_description, gboolean global,
    guint default_value)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_UINT);
  g_value_set_uint (&v, default_value);
  insanity_test_add_argument (test, label, description, full_description,
      global, &v);
  g_value_unset (&v);
}

void
insanity_test_add_int64_argument (InsanityTest * test, const char *label,
    const char *description, const char *full_description, gboolean global,
    gint64 default_value)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_INT64);
  g_value_set_int64 (&v, default_value);
  insanity_test_add_argument (test, label, description, full_description,
      global, &v);
  g_value_unset (&v);
}

void
insanity_test_add_uint64_argument (InsanityTest * test, const char *label,
    const char *description, const char *full_description, gboolean global,
    guint64 default_value)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_UINT64);
  g_value_set_uint64 (&v, default_value);
  insanity_test_add_argument (test, label, description, full_description,
      global, &v);
  g_value_unset (&v);
}

void
insanity_test_add_double_argument (InsanityTest * test, const char *label,
    const char *description, const char *full_description, gboolean global,
    gdouble default_value)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_DOUBLE);
  g_value_set_double (&v, default_value);
  insanity_test_add_argument (test, label, description, full_description,
      global, &v);
  g_value_unset (&v);
}

void
insanity_test_add_boolean_argument (InsanityTest * test, const char *label,
    const char *description, const char *full_description, gboolean global,
    gboolean default_value)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_BOOLEAN);
  g_value_set_boolean (&v, default_value);
  insanity_test_add_argument (test, label, description, full_description,
      global, &v);
  g_value_unset (&v);
}

gboolean
insanity_test_get_string_argument (InsanityTest * test, const char *label,
    char **value)
{
  GValue v = { 0 };
  gboolean ret = FALSE;

  ret = insanity_test_get_argument (test, label, &v);
  if (!ret)
    goto done;
  if (!G_VALUE_HOLDS_STRING (&v)) {
    ret = FALSE;
    goto done;
  }

  *value = g_value_dup_string (&v);
  ret = TRUE;

done:
  g_value_unset (&v);
  return ret;
}

gboolean
insanity_test_get_int_argument (InsanityTest * test, const char *label,
    gint * value)
{
  GValue v = { 0 };
  gboolean ret = FALSE;

  ret = insanity_test_get_argument (test, label, &v);
  if (!ret)
    goto done;
  if (!G_VALUE_HOLDS_INT (&v)) {
    ret = FALSE;
    goto done;
  }

  *value = g_value_get_int (&v);
  ret = TRUE;

done:
  g_value_unset (&v);
  return ret;
}

gboolean
insanity_test_get_uint_argument (InsanityTest * test, const char *label,
    guint * value)
{
  GValue v = { 0 };
  gboolean ret = FALSE;

  ret = insanity_test_get_argument (test, label, &v);
  if (!ret)
    goto done;
  if (!G_VALUE_HOLDS_UINT (&v)) {
    ret = FALSE;
    goto done;
  }

  *value = g_value_get_uint (&v);
  ret = TRUE;

done:
  g_value_unset (&v);
  return ret;
}

gboolean
insanity_test_get_int64_argument (InsanityTest * test, const char *label,
    gint64 * value)
{
  GValue v = { 0 };
  gboolean ret = FALSE;

  ret = insanity_test_get_argument (test, label, &v);
  if (!ret)
    goto done;
  if (!G_VALUE_HOLDS_INT64 (&v)) {
    ret = FALSE;
    goto done;
  }

  *value = g_value_get_int64 (&v);
  ret = TRUE;

done:
  g_value_unset (&v);
  return ret;
}

gboolean
insanity_test_get_uint64_argument (InsanityTest * test, const char *label,
    guint64 * value)
{
  GValue v = { 0 };
  gboolean ret = FALSE;

  ret = insanity_test_get_argument (test, label, &v);
  if (!ret)
    goto done;
  if (!G_VALUE_HOLDS_UINT64 (&v)) {
    ret = FALSE;
    goto done;
  }

  *value = g_value_get_uint64 (&v);
  ret = TRUE;

done:
  g_value_unset (&v);
  return ret;
}

gboolean
insanity_test_get_double_argument (InsanityTest * test, const char *label,
    gdouble * value)
{
  GValue v = { 0 };
  gboolean ret = FALSE;

  ret = insanity_test_get_argument (test, label, &v);
  if (!ret)
    goto done;
  if (!G_VALUE_HOLDS_DOUBLE (&v)) {
    ret = FALSE;
    goto done;
  }

  *value = g_value_get_double (&v);
  ret = TRUE;

done:
  g_value_unset (&v);
  return ret;
}

gboolean
insanity_test_get_boolean_argument (InsanityTest * test, const char *label,
    gboolean * value)
{
  GValue v = { 0 };
  gboolean ret = FALSE;

  ret = insanity_test_get_argument (test, label, &v);
  if (!ret)
    goto done;
  if (!G_VALUE_HOLDS_BOOLEAN (&v)) {
    ret = FALSE;
    goto done;
  }

  *value = g_value_get_boolean (&v);
  ret = TRUE;

done:
  g_value_unset (&v);
  return ret;
}

void
insanity_test_set_string_extra_info (InsanityTest * test, const char *label,
    const char *data)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_STRING);
  g_value_set_string (&v, data);
  insanity_test_set_extra_info (test, label, &v);
  g_value_unset (&v);
}

void
insanity_test_set_int_extra_info (InsanityTest * test, const char *label,
    gint data)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_INT);
  g_value_set_int (&v, data);
  insanity_test_set_extra_info (test, label, &v);
  g_value_unset (&v);
}

void
insanity_test_set_uint_extra_info (InsanityTest * test, const char *label,
    guint data)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_UINT);
  g_value_set_uint (&v, data);
  insanity_test_set_extra_info (test, label, &v);
  g_value_unset (&v);
}

void
insanity_test_set_int64_extra_info (InsanityTest * test, const char *label,
    gint64 data)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_INT64);
  g_value_set_int64 (&v, data);
  insanity_test_set_extra_info (test, label, &v);
  g_value_unset (&v);
}

void
insanity_test_set_uint64_extra_info (InsanityTest * test, const char *label,
    guint64 data)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_UINT64);
  g_value_set_uint64 (&v, data);
  insanity_test_set_extra_info (test, label, &v);
  g_value_unset (&v);
}

void
insanity_test_set_double_extra_info (InsanityTest * test, const char *label,
    gdouble data)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_DOUBLE);
  g_value_set_double (&v, data);
  insanity_test_set_extra_info (test, label, &v);
  g_value_unset (&v);
}

void
insanity_test_set_boolean_extra_info (InsanityTest * test, const char *label,
    gboolean data)
{
  GValue v = { 0 };

  g_value_init (&v, G_TYPE_BOOLEAN);
  g_value_set_boolean (&v, data);
  insanity_test_set_extra_info (test, label, &v);
  g_value_unset (&v);
}
