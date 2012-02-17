#ifndef INSANITY_THREADED_TEST_H_GUARD
#define INSANITY_THREADED_TEST_H_GUARD

#include <glib.h>
#include <glib-object.h>

#include "insanity.h"

struct InsanityThreadedTestPrivateData;
typedef struct InsanityThreadedTestPrivateData InsanityThreadedTestPrivateData;

struct InsanityThreadedTest;
typedef struct InsanityThreadedTest InsanityThreadedTest;

struct InsanityThreadedTest {
  InsanityTest parent;

  InsanityThreadedTestPrivateData *priv;
};

struct InsanityThreadedTestClass
{
  InsanityTestClass parent_class;

  void (*test) (InsanityThreadedTest *test);
};
typedef struct InsanityThreadedTestClass InsanityThreadedTestClass;

InsanityThreadedTest *insanity_threaded_test_new(const char *name, const char *description);

/* Handy macros */
#define INSANITY_THREADED_TEST_TYPE                (insanity_threaded_test_get_type ())
#define INSANITY_THREADED_TEST(obj)                (G_TYPE_CHECK_INSTANCE_CAST ((obj), INSANITY_THREADED_TEST_TYPE, InsanityThreadedTest))
#define INSANITY_THREADED_TEST_CLASS(c)            (G_TYPE_CHECK_CLASS_CAST ((c), INSANITY_THREADED_TEST_TYPE, InsanityThreadedTestClass))
#define IS_INSANITY_THREADED_TEST(obj)             (G_TYPE_CHECK_TYPE ((obj), INSANITY_THREADED_TEST_TYPE))
#define IS_INSANITY_THREADED_TEST_CLASS(c)         (G_TYPE_CHECK_CLASS_TYPE ((c), INSANITY_THREADED_TEST_TYPE))
#define INSANITY_THREADED_TEST_GET_CLASS(obj)      (G_TYPE_INSTANCE_GET_CLASS ((obj), INSANITY_THREADED_TEST_TYPE, InsanityThreadedTestClass))

GType insanity_threaded_test_get_type (void);

#endif

