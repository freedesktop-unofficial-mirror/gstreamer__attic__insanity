#ifndef INSANITY_GLIB_H_GUARD
#define INSANITY_GLIB_H_GUARD

#include "insanity.h"

struct InsanityGlibTest {
  GObject parent;

  InsanityTest *test;
};
typedef struct InsanityGlibTest InsanityGlibTest;

struct InsanityGlibTestClass
{
  GObjectClass parent_class;

  int (*setup) (InsanityGlibTest *test);
  int (*test) (InsanityGlibTest *test);
  int (*stop) (InsanityGlibTest *test);
};
typedef struct InsanityGlibTestClass InsanityGlibTestClass;


/* Handy macros */
#define INSANITY_GLIB_TEST_TYPE                (insanity_glib_test_get_type ())
#define INSANITY_GLIB_TEST(obj)                (G_TYPE_CHECK_INSTANCE_CAST ((obj), INSANITY_GLIB_TEST_TYPE, InsanityGlibTest))
#define INSANITY_GLIB_TEST_CLASS(c)            (G_TYPE_CHECK_CLASS_CAST ((c), INSANITY_GLIB_TEST_TYPE, InsanityGlibTestClass))
#define IS_INSANITY_GLIB_TEST(obj)             (G_TYPE_CHECK_TYPE ((obj), INSANITY_GLIB_TEST_TYPE))
#define IS_INSANITY_GLIB_TEST_CLASS(c)         (G_TYPE_CHECK_CLASS_TYPE ((c), INSANITY_GLIB_TEST_TYPE))
#define INSANITY_GLIB_TEST_GET_CLASS(obj)      (G_TYPE_INSTANCE_GET_CLASS ((obj), INSANITY_GLIB_TEST_TYPE, InsanityGlibTestClass))

GType insanity_glib_test_get_type (void);

const char *insanity_glib_get_arg_string(InsanityGlibTest *test, const char *key);
const char *insanity_glib_get_output_file(InsanityGlibTest *test, const char *key);
void insanity_glib_test_done (InsanityGlibTest *test);
void insanity_glib_test_validate(InsanityGlibTest *test, const char *name, int success);
void insanity_glib_test_extra_info(InsanityGlibTest *test, const char *name, int type, void *dataptr);

int insanity_glib_test_run(InsanityGlibTest *test, int argc, const char **argv);

#endif

