#include <stdio.h>
#include <glib-object.h>
#include "insanity.h"
#include "insanity_glib.h"

static int insanity_glib_test_setup_impl (InsanityGlibTest *test)
{
  (void)test;
  return 0;
}

static int insanity_glib_test_test_impl (InsanityGlibTest *test)
{
  insanity_glib_test_done (test);
  return 0;
}

static int insanity_glib_test_stop_impl (InsanityGlibTest *test)
{
  (void)test;
  return 0;
}

static int insanity_glib_test_setup (InsanityTest *test, intptr_t user)
{
  InsanityGlibTest *gtest = INSANITY_GLIB_TEST (user);
  (void)test;
  return INSANITY_GLIB_TEST_GET_CLASS (gtest)->setup (gtest);
}

static int insanity_glib_test_test (InsanityTest *test, intptr_t user)
{
  InsanityGlibTest *gtest = INSANITY_GLIB_TEST (user);
  (void)test;
  return INSANITY_GLIB_TEST_GET_CLASS (gtest)->test (gtest);
}

static int insanity_glib_test_stop (InsanityTest *test, intptr_t user)
{
  InsanityGlibTest *gtest = INSANITY_GLIB_TEST (user);
  (void)test;
  return INSANITY_GLIB_TEST_GET_CLASS (gtest)->stop (gtest);
}



G_DEFINE_TYPE (InsanityGlibTest, insanity_glib_test, G_TYPE_OBJECT);

static void insanity_glib_test_finalize (GObject *gobject)
{
  InsanityGlibTest *test = (InsanityGlibTest *)gobject;
  insanity_test_free (test->test);
  G_OBJECT_CLASS (insanity_glib_test_parent_class)->finalize (gobject);
}

static void insanity_glib_test_init (InsanityGlibTest *test)
{
  test->test = insanity_test_create ();

  insanity_test_set_user_setup_hook (test->test, &insanity_glib_test_setup, (intptr_t)test);
  insanity_test_set_user_test_hook (test->test, &insanity_glib_test_test, (intptr_t)test);
  insanity_test_set_user_stop_hook (test->test, &insanity_glib_test_stop, (intptr_t)test);
}

static void insanity_glib_test_class_init (InsanityGlibTestClass *klass)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);

  gobject_class->finalize = insanity_glib_test_finalize;

  klass->setup = &insanity_glib_test_setup_impl;
  klass->test = &insanity_glib_test_test_impl;
  klass->stop = &insanity_glib_test_stop_impl;
}

const char *insanity_glib_get_arg_string(InsanityGlibTest *test, const char *key)
{
  return insanity_test_get_arg_string (test->test, key);
}

const char *insanity_glib_get_output_file(InsanityGlibTest *test, const char *key)
{
  return insanity_test_get_output_file (test->test, key);
}

void insanity_glib_test_done (InsanityGlibTest *test)
{
  insanity_test_done (test->test);
}

void insanity_glib_test_validate(InsanityGlibTest *test, const char *name, int success)
{
  insanity_test_validate (test->test, name, success);
}

void insanity_glib_test_extra_info(InsanityGlibTest *test, const char *name, int type, void *dataptr)
{
  insanity_test_extra_info (test->test, name, type, dataptr);
}

int insanity_glib_test_run(InsanityGlibTest *test, int argc, const char **argv)
{
  return insanity_test_run (test->test, argc, argv);
}

