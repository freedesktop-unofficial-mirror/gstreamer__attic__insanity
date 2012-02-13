#include <dbus/dbus.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <sys/time.h>
#include <sys/resource.h>

/* getrusage is Unix API */
#define USE_CPU_LOAD

typedef struct InsanityTestData {
  DBusConnection *conn;
#ifdef USE_CPU_LOAD
  struct timeval start;
  struct rusage rusage;
#endif
  char name[128];
} InsanityTestData;

static const char *introspect_response_template=" \
  <!DOCTYPE node PUBLIC \"-//freedesktop//DTD D-BUS Object Introspection 1.0//EN\" \
  \"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd\"> \
  <node name=\"/net/gstreamer/Insanity/Test/Test%s\"> \
    <interface name=\"org.freedesktop.DBus.Introspectable\"> \
      <method name=\"Introspect\"> \
        <arg direction=\"out\" type=\"s\" /> \
      </method> \
    </interface> \
  </node> \
";

static int insanity_setup(InsanityTestData *data);
static int insanity_start(InsanityTestData *data);
static int insanity_stop(InsanityTestData *data);

static void send_signal(DBusConnection *conn, const char *signal_name, const char *path_name, int type,...)
{
   DBusMessage *msg;
   dbus_uint32_t serial = 0;
   va_list ap;

   msg = dbus_message_new_signal(path_name, "net.gstreamer.Insanity.Test", signal_name);
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
   
   printf("Signal %s sent from %s\n", signal_name, path_name);
   
   // free the message and close the connection
   dbus_message_unref(msg);
}

#ifdef USE_CPU_LOAD
static long tv_us_diff(const struct timeval *t0, const struct timeval *t1)
{
  return (t1->tv_sec - t0->tv_sec) * 1000000 + t1->tv_usec - t0->tv_usec;
}
#endif

static void gather_end_of_test_info(InsanityTestData *data)
{
#ifdef USE_CPU_LOAD
  static const char *cpu_load_name = "cpu-load";
  struct rusage rusage;
  struct timeval end;
  unsigned long us;
  int cpu_load;

  getrusage(RUSAGE_SELF, &rusage);
  gettimeofday(&end,NULL);
  us = tv_us_diff(&data->rusage.ru_utime, &rusage.ru_utime)
     + tv_us_diff(&data->rusage.ru_stime, &rusage.ru_stime);
  cpu_load = 100 * us / tv_us_diff (&data->start, &end);
  send_signal (data->conn, "remoteExtraInfoSignal", data->name, DBUS_TYPE_STRING, &cpu_load_name, DBUS_TYPE_UINT32, &cpu_load, DBUS_TYPE_INVALID);
#endif
}

static void insanity_validate(InsanityTestData *data, const char *name, int success)
{
  send_signal (data->conn,"remoteValidateStepSignal",data->name,DBUS_TYPE_STRING,&name,DBUS_TYPE_BOOLEAN,&success,DBUS_TYPE_INVALID);
}

static void insanity_done(InsanityTestData *data)
{
  gather_end_of_test_info(data);
  send_signal (data->conn, "remoteStopSignal", data->name, DBUS_TYPE_INVALID);
}

static int on_setup(InsanityTestData *data)
{
  int ret = insanity_setup(data);
  if (ret < 0) {
    send_signal (data->conn, "remoteStopSignal", data->name, DBUS_TYPE_INVALID);
  }
  else {
    send_signal (data->conn, "remoteReadySignal", data->name, DBUS_TYPE_INVALID);
  }
  return ret;
}

static int on_start(InsanityTestData *data)
{
#ifdef USE_CPU_LOAD
  gettimeofday(&data->start,NULL);
  getrusage(RUSAGE_SELF, &data->rusage);
#endif
  return insanity_start(data);
}

static int on_stop(InsanityTestData *data)
{
  int ret;

  ret=insanity_stop(data);
  if (ret<0)
    return ret;

  gather_end_of_test_info(data);

  return ret;
}

void listen(const char *bus_address,const char *uuid)
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

   InsanityTestData insanity_test_data;

   // initialise the error
   dbus_error_init(&err);
   
   // connect to the bus and check for errors
   conn = dbus_connection_open(bus_address, &err);
   insanity_test_data.conn = conn;
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

   snprintf(insanity_test_data.name, sizeof(insanity_test_data.name), "/net/gstreamer/Insanity/Test/Test%s", uuid);
   snprintf(object_name, sizeof(object_name), "net.gstreamer.Insanity.Test.Test%s", uuid);
   printf("Using object name %s\n",object_name);

   // request our name on the bus and check for errors
   ret = dbus_bus_request_name(conn, object_name, DBUS_NAME_FLAG_REPLACE_EXISTING , &err);
   if (dbus_error_is_set(&err)) { 
      fprintf(stderr, "Name Error (%s)\n", err.message); 
      dbus_error_free(&err);
   }
   if (DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER != ret) { 
      fprintf(stderr, "Not Primary Owner (%d)\n", ret);
      exit(1); 
   }

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
        printf("Got 'Introspect', answering introspect response\n");
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
      else if (dbus_message_is_method_call(msg, "net.gstreamer.Insanity.Test", "remoteInfo"))  {
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
      else if (dbus_message_is_method_call(msg, "net.gstreamer.Insanity.Test", "remoteSetUp"))  {
        printf("Got remoteSetUp\n");
        reply = dbus_message_new_method_return(msg);
        if (!dbus_connection_send(conn, reply, &serial)) {
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        dbus_connection_flush(conn);
        dbus_message_unref(reply);

        on_setup(&insanity_test_data);
      }
#if 0
      else if (dbus_message_is_method_call(msg, "net.gstreamer.Insanity.Test", "remoteTearDown"))  {
        printf("Got remoteTearDown\n");

        on_tear_down(&insanity_test_data);

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
      else if (dbus_message_is_method_call(msg, "net.gstreamer.Insanity.Test", "remoteStop"))  {
        printf("Got remoteStop\n");
        reply = dbus_message_new_method_return(msg);
        if (!dbus_connection_send(conn, reply, &serial)) {
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        dbus_connection_flush(conn);
        dbus_message_unref(reply);

        on_stop(&insanity_test_data);
        done=1;
      }
      else if (dbus_message_is_method_call(msg, "net.gstreamer.Insanity.Test", "remoteTest"))  {
        printf("Got remoteTest\n");
        reply = dbus_message_new_method_return(msg);
        if (!dbus_connection_send(conn, reply, &serial)) {
           fprintf(stderr, "Out Of Memory!\n"); 
           exit(1);
        }
        dbus_connection_flush(conn);
        dbus_message_unref(reply);

        on_start(&insanity_test_data);
      }
      else {
        printf("Got unhandled method call: interface %s, method %s\n", dbus_message_get_interface(msg), dbus_message_get_member(msg));
      }

      // free the message
      dbus_message_unref(msg);
   }

   dbus_connection_unref(conn);
}

int main(int argc, const char **argv)
{
  const char *private_dbus_address;
  const char *uuid;

  if (argc < 2) {
    fprintf(stderr, "Usage: %s <uuid>\n", argv[0]);
    return 1;
  }
  uuid = argv[1];
  private_dbus_address = getenv("PRIVATE_DBUS_ADDRESS");
  if (!private_dbus_address || !private_dbus_address[0]) {
    fprintf(stderr, "The PRIVATE_DBUS_ADDRESS environment variable must be set\n");
    return 1;
  }
#if 0
  printf("uuid: %s\n", uuid);
  printf("PRIVATE_DBUS_ADDRESS: %s\n",private_dbus_address);
#endif
  listen(private_dbus_address, uuid);
  return 0;
}


/* From here, user defined stuff - above is library */

/* Return 0 if success, < 0 if failure */
static int insanity_setup(InsanityTestData *data)
{
  printf("TEST CALLBACK: insanity_setup\n");
  return 0;
}

static int insanity_start(InsanityTestData *data)
{
#if 0
  /* random stuff that takes some cpu */
  int x,y,*z;
#define LIMIT 4096
  printf("TEST CALLBACK: insanity_start\n");
  z=malloc(sizeof(int)*LIMIT*LIMIT);
  for(x=0;x<LIMIT;++x) for (y=0;y<LIMIT;++y) {
    z[y*LIMIT+x]=x*74393/(y+1);
  }
  y=0;
  for(x=0;x<LIMIT*LIMIT;++x) y+=z[x];
  printf("%d\n",y);
  free(z);
#endif
  //insanity_validate(data, "random-event", 1);
  insanity_done(data);
  return 0;
}

static int insanity_stop(InsanityTestData *data)
{
  printf("TEST CALLBACK: insanity_stop\n");
  return 0;
}

