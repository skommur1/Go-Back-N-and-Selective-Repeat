import sys

import signal

import socket
import time
import random
from struct import *

import threading

hostname = "127.0.0.1"
filename = sys.argv[1]
file = open(filename, 'r')
PROTOCOL = file.readline().strip()
mN = file.readline()
m = int(mN.split()[0])
WINDOWSIZE = int(mN.split()[1])
TIMEOUT = int(file.readline().strip())
MSS = int(file.readline().strip())
port = int(sys.argv[2])
numberOfPackets = int(sys.argv[3])


msg = "HiWelcometoRDTonUDP"
sendMessage = msg * numberOfPackets

numAcked = -1

sendComplete = False
ackComplete = False

sendBuffer = []
timeoutTimers = []

seqNum = 0
base = -1
last = -1
lastAcked = -1

print("hostname: localhostname")
print("Protocol: " + PROTOCOL)
print("Window size: " + str(WINDOWSIZE))
print("Timeout: " + str(TIMEOUT))
print("MSS: " + str(MSS))
print("Port: " + str(port))
print("Number of packets to send: " + str((len(sendMessage) / MSS) + 1))

clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
clientSocket.bind(('', port))
lock = threading.Lock()


def next_byte():
    global sendComplete
    global sendMessage
    global file
    if sendMessage:
        nextByte = sendMessage[0]
        sendMessage = sendMessage[1:len(sendMessage)]
    else:
        nextByte = ''
        sendComplete = True
    return nextByte


def input_msg():
    global sendComplete
    global MSS

    message = ''
    while len(message) < MSS and not sendComplete:
        message += next_byte()
    return message.encode()


def resend_packets():
    global MSS
    global sendBuffer
    global clientSocket
    global TIMEOUT
    global timeoutTimers
    global last
    global base
    global hostname
    global port
    global WINDOWSIZE

    i = base
    while i <= last:
        if sendBuffer[i % WINDOWSIZE] != None:
            packet = sendBuffer[i % WINDOWSIZE]
            print("Resending packet: S" + str(i) + "; Timer started")
            clientSocket.sendto(packet, (hostname, port))
            timeoutTimers[i % WINDOWSIZE] = TIMEOUT
        i += 1

def CalculateChecksum(cs):
	if len(cs) % 2 != 0:
		cs  = cs + str(0).encode()
	i = 0
	checksum = 0
	while i < len(cs):
		cs1 = ord(chr(cs[i]))*128 + ord(chr(cs[i+1]))
		cs2 = 32767 - cs1
		cs3 = checksum + cs2
		checksum = (cs3 % 32768) + (cs3 / 32768)
		i += 2
	return (32767 - checksum)
    
def last_packet():
    header = int('1111111111111111', 2)
    checksum = int('0000000000000000', 2)
    return pack('IHH', seqNum, checksum, header)


def resend_on_timeout():
    global base
    global last
    global sendBuffer
    global lock
    global timeoutTimers
    global WINDOWSIZE

    if ackComplete:
        return

    if PROTOCOL == "GBN":
        for i, eachtimer in enumerate(timeoutTimers):
            timeoutTimers[i] = eachtimer - 1

        if len(timeoutTimers) > (base % WINDOWSIZE):
            print("Timeout, sequence number =", base)
            lock.acquire()
            resend_packets()
            print("resent")
            lock.release()


    elif PROTOCOL == "SR":
        i = base
        while i <= last:
            timeoutTimers[i % WINDOWSIZE] = timeoutTimers[i % WINDOWSIZE] - 1
            lock.acquire()
            if timeoutTimers[i % WINDOWSIZE] < 1 and sendBuffer[i % WINDOWSIZE] != None:
                print("Timeout, sequence number =", i)
                packet = sendBuffer[i % WINDOWSIZE]
                print("Resending packet: S" + str(i) + "; Timer started")
                clientSocket.sendto(packet, (hostname, port))
                timeoutTimers[i % WINDOWSIZE] = TIMEOUT
            lock.release()
            i = i + 1

def carry_around_add(a, b):
    c = a + b
    return (c & 0xffff) + (c >> 16)
def calc_checksum(msg):
    s = 0
    for i in range(1, len(msg), 2):
        w = msg[i-1] + msg[i] << 8
        s = carry_around_add(s, w)
    return ~s & 0xffff


def LookforACKs():
    global base
    global sendBuffer
    global WINDOWSIZE
    global clientSocket
    global numAcked
    global seqNum
    global ackComplete
    global sendComplete
    global lastAcked
    global last

    if PROTOCOL == "GBN":
        while not ackComplete:
            packet, addr = clientSocket.recvfrom(1024)
            ack = unpack('IHH', packet)
            ackNum = ack[0]
            if 0.05 < random.random():
                if ackNum == seqNum:
                    print("Received ACK: ", ackNum)
                    lock.acquire()
                    i = base
                    while i <= last:
                        sendBuffer[i % WINDOWSIZE] = None
                        timeoutTimers[i % WINDOWSIZE] = 0
                        lastAcked = lastAcked + 1
                        base = base + 1
                    lock.release()
                elif ackNum == lastAcked + 1:
                    print("Received ACK: ", ackNum)
                    lock.acquire()
                    sendBuffer[ackNum % WINDOWSIZE] = None
                    timeoutTimers[ackNum % WINDOWSIZE] = 0
                    lastAcked = lastAcked + 1
                    base = base + 1
                    lock.release()

                if sendComplete and lastAcked >= last:
                    ackComplete = True
            else:
                print("Ack " + str(ackNum) + " lost (Info for simulation).")

    elif PROTOCOL == "SR":
        while not ackComplete:
            packet, addr = clientSocket.recvfrom(8)
            ack = unpack('IHH', packet)
            ackNum = ack[0]
            if ACK_ERROR_PROBABILITY < random.random():
                print("Received ACK: ", ackNum)
                if ackNum == base:
                    lock.acquire()
                    sendBuffer[base % WINDOWSIZE] = None
                    timeoutTimers[base % WINDOWSIZE] = 0
                    lock.release()
                    numAcked = numAcked + 1
                    base = base + 1
                elif ackNum >= base and ackNum <= last:
                    sendBuffer[ackNum % WINDOWSIZE] = None
                    timeoutTimers[ackNum % WINDOWSIZE] = 0
                    numAcked += 1

                if sendComplete and numAcked >= last:
                    ackComplete = True
            else:
                print("Ack " + str(ackNum) + " lost")


threadForAck = threading.Thread(target=LookforACKs, args=())
threadForAck.start()
threading.Timer(TIMEOUT, resend_on_timeout, ()).start()

base = 0

while not sendComplete:
    toSend = last + 1
    data = input_msg()
    header = int('0101010101010101', 2)
    cs = pack('IH' + str(len(data)) + 's', seqNum, header, data)
    checksum = calc_checksum(cs)

    packet = pack('IHH' + str(len(data)) + 's', seqNum, checksum, header, data)
    if toSend < WINDOWSIZE:
        sendBuffer.append(packet)
        timeoutTimers.append(TIMEOUT)
    else:
        sendBuffer[toSend % WINDOWSIZE] = packet
        timeoutTimers[toSend % WINDOWSIZE] = TIMEOUT

    print("Sending S" + str(seqNum) + "; Timer started")
    if 0.1 > random.random():
        error_data = "0000000000000000000000000000000000000000000011111222"

        packet = pack('IHH' + str(len(error_data)) + 's', seqNum, checksum, header, data)
    clientSocket.sendto(packet, (hostname, port))

    last = last + 1
    seqNum = seqNum + 1

while not ackComplete:
    pass

clientSocket.sendto(last_packet(), (hostname, port))
clientSocket.close()
