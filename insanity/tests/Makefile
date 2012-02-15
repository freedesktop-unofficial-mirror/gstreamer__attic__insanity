# handmade, needs autofoo I guess (would that work in Windows though ?)

C_TESTS=blankc

pcfiles=glib-2.0 gobject-2.0 dbus-1

CFLAGS=-g -O0 -Wall -W $(shell pkg-config --cflags $(pcfiles))
LDFLAGS=$(shell pkg-config --libs $(pcfiles))

all: $(C_TESTS)

%: %.c insanity.a
	gcc $(CFLAGS) $(LDFLAGS) -o $@ $< insanity.a

insanity.a: insanity.o
	ar cru $@ $<
	ranlib $@

insanity.o: insanity.c
	gcc -c -o $@ $(CFLAGS) $<

#insanity_glib.a: insanity_glib.o
#	ar cru $@ $<
#	ranlib $@
#
#insanity_glib.o: insanity_glib.c
#	gcc -c -o $@ $(CFLAGS) $<

.PHONY: clean
clean:
	rm -f *.o *.a *.pyc $(C_TESTS)

#%.so: %.c
#	gcc -shared -c -o $@ $<
#
#all: $(foreach test, $(C_TESTS), $(test).so)

