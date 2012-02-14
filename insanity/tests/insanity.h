#ifndef INSANITY_H_GUARD
#define INSANITY_H_GUARD

struct InsanityTestData;
typedef struct InsanityTestData InsanityTestData;

InsanityTestData *insanity_lib_new_data (void);
void insanity_lib_free_data (InsanityTestData *data);

const char *insanity_lib_get_arg_string(InsanityTestData *data, const char *key);
const char *insanity_lib_get_output_file(InsanityTestData *data, const char *key);
void insanity_lib_done(InsanityTestData *data);
void insanity_lib_validate(InsanityTestData *data, const char *name, int success);
void insanity_lib_extra_info(InsanityTestData *data, const char *name, int type, void *dataptr);

void insanity_lib_set_user_setup_hook (InsanityTestData *data, int (*hook)(InsanityTestData *));
void insanity_lib_set_user_test_hook (InsanityTestData *data, int (*hook)(InsanityTestData *));
void insanity_lib_set_user_stop_hook (InsanityTestData *data, int (*hook)(InsanityTestData *));

int insanity_lib_run(InsanityTestData *data, int argc, const char **argv);

#endif

