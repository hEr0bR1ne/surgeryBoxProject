import argparse, socket, time, sys

def main():
    p = argparse.ArgumentParser(description="TestFlow end-to-end tester")
    p.add_argument("--host", default="192.168.4.1")
    p.add_argument("--port", type=int, default=4210)
    p.add_argument("--timeout", type=float, default=3.0)
    p.add_argument("--lowdamp-path", choices=["continue", "ok1"], default="continue",
                   help="LowDamp后的回应：Continue或OK1")
    args = p.parse_args()

    addr = (args.host, args.port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.timeout)

    def send(msg):
        sock.sendto(msg.encode(), addr)
        print(f"=> {msg}")

    send("TestFlow")

    got_keep = False
    while True:
        try:
            data, src = sock.recvfrom(1024)
        except socket.timeout:
            print("[TIMEOUT] no data, exiting"); break
        text = data.decode(errors="replace").strip()
        print(f"<= {text} from {src}")

        if text == "HighDamp":
            send("OK")
        elif text == "LowDamp":
            if args.lowdamp_path == "ok1":
                send("OK1")
            else:
                send("Continue")
        elif text == "Keep":
            got_keep = True
            send("OK2")
        elif text == "TestFlowDone":
            print("[DONE] Flow finished"); break

        # 对其它信号（Pain/Pain2/ACK等）仅打印

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
