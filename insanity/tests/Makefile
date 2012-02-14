# handmade, needs autofoo I guess (would that work in Windows though ?)

C_TESTS=blankc blankc-glib

pcfiles=glib-2.0 gobject-2.0 dbus-1

CFLAGS=-Wall -W $(shell pkg-config --cflags $(pcfiles))
LDFLAGS=$(shell pkg-config --libs $(pcfiles))

all: $(C_TESTS)

%: %.c insanity.a insanity_glib.a
	gcc $(CFLAGS) $(LDFLAGS) -o $@ $< insanity_glib.a insanity.a

insanity.a: insanity.o
	ar cru $@ $<
	ranlib $@

insanity.o: insanity.c
	gcc -c -o $@ $(CFLAGS) $<

insanity_glib.a: insanity_glib.o
	ar cru $@ $<
	ranlib $@

insanity_glib.o: insanity_glib.c
	gcc -c -o $@ $(CFLAGS) $<

.PHONY: clean
clean:
	rm -f *.o *.a

#%.so: %.c
#	gcc -shared -c -o $@ $<
#
#all: $(foreach test, $(C_TESTS), $(test).so)

