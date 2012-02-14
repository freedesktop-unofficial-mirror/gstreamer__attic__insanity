#ifndef INSANITY_GLIB_H_GUARD
#define INSANITY_GLIB_H_GUARD

#include "insanity.h"

struct InsanityGlibTestData {
  GObject parent;

  InsanityTestData *data;
};
typedef struct InsanityGlibTestData InsanityGlibTestData;

struct InsanityGlibTestDataClass
{
  GObjectClass parent_class;

  int (*setup) (InsanityGlibTestData *data);
  int (*test) (InsanityGlibTestData *data);
  int (*stop) (InsanityGlibTestData *data);
};
typedef struct InsanityGlibTestDataClass InsanityGlibTestDataClass;


/* Handy macros */
#define INSANITY_GLIB_TEST_DATA_TYPE                (insanity_glib_test_data_get_type ())
#define INSANITY_GLIB_TEST_DATA(obj)                (G_TYPE_CHECK_INSTANCE_CAST ((obj), INSANITY_GLIB_TEST_DATA_TYPE, InsanityGlibTestData))
#define INSANITY_GLIB_TEST_DATA_CLASS(c)            (G_TYPE_CHECK_CLASS_CAST ((c), INSANITY_GLIB_TEST_DATA_TYPE, InsanityGlibTestDataClass))
#define IS_INSANITY_GLIB_TEST_DATA(obj)             (G_TYPE_CHECK_TYPE ((obj), INSANITY_GLIB_TEST_DATA_TYPE))
#define IS_INSANITY_GLIB_TEST_DATA_CLASS(c)         (G_TYPE_CHECK_CLASS_TYPE ((c), INSANITY_GLIB_TEST_DATA_TYPE))
#define INSANITY_GLIB_TEST_DATA_GET_CLASS(obj)      (G_TYPE_INSTANCE_GET_CLASS ((obj), INSANITY_GLIB_TEST_DATA_TYPE, InsanityGlibTestDataClass))

GType insanity_glib_test_data_get_type (void);

const char *insanity_glib_get_arg_string(InsanityGlibTestData *data, const char *key);
const char *insanity_glib_get_output_file(InsanityGlibTestData *data, const char *key);
void insanity_glib_test_data_done (InsanityGlibTestData *data);
void insanity_glib_validate(InsanityGlibTestData *data, const char *name, int success);
void insanity_glib_extra_info(InsanityGlibTestData *data, const char *name, int type, void *dataptr);

int insanity_glib_run(InsanityGlibTestData *data, int argc, const char **argv);

#endif

