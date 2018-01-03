import socket
import sys
from struct import *
import random

def carry_around_add(a, b):
    c = a + b
    return (c & 0xffff) + (c >> 16)

def calc_checksum(msg):
    s = 0
    for i in range(1, len(msg), 2):
        w = msg[i-1] + msg[i] << 8
        s = carry_around_add(s, w)
    return ~s & 0xffff


def Checksum(csum, seq, header, data):
    checksum = pack('IH' + str(len(data)) + 's', seq, header, data)
    if calc_checksum(checksum) == csum:
        return True
    else:
        return False


def send_ack(seqNum, clientAddr, sock):
    allZeroes = int('0000000000000000', 2)
    header = int('1010101010101010', 2)
    packet = pack('III', seqNum, allZeroes, header)
    sock.sendto(packet, clientAddr)

def main():
    port = int(sys.argv[1])
    host = '127.0.0.1'
    protocol = sys.argv[2]
    windowSize = 0
    print("Host: " + host)
    print("Port: " + str(port))
    print("Protocol: " + protocol)
    if protocol == 'SR':
        windowSize = int(sys.argv[3])
        print("Window size: " + str(windowSize))

    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serverSocket.bind((host, port))

    seqNum = 0
    base = 0
    last = base + windowSize - 1
    lastReceived = -1
    received = []
    receiveBuffer = []
    for i in range(windowSize):
        received.append(0)
        receiveBuffer.append(None)

    while True:
        message, addr = serverSocket.recvfrom(1024)
        fmt = 'IHH' + str(len(message)-8) + 's'
        packet = unpack(fmt, message)

        if packet[2] == int('1111111111111111', 2):
            break

        if 0.1 < random.random():
            seqNum = packet[0]
            checksum = packet[1]
            header = packet[2]
            data = packet[3]
            print("Packet received for S" + str(seqNum))

            if protocol == "GBN":
                if Checksum(checksum, seqNum, header, data):
                    if seqNum == lastReceived + 1:
                        print("ACK sent for S" + str(seqNum))
                        send_ack(seqNum, addr, serverSocket)
                        lastReceived = seqNum
                    elif seqNum != lastReceived + 1 and seqNum > lastReceived + 1:
                        if lastReceived >= 0:
                            print("(Packet out of order, discarded): last received packet in sequence: packet " \
                                  + str(lastReceived))
                    else:
                        print("ACK sent for S" + str(seqNum))
                        send_ack(seqNum, addr, serverSocket)
                        lastReceived = seqNum
                else:
                    print("Packet discarded. checksum mismatch.")

            # Protocol = Selective repeat
            elif protocol == "SR":
                if seqNum < base:
                    print("Old packet received: S" + str(seqNum))
                    send_ack(seqNum, addr, serverSocket)
                else:
                    if Checksum(checksum, seqNum, header, data):
                        if seqNum >= base and seqNum <= last:
                            if seqNum == base:
                                receiveBuffer[base % windowSize] = None
                                received[base % windowSize] = 0
                                base += 1
                                last += 1
                            elif received[seqNum % windowSize] == 0:
                                receiveBuffer[seqNum % windowSize] = packet
                                received[seqNum % windowSize] = 1
                        print("ACK sent for S" + str(seqNum))
                        send_ack(seqNum, addr, serverSocket)
                    else:
                        print("Packet discarded. Checksum mismatch.")
        else:
            print("Packet S" + str(packet[0]) + " lost.")


if __name__ == '__main__':
    main()