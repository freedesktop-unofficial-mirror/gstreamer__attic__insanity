/* Insanity QA system

       insanitythreadedtest.c

 Copyright (c) 2012, Collabora Ltd <slomo@collabora.co.uk>

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
/**
 * SECTION:insanitythreadedtest
 * @short_description: Threaded Test
 * @see_also: #InsanityTest
 *
 * %TODO.
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include "insanitythreadedtest.h"
#include "insanityprivate.h"

/* if global vars are good enough for gstreamer, it's good enough for insanity */
static guint test_signal;

G_DEFINE_TYPE (InsanityThreadedTest, insanity_threaded_test,
    INSANITY_TYPE_TEST);

struct _InsanityThreadedTestPrivateData
{
  GThread *thread;
};

static gpointer
test_thread_func (gpointer data)
{
  InsanityThreadedTest *test = INSANITY_THREADED_TEST (data);

  g_signal_emit (test, test_signal, 0, NULL);

  test->priv->thread = NULL;

  return NULL;
}

static gboolean
insanity_threaded_test_start (InsanityTest * itest)
{
  InsanityThreadedTest *test = INSANITY_THREADED_TEST (itest);

  if (test->priv->thread)
    return FALSE;

  if (!INSANITY_TEST_CLASS (insanity_threaded_test_parent_class)->start (itest))
    return FALSE;

  test->priv->thread =
#if GLIB_CHECK_VERSION(2,31,2)
      g_thread_new ("insanity_worker", test_thread_func, test);
#else
      g_thread_create (test_thread_func, test, TRUE, NULL);
#endif

  if (!test->priv->thread)
    return FALSE;

  return TRUE;
}

static void
insanity_threaded_test_init (InsanityThreadedTest * test)
{
  InsanityThreadedTestPrivateData *priv = G_TYPE_INSTANCE_GET_PRIVATE (test,
      INSANITY_TYPE_THREADED_TEST, InsanityThreadedTestPrivateData);

  test->priv = priv;
}

static void
insanity_threaded_test_class_init (InsanityThreadedTestClass * klass)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);
  InsanityTestClass *test_class = INSANITY_TEST_CLASS (klass);

  test_class->start = &insanity_threaded_test_start;

  g_type_class_add_private (klass, sizeof (InsanityThreadedTestPrivateData));

  test_signal = g_signal_new ("test",
      G_TYPE_FROM_CLASS (gobject_class),
      G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS,
      G_STRUCT_OFFSET (InsanityThreadedTestClass, test),
      NULL, NULL, NULL, G_TYPE_NONE /* return_type */ ,
      0, NULL);
}

/**
 * insanity_threaded_test_new:
 * @name: the short name of the test.
 * @description: a one line description of the test.
 * @full_description: (allow-none): an optional longer description of the test.
 *
 * This function creates a new threaded test with the given properties.
 *
 * Threaded tests create a thread, and the test signal which will be called
 * in the new thread.
 *
 * Returns: (transfer full): a new #InsanityThreadedTest instance.
 */
InsanityThreadedTest *
insanity_threaded_test_new (const char *name, const char *description,
    const char *full_description)
{
  InsanityThreadedTest *test;

  g_return_val_if_fail (name != NULL, NULL);
  g_return_val_if_fail (check_valid_label (name), NULL);
  g_return_val_if_fail (description != NULL, NULL);


  if (full_description)
    test = g_object_new (INSANITY_TYPE_THREADED_TEST,
        "name", name, "description", description, "full-description",
        full_description, NULL);
  else
    test = g_object_new (INSANITY_TYPE_THREADED_TEST,
        "name", name, "description", description, NULL);

  return test;
}
