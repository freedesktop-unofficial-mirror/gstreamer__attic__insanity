/* Insanity QA system

       insanitytest.h

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

#ifndef INSANITY_TEST_H_GUARD
#define INSANITY_TEST_H_GUARD

#include <glib.h>
#include <glib-object.h>
#include <insanity/insanitydefs.h>

G_BEGIN_DECLS

typedef struct _InsanityTest InsanityTest;
typedef struct _InsanityTestClass InsanityTestClass;
typedef struct _InsanityTestPrivateData InsanityTestPrivateData;

/**
 * InsanityTest:
 *
 * The opaque #InsanityTest data structure.
 */
struct _InsanityTest {
  GObject parent;

  /*< private >*/
  InsanityTestPrivateData *priv;

  gpointer _insanity_reserved[INSANITY_PADDING];
};

/**
 * InsanityTestClass:
 * @parent_class: the parent class structure
 * @setup: setup anything the test needs before starting. Arguments are
 *         now available at this time. Any cleanup for this work should
 *         be done in teardown.
 * @start: start the test. Should signal ready when done.
 * @stop: stop the test.
 * @teardown: cleanup anything before leaving the test. The test will not
 *            be started again after this.
 *
 * Insanity test class. Override the vmethods to customize functionality.
 */
struct _InsanityTestClass
{
  GObjectClass parent_class;

  /*< public >*/
  /* vtable */
  gboolean (*setup) (InsanityTest *test);
  gboolean (*start) (InsanityTest *test);
  void (*stop) (InsanityTest *test);
  void (*teardown) (InsanityTest *test);

  /*< private >*/
  gpointer _insanity_reserved[INSANITY_PADDING];
};

/* Handy macros */
#define INSANITY_TYPE_TEST                (insanity_test_get_type ())
#define INSANITY_TEST(obj)                (G_TYPE_CHECK_INSTANCE_CAST ((obj), INSANITY_TYPE_TEST, InsanityTest))
#define INSANITY_TEST_CLASS(c)            (G_TYPE_CHECK_CLASS_CAST ((c), INSANITY_TYPE_TEST, InsanityTestClass))
#define INSANITY_IS_TEST(obj)             (G_TYPE_CHECK_INSTANCE_TYPE ((obj), INSANITY_TYPE_TEST))
#define INSANITY_IS_TEST_CLASS(c)         (G_TYPE_CHECK_CLASS_TYPE ((c), INSANITY_TYPE_TEST))
#define INSANITY_TEST_GET_CLASS(obj)      (G_TYPE_INSTANCE_GET_CLASS ((obj), INSANITY_TYPE_TEST, InsanityTestClass))

GType insanity_test_get_type (void);

InsanityTest *insanity_test_new(const char *name, const char *description, const char *full_description);
void insanity_test_add_checklist_item(InsanityTest *test, const char *label, const char *description, const char *error_hint);
void insanity_test_add_argument(InsanityTest *test, const char *label, const char *description, const char *full_description, gboolean global, const GValue *default_value);
void insanity_test_add_output_file(InsanityTest *test, const char *label, const char *description, gboolean global);
void insanity_test_add_extra_info(InsanityTest *test, const char *label, const char *description);

gboolean insanity_test_get_argument(InsanityTest *test, const char *key, GValue *value);
const char *insanity_test_get_output_filename(InsanityTest *test, const char *key);
void insanity_test_done(InsanityTest *test);
void insanity_test_validate_step(InsanityTest *test, const char *name, gboolean success, const char *description);
void insanity_test_set_extra_info(InsanityTest *test, const char *name, const GValue *data);
void insanity_test_ping(InsanityTest *test);

gboolean insanity_test_check (InsanityTest *test, const char *step, gboolean expr, const char *msg,...);
#define INSANITY_TEST_CHECK(test, step, expr) insanity_test_check(test, step, (expr), "%s:%u: check failed: %s", __FILE__, __LINE__, #expr)

void insanity_test_printf (InsanityTest *test, const char *format,...);

gboolean insanity_test_run(InsanityTest *test, int *argc, char ***argv);

G_END_DECLS

#endif

