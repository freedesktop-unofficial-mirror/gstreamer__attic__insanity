# handmade, needs autofoo I guess (would that work in Windows though ?)

C_TESTS=blankc

pcfiles=dbus-1

CFLAGS=-Wall -W $(shell pkg-config --cflags $(pcfiles))
LDFLAGS=$(shell pkg-config --libs $(pcfiles))

all: $(C_TESTS)

%: %.c insanity.a
	gcc $(CFLAGS) $(LDFLAGS) -o $@ $< insanity.a

insanity.a: insanity.o
	ar cru $@ $<
	ranlib $@

insanity.o: insanity.c
	gcc -c -o $@ $(CFLAGS) $<

#%.so: %.c
#	gcc -shared -c -o $@ $<
#
#all: $(foreach test, $(C_TESTS), $(test).so)

