C_TESTS=blankc

CFLAGS=-Wall -W

%: %.c
	gcc $(CFLAGS) -o $@ $< `pkg-config --cflags --libs dbus-glib-1`

all: $(C_TESTS)

#%.so: %.c
#	gcc -shared -c -o $@ $<
#
#all: $(foreach test, $(C_TESTS), $(test).so)

