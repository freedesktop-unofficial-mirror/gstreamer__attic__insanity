#include <dbus/dbus.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <stdint.h>
#include "insanity.h"

/* Return 0 if success, < 0 if failure */
static int blank_setup(InsanityTest *test, intptr_t user)
{
  (void)test;
  (void)user;
  printf("blank_setup callback\n");

  /*
  printf("Example args:\n");
  printf("uri: %s\n", insanity_lib_get_arg_string (test, "uri"));
  printf("uuid: %s\n", insanity_lib_get_arg_string (test, "uuid"));
  printf("foo: %s\n", insanity_lib_get_arg_string (test, "foo"));
  printf("output file 'foo': %s\n", insanity_lib_get_output_file (test, "foo"));
  printf("output file 'dummy-output-file': %s\n", insanity_lib_get_output_file (test, "dummy-output-file"));
  */
  return 0;
}

static int blank_test(InsanityTest *test, intptr_t user)
{
  (void)test;
  (void)user;
  printf("blank_test callback\n");
#if 0
  /* random stuff that takes some cpu */
  int x,y,*z;
#define LIMIT 4096
  z=malloc(sizeof(int)*LIMIT*LIMIT);
  for(x=0;x<LIMIT;++x) for (y=0;y<LIMIT;++y) {
    z[y*LIMIT+x]=x*74393/(y+1);
  }
  y=0;
  for(x=0;x<LIMIT*LIMIT;++x) y+=z[x];
  printf("%d\n",y);
  free(z);
#endif
  //insanity_test_validate(test, "random-event", 1);
  insanity_test_done(test);
  return 0;
}

static int blank_stop(InsanityTest *test, intptr_t user)
{
  (void)test;
  (void)user;
  printf("blank_stop callback\n");
  return 0;
}

int main(int argc, const char **argv)
{
  InsanityTest *test = insanity_test_create ();
  int ret;

  insanity_test_set_user_setup_hook(test, &blank_setup, 0);
  insanity_test_set_user_test_hook(test, &blank_test, 0);
  insanity_test_set_user_stop_hook(test, &blank_stop, 0);

  ret = insanity_test_run(test, argc, argv);

  insanity_test_free (test);

  return ret;
}

