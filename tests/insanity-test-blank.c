/* Insanity QA system

 Copyright (c) 2012, Collabora Ltd <vincent@collabora.co.uk>

 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU Lesser General Public
 License as published by the Free Software Foundation; either
 version 2.1 of the License, or (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 Lesser General Public License for more details.

 You should have received a copy of the GNU Lesser General Public
 License along with this program; if not, write to the
 Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 Boston, MA 02111-1307, USA.
*/

#include <stdio.h>
#include <glib.h>
#include <glib-object.h>
#include <insanity/insanity.h>

static gboolean
blank_test_setup (InsanityTest * test)
{
  (void) test;
  printf ("blank_test_setup\n");
  return TRUE;
}

static gboolean
blank_test_start (InsanityTest * test)
{
  GValue value, zero = { 0 };
  const char *fn;

  value = zero;

  if (insanity_test_get_argument (test, "uri", &value)) {
    const char *uri = g_value_get_string (&value);
    printf ("uri: %s\n", uri);
    g_value_unset (&value);
  }

  fn = insanity_test_get_output_filename (test, "dummy-output-file");
  printf ("fn: %s\n", fn);
  fn = insanity_test_get_output_filename (test, "dummy-output-file-global");
  printf ("fn-global: %s\n", fn);

  value = zero;
  if (insanity_test_get_argument (test, "some-int", &value)) {
    gint i = g_value_get_int (&value);
    printf ("some-int: %d\n", i);
    g_value_unset (&value);
  }

  (void) test;
  printf ("blank_test_start\n");

  return TRUE;
}

static void
blank_test_stop (InsanityTest * test)
{
  (void) test;
  printf ("blank_test_stop\n");
}

static void
blank_test_teardown (InsanityTest * test)
{
  (void) test;
  printf ("blank_test_teardown\n");
}

static void
blank_test_test (InsanityTest * test)
{
  GValue info = { 0 };

  printf ("blank_test_test\n");

  /* Show how to validate checklist items and send extra info */
  insanity_test_validate_checklist_item (test, "random-checklist-item", TRUE,
      "Explanation of random-checklist-item failure");
  g_value_init (&info, G_TYPE_STRING);
  g_value_set_string (&info, "Foo");
  insanity_test_set_extra_info (test, "random-extra-info", &info);
  g_value_unset (&info);

  if (!INSANITY_TEST_CHECK (test, "random-other-checklist-item", 1 != 0))
    goto done;

  insanity_test_ping (test);

  insanity_test_validate_checklist_item (test, "random-other-checklist-item", TRUE,
      "Explanation of random-checklist-item failure");

  INSANITY_LOG(test,"default",INSANITY_LOG_LEVEL_NONE,"log:none\n");
  INSANITY_LOG(test,"default",INSANITY_LOG_LEVEL_INFO,"log:info\n");
  INSANITY_LOG(test,"default",INSANITY_LOG_LEVEL_DEBUG,"log:debug\n");
  INSANITY_LOG(test,"default",INSANITY_LOG_LEVEL_SPAM,"log:spam\n");
  insanity_test_printf(test,"log:via-test\n");
  INSANITY_LOG(test,"cat1",INSANITY_LOG_LEVEL_INFO,"log:cat1\n");
  INSANITY_LOG(test,"cat2",INSANITY_LOG_LEVEL_INFO,"log:cat2\n");

done:
  /* Must be called when the test is done */
  insanity_test_done (test);
}

int
main (int argc, char **argv)
{
  InsanityTest *test;
  gboolean ret;
  GValue def = { 0 };

  g_type_init ();

  test =
      INSANITY_TEST (insanity_threaded_test_new ("blank-c-test",
          "Sample test that does nothing", "some longer description"));

  insanity_test_add_checklist_item (test, "random-checklist-item",
      "Some random checklist item, nothing much", "Probably something wrong here");
  insanity_test_add_checklist_item (test, "random-other-checklist-item",
      "Some random checklist item, nothing much", "Not going to happen");
  insanity_test_add_extra_info (test, "random-extra-info",
      "Some random extra info");

  g_value_init (&def, G_TYPE_STRING);
  g_value_set_string (&def, "http://127.0.0.1/");
  insanity_test_add_argument (test, "uri", "URI description",
      "URI full description", TRUE, &def);
  g_value_unset (&def);

  g_value_init (&def, G_TYPE_INT);
  g_value_set_int (&def, 123);
  insanity_test_add_argument (test, "some-int", "Some random integer",
      "Some integer here", TRUE, &def);
  g_value_unset (&def);

  insanity_test_add_output_file (test, "dummy-output-file", "dummy output file",
      FALSE);
  insanity_test_add_output_file (test, "dummy-output-file-global",
      "dummy output file", TRUE);

  g_signal_connect_after (test, "setup", G_CALLBACK (&blank_test_setup), 0);
  g_signal_connect_after (test, "start", G_CALLBACK (&blank_test_start), 0);
  g_signal_connect (test, "stop", G_CALLBACK (&blank_test_stop), 0);
  g_signal_connect (test, "teardown", G_CALLBACK (&blank_test_teardown), 0);
  g_signal_connect_after (test, "test", G_CALLBACK (&blank_test_test), 0);


  ret = insanity_test_run (test, &argc, &argv);

  g_object_unref (test);

  return ret ? 0 : 1;
}
