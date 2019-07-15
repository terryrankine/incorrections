import socket
# addressing information of target

IPADDR = 'localhost'
PORTNUM = 5019


# enter the data content of the UDP packet as hex
message = 'Hello World. Packet'

if __name__ == "__main__":
    try:
            # initialize a socket, think of it as a cable
        # SOCK_DGRAM specifies that this is UDP

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # connect the socket, think of it as connecting the cable to the address location
        s.sendto(bytes(message, 'utf-8'),(IPADDR, PORTNUM))
        s.close()
    except:
        raise