#ifndef INSANITY_H_GUARD
#define INSANITY_H_GUARD

#include <glib.h>
#include <glib-object.h>
#include <dbus/dbus.h>

#include <stdint.h>

#include <unistd.h>
#include <sys/time.h>
#include <sys/resource.h>

/* getrusage is Unix API */
#define USE_CPU_LOAD

// FIXME: move this to a private struct
struct InsanityTest;
typedef struct InsanityTest InsanityTest;
struct InsanityTest {
  GObject parent;

  DBusConnection *conn;
#ifdef USE_CPU_LOAD
  struct timeval start;
  struct rusage rusage;
#endif
  char name[128];
  DBusMessage *args;
  int cpu_load;
};

struct InsanityTestClass
{
  GObjectClass parent_class;

  gboolean (*setup) (InsanityTest *test);
  gboolean (*start) (InsanityTest *test);
  gboolean (*stop) (InsanityTest *test);
};
typedef struct InsanityTestClass InsanityTestClass;


/* Handy macros */
#define INSANITY_TEST_TYPE                (insanity_test_get_type ())
#define INSANITY_TEST(obj)                (G_TYPE_CHECK_INSTANCE_CAST ((obj), INSANITY_TEST_TYPE, InsanityTest))
#define INSANITY_TEST_CLASS(c)            (G_TYPE_CHECK_CLASS_CAST ((c), INSANITY_TEST_TYPE, InsanityTestClass))
#define IS_INSANITY_TEST(obj)             (G_TYPE_CHECK_TYPE ((obj), INSANITY_TEST_TYPE))
#define IS_INSANITY_TEST_CLASS(c)         (G_TYPE_CHECK_CLASS_TYPE ((c), INSANITY_TEST_TYPE))
#define INSANITY_TEST_GET_CLASS(obj)      (G_TYPE_INSTANCE_GET_CLASS ((obj), INSANITY_TEST_TYPE, InsanityTestClass))

GType insanity_test_get_type (void);

const char *insanity_test_get_arg_string(InsanityTest *test, const char *key);
const char *insanity_test_get_output_file(InsanityTest *test, const char *key);
void insanity_test_done(InsanityTest *test);
void insanity_test_validate(InsanityTest *test, const char *name, gboolean success);
void insanity_test_extra_info(InsanityTest *test, const char *name, int type, void *dataptr);

gboolean insanity_test_run(InsanityTest *test, int argc, const char **argv);

#endif

