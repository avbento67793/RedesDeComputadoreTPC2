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


def tx_thread(s, receiver, windowSize, cond, timeout):
    global window, blocksInWindow

    last_ack = 0
    dup_ack_count = 0
    FAST_RETRANSMIT_THRESHOLD = 2  # duplicate ACK threshold
    last_seq_sent = 0  # keep track of last sequence number sent

    while True:
        with cond:
            # If window is empty, wait briefly
            if blocksInWindow == 0:
                cond.wait(timeout)  # short wait to see if more blocks arrive
                if blocksInWindow == 0:
                    # Window is empty and no more blocks → send final zero-length block
                    if last_seq_sent > 0:
                        final_block = (last_seq_sent + 1, b"")
                        msg = pickle.dumps(final_block)
                        s.sendto(msg, receiver)
                        print(f"[TX] Sent final zero-length block seq={last_seq_sent + 1}")
                    print("[TX] All data acknowledged, exiting tx_thread.")
                    break

            if blocksInWindow > 0:
                oldest_entry = window[0]
                time_elapsed = time.monotonic() - oldest_entry['sent_time']
                time_remaining = timeout - time_elapsed

                # Timeout → retransmit all blocks in window
                if time_remaining <= 0:
                    print(f"[TIMEOUT] Retransmitting from seq={window[0]['seq']}")
                    for entry in window:
                        sendDatagram(entry['seq'], entry['data'], s, receiver)
                        entry['sent_time'] = time.monotonic()
                        last_seq_sent = max(last_seq_sent, entry['seq'])
                    dup_ack_count = 0
                    cond.notify_all()
                    continue

        # Wait for ACK with timeout (non-blocking)
        ack_available = waitForAck(s, max(time_remaining, 0.001))
        if not ack_available:
            continue

        try:
            # Receive ACK
            rep, _ = s.recvfrom(128)
            ack_tuple = pickle.loads(rep)
            if not isinstance(ack_tuple, tuple) or len(ack_tuple) != 1:
                continue
            ack_num = ack_tuple[0]
        except Exception as e:
            print(f"[TX] Error receiving ACK: {e}")
            continue

        with cond:
            # New cumulative ACK → slide window
            if ack_num > last_ack:
                num_confirmed = ack_num - last_ack
                window = window[num_confirmed:]
                blocksInWindow -= num_confirmed
                last_ack = ack_num
                dup_ack_count = 0
                print(f"[ACK] Received {ack_num}, window now {blocksInWindow}/{windowSize}")
                cond.notify_all()

            # Duplicate ACK → may trigger fast retransmit
            elif ack_num == last_ack and last_ack > 0:
                dup_ack_count += 1
                print(f"[DUPACK] For {ack_num} ({dup_ack_count}/{FAST_RETRANSMIT_THRESHOLD})")
                if dup_ack_count >= FAST_RETRANSMIT_THRESHOLD and blocksInWindow > 0:
                    print(f"[FAST RETRANSMIT] Retransmitting from seq={window[0]['seq']}")
                    for entry in window:
                        sendDatagram(entry['seq'], entry['data'], s, receiver)
                        entry['sent_time'] = time.monotonic()
                        last_seq_sent = max(last_seq_sent, entry['seq'])
                    dup_ack_count = 0
                    cond.notify_all()

    return
            

def sendBlock(seqNo, fileBytes, s, receiver, windowSize, cond):
    global window, blocksInWindow

    with cond:
        # Wait until there is space in the sliding window
        while blocksInWindow >= windowSize:
            cond.wait()

        # Register block in the window
        entry = {
            'seq': seqNo,
            'data': fileBytes,
            'sent_time': time.monotonic()
        }
        window.append(entry)
        blocksInWindow += 1

        # Send it
        sendDatagram(seqNo, fileBytes, s, receiver)
        print(f"[SEND] Block {seqNo} sent (Window={blocksInWindow}/{windowSize})")

        # Notify tx_thread
        cond.notify_all()

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
