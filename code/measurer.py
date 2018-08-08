import commands
import socket
import SocketServer
import time



MEASUREMENT_PORT = 60532


def get_connection_time(ip_address):
    """
    measure TCP connection time
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    start = time.time()
    try:
        sock.connect((ip_address, 22))
    except socket.error:
        res = 'inf'
    else:
        end = time.time()
        res = str((end - start) * 1000)
    finally:
        sock.close()
    return res


def get_latency(ip_address):
    """
    extract average time from ping -c
    scamper -c 'ping -c 1 -P tcp-ack -d 49999' -i 54.84.248.26
    """
    # cmd = "scamper -c 'ping -c 1 -P tcp-ack -d 22' -i " + ip_address + " |awk 'NR==2 {print $8}'|cut -d '=' -f 2"
    cmd = "scamper -c 'ping -c 1' -i " + ip_address + " |awk 'NR==2 {print $7}'|cut -d '=' -f 2"
    res = commands.getoutput(cmd)
    if not res:
        res = 'inf'
    return res


class MeasureHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        target_ip = self.request.recv(1024).strip()
        print '[DEBUG]Client address: %s' % target_ip
        avg_time = get_latency(target_ip)
        # avg_time = get_connection_time(target_ip)
        print '[DEBUG]Latency: %s' % avg_time
        self.request.sendall(avg_time)

        # def handle(self):
        # target_ip = self.request[0].strip()
        #     sock = self.request[1]
        #     # avg_time = get_latency(target_ip)
        #     avg_time = get_connection_time(target_ip)
        #     print '[DEBUG]latency' + avg_time
        #     sock.sendto(avg_time, self.client_address)


class MeasurementServer:
    def __init__(self, port=MEASUREMENT_PORT):
        self.port = port

    def start(self):
        # server = SocketServer.UDPServer(('', self.port), MeasureHandler)
        server = SocketServer.TCPServer(('', self.port), MeasureHandler)
        server.serve_forever()


if __name__ == '__main__':
    measure_server = MeasurementServer()
    measure_server.start()
