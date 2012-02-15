#include <dbus/dbus.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "insanity.h"

/* getrusage is Unix API */
#define USE_CPU_LOAD

#ifdef USE_CPU_LOAD
#include <sys/time.h>
#include <sys/resource.h>
#endif

struct InsanityTestPrivateData {
  DBusConnection *conn;
#ifdef USE_CPU_LOAD
  struct timeval start;
  struct rusage rusage;
#endif
  char name[128];
  DBusMessage *args;
  int cpu_load;
};

static gboolean default_insanity_user_setup(InsanityTest *test)
{
  (void)test;
  return TRUE;
}

static gboolean default_insanity_user_start(InsanityTest *test)
{
  insanity_test_done(test);
  return TRUE;
}

static gboolean default_insanity_user_stop(InsanityTest *test)
{
  (void)test;
  return TRUE;
}

static void insanity_test_connect (InsanityTest *test, DBusConnection *conn, const char *uuid)
{
  if (test->priv->conn)
    dbus_connection_unref (test->priv->conn);
  test->priv->conn = dbus_connection_ref (conn);
  snprintf(test->priv->name, sizeof(test->priv->name), "/net/gstreamer/Insanity/Test/Test%s", uuid);
}

static void insanity_test_set_args (InsanityTest *test, DBusMessage *msg)
{
  if (test->priv->args) {
    dbus_message_unref (test->priv->args);
    test->priv->args = NULL;
  }
  if (msg) {
    test->priv->args = dbus_message_ref (msg);
  }
}

static void insanity_test_record_start_time (InsanityTest *test)
{
#ifdef USE_CPU_LOAD
  gettimeofday(&test->priv->start,NULL);
  getrusage(RUSAGE_SELF, &test->priv->rusage);
#endif
}

#ifdef USE_CPU_LOAD
static long tv_us_diff(const struct timeval *t0, const struct timeval *t1)
{
  return (t1->tv_sec - t0->tv_sec) * 1000000 + t1->tv_usec - t0->tv_usec;
}
#endif

static void insanity_test_record_stop_time(InsanityTest *test)
{
#ifdef USE_CPU_LOAD
  struct rusage rusage;
  struct timeval end;
  unsigned long us;

  getrusage(RUSAGE_SELF, &rusage);
  gettimeofday(&end,NULL);
  us = tv_us_diff(&test->priv->rusage.ru_utime, &rusage.ru_utime)
     + tv_us_diff(&test->priv->rusage.ru_stime, &rusage.ru_stime);
  test->priv->cpu_load = 100 * us / tv_us_diff (&test->priv->start, &end);
#endif
}

// TODO: add the full API
#define INSANITY_TEST_INTERFACE "net.gstreamer.Insanity.Test"
static const char *introspect_response_template=" \
  <!DOCTYPE node PUBLIC \"-//freedesktop//DTD D-BUS Object Introspection 1.0//EN\" \
  \"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd\"> \
  <node name=\"/net/gstreamer/Insanity/Test/Test%s\"> \
    <interface name=\"org.freedesktop.DBus.Introspectable\"> \
      <method name=\"Introspect\"> \
        <arg direction=\"out\" type=\"s\" /> \
      </method> \
    </interface> \
    <interface name=\""INSANITY_TEST_INTERFACE"\"> \
      <method name=\"remoteSetUp\"> \
        <arg direction=\"in\" type=\"a{sv}\" /> \
      </method> \
    </interface> \
  </node> \
";

static void send_signal(DBusConnection *conn, const char *signal_name, const char *path_name, int type,...)
{
   DBusMessage *msg;
   dbus_uint32_t serial = 0;
   va_list ap;

   msg = dbus_message_new_signal(path_name, INSANITY_TEST_INTERFACE, signal_name);
   if (NULL == msg) 
   { 
      fprintf(stderr, "Message Null\n"); 
      exit(1); 
   }

  // append any arguments onto signal
  if (type != DBUS_TYPE_INVALID) {
    va_start (ap, type);
    if (!dbus_message_append_args_valist (msg, type, ap)) {
      fprintf(stderr, "Out Of Memory!\n"); 
      exit(1);
    }
    va_end(ap);
  }

   // send the message and flush the connection
   if (!dbus_connection_send(conn, msg, &serial)) {
      fprintf(stderr, "Out Of Memory!\n"); 
      exit(1);
   }
   dbus_connection_flush(conn);
   
   //printf("Signal %s sent from %s\n", signal_name, path_name);
   
   // free the message and close the connection
   dbus_message_unref(msg);
}

void insanity_test_validate(InsanityTest *test, const char *name, int success)
{
  send_signal (test->priv->conn,"remoteValidateStepSignal",test->priv->name,DBUS_TYPE_STRING,&name,DBUS_TYPE_BOOLEAN,&success,DBUS_TYPE_INVALID);
}

void insanity_test_extra_info(InsanityTest *test, const char *name, int type, void *dataptr)
{
  send_signal (test->priv->conn,"remoteExtraInfoSignal",test->priv->name,DBUS_TYPE_STRING,&name,type,dataptr,DBUS_TYPE_INVALID);
}

static void gather_end_of_test_info(InsanityTest *test)
{
  insanity_test_record_stop_time(test);
  insanity_test_extra_info (test, "cpu-load", DBUS_TYPE_INT32, &test->priv->cpu_load);
}

void insanity_test_done(InsanityTest *test)
{
  gather_end_of_test_info(test);
  send_signal (test->priv->conn, "remoteStopSignal", test->priv->name, DBUS_TYPE_INVALID);
}

static gboolean insanity_test_setup (InsanityTest *test)
{
  return INSANITY_TEST_GET_CLASS (test)->setup (test);
}

static gboolean insanity_test_start (InsanityTest *test)
{
  return INSANITY_TEST_GET_CLASS (test)->start (test);
}

static gboolean insanity_test_stop (InsanityTest *test)
{
  return INSANITY_TEST_GET_CLASS (test)->stop (test);
}

static gboolean on_setup(InsanityTest *test)
{
  gboolean ret = insanity_test_setup (test);
  if (!ret) {
    send_signal (test->priv->conn, "remoteStopSignal", test->priv->name, DBUS_TYPE_INVALID);
  }
  else {
    send_signal (test->priv->conn, "remoteReadySignal", test->priv->name, DBUS_TYPE_INVALID);
  }
  return ret;
}

static gboolean on_start(InsanityTest *test)
{
  insanity_test_record_start_time(test);
  return insanity_test_start (test);
}

static gboolean on_stop(InsanityTest *test)
{
  gboolean ret;

  ret = insanity_test_stop (test);
  if (!ret)
    return ret;

  gather_end_of_test_info(test);

  return ret;
}

static int foreach_dbus_array (DBusMessageIter *iter, int (*f)(const char *key, int type, void *value, guintptr userdata), guintptr userdata)
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
  DBusMessageIter array_value;
  int type;
  int ret;
  void *ptr;

  type = dbus_message_iter_get_arg_type (iter);
  if (type != DBUS_TYPE_ARRAY) {
    fprintf(stderr, "Expected array, got %c\n", type);
    exit(1);
  }
  dbus_message_iter_recurse (iter, &subiter);
  do {
    type = dbus_message_iter_get_arg_type (&subiter);
    if (type != DBUS_TYPE_DICT_ENTRY) {
      fprintf(stderr, "Expected dict entry, got %c\n", type);
      exit(1);
    }
    dbus_message_iter_recurse (&subiter, &subsubiter);

    type = dbus_message_iter_get_arg_type (&subsubiter);
    if (type != DBUS_TYPE_STRING) {
      fprintf(stderr, "Expected string, got %c\n", type);
      exit(1);
    }
    dbus_message_iter_get_basic (&subsubiter,&key);
    if (!dbus_message_iter_next (&subsubiter)) {
      fprintf(stderr, "Value not present\n");
      exit(1);
    }
    type = dbus_message_iter_get_arg_type (&subsubiter);
    if (type == DBUS_TYPE_STRING) {
      dbus_message_iter_get_basic (&subsubiter,&string_value);
      ptr = &string_value;
    }
    else if (type == DBUS_TYPE_VARIANT) {
      dbus_message_iter_recurse (&subsubiter, &subsubsubiter);

      type = dbus_message_iter_get_arg_type (&subsubsubiter);

      switch (type) {
        case DBUS_TYPE_STRING:
          dbus_message_iter_get_basic (&subsubsubiter,&string_value);
          ptr = &string_value;
          break;
        case DBUS_TYPE_INT32:
          dbus_message_iter_get_basic (&subsubsubiter,&int32_value);
          ptr = &int32_value;
          break;
        case DBUS_TYPE_UINT32:
          dbus_message_iter_get_basic (&subsubsubiter,&uint32_value);
          ptr = &uint32_value;
          break;
        case DBUS_TYPE_INT64:
          dbus_message_iter_get_basic (&subsubsubiter,&int64_value);
          ptr = &int64_value;
          break;
        case DBUS_TYPE_UINT64:
          dbus_message_iter_get_basic (&subsubsubiter,&uint64_value);
          ptr = &uint64_value;
          break;
        case DBUS_TYPE_DOUBLE:
          dbus_message_iter_get_basic (&subsubsubiter,&double_value);
          ptr = &double_value;
          break;
        case DBUS_TYPE_BOOLEAN:
          dbus_message_iter_get_basic (&subsubsubiter,&boolean_value);
          ptr = &boolean_value;
          break;
        case DBUS_TYPE_ARRAY:
          array_value = subsubsubiter;
          ptr = &array_value;
          break;
        default:
          fprintf(stderr, "Unsupported type: %c\n", type);
          exit(1);
          break;
      }
    }
    else {
      fprintf(stderr, "Expected variant, got %c\n", type);
      exit(1);
    }

    /* < 0 -> error, 0 -> continue, > 0 -> stop */
    ret = (*f)(key, type, ptr, userdata);
    if (ret)
      return ret;

  } while (dbus_message_iter_next (&subiter));

  return 0;
}

int foreach_dbus_args (InsanityTest *test, int (*f)(const char *key, int type, void *value, guintptr userdata), guintptr userdata)
{
  DBusMessageIter iter;

  dbus_message_iter_init (test->priv->args, &iter);
  return foreach_dbus_array (&iter, f, userdata);
}

struct finder_data {
  const char *key;
  int type;
  void *value;
};

static int typed_finder(const char *key, int type, void *value, guintptr userdata)
{
  struct finder_data *fd = (struct finder_data *)userdata;
  if (strcmp (key, fd->key))
    return 0;
  if (type != fd->type) {
    fprintf(stderr, "Key '%s' was found, but not of the expected type (was %c, expected %c)\n", key, type, fd->type);
    return -1;
  }
  fd->value = value;
  return 1;
}

const char *insanity_test_get_arg_string(InsanityTest *test, const char *key)
{
  struct finder_data fd;
  int ret;

  fd.key = key;
  fd.type = DBUS_TYPE_STRING;
  fd.value = NULL;
  ret = foreach_dbus_args(test, &typed_finder, (guintptr)&fd);
  return (ret>0 && fd.value) ? * (const char **)fd.value : NULL;
}

const char *insanity_test_get_output_file(InsanityTest *test, const char *key)
{
  struct finder_data fd;
  int ret;
  DBusMessageIter array;

  fd.key = "outputfiles";
  fd.type = DBUS_TYPE_ARRAY;
  fd.value = NULL;
  ret = foreach_dbus_args(test, &typed_finder, (guintptr)&fd);
  if (ret <= 0)
    return NULL;

  array = *(DBusMessageIter*)fd.value;
  fd.key = key;
  fd.type = DBUS_TYPE_STRING;
  fd.value = NULL;
  ret = foreach_dbus_array (&array, &typed_finder, (guintptr)&fd);
  return (ret>0 && fd.value) ? * (const char **)fd.value : NULL;
}

static gboolean listen(InsanityTest *test, const char *bus_address,const char *uuid)
{
   DBusMessage* msg;
   DBusMessage* reply;
   DBusMessageIter args;
   DBusConnection* conn;
   DBusError err;
   int ret;
   char object_name[128];
   dbus_uint32_t serial = 0;
   int done;

   // initialise the error
   dbus_error_init(&err);
   
   // connect to the bus and check for errors
   conn = dbus_connection_open(bus_address, &err);
   if (dbus_error_is_set(&err)) { 
      fprintf(stderr, "Connection Error (%s)\n", err.message); 
      dbus_error_free(&err); 
   }
   if (NULL == conn) {
      fprintf(stderr, "Connection Null\n"); 
      exit(1); 
   }

   ret = dbus_bus_register (conn, &err);
   if (dbus_error_is_set(&err)) { 
      fprintf(stderr, "Failed to register bus (%s)\n", err.message); 
      dbus_error_free(&err); 
   }

   // request our name on the bus and check for errors
   snprintf(object_name, sizeof(object_name), INSANITY_TEST_INTERFACE ".Test%s", uuid);
   //printf("Using object name %s\n",object_name);
   ret = dbus_bus_request_name(conn, object_name, DBUS_NAME_FLAG_REPLACE_EXISTING , &err);
   if (dbus_error_is_set(&err)) { 
      fprintf(stderr, "Name Error (%s)\n", err.message); 
      dbus_error_free(&err);
   }
   if (DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER != ret) { 
      fprintf(stderr, "Not Primary Owner (%d)\n", ret);
      exit(1); 
   }

   insanity_test_connect (test, conn, uuid);

   // loop, testing for new messages
   done=0;
   while (1) {
      // barely blocking update of dbus
      dbus_connection_read_write(conn, 100);

      if (done)
        break;

      // see if we have a message to handle
      msg = dbus_connection_pop_message(conn);
      if (NULL == msg) {
         continue; 
      }
      
#if 0
      printf("Got message:\n");
      printf("  type %d\n", dbus_message_get_type (msg));
      printf("  path %s\n", dbus_message_get_path (msg));
      printf("  interface %s\n", dbus_message_get_interface (msg));
      printf("  member %s\n", dbus_message_get_member (msg));
      printf("  sender %s\n", dbus_message_get_sender (msg));
      printf("  destination %s\n", dbus_message_get_destination (msg));
      printf("  signature %s\n", dbus_message_get_signature (msg));
#endif

      // check this is a method call for the right interface & method
      if (dbus_message_is_method_call(msg, "org.freedesktop.DBus.Introspectable", "Introspect"))  {
        char *introspect_response = malloc (strlen(introspect_response_template)+strlen(uuid)+1);
        sprintf (introspect_response, introspect_response_template, uuid);
        //printf("Got 'Introspect', answering introspect response\n");
        reply = dbus_message_new_method_return(msg);
        dbus_message_iter_init_append(reply, &args);
        if (!dbus_message_iter_append_basic(&args, DBUS_TYPE_STRING, &introspect_response)) { 
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        free (introspect_response);
        if (!dbus_connection_send(conn, reply, &serial)) {
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        dbus_connection_flush(conn);
        dbus_message_unref(reply);
      }
#if 0
      else if (dbus_message_is_method_call(msg, INSANITY_TEST_INTERFACE, "remoteInfo"))  {
        static const char *info = "blankc-info";
        printf("Got remoteInfo\n");
        reply = dbus_message_new_method_return(msg);
        dbus_message_append_args (reply, DBUS_TYPE_STRING, &info, DBUS_TYPE_INVALID);
        if (!dbus_connection_send(conn, reply, &serial)) {
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        dbus_connection_flush(conn);
        dbus_message_unref(reply);
      }
#endif
      else if (dbus_message_is_method_call(msg, INSANITY_TEST_INTERFACE, "remoteSetUp"))  {
        //printf("Got remoteSetUp\n");
        reply = dbus_message_new_method_return(msg);
        if (!dbus_connection_send(conn, reply, &serial)) {
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        dbus_connection_flush(conn);
        dbus_message_unref(reply);

        insanity_test_set_args (test, msg);
        on_setup(test);
      }
#if 0
      else if (dbus_message_is_method_call(msg, INSANITY_TEST_INTERFACE, "remoteTearDown"))  {
        printf("Got remoteTearDown\n");

        on_tear_down(&insanity_test);

        reply = dbus_message_new_method_return(msg);
        if (!dbus_connection_send(conn, reply, &serial)) {
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        dbus_connection_flush(conn);
        dbus_message_unref(reply);

        done=1;
      }
#endif
      else if (dbus_message_is_method_call(msg, INSANITY_TEST_INTERFACE, "remoteStop"))  {
        //printf("Got remoteStop\n");
        reply = dbus_message_new_method_return(msg);
        if (!dbus_connection_send(conn, reply, &serial)) {
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        dbus_connection_flush(conn);
        dbus_message_unref(reply);

        on_stop(test);
        done=1;
      }
      else if (dbus_message_is_method_call(msg, INSANITY_TEST_INTERFACE, "remoteStart"))  {
        //printf("Got remoteStart\n");
        reply = dbus_message_new_method_return(msg);
        if (!dbus_connection_send(conn, reply, &serial)) {
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        dbus_connection_flush(conn);
        dbus_message_unref(reply);

        on_start(test);
      }
      else {
        //printf("Got unhandled method call: interface %s, method %s\n", dbus_message_get_interface(msg), dbus_message_get_member(msg));
      }

      // free the message
      dbus_message_unref(msg);
   }

   dbus_connection_unref (conn);

  return TRUE;
}

gboolean insanity_test_run(InsanityTest *test, int argc, const char **argv)
{
  const char *private_dbus_address;
  const char *uuid;

  if (argc < 2) {
    fprintf(stderr, "Usage: %s <uuid>\n", argv[0]);
    return FALSE;
  }
  uuid = argv[1];
  private_dbus_address = getenv("PRIVATE_DBUS_ADDRESS");
  if (!private_dbus_address || !private_dbus_address[0]) {
    fprintf(stderr, "The PRIVATE_DBUS_ADDRESS environment variable must be set\n");
    return FALSE;
  }
#if 0
  printf("uuid: %s\n", uuid);
  printf("PRIVATE_DBUS_ADDRESS: %s\n",private_dbus_address);
#endif
  return listen(test, private_dbus_address, uuid);
}



G_DEFINE_TYPE (InsanityTest, insanity_test, G_TYPE_OBJECT);

static void insanity_test_finalize (GObject *gobject)
{
  InsanityTest *test = (InsanityTest *)gobject;
  InsanityTestPrivateData *priv = test->priv;
  if (priv->args)
    dbus_message_unref(priv->args);
  if (priv->conn)
    dbus_connection_unref(priv->conn);
  free(priv);
  G_OBJECT_CLASS (insanity_test_parent_class)->finalize (gobject);
}

static void insanity_test_init (InsanityTest *test)
{
  InsanityTestPrivateData *priv = malloc (sizeof (InsanityTestPrivateData));
  test->priv = priv;
  priv->conn = NULL;
  strcpy (priv->name, "");
  priv->args = NULL;
}

static void insanity_test_class_init (InsanityTestClass *klass)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);

  gobject_class->finalize = insanity_test_finalize;

  klass->setup = &default_insanity_user_setup;
  klass->start = &default_insanity_user_start;
  klass->stop = &default_insanity_user_stop;
}

