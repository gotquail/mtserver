CC = gcc
CFLAGS = -I.
DEPS = mtserver.h
OBJ = mtserver.o

%.o: %.c $(DEPS)
	$(CC) -c -o $@ $< $(CFLAGS)

mtserver: $(OBJ)
	gcc -pthread -o $@ $^ $(CFLAGS)
