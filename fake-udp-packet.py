import socket
# addressing information of target

IPADDR = 'localhost'
PORTNUM = 5019


# enter the data content of the UDP packet as hex
message = 'Hello World. Packet'

if __name__ == "__main__":
    # initialize a socket, SOCK_DGRAM specifies UDP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(bytes(message, 'utf-8'), (IPADDR, PORTNUM))
    s.close()
