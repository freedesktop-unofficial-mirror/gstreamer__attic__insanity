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
#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <insanity/insanitytest.h>

#include <dbus/dbus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

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
  N_PROPERTIES
};

/* if global vars are good enough for gstreamer, it's good enough for insanity */
static guint setup_signal;
static guint start_signal;
static guint stop_signal;
static guint test_signal;
static GParamSpec *properties[N_PROPERTIES] = { NULL, };

struct InsanityTestPrivateData
{
  DBusConnection *conn;
#ifdef USE_CPU_LOAD
  struct timeval start;
  struct rusage rusage;
#endif
  char *name;
  DBusMessage *args;
  int cpu_load;
  gboolean done;
  gboolean exit;
  GHashTable *filename_cache;
  GMutex lock;

  /* test metadata */
  char *test_name;
  char *test_desc;
  GHashTable *test_checklist;
  GHashTable *test_arguments;
  GHashTable *test_output_files;
  GHashTable *test_likely_errors;
};

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
insanity_test_connect (InsanityTest * test, DBusConnection * conn,
    const char *uuid)
{
  g_mutex_lock (&test->priv->lock);
  if (test->priv->conn)
    dbus_connection_unref (test->priv->conn);
  test->priv->conn = dbus_connection_ref (conn);
  if (test->priv->name)
    g_free (test->priv->name);
  test->priv->name =
      g_strdup_printf ("/net/gstreamer/Insanity/Test/Test%s", uuid);
  g_mutex_unlock (&test->priv->lock);
}

static void
insanity_test_set_args (InsanityTest * test, DBusMessage * msg)
{
  g_mutex_lock (&test->priv->lock);
  if (test->priv->args) {
    dbus_message_unref (test->priv->args);
    test->priv->args = NULL;
  }
  if (msg) {
    test->priv->args = dbus_message_ref (msg);
  }
  g_mutex_unlock (&test->priv->lock);
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

  /* getrusage times are apparently quite granular, and jump above realtime */
  if (test->priv->cpu_load > 100)
    test->priv->cpu_load = 100;
#endif
}

/* TODO: add the full API */
#define INSANITY_TEST_INTERFACE "net.gstreamer.Insanity.Test"
static const char *introspect_response_template = " \
  <!DOCTYPE node PUBLIC \"-//freedesktop//DTD D-BUS Object Introspection 1.0//EN\" \
  \"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd\"> \
  <node name=\"/net/gstreamer/Insanity/Test/Test%s\"> \
    <interface name=\"org.freedesktop.DBus.Introspectable\"> \
      <method name=\"Introspect\"> \
        <arg direction=\"out\" type=\"s\" /> \
      </method> \
    </interface> \
    <interface name=\"" INSANITY_TEST_INTERFACE "\"> \
      <method name=\"remoteSetUp\"> \
        <arg direction=\"in\" type=\"a{sv}\" /> \
      </method> \
    </interface> \
  </node> \
";

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

void
insanity_test_validate_step (InsanityTest * test, const char *name,
    gboolean success)
{
  g_mutex_lock (&test->priv->lock);
  if (!test->priv->conn) {
    printf("step: %s: %s\n", name, success ? "PASS" : "FAIL");
  }
  else {
    send_signal (test->priv->conn, "remoteValidateStepSignal", test->priv->name,
        DBUS_TYPE_STRING, &name, DBUS_TYPE_BOOLEAN, &success, DBUS_TYPE_INVALID);
  }
  g_mutex_unlock (&test->priv->lock);
}

static void
insanity_test_add_extra_info_internal (InsanityTest * test, const char *name,
    const GValue * data, gboolean locked)
{
  GType glib_type;
  int dbus_type;
  dbus_int32_t int32_value;
  dbus_int64_t int64_value;
  const char *string_value;
  void *dataptr = NULL;

  if (!locked)
    g_mutex_lock (&test->priv->lock);

  if (!test->priv->conn) {
    char *s = g_strdup_value_contents (data);
    printf("Extra info: %s: %s\n", name, s);
    g_free (s);
    if (!locked)
      g_mutex_unlock (&test->priv->lock);
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
    g_mutex_unlock (&test->priv->lock);
}

void
insanity_test_add_extra_info (InsanityTest * test, const char *name,
    const GValue * data)
{
  insanity_test_add_extra_info_internal (test, name, data, FALSE);
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
  insanity_test_add_extra_info_internal (test, "cpu-load", &value, TRUE);
  g_value_unset (&value);
}

void
insanity_test_done (InsanityTest * test)
{
  g_mutex_lock (&test->priv->lock);
  gather_end_of_test_info (test);
  if (test->priv->conn) {
    send_signal (test->priv->conn, "remoteStopSignal", test->priv->name,
        DBUS_TYPE_INVALID);
  }
  test->priv->done = TRUE;
  g_mutex_unlock (&test->priv->lock);
}

static gboolean
on_setup (InsanityTest * test)
{
  gboolean ret = TRUE;

  g_signal_emit (test, setup_signal, 0, &ret);

  if (test->priv->conn) {
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

  insanity_test_record_start_time (test);
  g_signal_emit (test, start_signal, 0, &ret);
  return ret;
}

static void
on_stop (InsanityTest * test)
{
  g_signal_emit (test, stop_signal, 0, NULL);

  g_mutex_lock (&test->priv->lock);
  gather_end_of_test_info (test);
  test->priv->exit = TRUE;
  g_mutex_unlock (&test->priv->lock);
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

int
foreach_dbus_args (InsanityTest * test, int (*f) (const char *key,
        const GValue * value, guintptr userdata), guintptr userdata)
{
  DBusMessageIter iter;

  dbus_message_iter_init (test->priv->args, &iter);
  return foreach_dbus_array (&iter, f, userdata);
}

struct finder_data
{
  const char *key;
  GValue value;
  void *userdata;
};

static int
typed_finder (const char *key, const GValue * value, guintptr userdata)
{
  struct finder_data *fd = (struct finder_data *) userdata;

  if (strcmp (key, fd->key))
    return 0;
  g_value_init (&fd->value, G_VALUE_TYPE (value));
  g_value_copy (value, &fd->value);     /* src is first parm */
  return 1;
}

gboolean
insanity_test_get_argument (InsanityTest * test, const char *key,
    GValue * value)
{
  struct finder_data fd;
  int ret;
  GValue zero_value = { 0 };

  g_mutex_lock (&test->priv->lock);

  if (!test->priv->conn) {
    g_mutex_unlock (&test->priv->lock);
    return FALSE;
  }

  fd.key = key;
  fd.value = zero_value;
  ret = foreach_dbus_args (test, &typed_finder, (guintptr) & fd);
  if (ret <= 0) {
    g_mutex_unlock (&test->priv->lock);
    return FALSE;
  }
  g_value_init (value, G_VALUE_TYPE (&fd.value));
  g_value_copy (&fd.value, value);      /* src is first parm */
  g_value_unset (&fd.value);

  g_mutex_unlock (&test->priv->lock);
  return TRUE;
}

static int
filename_finder (const char *key, const GValue * value, guintptr userdata)
{
  DBusMessageIter *array;
  struct finder_data fd2;
  GValue zero_value = { 0 };
  int ret;

  struct finder_data *fd = (struct finder_data *) userdata;
  if (strcmp (key, fd->key))
    return 0;

  if (G_VALUE_TYPE (value) != G_TYPE_POINTER) {
    return 0;
  }

  array = (DBusMessageIter *) g_value_get_pointer (value);
  fd2.key = fd->userdata;
  fd2.value = zero_value;
  ret = foreach_dbus_array (array, &typed_finder, (guintptr) & fd2);
  if (ret <= 0)
    return 0;

  g_value_init (&fd->value, G_TYPE_STRING);
  g_value_copy (&fd2.value, &fd->value);        /* src is first */
  g_value_unset (&fd2.value);

  return 1;
}

const char *
insanity_test_get_output_filename (InsanityTest * test, const char *key)
{
  struct finder_data fd;
  int ret;
  char *fn;
  GValue zero_value = { 0 };
  gpointer ptr;

  g_mutex_lock (&test->priv->lock);

  if (!test->priv->conn) {
    g_mutex_unlock (&test->priv->lock);
    return NULL; /* TODO: dummy files */
  }

  ptr = g_hash_table_lookup (test->priv->filename_cache, key);
  if (ptr) {
    g_mutex_unlock (&test->priv->lock);
    return ptr;
  }

  fd.key = "outputfiles";
  fd.value = zero_value;
  fd.userdata = (void *) key;
  ret = foreach_dbus_args (test, &filename_finder, (guintptr) & fd);
  if (ret <= 0) {
    g_mutex_unlock (&test->priv->lock);
    return NULL;
  }

  if (G_VALUE_TYPE (&fd.value) != G_TYPE_STRING) {
    g_value_unset (&fd.value);
    g_mutex_unlock (&test->priv->lock);
    return FALSE;
  }

  fn = g_strdup (g_value_get_string (&fd.value));
  g_value_unset (&fd.value);

  g_hash_table_insert (test->priv->filename_cache, g_strdup (key), fn);
  g_mutex_unlock (&test->priv->lock);
  return fn;
}

static void
insanity_test_dbus_handler_remoteSetup (InsanityTest * test, DBusMessage * msg)
{
  insanity_test_set_args (test, msg);
  on_setup (test);
}

static void
insanity_test_dbus_handler_remoteStart (InsanityTest * test, DBusMessage * msg)
{
  (void) msg;
  on_start (test);
}

static void
insanity_test_dbus_handler_remoteStop (InsanityTest * test, DBusMessage * msg)
{
  (void) msg;
  on_stop (test);
}

static const struct
{
  const char *method;
  void (*handler) (InsanityTest *, DBusMessage *);
} dbus_test_handlers[] = {
  { "remoteSetUp", &insanity_test_dbus_handler_remoteSetup },
  { "remoteStart", &insanity_test_dbus_handler_remoteStart },
  { "remoteStop", &insanity_test_dbus_handler_remoteStop },
  { "remoteInfo", NULL },
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
    const char *name)
{
  GHashTableIter it;
  const char *label, *desc, *comma = "";

  if (g_hash_table_size (table) == 0)
    return;

  fprintf (f, ",\n  \"%s\": {\n", name);
  g_hash_table_iter_init (&it, table);
  while (g_hash_table_iter_next (&it, (gpointer) & label, (gpointer) & desc)) {
    fprintf (f, "%s\n    \"%s\" : \"%s\"", comma, label, desc);
    comma = ",";
  }
  fprintf (f, "\n  }", name);
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
  output_table (test, f, test->priv->test_checklist, "__checklist__");
  output_table (test, f, test->priv->test_arguments, "__arguments__");
  output_table (test, f, test->priv->test_output_files, "__output_files__");
  output_table (test, f, test->priv->test_likely_errors, "__likely_errors__");
  fprintf (f, "\n}\n");

  g_free (name);
  g_free (desc);
}

gboolean
insanity_test_run (InsanityTest * test, int argc, const char **argv)
{
  const char *private_dbus_address;
  const char *uuid;

  if (argc < 2 || !strcmp (argv[1], "--help") || !strcmp (argv[1], "-h")) {
    fprintf (stderr, "Usage: %s [--insanity-metadata | --run | <uuid>]\n", argv[0]);
    return FALSE;
  }

  if (!strcmp (argv[1], "--insanity-metadata")) {
    insanity_test_write_metadata (test);
    return TRUE;
  }

  if (!strcmp (argv[1], "--run")) {
    if (on_setup (test)) {
      if (on_start (test)) {
        while (!test->priv->done)
          g_usleep (100);
      }
      on_stop (test);
    }
    return TRUE;
  }

  uuid = argv[1];
  private_dbus_address = getenv ("PRIVATE_DBUS_ADDRESS");
  if (!private_dbus_address || !private_dbus_address[0]) {
    fprintf (stderr,
        "The PRIVATE_DBUS_ADDRESS environment variable must be set\n");
    return FALSE;
  }
#if 0
  printf ("uuid: %s\n", uuid);
  printf ("PRIVATE_DBUS_ADDRESS: %s\n", private_dbus_address);
#endif
  return listen (test, private_dbus_address, uuid);
}



G_DEFINE_TYPE (InsanityTest, insanity_test, G_TYPE_OBJECT);

static void
insanity_test_finalize (GObject * gobject)
{
  InsanityTest *test = (InsanityTest *) gobject;
  InsanityTestPrivateData *priv = test->priv;

  if (priv->args)
    dbus_message_unref (priv->args);
  if (priv->conn)
    dbus_connection_unref (priv->conn);
  if (test->priv->name)
    g_free (test->priv->name);
  if (priv->filename_cache)
    g_hash_table_destroy (priv->filename_cache);
  g_free (test->priv->test_name);
  g_free (test->priv->test_desc);
  g_hash_table_destroy (priv->test_checklist);
  g_hash_table_destroy (priv->test_arguments);
  g_hash_table_destroy (priv->test_output_files);
  g_hash_table_destroy (priv->test_likely_errors);
  g_mutex_clear (&priv->lock);
  G_OBJECT_CLASS (insanity_test_parent_class)->finalize (gobject);
}

static void
insanity_test_init (InsanityTest * test)
{
  InsanityTestPrivateData *priv = G_TYPE_INSTANCE_GET_PRIVATE (test,
      INSANITY_TYPE_TEST, InsanityTestPrivateData);

  g_mutex_init (&priv->lock);
  test->priv = priv;
  priv->conn = NULL;
  priv->name = NULL;
  priv->args = NULL;
  priv->cpu_load = -1;
  priv->done = FALSE;
  priv->exit = FALSE;
  priv->filename_cache =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, g_free);

  priv->test_name = NULL;
  priv->test_desc = NULL;
  priv->test_checklist =
      g_hash_table_new_full (&g_str_hash, &g_str_equal, &g_free, g_free);
  priv->test_arguments =
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

  g_mutex_lock (&test->priv->lock);
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
    default:
      g_assert_not_reached ();
  }
  g_mutex_unlock (&test->priv->lock);
}

static void
insanity_test_get_property (GObject * gobject,
    guint prop_id, GValue * value, GParamSpec * pspec)
{
  InsanityTest *test = (InsanityTest *) gobject;

  g_mutex_lock (&test->priv->lock);
  switch (prop_id) {
    case PROP_NAME:
      g_value_set_string (value, test->priv->test_name);
      break;
    case PROP_DESC:
      g_value_set_string (value, test->priv->test_desc);
      break;
    default:
      g_assert_not_reached ();
  }
  g_mutex_unlock (&test->priv->lock);
}

static void
insanity_test_class_init (InsanityTestClass * klass)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);

  gobject_class->finalize = insanity_test_finalize;

  klass->setup = &insanity_test_setup;
  klass->start = &insanity_test_start;
  klass->stop = &insanity_test_stop;

  gobject_class->get_property = &insanity_test_get_property;
  gobject_class->set_property = &insanity_test_set_property;

  g_type_class_add_private (klass, sizeof (InsanityTestPrivateData));

  properties[PROP_NAME] =
      g_param_spec_string ("name", "Name", "Name of the test", NULL,
      G_PARAM_READWRITE);
  properties[PROP_DESC] =
      g_param_spec_string ("desc", "Description", "Description of the test",
      NULL, G_PARAM_READWRITE);

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
}

InsanityTest *
insanity_test_new (const char *name, const char *description)
{
  return g_object_new (insanity_test_get_type (), "name", name, "desc",
      description, NULL);
}

static void
insanity_add_metadata_entry (GHashTable * hash, const char *label,
    const char *description)
{
  g_hash_table_insert (hash, g_strdup (label), g_strdup (description));
}

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

void
insanity_test_add_argument (InsanityTest * test, const char *label,
    const char *description)
{
  insanity_add_metadata_entry (test->priv->test_arguments, label, description);
}

void
insanity_test_add_output_file (InsanityTest * test, const char *label,
    const char *description)
{
  insanity_add_metadata_entry (test->priv->test_output_files, label,
      description);
}
