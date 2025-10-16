import sys
import os
from socket import *
import threading
import time
import queue
import pickle
import random
import select

blocksInWindow = 0
window = []

def sendDatagram( blockNo, contents, sock, end ):
    rand = random.randint(0,9)
    if rand > 1:
        toSend = (blockNo, contents)
        msg = pickle.dumps( toSend)
        sock.sendto( msg, end)
        
def waitForAck( s, seg ):
    rx, tx, er = select.select( [s], [],[], seg)
    return rx!=[]


def tx_thread( s, receiver, windowSize, cond, timeout ):
    # TO DO
    return
            

def sendBlock( seqNo, fileBytes, s, receiver, windowSize, cond ):  #producer
    #TO DO
    return

def main(hostname, senderPort, windowSize, timeOutInSec):
    s = socket( AF_INET, SOCK_DGRAM)
    s.bind((hostname, senderPort))
    # interaction with receiver; no datagram loss
    buf, rem = s.recvfrom( 256 )
    req = pickle.loads( buf)
    fileName = req[0]
    blockSize = req[1]
    result = os.path.exists(fileName)
    if not result:
        print(f'file {fileName} does not exist in server')
        reply = ( -1, 0 )
        rep=pickle.dumps(reply)
        s.sendto( rep, rem )
        sys.exit(1)
    fileSize = os.path.getsize(fileName)
    reply = ( 0, fileSize)
    rep=pickle.dumps(reply)
    s.sendto( rep, rem )
    # file transfer; datagram loss possible
    windowCond = threading.Condition()
    tid = threading.Thread( target=tx_thread,
                            args=(s,rem,windowSize, windowCond,timeOutInSec))
    tid.start()
    f = open( fileName, 'rb')
    blockNo = 1
    
    while True:
        b = f.read( blockSize  )
        sizeOfBlockRead = len(b)
        if sizeOfBlockRead > 0:
            sendBlock( blockNo, b, s, rem, windowSize, windowCond)
        if sizeOfBlockRead == blockSize:
            blockNo=blockNo+1
        else:
            break
    f.close()
    tid.join()


if __name__ == "__main__":
    # python sender.py senderPort windowSize timeOutInSec
    if len(sys.argv) != 4:
        print("Usage: python sender.py senderPort windowSize timeOutInSec")
    else:
        senderPort = int(sys.argv[1])
        windowSize = int(sys.argv[2])
        timeOutInSec = int(sys.argv[3])
        hostname = gethostbyname(gethostname())
        random.seed( 5 )
        main( hostname, senderPort, windowSize, timeOutInSec)
