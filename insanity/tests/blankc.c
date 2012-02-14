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
static int blank_setup(InsanityTestData *data, intptr_t user)
{
  (void)data;
  (void)user;
  printf("blank_setup callback\n");

  /*
  printf("Example args:\n");
  printf("uri: %s\n", insanity_lib_get_arg_string (data, "uri"));
  printf("uuid: %s\n", insanity_lib_get_arg_string (data, "uuid"));
  printf("foo: %s\n", insanity_lib_get_arg_string (data, "foo"));
  printf("output file 'foo': %s\n", insanity_lib_get_output_file (data, "foo"));
  printf("output file 'dummy-output-file': %s\n", insanity_lib_get_output_file (data, "dummy-output-file"));
  */
  return 0;
}

static int blank_test(InsanityTestData *data, intptr_t user)
{
  (void)data;
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
  //insanity_lib_validate(data, "random-event", 1);
  insanity_lib_done(data);
  return 0;
}

static int blank_stop(InsanityTestData *data, intptr_t user)
{
  (void)data;
  (void)user;
  printf("blank_stop callback\n");
  return 0;
}

int main(int argc, const char **argv)
{
  InsanityTestData *data = insanity_lib_new_data ();
  int ret;

  insanity_lib_set_user_setup_hook(data, &blank_setup, 0);
  insanity_lib_set_user_test_hook(data, &blank_test, 0);
  insanity_lib_set_user_stop_hook(data, &blank_stop, 0);

  ret = insanity_lib_run(data, argc, argv);

  insanity_lib_free_data (data);

  return ret;
}

