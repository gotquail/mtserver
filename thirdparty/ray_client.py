import socket
import sys
import struct
import time

def new_sock():
  global port
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.settimeout(0.100)
  time.sleep(0.05)
  sock.connect(('localhost', port))
  return sock

port = int(sys.argv[1])


sock = new_sock()

# Single-connection tests

# TEST 1: Well-formed requests
#
# (1) send uptime, and make sure it gets *something back*
# (2) send uptime again, making sure *something* is received back, and 
#     a reasonable time difference was observed
# (3) check that "load" correctly returns 1 a few times
# (4) check that "exit" correctly returns 0, and the connection is actually closed
#sock = new_sock()
print "="*10 + "\nTEST 1\n" + "="*10

# (1)
sock.sendall("uptime")
v = -1
try:
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 1.1: receive timed out"

# (2)
time.sleep(1.2)

sock.sendall("uptime")
v2 = -2
try:
  r = sock.recv(4)
  v2 = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 1.2: receive timed out"
if v2 - v > 0 and v > 0 and v2 > 0:
  print "TEST 1.2: OK... Reasonable, difference is " + str(v2-v) + " seconds"
else:
  print "TEST 1.2: ERROR... first time received was " + str(v) + ", second was " + str(v2)

# (3)
sock.sendall("load")
v = -1
try:
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 1.3: receive timed out"
if v == 1:
  print "TEST 1.3: OK... Correctly received a load of 1"
else:
  print "TEST 1.3: ERROR... load returned " + str(v)

sock.sendall("load")
v = -1
try:
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 1.3: receive timed out"
if v == 1:
  print "TEST 1.3: OK... Correctly received a load of 1"
else:
  print "TEST 1.3: ERROR... load returned " + str(v)

# (4)
sock.sendall("exit")
v = -1
try:
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 1.4: receive timed out"
if v == 0:
  print "TEST 1.4: OK... Correctly received exit code of 0"
else:
  print "TEST 1.4: ERROR... exit returned " + str(v)

time.sleep(0.1)

v = -1
try:
  sock.sendall("exit")
  r = sock.recv(4)
  if (r):
    v = struct.unpack("i", r)[0]
except:
  pass
if v == -1:
  print "TEST 1.4: OK... receive timed out; connection is correctly closed"
else:
  print "TEST 1.4: ERROR... exit command didn't close connection " + str(v)


# TEST 2: Robustness tests
#
# (1) send 3 garbage chars, expecting a close
# (2) send another 4 garbage chars on a new socket, which should be closed after only 3 get through
# (3) send 1 garbage char, a valid "load", and 2 more garbage chars
# (4) Test "control-C"
# (5) Test buffer overrun
# (6) Test "uptimexit" - make sure the "e" can't be shared
sock.close()
sock = new_sock()
time.sleep(0.1)
print "\n" + "="*10 + "\nTEST 2\n" + "="*10

# (1)
sock.sendall("a")
v = -2
try:
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 2.1: receive timed out"
if v == -1:
  print "TEST 2.1: OK... Correctly received return code of -1"
else:
  print "TEST 2.1: ERROR... -1 not returned for bogus request"

time.sleep(0.001)
sock.sendall("b")
v = -2
try:
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 2.1: receive timed out"
if v == -1:
  print "TEST 2.1: OK... Correctly received return code of -1"
else:
  print "TEST 2.1: ERROR... -1 not returned for bogus request"

time.sleep(0.001)
sock.sendall("c")
v = -2
try:
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 2.1: receive timed out"
if v == -1:
  print "TEST 2.1: OK... Correctly received return code of -1"
else:
  print "TEST 2.1: ERROR... -1 not returned for bogus request"
v = -2
try:
  r = sock.recv(4)
  if r:
    v = struct.unpack("i", r)[0]
except socket.timeout:
  pass
if v == -2:
  print "TEST 2.1: OK... Correctly timed out"
else:
  print "TEST 2.1: Didn't time out"

# (2)
sock.close()
sock = new_sock()

time.sleep(0.001)
v = -2
try:
  sock.sendall("xyzz")
  r = sock.recv(4)
  if (r):
    v = struct.unpack("i", r)[0]
except:
  print "TEST 2.2: first receive timed out"
if v == -1:
  print "TEST 2.2: OK... received first -1"
else:
  print "TEST 2.2: ERROR... didn't get -1 back for the 'x'"
v = -2
try:
  r = sock.recv(4)
  if (r):
    v = struct.unpack("i", r)[0]
except:
  print "TEST 2.2: second receive timed out"
if v == -1:
  print "TEST 2.2: OK... received second -1"
else:
  print "TEST 2.2: ERROR... didn't get -1 back for the 'y'"
v = -2
try:
  r = sock.recv(4)
  if (r):
    v = struct.unpack("i", r)[0]
except:
  print "TEST 2.2: second receive timed out"
if v == -1:
  print "TEST 2.2: OK... received third -1"
else:
  print "TEST 2.2: ERROR... didn't get -1 back for the 'y'"
v = -2
try:
  r = sock.recv(4)
  if (r):
    v = struct.unpack("i", r)[0]
except:
  pass
if v == -2:
  print "TEST 2.2: OK... receive timed out; connection is correctly closed"
else:
  print "TEST 2.2: ERROR... exit command didn't close connection " + str(v)

# (3)
sock.close()
sock = new_sock()

sock.sendall("zloady")
v, v2, v3 = -2, -2, -2
try:
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
  r2 = sock.recv(4)
  v2 = struct.unpack("i", r2)[0]
  r3 = sock.recv(4)
  v3 = struct.unpack("i", r3)[0]
except socket.timeout:
  print "TEST 2.3: receive timed out"
if v == -1:
  print "TEST 2.3: OK... Correctly received return code of -1"
else:
  print "TEST 2.3: ERROR... -1 not returned for bogus request"
if v2 == 1:
  print "TEST 2.3: OK... Correctly received load of 1"
else:
  print "TEST 2.3: ERROR... load was not 1, it was " + str(v2)
if v3 == -1:
  print "TEST 2.3: OK... Correctly received return code of -1"
else:
  print "TEST 2.3: ERROR... -1 not returned for bogus request"

v, v2 = -2, -2
try:
  sock.sendall("zz")
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
  r2 = sock.recv(4)
  if (r2):
    v2 = struct.unpack("i", r2)[0]
except:
  pass
if v == -1:
  print "TEST 2.3: OK... -1 returned for invalid request"
else:
  print "TEST 2.3: ERROR... -1 not returned for bogus request"
if v2 == -1:
  print "TEST 2.3: OK... -1 returned for invalid request"
else:
  print "TEST 2.3: ERROR... -1 not returned for bogus request"
v = -2
try:
  sock.sendall("z")
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
except:
  pass
if v == -2:
  print "TEST 2.3: OK... receive timed out; connection is correctly closed"
else:
  print "TEST 2.3: ERROR... exit command didn't close connection " + str(v)
  

# (4)
sock.close()
sock = new_sock()

time.sleep(0.001)
v = -2
try:
  sock.sendall("l" + chr(3))
  r = sock.recv(4)
  if (r):
    v = struct.unpack("i", r)[0]
except:
  pass
if v == -2:
  print "TEST 2.4: OK... receive timed out; connection is correctly closed"
else:
  print "TEST 2.4: ERROR... ctrl-C (ASCII char 3) didn't close connection"


# (5)
sock.close()
sock = new_sock()
time.sleep(0.001)
v = [-2]*4096
try:
  sock.sendall("uptime"*4094 + "load" + "uptime")
  r = []
  for i in range(4096):
    r += [sock.recv(4)]
  if len(r) == 4096:
    v = map(lambda e: struct.unpack("i", e)[0], r)
except:
  pass
if len(v) < 4096 or -2 in v or v[4094] != 1:
  print "TEST 2.5: ERROR... Buffer overrun test (or maybe load) failed"
else:
  print "TEST 2.5: OK... Received all the correct return codes"

# (6)
sock.close()
sock = new_sock()
time.sleep(0.001)
sock.sendall("uptimexit")
v = -2
v2 = -2
try:
  r = sock.recv(4)
  r2 = sock.recv(4)
  v = struct.unpack("i", r)[0]
  v2 = struct.unpack("i", r2)[0]
except socket.timeout:
  print "TEST 2.6: receive timed out"
if v > 0:
  print "TEST 2.6: OK... Correctly received a non-negative uptime"
else:
  print "TEST 2.6: ERROR... uptime request failed"
if v2 == 0:
  print "TEST 2.6: ERROR... 0 return code from the \"xit\" after \"uptime\", 'e' likely double-counted"
else:
  print "TEST 2.6: OK... 'e' wasn't double-counted"

# (7)
sock.close()
sock = new_sock()
time.sleep(0.001)
v, v2 = -2, -2
try:
  sock.sendall("xl")
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
  r2 = sock.recv(4)
  if r2:
    v2 = struct.unpack("i", r2)[0]
except socket.timeout:
  print "TEST 2.7: receive timed out"
if v == -1:
  print "TEST 2.7: OK... first x correctly received -1 return value"
else:
  print "TEST 2.7: ERROR... first x didn't receive -1 return value"
if v2 == -2:
  print "TEST 2.7: OK... value for l wasn't sent back"
else:
  print "TEST 2.7: ERROR... a value of " + str(v2) + " was erroneously sent for the l"

v = -2
try:
  sock.sendall("x")
  r = sock.recv(4)
  v = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 2.7: receive timed out"
if v == -1:
  print "TEST 2.7: OK... first x after l correctly received -1 return value"
else:
  print "TEST 2.7: ERROR... first x after l didn't receive -1 return value"
v = -2
try:
  sock.sendall("x")
  r = sock.recv(4)
  if r:
    v = struct.unpack("i", r)[0]
except:
  pass
if v == -1:
  print "TEST 2.7: OK... second x after l correctly received -1 return value"
else:
  print "TEST 2.7: ERROR... second x after l didn't receive -1 return value"
v = -2
try:
  sock.sendall("x")
  r = sock.recv(4)
  if r:
    v = struct.unpack("i", r)[0]
except:
  pass
if v == -2:
  print "TEST 2.7: OK... connection is correctly closed after xlxx"
else:
  print "TEST 2.7: ERROR... connection didn't correctly close after xlxx, got back a value of " + str(v)

sock.close()


# Multi-connection tests

# TEST 3:
# (1) Make 3 connections and see what it says for the load (should be 3)
# (2) Exit a connection, and see what it says for the load
# (3) Make sure load seen by all connections is the same (synchronization across all threads)
print "\n" + "="*10 + "\nTEST 3\n" + "="*10
time.sleep(1.001)

# (1)
socks = map(lambda ign: new_sock(), range(3))
socks[0].sendall("load")
v = -1
try:
  r = socks[0].recv(4)
  v = struct.unpack("i", r)[0]
except socket.timeout:
  print "TEST 3.1: receive timed out"
if v == 3:
  print "TEST 3.1: OK... Correctly received a load of 3"
else:
  print "TEST 3.1: ERROR... load returned " + str(v) + " instead of 3"


# (2)
socks[1].sendall("exit")
time.sleep(0.001)
socks[2].sendall("load")
v, v2 = -2, -2
try:
  r = socks[1].recv(4)
  r2 = socks[2].recv(4)
  v = struct.unpack("i", r)[0]
  v2 = struct.unpack("i", r2)[0]
except socket.timeout:
  print "TEST 3.2: receive timed out"
if v == 0:
  print "TEST 3.2: OK... Correctly exited"
else:
  print "TEST 3.2: ERROR... got return code " + str(v) + " instead of 0 for exit"
if v2 == 2:
  print "TEST 3.2: OK... Correctly received a load of 2"
else:
  print "TEST 3.2: ERROR... load returned " + str(v2) + " instead of 2"

socks[0].sendall("exit")
time.sleep(0.001)
socks[2].sendall("load")
v, v2 = -2, -2
try:
  r = socks[0].recv(4)
  r2 = socks[2].recv(4)
  v = struct.unpack("i", r)[0]
  v2 = struct.unpack("i", r2)[0]
except socket.timeout:
  print "TEST 3.2: receive timed out"
if v == 0:
  print "TEST 3.2: OK... Correctly exited"
else:
  print "TEST 3.2: ERROR... got return code " + str(v) + " instead of 0 for exit"
if v2 == 1:
  print "TEST 3.2: OK... Correctly received a load of 1"
else:
  print "TEST 3.2: ERROR... load returned " + str(v2) + " instead of 1"

# (3)
map(lambda s: s.close(), socks)
socks = map(lambda ign: new_sock(), range(3))
socks[0].sendall("exit")
time.sleep(0.1)
socks[1].sendall("load")
socks[2].sendall("load")
v, v2, v3 = -2, -2, -2
try:
  r = socks[0].recv(4)
  r2 = socks[1].recv(4)
  r3 = socks[2].recv(4)
  v = struct.unpack("i", r)[0]
  v2 = struct.unpack("i", r2)[0]
  v3 = struct.unpack("i", r3)[0]
except socket.timeout:
  print "TEST 3.3: receive timed out"
if v == 0:
  print "TEST 3.3: OK... Correctly exited"
else:
  print "TEST 3.3: ERROR... got return code " + str(v) + " instead of 0 for exit"
if v2 == v3:
  print "TEST 3.3: OK... All live connections are synchronized, reporting the same load"
else:
  print "TEST 3.3: ERROR... Connections are not load synchronized, one says " \
        + str(v2) + " and the other says " + str(v3)
map(lambda s: s.close(), socks)

x = raw_input("\nPress any key to exit...")





