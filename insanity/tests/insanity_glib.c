#include <stdio.h>
#include <glib-object.h>
#include "insanity.h"
#include "insanity_glib.h"

static int insanity_glib_test_data_setup_impl (InsanityGlibTestData *data)
{
  (void)data;
  return 0;
}

static int insanity_glib_test_data_test_impl (InsanityGlibTestData *data)
{
  insanity_glib_test_data_done (data);
  return 0;
}

static int insanity_glib_test_data_stop_impl (InsanityGlibTestData *data)
{
  (void)data;
  return 0;
}

static int insanity_glib_test_data_setup (InsanityTestData *data, intptr_t user)
{
  InsanityGlibTestData *gdata = INSANITY_GLIB_TEST_DATA (user);
  (void)data;
  return INSANITY_GLIB_TEST_DATA_GET_CLASS (gdata)->setup (gdata);
}

static int insanity_glib_test_data_test (InsanityTestData *data, intptr_t user)
{
  InsanityGlibTestData *gdata = INSANITY_GLIB_TEST_DATA (user);
  (void)data;
  return INSANITY_GLIB_TEST_DATA_GET_CLASS (gdata)->test (gdata);
}

static int insanity_glib_test_data_stop (InsanityTestData *data, intptr_t user)
{
  InsanityGlibTestData *gdata = INSANITY_GLIB_TEST_DATA (user);
  (void)data;
  return INSANITY_GLIB_TEST_DATA_GET_CLASS (gdata)->stop (gdata);
}



G_DEFINE_TYPE (InsanityGlibTestData, insanity_glib_test_data, G_TYPE_OBJECT);

static void insanity_glib_test_data_finalize (GObject *gobject)
{
  InsanityGlibTestData *data = (InsanityGlibTestData *)gobject;
  insanity_lib_free_data (data->data);
  G_OBJECT_CLASS (insanity_glib_test_data_parent_class)->finalize (gobject);
}

static void insanity_glib_test_data_init (InsanityGlibTestData *data)
{
  data->data = insanity_lib_new_data ();

  insanity_lib_set_user_setup_hook (data->data, &insanity_glib_test_data_setup, (intptr_t)data);
  insanity_lib_set_user_test_hook (data->data, &insanity_glib_test_data_test, (intptr_t)data);
  insanity_lib_set_user_stop_hook (data->data, &insanity_glib_test_data_stop, (intptr_t)data);
}

static void insanity_glib_test_data_class_init (InsanityGlibTestDataClass *klass)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);

  gobject_class->finalize = insanity_glib_test_data_finalize;

  klass->setup = &insanity_glib_test_data_setup_impl;
  klass->test = &insanity_glib_test_data_test_impl;
  klass->stop = &insanity_glib_test_data_stop_impl;
}

const char *insanity_glib_get_arg_string(InsanityGlibTestData *data, const char *key)
{
  return insanity_lib_get_arg_string (data->data, key);
}

const char *insanity_glib_get_output_file(InsanityGlibTestData *data, const char *key)
{
  return insanity_lib_get_output_file (data->data, key);
}

void insanity_glib_test_data_done (InsanityGlibTestData *data)
{
  insanity_lib_done (data->data);
}

void insanity_glib_validate(InsanityGlibTestData *data, const char *name, int success)
{
  insanity_lib_validate (data->data, name, success);
}

void insanity_glib_extra_info(InsanityGlibTestData *data, const char *name, int type, void *dataptr)
{
  insanity_lib_extra_info (data->data, name, type, dataptr);
}

int insanity_glib_run(InsanityGlibTestData *data, int argc, const char **argv)
{
  return insanity_lib_run (data->data, argc, argv);
}

