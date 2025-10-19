import sys
from socket import *
import threading
import time
import queue
import pickle
import random

def sendAck(ackNo, sock, end):
    rand = random.randint(0, 9)
    if rand > 1:
        toSend = (ackNo,)
        msg = pickle.dumps(toSend)
        sock.sendto(msg, end)

def rx_thread(s, sender, que, bSize):
    expected_block_number = 1
    MAX_PACKET_SIZE = bSize + 128

    while True:
        try:
            # Receive UDP packet
            rep, ad = s.recvfrom(MAX_PACKET_SIZE)
            received_data = pickle.loads(rep)

            # Detect FIN message from sender
            if isinstance(received_data, tuple) and received_data == ("FIN",):
                print("[RX] FIN received. File transfer completed.")
                break

            # Validate packet format
            if not isinstance(received_data, tuple) or len(received_data) != 2:
                continue

            block_num, data = received_data

            # If this is the expected block
            if block_num == expected_block_number:
                que.put(data)

                # Send ACK for correct block
                sendAck(block_num, s, sender)
                expected_block_number += 1

            else:
                # Out of order → resend last ACK
                last_received = expected_block_number - 1
                if last_received > 0:
                    sendAck(last_received, s, sender)

        except timeout:
            continue
        except Exception as e:
            print(f"[RX] Error: {e}")
            continue

    return
    
def receiveNextBlock(q):
    """Returns the next block of data from the queue."""
    return q.get()

def main(sIP, sPort, fNameRemote, fNameLocal, blockSize):

    # Initial request phase (no losses)
    s = socket(AF_INET, SOCK_DGRAM)
    request = (fNameRemote, blockSize)
    req = pickle.dumps(request)
    sender = (sIP, sPort)

    print("[MAIN] Sending file request...")
    s.sendto(req, sender)

    print("[MAIN] Waiting for reply...")
    rep, ad = s.recvfrom(128)
    reply = pickle.loads(rep)
    print(f"[MAIN] Reply received: code={reply[0]} fileSize={reply[1]}")

    if reply[0] != 0:
        print(f"[MAIN] Remote file '{fNameRemote}' does not exist.")
        sys.exit(1)

    # Start data reception (losses possible)
    fileSize = reply[1]
    q = queue.Queue()
    tid = threading.Thread(target=rx_thread, args=(s, sender, q, blockSize))
    tid.start()

    f = open(fNameLocal, 'wb')
    noBytesRcv = 0

    while noBytesRcv < fileSize:
        print(f"[MAIN] Waiting for next block... Received so far: {noBytesRcv}/{fileSize} bytes")
        b = receiveNextBlock(q)
        sizeOfBlockReceived = len(b)
        if sizeOfBlockReceived > 0:
            f.write(b)
            noBytesRcv += sizeOfBlockReceived

    f.close()
    tid.join()

    print("✅ File successfully received and saved.")
    print(f"📌 Output file: {fNameLocal}")

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python receiver.py senderIP senderPort fileNameRemote fileNameLocal blockSize")
        sys.exit(1)

    senderIP = sys.argv[1]
    senderPort = int(sys.argv[2])
    fileNameRemote = sys.argv[3]
    fileNameLocal = sys.argv[4]
    blockSize = int(sys.argv[5])
    random.seed(7)

    main(senderIP, senderPort, fileNameRemote, fileNameLocal, blockSize)
