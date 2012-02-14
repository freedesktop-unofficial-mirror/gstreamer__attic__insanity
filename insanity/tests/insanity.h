#ifndef INSANITY_H_GUARD
#define INSANITY_H_GUARD

#include <stdint.h>

struct InsanityTest;
typedef struct InsanityTest InsanityTest;

InsanityTest *insanity_test_create (void);
void insanity_test_init (InsanityTest *test);
void insanity_test_clear (InsanityTest *test);
void insanity_test_free (InsanityTest *test);

const char *insanity_test_get_arg_string(InsanityTest *test, const char *key);
const char *insanity_test_get_output_file(InsanityTest *test, const char *key);
void insanity_test_done(InsanityTest *test);
void insanity_test_validate(InsanityTest *test, const char *name, int success);
void insanity_test_extra_info(InsanityTest *test, const char *name, int type, void *dataptr);

void insanity_test_set_user_setup_hook (InsanityTest *test, int (*hook)(InsanityTest *, intptr_t), intptr_t user);
void insanity_test_set_user_test_hook (InsanityTest *test, int (*hook)(InsanityTest *, intptr_t), intptr_t user);
void insanity_test_set_user_stop_hook (InsanityTest *test, int (*hook)(InsanityTest *, intptr_t), intptr_t user);

int insanity_test_run(InsanityTest *test, int argc, const char **argv);

#endif

