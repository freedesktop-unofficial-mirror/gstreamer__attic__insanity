#include <stdio.h>
#include <glib.h>
#include <glib-object.h>
#include "insanity_glib.h"

struct BlankGlibTest {
  InsanityGlibTest parent;
};
typedef struct BlankGlibTest BlankGlibTest;

struct BlankGlibTestClass {
  InsanityGlibTestClass parent_class;
};
typedef struct BlankGlibTestClass BlankGlibTestClass;

#define BLANK_GLIB_TEST_TYPE                (blank_glib_test_get_type ())
#define BLANK_GLIB_TEST(obj)                (G_TYPE_CHECK_INSTANCE_CAST ((obj), BLANK_GLIB_TEST_TYPE, BlankGlibTest))
#define BLANK_GLIB_TEST_CLASS(c)            (G_TYPE_CHECK_CLASS_CAST ((c), BLANK_GLIB_TEST_TYPE, BlankGlibTestClass))
#define IS_BLANK_GLIB_TEST(obj)             (G_TYPE_CHECK_TYPE ((obj), BLANK_GLIB_TEST_TYPE))
#define IS_BLANK_GLIB_TEST_CLASS(c)         (G_TYPE_CHECK_CLASS_TYPE ((c), BLANK_GLIB_TEST_TYPE))
#define BLANK_GLIB_TEST_GET_CLASS(obj)      (G_TYPE_INSTANCE_GET_CLASS ((obj), BLANK_GLIB_TEST_TYPE, BlankGlibTestClass))

G_DEFINE_TYPE (BlankGlibTest, blank_glib_test, INSANITY_GLIB_TEST_TYPE);

static int blank_glib_test_setup(InsanityGlibTest *test)
{
  printf("blank_glib_test_setup\n");
  return INSANITY_GLIB_TEST_CLASS (blank_glib_test_parent_class)->setup(test);
}

static int blank_glib_test_test(InsanityGlibTest *test)
{
  printf("blank_glib_test_test\n");
  return INSANITY_GLIB_TEST_CLASS (blank_glib_test_parent_class)->test(test);
}

static int blank_glib_test_stop(InsanityGlibTest *test)
{
  printf("blank_glib_test_stop\n");
  return INSANITY_GLIB_TEST_CLASS (blank_glib_test_parent_class)->stop(test);
}

static void blank_glib_test_class_init (BlankGlibTestClass *klass)
{
  InsanityGlibTestClass *base_class = INSANITY_GLIB_TEST_CLASS (klass);

  base_class->setup = &blank_glib_test_setup;
  base_class->test = &blank_glib_test_test;
  base_class->stop = &blank_glib_test_stop;
}

static void blank_glib_test_init (BlankGlibTest *test)
{
  (void)test;
}

int main(int argc, const char **argv)
{
  BlankGlibTest *test;
  int ret;

  g_type_init ();

  test = BLANK_GLIB_TEST (g_type_create_instance (blank_glib_test_get_type()));

  ret = insanity_glib_test_run (INSANITY_GLIB_TEST (test), argc, argv);

  g_object_unref (test);

  return ret;
}

