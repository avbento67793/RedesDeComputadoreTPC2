import sys
from socket import *
import threading
import time
import queue
import pickle
import random

def sendAck( ackNo, sock, end ):
    rand = random.randint(0,9)
    if rand > 1:
        toSend = (ackNo,)
        msg = pickle.dumps( toSend)
        sock.sendto( msg, end)

def rx_thread( s, sender, que, bSize):
    # The first expected block sequence number
    next_seq_expected = 1

    # Define the maximum size of the incoming packet (block + metadata)
    MAX_PACKET_SIZE = bSize + 128

    while True:
        try:
            # Receive a UDP packet from the sender
            rep, ad = s.recvfrom(MAX_PACKET_SIZE)

            # Deserialize the received packet (should be a tuple)
            received_data = pickle.loads(rep)

            # Validate packet format: must be a tuple of (block_num, data)
            if not isinstance(received_data, tuple) or len(received_data) != 2:
                continue

            # Extract the block number and data payload
            block_num, data = received_data

            # If this is the expected block
            if block_num == next_seq_expected:
                # Put the data in the shared queue for processing
                que.put(data)

                # If data is empty, it indicates EOF (end of file)
                if not data:
                    print("EOF. Ending rx_thread.")
                    break

                # Send acknowledgment for this block
                sendAck(block_num, s, sender)

                # Updated to the next expected block
                next_seq_expected += 1

            else:
                # If an unexpected block arrives, resend the last valid ACK
                last_received = next_seq_expected - 1
                if last_received > 0:
                    sendAck(last_received, s, sender)

        except timeout:
            # If no data is received within timeout, retry
            continue

        except Exception as e:
            # Handle unexpected errors without crashing the program
            print(f"Error in rx_thread: {e}")
            continue

    return
    
def receiveNextBlock( q ):
    return q.get()

def main(sIP, sPort, fNameRemote, fNameLocal, blockSize):

    s = socket( AF_INET, SOCK_DGRAM)
    #interact with sender without losses
    request = (fNameRemote, blockSize)
    req = pickle.dumps(request)
    sender = (sIP, sPort)
    print("sending request")
    s.sendto( req, sender)
    print("waiting for reply")
    rep, ad = s.recvfrom(128)
    reply = pickle.loads(rep)
    print(f"Received reply: code = {reply[0]} fileSize = {reply[1]}")
    if reply[0]!=0:
        print(f'file {fNameRemote} does not exist in sender')
        sys.exit(1)
    #start transfer with data and ack losses
    fileSize = reply[1]
    q = queue.Queue( )
    tid = threading.Thread( target=rx_thread, args=(s, sender, q, blockSize))
    tid.start()
    f = open( fNameLocal, 'wb')
    noBytesRcv = 0
    while noBytesRcv < fileSize:
        print(f'Going to receive; noByteRcv={noBytesRcv}')
        b = receiveNextBlock( q )
        sizeOfBlockReceived = len(b)
        if sizeOfBlockReceived > 0:
            f.write(b)
            noBytesRcv += sizeOfBlockReceived

    f.close()
    tid.join()
       

if __name__ == "__main__":
    # python receiver.py senderIP senderPort fileNameInSender fileNameInReceiver blockSize
    if len(sys.argv) != 6:
        print("Usage: python receiver.py senderIP senderPort fileNameRemote fileNameLocal blockSize")
        sys.exit(1)
    senderIP = sys.argv[1]
    senderPort = int(sys.argv[2])
    fileNameRemote = sys.argv[3]
    fileNameLocal = sys.argv[4]
    blockSize = int(sys.argv[5])
    random.seed( 7 )
    main( senderIP, senderPort, fileNameRemote, fileNameLocal, blockSize)
    
