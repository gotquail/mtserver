Simple multi-threaded server done at school, 2013.

Creates a socket to listen on, and accepts multiple clients, each having their own thread. Clients can make simple requests like querying upload time and number of clients.

Usage:
make
./mtserver NUM_THREADS PORT

Test client takes the port number as its only argument.