#include <stdio.h>
#include <glib.h>
#include <glib-object.h>
#include "insanity.h"

struct BlankTest {
  InsanityTest parent;
};
typedef struct BlankTest BlankTest;

struct BlankTestClass {
  InsanityTestClass parent_class;
};
typedef struct BlankTestClass BlankTestClass;

#define BLANK_TEST_TYPE                (blank_test_get_type ())
#define BLANK_TEST(obj)                (G_TYPE_CHECK_INSTANCE_CAST ((obj), BLANK_TEST_TYPE, BlankTest))
#define BLANK_TEST_CLASS(c)            (G_TYPE_CHECK_CLASS_CAST ((c), BLANK_TEST_TYPE, BlankTestClass))
#define IS_BLANK_TEST(obj)             (G_TYPE_CHECK_TYPE ((obj), BLANK_TEST_TYPE))
#define IS_BLANK_TEST_CLASS(c)         (G_TYPE_CHECK_CLASS_TYPE ((c), BLANK_TEST_TYPE))
#define BLANK_TEST_GET_CLASS(obj)      (G_TYPE_INSTANCE_GET_CLASS ((obj), BLANK_TEST_TYPE, BlankTestClass))

G_DEFINE_TYPE (BlankTest, blank_test, INSANITY_TEST_TYPE);

static int blank_test_setup(InsanityTest *test)
{
  printf("blank_test_setup\n");
  return INSANITY_TEST_CLASS (blank_test_parent_class)->setup(test);
}

static int blank_test_start(InsanityTest *test)
{
  printf("blank_test_start\n");
  return INSANITY_TEST_CLASS (blank_test_parent_class)->start(test);
}

static int blank_test_stop(InsanityTest *test)
{
  printf("blank_test_stop\n");
  return INSANITY_TEST_CLASS (blank_test_parent_class)->stop(test);
}

static void blank_test_class_init (BlankTestClass *klass)
{
  InsanityTestClass *base_class = INSANITY_TEST_CLASS (klass);

  base_class->setup = &blank_test_setup;
  base_class->start = &blank_test_start;
  base_class->stop = &blank_test_stop;
}

static void blank_test_init (BlankTest *test)
{
  (void)test;
}

int main(int argc, const char **argv)
{
  BlankTest *test;
  int ret;

  g_type_init ();

  test = BLANK_TEST (g_type_create_instance (blank_test_get_type()));

  ret = insanity_test_run (INSANITY_TEST (test), argc, argv);

  g_object_unref (test);

  return ret;
}

