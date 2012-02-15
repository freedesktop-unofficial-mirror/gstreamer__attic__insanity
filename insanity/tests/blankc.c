#include <stdio.h>
#include <glib.h>
#include <glib-object.h>
#include "insanity.h"

static gboolean blank_test_setup(InsanityTest *test)
{
  (void)test;
  printf("blank_test_setup\n");
  return TRUE;
}

static gboolean blank_test_start(InsanityTest *test)
{
  printf("blank_test_start\n");
  insanity_test_done(test);
  return TRUE;
}

static void blank_test_stop(InsanityTest *test)
{
  (void)test;
  printf("blank_test_stop\n");
}

int main(int argc, const char **argv)
{
  InsanityTest *test;
  int ret;

  g_type_init ();

  test = INSANITY_TEST (g_type_create_instance (insanity_test_get_type()));

  g_signal_connect_after (test, "setup", G_CALLBACK (&blank_test_setup), 0);
  g_signal_connect_after (test, "start", G_CALLBACK (&blank_test_start), 0);
  g_signal_connect (test, "stop", G_CALLBACK (&blank_test_stop), 0);

  ret = insanity_test_run (test, argc, argv);

  g_object_unref (test);

  return ret;
}

