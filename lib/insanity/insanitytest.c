/* Insanity QA system

       insanity.c

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
 Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 Boston, MA 02111-1307, USA.
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

#include <insanity/insanitytest.h>

#include <glib/gstdio.h>
#include <dbus/dbus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <errno.h>

/* TODO:
  - logs ?
  - gather timings at every step validated ?
  - implement timeouts
*/

#ifdef USE_CPU_LOAD
#include <sys/time.h>
#include <sys/resource.h>
#endif

enum
{
  PROP_0,
  PROP_NAME,
  PROP_DESC,
  PROP_FULL_DESC,
  N_PROPERTIES
};

/* if global vars are good enough for gstreamer, it's good enough for insanity */
static guint setup_signal;
static guint start_signal;
static guint stop_signal;
static guint test_signal;
static guint teardown_signal;
static GParamSpec *properties[N_PROPERTIES] = { NULL, };

#if GLIB_CHECK_VERSION(2,30,2)
#define USE_NEW_GLIB_MUTEX_API
#endif

#ifdef USE_NEW_GLIB_MUTEX_API
#define LOCK(test) g_mutex_lock(&((test)->priv->lock))
#define UNLOCK(test) g_mutex_unlock(&((test)->priv->lock))
#else
#define LOCK(test) g_mutex_lock((test)->priv->lock)
#define UNLOCK(test) g_mutex_unlock((test)->priv->lock)
#endif

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
  gboolean done;
  gboolean exit;
  GHashTable *filename_cache;
  char *tmpdir;
#ifdef USE_NEW_GLIB_MUTEX_API
  GMutex lock;
#else
  GMutex *lock;
#endif
  gboolean standalone;
  GHashTable *checklist_results;

  /* test metadata */
  char *test_name;
  char *test_desc;
  char *test_full_desc;
  GHashTable *test_checklist;
  GHashTable *test_arguments;
  GHashTable *test_extra_infos;
  GHashTable *test_output_files;
  GHashTable *test_likely_errors;
};

typedef struct Argument {
  char *description;
  GValue default_value;
  char *full_description;
} Argument;

static void
free_argument (void *ptr)
{
  Argument *arg = (Argument *)ptr;

  g_free(arg->description);
  g_value_unset(&arg->default_value);
  g_free(arg->full_description);
  g_slice_free1 (sizeof (Argument), ptr);
}

static void
insanity_cclosure_marshal_BOOLEAN__VOID (GClosure * closure,
    GValue * return_value G_GNUC_UNUSED,
    guint n_param_values,
    const GValue * param_values,
    gpointer invocation_hint G_GNUC_UNUSED, gpointer marshal_data)
{
  typedef gboolean (*GMarshalFunc_BOOLEAN__VOID) (gpointer data1,
      gpointer data2);
  register GMarshalFunc_BOOLEAN__VOID callback;
  register GCClosure *cc = (GCClosure *) closure;
  register gpointer data1, data2;
  gboolean v_return;

  g_return_if_fail (return_value != NULL);
  g_return_if_fail (n_param_values == 1);

  if (G_CCLOSURE_SWAP_DATA (closure)) {
    data1 = closure->data;
    data2 = g_value_peek_pointer (param_values + 0);
  } else {
    data1 = g_value_peek_pointer (param_values + 0);
    data2 = closure->data;
  }
  callback =
      (GMarshalFunc_BOOLEAN__VOID) (marshal_data ? marshal_data : cc->callback);

  v_return = callback (data1, data2);

  g_value_set_boolean (return_value, v_return);
}

static gboolean
insanity_test_setup (InsanityTest * test)
{
  (void) test;
  printf ("insanity_test_setup\n");
  return TRUE;
}

static gboolean
insanity_test_start (InsanityTest * test)
{
  (void) test;
  printf ("insanity_test_start\n");
  return TRUE;
}

static void
insanity_test_stop (InsanityTest * test)
{
  (void) test;
  printf ("insanity_test_stop\n");
}

static void
insanity_test_teardown (InsanityTest * test)
{
  (void) test;
  printf ("insanity_test_teardown\n");
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
static const char *introspect_response_template =
  "<!DOCTYPE node PUBLIC \"-//freedesktop//DTD D-BUS Object Introspection 1.0//EN\" "
  "\"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd\">\n"
  "<node name=\"/net/gstreamer/Insanity/Test/Test%s\">\n"
  "  <interface name=\"org.freedesktop.DBus.Introspectable\">\n"
  "    <method name=\"Introspect\">\n"
  "      <arg direction=\"out\" type=\"s\" />\n"
  "    </method>\n"
  "  </interface>\n"
  "  <interface name=\"" INSANITY_TEST_INTERFACE "\">\n"
  "    <method name=\"remoteSetUp\"> </method>\n"
  "    <method name=\"remoteStart\"> <arg direction=\"in\" type=\"a{sv}\" /> </method>\n"
  "    <method name=\"remoteStop\"> </method>\n"
  "    <method name=\"remoteTearDown\"> </method>\n"
  "  </interface>\n"
  "</node>\n";

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
    fprintf (stderr, "Message Null\n");
    return FALSE;
  }
  if (type != DBUS_TYPE_INVALID) {
    va_start (ap, type);
    if (!dbus_message_append_args_valist (msg, type, ap)) {
      fprintf (stderr, "Out Of Memory!\n");
      va_end (ap);
      dbus_message_unref (msg);
      return FALSE;
    }
    va_end (ap);
  }
  if (!dbus_connection_send (conn, msg, &serial)) {
    fprintf (stderr, "Out Of Memory!\n");
    dbus_message_unref (msg);
    return FALSE;
  }
  dbus_connection_flush (conn);

  dbus_message_unref (msg);

  return TRUE;
}

/**
 * insanity_test_validate_step:
 * @test: a #InsanityTest to operate on
 * @name: the name of the step
 * @success: whether the step passed, or failed
 * @description: (allow-none): optional description string
 *
 * Declares a given step as either passed, or failed.
 * An optional description may be given to supply more information
 * about the reason for a particular failure.
 */
void
insanity_test_validate_step (InsanityTest * test, const char *name,
    gboolean success, const char *description)
{
  gboolean *b;

  LOCK (test);
  if (test->priv->standalone) {
    if (description) {
      printf("step: %s: %s (%s)\n", name, success ? "PASS" : "FAIL",
          description);
    }
    else {
      printf("step: %s: %s\n", name, success ? "PASS" : "FAIL");
    }
  }
  else {
    const char *desc = description ? description : "";
    send_signal (test->priv->conn, "remoteValidateStepSignal", test->priv->name,
        DBUS_TYPE_STRING, &name, DBUS_TYPE_BOOLEAN, &success,
        DBUS_TYPE_STRING, &desc, DBUS_TYPE_INVALID);
  }

  b = g_malloc (sizeof (gboolean));
  *b = success;
  g_hash_table_insert (test->priv->checklist_results, g_strdup (name), b);
  UNLOCK (test);
}

static void
insanity_test_set_extra_info_internal (InsanityTest * test, const char *name,
    const GValue * data, gboolean locked)
{
  GType glib_type;
  int dbus_type;
  dbus_int32_t int32_value;
  dbus_int64_t int64_value;
  const char *string_value;
  void *dataptr = NULL;

  if (!locked)
    LOCK (test);

  if (test->priv->standalone) {
    char *s = g_strdup_value_contents (data);
    printf("Extra info: %s: %s\n", name, s);
    g_free (s);
    if (!locked)
      UNLOCK (test);
    return;
  }

  glib_type = G_VALUE_TYPE (data);
  if (glib_type == G_TYPE_INT) {
    int32_value = g_value_get_int (data);
    dbus_type = DBUS_TYPE_INT32;
    dataptr = &int32_value;
  } else if (glib_type == G_TYPE_INT64) {
    int64_value = g_value_get_int64 (data);
    dbus_type = DBUS_TYPE_INT64;
    dataptr = &int64_value;
  } else if (glib_type == G_TYPE_STRING) {
    string_value = g_value_get_string (data);
    dbus_type = DBUS_TYPE_STRING;
    dataptr = &string_value;
  } else {
    /* Add more if needed, there doesn't seem to be a glib "glib to dbus" conversion public API,
       but if I missed one, it could replace the above. */
  }

  if (dataptr) {
    send_signal (test->priv->conn, "remoteExtraInfoSignal", test->priv->name,
        DBUS_TYPE_STRING, &name, dbus_type, dataptr, DBUS_TYPE_INVALID);
  } else {
    char *s = g_strdup_value_contents (data);
    fprintf (stderr, "Unsupported extra info: %s\n", s);
    g_free (s);
  }

  if (!locked)
    UNLOCK (test);
}

/**
 * insanity_test_set_extra_info:
 * @test: a #InsanityTest to operate on
 * @name: a label for the extra information
 * @data: the extra information
 *
 * Allows a test to supply any relevant information of interest.
 * As an example, Insanity uses this system to record the CPU load
 * used by a given test, the data here being an integer.
 */
void
insanity_test_set_extra_info (InsanityTest * test, const char *name,
    const GValue * data)
{
  insanity_test_set_extra_info_internal (test, name, data, FALSE);
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
  LOCK (test);
  if (!test->priv->standalone) {
    send_signal (test->priv->conn, "remoteStopSignal", test->priv->name,
        DBUS_TYPE_INVALID);
  }
  test->priv->done = TRUE;
  UNLOCK (test);
}

static gboolean
on_setup (InsanityTest * test)
{
  gboolean ret = TRUE;

  g_signal_emit (test, setup_signal, 0, &ret);

  LOCK (test);
  insanity_test_record_start_time (test);
  UNLOCK (test);

  if (!test->priv->standalone) {
    if (!ret) {
      send_signal (test->priv->conn, "remoteStopSignal", test->priv->name,
          DBUS_TYPE_INVALID);
    } else {
      send_signal (test->priv->conn, "remoteReadySignal", test->priv->name,
          DBUS_TYPE_INVALID);
    }
  }

  return ret;
}

static gboolean
on_start (InsanityTest * test)
{
  gboolean ret = TRUE;

  g_signal_emit (test, start_signal, 0, &ret);
  return ret;
}

static void
on_stop (InsanityTest * test)
{
  g_signal_emit (test, stop_signal, 0, NULL);

  if (!test->priv->standalone) {
    send_signal (test->priv->conn, "remoteReadySignal", test->priv->name,
        DBUS_TYPE_INVALID);
  }
}

static void
on_teardown (InsanityTest * test)
{
  LOCK (test);
  gather_end_of_test_info (test);
  UNLOCK (test);

  g_signal_emit (test, teardown_signal, 0, NULL);

  LOCK (test);
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
  DBusMessageIter array_value;
  int type;
  int ret;
  void *ptr;

  type = dbus_message_iter_get_arg_type (iter);
  if (type != DBUS_TYPE_ARRAY) {
    fprintf (stderr, "Expected array, got %c\n", type);
    return -1;
  }
  dbus_message_iter_recurse (iter, &subiter);
  do {
    type = dbus_message_iter_get_arg_type (&subiter);
    if (type != DBUS_TYPE_DICT_ENTRY) {
      fprintf (stderr, "Expected dict entry, got %c\n", type);
      return -1;
    }
    dbus_message_iter_recurse (&subiter, &subsubiter);

    type = dbus_message_iter_get_arg_type (&subsubiter);
    if (type != DBUS_TYPE_STRING) {
      fprintf (stderr, "Expected string, got %c\n", type);
      return -1;
    }
    dbus_message_iter_get_basic (&subsubiter, &key);
    if (!dbus_message_iter_next (&subsubiter)) {
      fprintf (stderr, "Value not present\n");
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
          fprintf (stderr, "Unsupported type: %c\n", type);
          return -1;
          break;
      }
    } else {
      fprintf (stderr, "Expected variant, got %c\n", type);
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
output_filename_converter (const char *key, const GValue * value, guintptr userdata)
{
  InsanityTest *test = (InsanityTest *)userdata;

  if (G_VALUE_TYPE (value) != G_TYPE_STRING) {
    fprintf (stderr, "Output filename %s is not a string, ignored\n", key);
    return 0;
  }

  g_hash_table_insert (test->priv->filename_cache, g_strdup (key), g_value_dup_string (value));
  return 0;
}

static int
arg_converter (const char *key, const GValue * value, guintptr userdata)
{
  InsanityTest *test = (InsanityTest *)userdata;
  const Argument *arg;
  GValue *v;

  /* outputfiles is special, a list of key/values */
  if (!strcmp (key, "outputfiles")) {
    DBusMessageIter *array;
    if (G_VALUE_TYPE (value) != G_TYPE_POINTER) {
      return 0;
    }

    array = (DBusMessageIter *) g_value_get_pointer (value);
    foreach_dbus_array (array, &output_filename_converter, userdata);
    return 0;
  }

  arg = g_hash_table_lookup (test->priv->test_arguments, key);
  if (!arg) {
    /* fprintf (stderr, "Key '%s' is not a declared argument, ignored\n", key); */
    return 0;
  }
  if (G_VALUE_TYPE (value) != G_VALUE_TYPE (&arg->default_value)) {
    fprintf (stderr, "Key '%s' does not have the expected type\n", key);
    return -1;
  }

  v = g_slice_alloc0 (sizeof (GValue));
  g_value_init (v, G_VALUE_TYPE (value));
  g_value_copy (value, v); /* src first */
  g_hash_table_insert (test->priv->args, g_strdup (key), v);
  return 0;
}

static void
free_gvalue (void *ptr)
{
  GValue *v = (GValue*)ptr;

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

  if (msg) {
    int ret;
    DBusMessageIter iter;

    dbus_message_iter_init (msg, &iter);

    test->priv->args = g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, &free_gvalue);
    ret = foreach_dbus_array (&iter, &arg_converter, (guintptr) test);
    if (ret <= 0) {
      UNLOCK (test);
      return;
    }
  }

  UNLOCK (test);
}

/**
 * insanity_test_get_argument:
 * @test: a #InsanityTest to operate on
 * @key: the name of the argument to retrieve
 * @value: (out caller-allocates): a pointer to a value to receive the contents of the argument
 *
 * Returns: TRUE if the argument was found (in which case the value
 * is initialized and contains its value), FALSE otherwise (in which
 * case the value is left untouched).
 */
gboolean
insanity_test_get_argument (InsanityTest * test, const char *key,
    GValue * value)
{
  const Argument *arg;
  const GValue *v;
  gboolean ret = FALSE;

  if (test->priv->args) {
    v = g_hash_table_lookup (test->priv->args, key);
    if (v) {
      g_value_init (value, G_VALUE_TYPE (v));
      g_value_copy (v, value);
      ret = TRUE;
    }
  }

  if (!ret) {
    arg = g_hash_table_lookup (test->priv->test_arguments, key);
    if (arg) {
      g_value_init (value, G_VALUE_TYPE (&arg->default_value));
      g_value_copy (&arg->default_value, value);
      ret = TRUE;
    }
  }

  if (!ret) {
    fprintf (stderr, "Argument %s not found\n", key);
  }

  UNLOCK (test);

  return ret;
}

/**
 * insanity_test_get_output_filename:
 * @test: a #InsanityTest to operate on
 * @key: the label of the filename to retrieve
 *
 * Returns: the filename associated to the key, or NULL if none.
 */
const char *
insanity_test_get_output_filename (InsanityTest * test, const char *key)
{
  gpointer ptr;
  char *fn = NULL;

  LOCK (test);

  ptr = g_hash_table_lookup (test->priv->filename_cache, key);
  if (ptr) {
    fn = ptr;
  }

  else if (test->priv->standalone) {
    char *template;
    int fd;

    if (!test->priv->tmpdir) {
      GError *error = NULL;
      test->priv->tmpdir = g_dir_make_tmp (NULL, &error);
      if (error)
        g_error_free (error);
      if (!test->priv->tmpdir) {
        fprintf (stderr, "Failed to create temporary directory\n");
        UNLOCK (test);
        return NULL;
      }
    }

    template = g_strdup_printf ("%s/insanity-standalone-XXXXXX", test->priv->tmpdir);
    fd = g_mkstemp (template);
    if (fd < 0) {
      fprintf (stderr, "Failed creating temporary file %s: %s\n",
          template, strerror (errno));
      fn = NULL;
      g_free (template);
    }
    else {
      fn = template;
      g_hash_table_insert (test->priv->filename_cache, g_strdup (key), fn);
    }
  }

  UNLOCK (test);

  return fn;
}

static void
insanity_test_dbus_handler_remoteSetup (InsanityTest * test, DBusMessage * msg)
{
  on_setup (test);
}

static void
insanity_test_dbus_handler_remoteStart (InsanityTest * test, DBusMessage * msg)
{
  insanity_test_set_args (test, msg);
  on_start (test);
}

static void
insanity_test_dbus_handler_remoteStop (InsanityTest * test, DBusMessage * msg)
{
  (void) msg;
  on_stop (test);
}

static void
insanity_test_dbus_handler_remoteTearDown (InsanityTest * test, DBusMessage * msg)
{
  (void) msg;
  on_teardown (test);
}

static const struct
{
  const char *method;
  void (*handler) (InsanityTest *, DBusMessage *);
} dbus_test_handlers[] = {
  { "remoteSetUp", &insanity_test_dbus_handler_remoteSetup },
  { "remoteStart", &insanity_test_dbus_handler_remoteStart },
  { "remoteStop", &insanity_test_dbus_handler_remoteStop },
  { "remoteTearDown", &insanity_test_dbus_handler_remoteTearDown },
};

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
      if (!dbus_connection_send (test->priv->conn, reply, &serial)) {
        fprintf (stderr, "Out Of Memory!\n");
      }
      else {
        dbus_connection_flush (test->priv->conn);
      }
      dbus_message_unref (reply);

      if (dbus_test_handlers[n].handler)
        (*dbus_test_handlers[n].handler) (test, msg);
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
    fprintf (stderr, "Connection Error (%s)\n", err.message);
    dbus_error_free (&err);
    return FALSE;
  }
  if (NULL == conn) {
    fprintf (stderr, "Connection Null\n");
    return FALSE;
  }

  ret = dbus_bus_register (conn, &err);
  if (dbus_error_is_set (&err)) {
    fprintf (stderr, "Failed to register bus (%s)\n", err.message);
    dbus_error_free (&err);
    /* Is this supposed to be fatal ? */
  }
  /* request our name on the bus and check for errors */
  object_name = g_strdup_printf (INSANITY_TEST_INTERFACE ".Test%s", uuid);
  ret =
      dbus_bus_request_name (conn, object_name, DBUS_NAME_FLAG_REPLACE_EXISTING,
      &err);
  if (dbus_error_is_set (&err)) {
    fprintf (stderr, "Name Error (%s)\n", err.message);
    dbus_error_free (&err);
    /* Is this supposed to be fatal ? */
  }
  if (DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER != ret) {
    fprintf (stderr, "Not Primary Owner (%d)\n", ret);
    return FALSE;
  }

  insanity_test_connect (test, conn, uuid);

  /* loop, testing for new messages */
  test->priv->done = FALSE;
  test->priv->exit = FALSE;
  while (1) {
    /* barely blocking update of dbus */
    dbus_connection_read_write (conn, 10);

    if (test->priv->exit)
      break;

    /* see if we have a message to handle */
    msg = dbus_connection_pop_message (conn);
    if (NULL == msg) {
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
          malloc (strlen (introspect_response_template) + strlen (uuid) + 1);
      sprintf (introspect_response, introspect_response_template, uuid);
      reply = dbus_message_new_method_return (msg);
      dbus_message_iter_init_append (reply, &args);
      if (!dbus_message_iter_append_basic (&args, DBUS_TYPE_STRING,
              &introspect_response)) {
        fprintf (stderr, "Out Of Memory!\n");
        dbus_message_unref (reply);
        goto msg_error;
      }
      free (introspect_response);
      if (!dbus_connection_send (conn, reply, &serial)) {
        fprintf (stderr, "Out Of Memory!\n");
        dbus_message_unref (reply);
        goto msg_error;
      }
      dbus_connection_flush (conn);
      dbus_message_unref (reply);
    } else if (!strcmp (dbus_message_get_interface (msg),
            INSANITY_TEST_INTERFACE)) {
      insanity_call_interface (test, msg);
    } else {
      /*printf("Got unhandled method call: interface %s, method %s\n", dbus_message_get_interface(msg), dbus_message_get_member(msg));*/
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
    const char *name, const char * (*getname)(void*))
{
  GHashTableIter it;
  const char *label, *comma = "";
  void *data;

  if (g_hash_table_size (table) == 0)
    return;

  fprintf (f, ",\n  \"%s\": {\n", name);
  g_hash_table_iter_init (&it, table);
  while (g_hash_table_iter_next (&it, (gpointer) & label, (gpointer) & data)) {
    fprintf (f, "%s    \"%s\" : \"%s\"", comma, label, (*getname)(data));
    comma = ",\n";
  }
  fprintf (f, "\n  }", name);
}

static const char *
get_raw_string (void *ptr)
{
  return ptr;
}

static const char *
get_argument_desc (void *ptr)
{
  return ((Argument *)ptr)->description;
}

static void
insanity_test_write_metadata (InsanityTest * test)
{
  FILE *f = stdout;
  char *name, *desc;

  g_object_get (G_OBJECT (test), "name", &name, NULL);
  g_object_get (G_OBJECT (test), "desc", &desc, NULL);

  fprintf (f, "Insanity test metadata:\n");
  fprintf (f, "{\n");
  fprintf (f, "  \"__name__\": \"%s\",\n", name);
  fprintf (f, "  \"__description__\": \"%s\"", desc);
  output_table (test, f, test->priv->test_checklist, "__checklist__", &get_raw_string);
  output_table (test, f, test->priv->test_arguments, "__arguments__", &get_argument_desc);
  output_table (test, f, test->priv->test_extra_infos, "__extra_infos__", &get_raw_string);
  output_table (test, f, test->priv->test_output_files, "__output_files__", &get_raw_string);
  output_table (test, f, test->priv->test_likely_errors, "__likely_errors__", &get_raw_string);
  fprintf (f, "\n}\n");

  g_free (name);
  g_free (desc);
}

static void
usage (const char *argv0)
{
  fprintf (stderr, "Usage: %s [--insanity-metadata | --run [name=value]... | <uuid>]\n", argv0);
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
  static const char *true_values[] = {"1", "true", NULL};
  return find_string (string_value, true_values);
}

static gboolean
is_false (const char *string_value)
{
  static const char *false_values[] = {"0", "false", NULL};
  return find_string (string_value, false_values);
}

static gboolean
parse_value (InsanityTest *test, const char *key, const char *string_value, GValue *value)
{
  const Argument *arg;
  GType type;

  arg = g_hash_table_lookup (test->priv->test_arguments, key);
  if (arg) {
    type = G_VALUE_TYPE (&arg->default_value);
    if (type == G_TYPE_STRING) {
      g_value_init (value, G_TYPE_STRING);
      g_value_set_string (value, string_value);
      return TRUE;
    }
    else if (type == G_TYPE_INT) {
      char *ptr = NULL;
      long n = strtol (string_value, &ptr, 10);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_INT);
        g_value_set_int (value, n);
        return TRUE;
      }
    }
    else if (type == G_TYPE_UINT) {
      char *ptr = NULL;
      unsigned long n = strtoul (string_value, &ptr, 10);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_UINT);
        g_value_set_uint (value, n);
        return TRUE;
      }
    }
    else if (type == G_TYPE_INT64) {
      char *ptr = NULL;
      gint64 n = g_ascii_strtoll (string_value, &ptr, 10);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_INT64);
        g_value_set_int64 (value, n);
        return TRUE;
      }
    }
    else if (type == G_TYPE_UINT64) {
      char *ptr = NULL;
      guint64 n = g_ascii_strtoull (string_value, &ptr, 10);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_UINT64);
        g_value_set_uint64 (value, n);
        return TRUE;
      }
    }
    else if (type == G_TYPE_DOUBLE) {
      char *ptr = NULL;
      float f = strtof (string_value, &ptr);
      if (!ptr || !*ptr) {
        g_value_init (value, G_TYPE_DOUBLE);
        g_value_set_float (value, f);
        return TRUE;
      }
    }
    else if (type == G_TYPE_BOOLEAN) {
      if (is_true (string_value)) {
        g_value_init (value, G_TYPE_BOOLEAN);
        g_value_set_boolean (value, TRUE);
        return TRUE;
      }
      else if (is_false (string_value)) {
        g_value_init (value, G_TYPE_BOOLEAN);
        g_value_set_boolean (value, FALSE);
        return TRUE;
      }
    }
    fprintf (stderr, "Unable to convert '%s' to the declared type\n", string_value);
    return FALSE;
  }

  return FALSE;
}

static unsigned int
insanity_report_failed_tests (InsanityTest *test, gboolean verbose)
{
  GHashTableIter i;
  gpointer key, value;
  unsigned int failed = 0;

  /* Get all checklist items that were passed or failed */
  g_hash_table_iter_init (&i, test->priv->checklist_results);
  while (g_hash_table_iter_next (&i, &key, &value)) {
    gboolean success = *(gboolean *)value;
    if (verbose)
      printf ("%s: %s\n", (const char *)key, success ? "PASS" : "FAIL");
    if (!success)
      failed++;
  }

  /* Get all checklist items that were not passed nor failed */
  g_hash_table_iter_init (&i, test->priv->test_checklist);
  while (g_hash_table_iter_next (&i, &key, &value)) {
    if (!g_hash_table_lookup (test->priv->checklist_results, key)) {
      if (verbose)
        printf ("%s: SKIP\n", (const char *)key);
      ++failed;
    }
  }

  if (verbose)
    printf("%u/%u failed tests\n", failed,
        g_hash_table_size (test->priv->test_checklist));

  return failed;
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
  const GOptionEntry options[] = {
    {"run", 0, 0, G_OPTION_ARG_NONE, &opt_run, "Run the test standalone", NULL},
    {"insanity-metadata", 0, 0, G_OPTION_ARG_NONE, &opt_metadata, "Output test metadata", NULL},
    {"dbus-uuid", 0, 0, G_OPTION_ARG_STRING, &opt_uuid, "Set D-Bus uuid", "UUID"},
    {NULL}
  };
  GOptionContext *ctx;
  GError *err = NULL;
  gboolean ret = TRUE;

  ctx = g_option_context_new (test->priv->test_desc);
  g_option_context_add_main_entries (ctx, options, NULL);
  if (!g_option_context_parse (ctx, argc, argv, &err)) {
    fprintf (stderr, "Error initializing: %s\n", err->message);
    g_error_free (err);
    g_option_context_free (ctx);
    return FALSE;
  }

  if (opt_metadata) {
    insanity_test_write_metadata (test);
    ret = TRUE;
  }
  else if (opt_run && !opt_uuid) {
    int n;

    /* Load any command line output files and arguments */
    test->priv->args = g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, &free_gvalue);
    for (n = 1; n < *argc; ++n) {
      char *key;
      const char *equals;
      GValue value = {0}, *v;

      equals = strchr ((*argv)[n], '=');
      if (!equals) {
        usage ((*argv)[0]);
        return FALSE;
      }

      key = g_strndup ((*argv)[n], equals - (*argv)[n]);
      if (g_hash_table_lookup (test->priv->test_output_files, key)) {
        g_hash_table_insert (test->priv->filename_cache, key, g_strdup (equals+1));
      }
      else {
        if (parse_value (test, key, equals+1, &value)) {
          v = g_slice_alloc0 (sizeof (GValue));
          g_value_init (v, G_VALUE_TYPE (&value));
          g_value_copy (&value, v); /* src first */
          g_hash_table_insert (test->priv->args, key, v);
        }
        else {
          g_free (key);
        }
      }
    }

    if (on_setup (test)) {
      if (on_start (test)) {
        while (1) {
          gboolean done;
          LOCK (test);
          done = test->priv->done;
          UNLOCK (test);
          if (done)
            break;
          g_usleep (100);
        }
      }
      on_stop (test);
      on_teardown (test);
    }
    ret = (insanity_report_failed_tests (test, TRUE) == 0);
  }

  else if (opt_run && opt_uuid) {
    private_dbus_address = getenv ("PRIVATE_DBUS_ADDRESS");
    if (!private_dbus_address || !private_dbus_address[0]) {
      fprintf (stderr,
          "The PRIVATE_DBUS_ADDRESS environment variable must be set\n");
      ret = FALSE;
    }
    else {
#if 0
      printf ("uuid: %s\n", opt_uuid);
      printf ("PRIVATE_DBUS_ADDRESS: %s\n", private_dbus_address);
#endif
      ret = listen (test, private_dbus_address, opt_uuid);
    }
  }

  else {
    fprintf (stderr, "%s\n", g_option_context_get_help (ctx, FALSE, NULL));
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
    if (!priv->conn) { /* unreffed, but value still set */
      GHashTableIter i;
      gpointer key, value;
      g_hash_table_iter_init (&i, priv->filename_cache);
      while (g_hash_table_iter_next (&i, &key, &value)) {
        /* only unlink those random ones */
        if (test->priv->tmpdir && g_str_has_prefix (value, test->priv->tmpdir)) {
          g_unlink (value);
        }
      }
    }
    g_hash_table_destroy (priv->filename_cache);
  }
  g_hash_table_destroy (priv->checklist_results);
  if (priv->tmpdir) {
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
  g_hash_table_destroy (priv->test_likely_errors);
#ifdef USE_NEW_GLIB_MUTEX_API
  g_mutex_clear (&priv->lock);
#else
  g_mutex_destroy (priv->lock);
#endif
  G_OBJECT_CLASS (insanity_test_parent_class)->finalize (gobject);
}

static void
insanity_test_init (InsanityTest * test)
{
  InsanityTestPrivateData *priv = G_TYPE_INSTANCE_GET_PRIVATE (test,
      INSANITY_TYPE_TEST, InsanityTestPrivateData);

#ifdef USE_NEW_GLIB_MUTEX_API
  g_mutex_init (&priv->lock);
#else
  priv->lock = g_mutex_new ();
#endif
  test->priv = priv;
  priv->conn = NULL;
  priv->name = NULL;
  priv->args = NULL;
  priv->cpu_load = -1;
  priv->standalone = TRUE;
  priv->tmpdir = NULL;
  priv->done = FALSE;
  priv->exit = FALSE;
  priv->filename_cache =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, g_free);
  priv->checklist_results =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, &g_free);

  priv->test_name = NULL;
  priv->test_desc = NULL;
  priv->test_full_desc = NULL;
  priv->test_checklist =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, g_free);
  priv->test_arguments =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, &free_argument);
  priv->test_extra_infos =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, g_free);
  priv->test_output_files =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, g_free);
  priv->test_likely_errors =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, g_free);
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
    case PROP_DESC:
      if (test->priv->test_desc)
        g_free (test->priv->test_desc);
      test->priv->test_desc = g_strdup (g_value_get_string (value));
      break;
    case PROP_FULL_DESC:
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
    case PROP_DESC:
      g_value_set_string (value, test->priv->test_desc);
      break;
    case PROP_FULL_DESC:
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
      G_PARAM_READWRITE);
  properties[PROP_DESC] =
      g_param_spec_string ("desc", "Description", "Description of the test",
      NULL, G_PARAM_READWRITE);
  properties[PROP_FULL_DESC] =
      g_param_spec_string ("full-desc", "Full description",
      "Full description of the test", NULL, G_PARAM_READWRITE);

  g_object_class_install_properties (gobject_class, N_PROPERTIES, properties);

  setup_signal = g_signal_new ("setup",
      G_TYPE_FROM_CLASS (gobject_class),
      G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS,
      G_STRUCT_OFFSET (InsanityTestClass, setup),
      &insanity_signal_stop_accumulator, NULL,
      insanity_cclosure_marshal_BOOLEAN__VOID,
      G_TYPE_BOOLEAN /* return_type */ ,
      0, NULL);
  start_signal = g_signal_new ("start",
      G_TYPE_FROM_CLASS (gobject_class),
      G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS,
      G_STRUCT_OFFSET (InsanityTestClass, start),
      &insanity_signal_stop_accumulator, NULL,
      insanity_cclosure_marshal_BOOLEAN__VOID,
      G_TYPE_BOOLEAN /* return_type */ ,
      0, NULL);
  stop_signal = g_signal_new ("stop",
      G_TYPE_FROM_CLASS (gobject_class),
      G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS,
      G_STRUCT_OFFSET (InsanityTestClass, stop),
      NULL, NULL, g_cclosure_marshal_VOID__VOID, G_TYPE_NONE /* return_type */ ,
      0, NULL);
  teardown_signal = g_signal_new ("teardown",
      G_TYPE_FROM_CLASS (gobject_class),
      G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS,
      G_STRUCT_OFFSET (InsanityTestClass, teardown),
      NULL, NULL, g_cclosure_marshal_VOID__VOID, G_TYPE_NONE /* return_type */ ,
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
  InsanityTest *test = g_object_new (insanity_test_get_type (),
      "name", name, "desc", description, NULL);
  if (full_description)
    g_object_set (test, "full-desc", full_description, NULL);
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
 * @label: the new checklist item's name
 * @description: a one line description of that item
 * @error_hint: (allow-none): an optional explanatory description of why this error may happen
 *
 * This function adds a checklist item declaration to the test.
 *
 * Checklist items are the individual steps that a test can pass or fail
 * using insanity_test_validate_step.
 */
void
insanity_test_add_checklist_item (InsanityTest * test, const char *label,
    const char *description, const char *error_hint)
{
  insanity_add_metadata_entry (test->priv->test_checklist, label, description);
  if (error_hint) {
    insanity_add_metadata_entry (test->priv->test_likely_errors, label,
        error_hint);
  }
}

/**
 * insanity_test_add_argument:
 * @test: a #InsanityTest instance to operate on.
 * @label: the new argument's name
 * @description: a one line description of that argument
 * @full_description: (allow-none): an optional longer description of that argument
 * @default_value: the default value for this parameter if not supplied at runtime
 *
 * This function adds an argument declaration to the test.
 *
 * Arguments are paramters which can be passed to the test, and which value
 * may be queried at runtime with insanity_test_get_argument. Arguments may
 * be changed every time a test is started, so should be inspected each time
 * the start function is called.
 */
void
insanity_test_add_argument (InsanityTest * test, const char *label,
    const char *description, const char *full_description,
    const GValue *default_value)
{
  Argument *arg;

  arg = g_slice_alloc0 (sizeof (Argument));
  arg->description = g_strdup (description);
  arg->full_description = full_description ? g_strdup (full_description) : NULL;
  g_value_init (&arg->default_value, G_VALUE_TYPE (default_value));
  g_value_copy (default_value, &arg->default_value); /* Source is first */
  g_hash_table_insert (test->priv->test_arguments, g_strdup (label), arg);
}

/**
 * insanity_test_add_extra_info:
 * @test: a #InsanityTest instance to operate on.
 * @label: the new extra info's name
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
  insanity_add_metadata_entry (test->priv->test_extra_infos, label,
      description);
}

/**
 * insanity_test_add_output_file:
 * @test: a #InsanityTest instance to operate on.
 * @label: the new output file's name
 * @description: a one line description of that file's purpose
 *
 * This function adds an output file declaration to the test.
 *
 * Output files will be named automatically for the test's use.
 * A test can obtain the filename assigned to an output file
 * using insanity_test_get_output_filename, open it, and write
 * to it. After the test has finished, these files will be
 * either collected, deleted, or left for the user as requested.
 */
void
insanity_test_add_output_file (InsanityTest * test, const char *label,
    const char *description)
{
  insanity_add_metadata_entry (test->priv->test_output_files, label,
      description);
}
