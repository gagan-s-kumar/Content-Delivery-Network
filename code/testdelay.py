from struct import unpack
import math
import socket
import threading
import urllib2


hostnames = ['ec2-54-84-248-26.compute-1.amazonaws.com',
             'ec2-54-186-185-27.us-west-2.compute.amazonaws.com',
             'ec2-54-215-216-108.us-west-1.compute.amazonaws.com',
             'ec2-54-72-143-213.eu-west-1.compute.amazonaws.com',
             'ec2-54-255-143-38.ap-southeast-1.compute.amazonaws.com',
             'ec2-54-199-204-174.ap-northeast-1.compute.amazonaws.com',
             'ec2-54-206-102-208.ap-southeast-2.compute.amazonaws.com',
             'ec2-54-207-73-134.sa-east-1.compute.amazonaws.com']
# hostnames = ['login.ccs.neu.edu', 'cs5700cdnproject.ccs.neu.edu']

MAP = {  # '54.85.79.138': (39.0437, -77.4875),
         '54.215.216.108': (37.7749, -122.419),
         '54.206.102.208': (-33.8679, 151.207),
         '54.199.204.174': (35.6895, 139.692),
         '54.84.248.26': (39.0437, -77.4875),
         '54.207.73.134': (-23.5475, -46.6361),
         '54.72.143.213': (53.344, -6.26719),
         '54.186.185.27': (45.5234, -122.676),
         '54.255.143.38': (1.28967, 103.85)}

KEY = '77e206c91186da6b8c7e8a2b2f06936c590b5bce9d6162356a83c58b0dbc96ac'
URL = 'http://api.ipinfodb.com/v3/ip-city/?key=' + KEY + '&ip='

MEASUREMENT_PORT = 60532
dic = {}


class TestThread(threading.Thread):
    def __init__(self, host, target, execute_lock):
        threading.Thread.__init__(self)
        self.host = host
        self.target = target
        self.lock = execute_lock

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ip = socket.gethostbyname(self.host)
        try:
            sock.connect((ip, MEASUREMENT_PORT))
            sock.sendall(self.target)
            latency = sock.recv(1024)
        except socket.error as e:
            print '[Error]Connect Measurer' + str(e)
            latency = 'inf'
        finally:
            sock.close()

        print '[DEBUG]IP: %s\tLatency:%s' % (ip, latency)
        with self.lock:
            dic.update({ip: float(latency)})


def sort_replica_act(target_ip):
    """
    Sort replica server using active measurement
    """
    lock = threading.Lock()
    threads = []

    for i in range(len(hostnames)):
        t = TestThread(hostnames[i], target_ip, lock)
        t.start()
        threads.append(t)

    # Wait for all threads to complete
    for t in threads:
        t.join()

    print '[DEBUG]Sorted Replica Server:', dic
    return dic


def sort_replica_geo(target_ip):
    """
    Sort replica server based on GeoLocation
    """

    def get_location(_ip):
        res = urllib2.urlopen(URL + _ip)
        loc_info = res.read().split(';')
        return float(loc_info[8]), float(loc_info[9])

    def get_distance(target, src):
        return math.sqrt(reduce(lambda x, y: x + y,
                                map(lambda x, y: math.pow((x - y), 2), target, src), 0))

    distance = {}
    for ip in MAP.keys():
        distance[ip] = 0
    target_address = get_location(target_ip)
    for ip, loc in MAP.iteritems():
        distance[ip] = get_distance(target_address, loc)

    print '[DEBUG]Sorted Replica Server:', distance
    return distance


def is_private(ip):
    f = unpack('!I', socket.inet_pton(socket.AF_INET, ip))[0]
    private = (
        [2130706432, 4278190080],  # 127.0.0.0,   255.0.0.0
        [3232235520, 4294901760],  # 192.168.0.0, 255.255.0.0
        [2886729728, 4293918720],  # 172.16.0.0,  255.240.0.0
        [167772160, 4278190080],  # 10.0.0.0,    255.0.0.0
    )
    for net in private:
        if f & net[1] == net[0]:
            return True
    return False


def select_replica(target_ip):
    if is_private(target_ip):
        return '54.84.248.26'
    result = sort_replica_act(target_ip)
    if len(set(result.values())) <= 1:
        result = sort_replica_geo(target_ip)
    sorted_result = sorted(result.items(), key=lambda e: e[1])
    return sorted_result[0][0]


if __name__ == '__main__':
    print '[DEBUG]Select replica server:'
    print select_replica('139.82.16.196')
