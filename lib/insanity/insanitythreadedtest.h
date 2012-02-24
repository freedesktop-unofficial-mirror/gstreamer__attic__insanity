/* Insanity QA system

       insanitythreadedtest.h

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

#ifndef INSANITY_THREADED_TEST_H_GUARD
#define INSANITY_THREADED_TEST_H_GUARD

#include <glib.h>
#include <glib-object.h>

#include <insanity/insanitydefs.h>
#include <insanity/insanitytest.h>

typedef struct _InsanityThreadedTest InsanityThreadedTest;
typedef struct _InsanityThreadedTestClass InsanityThreadedTestClass;
typedef struct _InsanityThreadedTestPrivateData InsanityThreadedTestPrivateData;

/**
 * InsanityTest:
 *
 * The opaque #InsanityTest data structure.
 */
struct _InsanityThreadedTest {
  InsanityTest parent;

  /*< private >*/
  InsanityThreadedTestPrivateData *priv;

  gpointer _insanity_reserved[INSANITY_PADDING];
};

/**
 * InsanityThreadedTestClass:
 * @parent_class: the parent class structure
 * @test: Start the test
 *
 * Insanity threaded test class. Override the vmethods to customize
 * functionality.
 */
struct _InsanityThreadedTestClass
{
  InsanityTestClass parent_class;

  void (*test) (InsanityThreadedTest *test);

  /*< private >*/
  gpointer _insanity_reserved[INSANITY_PADDING];
};

InsanityThreadedTest *insanity_threaded_test_new(const char *name, const char *description, const char *full_description);

/* Handy macros */
#define INSANITY_TYPE_THREADED_TEST                (insanity_threaded_test_get_type ())
#define INSANITY_THREADED_TEST(obj)                (G_TYPE_CHECK_INSTANCE_CAST ((obj), INSANITY_TYPE_THREADED_TEST, InsanityThreadedTest))
#define INSANITY_THREADED_TEST_CLASS(c)            (G_TYPE_CHECK_CLASS_CAST ((c), INSANITY_TYPE_THREADED_TEST, InsanityThreadedTestClass))
#define INSANITY_IS_THREADED_TEST(obj)             (G_TYPE_CHECK_INSTANCE_TYPE ((obj), INSANITY_TYPE_THREADED_TEST))
#define INSANITY_IS_THREADED_TEST_CLASS(c)         (G_TYPE_CHECK_CLASS_TYPE ((c), INSANITY_TYPE_THREADED_TEST))
#define INSANITY_THREADED_TEST_GET_CLASS(obj)      (G_TYPE_INSTANCE_GET_CLASS ((obj), INSANITY_TYPE_THREADED_TEST, InsanityThreadedTestClass))

GType insanity_threaded_test_get_type (void);

#endif

