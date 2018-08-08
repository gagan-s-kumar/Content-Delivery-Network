from SocketServer import BaseRequestHandler, UDPServer
import random
import getopt
import socket
import struct
import sys

from testdelay import select_replica



"""
DNS Header
0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5  6
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                       ID                      |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|QR| Opcode |AA|TC|RD|RA|    Z   |     RCODE    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    QDCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ANCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    NSCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ARCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
DNS Query
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
/                      QNAME                    /
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      QTYPE                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      QCLASS                   |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
DNS Answer
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
/                       NAME                    /
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                       TYPE                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      CLASS                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                       TTL                     |
|                                               |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                     RDLENGTH                  |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--|
/                      RDATA                    /
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

EC2 Hosts
ec2-54-85-79-138.compute-1.amazonaws.com    Origin server (port 8080)
ec2-54-84-248-26.compute-1.amazonaws.com    N. Virginia
ec2-54-186-185-27.us-west-2.compute.amazonaws.com   Oregon
ec2-54-215-216-108.us-west-1.compute.amazonaws.com  N. California
ec2-54-72-143-213.eu-west-1.compute.amazonaws.com   Ireland
ec2-54-255-143-38.ap-southeast-1.compute.amazonaws.com  Singapore
ec2-54-199-204-174.ap-northeast-1.compute.amazonaws.com Tokyo
ec2-54-206-102-208.ap-southeast-2.compute.amazonaws.com Sydney
ec2-54-207-73-134.sa-east-1.compute.amazonaws.com   Sao Paulo
"""

RECORD = {'ec2-54-85-79-138.compute-1.amazonaws.com': '54.85.79.138',
          'ec2-54-84-248-26.compute-1.amazonaws.com': '54.84.248.26',
          'ec2-54-186-185-27.us-west-2.compute.amazonaws.com': '54.186.185.27',
          'ec2-54-215-216-108.us-west-1.compute.amazonaws.com': '54.215.216.108',
          'c2-54-72-143-213.eu-west-1.compute.amazonaws.com': '54.72.143.213',
          'ec2-54-255-143-38.ap-southeast-1.compute.amazonaws.com': '54.255.143.38',
          'ec2-54-199-204-174.ap-northeast-1.compute.amazonaws.com': '54.199.204.174',
          'ec2-54-206-102-208.ap-southeast-2.compute.amazonaws.com': '54.206.102.208',
          'ec2-54-207-73-134.sa-east-1.compute.amazonaws.com': '54.207.73.134'}


class DNSPacket:
    def __init__(self):
        self.id = random.randint(0, 65535)
        self.flags = 0
        self.qcount = 0
        self.acount = 0
        self.nscount = 0
        self.arcount = 0
        self.query = DNSQuery()
        self.answer = DNSAnswer()

    def build_query(self, domain_name):
        packet = struct.pack('>HHHHHH', self.id, self.flags,
                             self.qcount, self.acount,
                             self.nscount, self.arcount)
        packet += self.query.create(domain_name)
        return packet

    def build_answer(self, domain_name, ip):
        self.answer = DNSAnswer()
        self.acount = 1
        self.flags = 0x8180
        packet = self.build_query(domain_name)
        packet += self.answer.create(ip)
        return packet

    def rebuild(self, raw_packet):
        [self.id,
         self.flags,
         self.qcount,
         self.acount,
         self.nscount,
         self.arcount] = struct.unpack('>HHHHHH', raw_packet[:12])
        self.query = DNSQuery()
        self.query.rebuild(raw_packet[12:])
        self.answer = None

    def debug_print(self):
        print 'ID: %X\tFlags:%.4X' % (self.id, self.flags)
        print 'Query Count:%d\tAnswer Count:%d' % (self.qcount, self.acount)
        if self.qcount > 0:
            self.query.debug_print()
        if self.acount > 0:
            self.answer.debug_print()


class DNSQuery:
    def __init__(self):
        self.qname = ''
        self.qtype = 0
        self.qclass = 0

    def create(self, domain_name):
        self.qname = domain_name
        query = ''.join(chr(len(x)) + x for x in domain_name.split('.'))
        query += '\x00'  # add end symbol
        return query + struct.pack('>HH', self.qtype, self.qclass)

    def rebuild(self, raw_data):
        [self.qtype, self.qclass] = struct.unpack('>HH', raw_data[-4:])
        s = raw_data[:-4]
        ptr = 0
        temp = []
        while True:
            count = ord(s[ptr])
            if count == 0:
                break
            ptr += 1
            temp.append(s[ptr:ptr + count])
            ptr += count
        self.qname = '.'.join(temp)

    def debug_print(self):
        print '[DEBUG]DNS QUERY'
        print 'Request:', self.qname
        print 'Type: %d\tClass: %d' % (self.qtype, self.qclass)


class DNSAnswer:
    def __init__(self):
        self.aname = 0
        self.atype = 0
        self.aclass = 0
        self.ttl = 0  # time to live
        self.data = ''
        self.len = 0

    def create(self, ip):
        self.aname = 0xC00C
        self.atype = 0x0001
        self.aclass = 0x0001
        self.ttl = 60  # time to live
        self.data = ip
        self.len = 4
        ans = struct.pack('>HHHLH4s', self.aname, self.atype, self.aclass,
                          self.ttl, self.len, socket.inet_aton(self.data))
        return ans

    def debug_print(self):
        print '[DEBUG]DNS ANSWER'
        print 'Query: %X' % self.aname
        print 'Type: %d\tClass: %d' % (self.atype, self.aclass)
        print 'TTL: %d\tLength: %d' % (self.ttl, self.len)
        print 'IP: %s' % self.data


class DNSUDPHandler(BaseRequestHandler):
    def handle(self):
        print '[DEBUG]CDN Name: %s' % self.server.name
        data = self.request[0].strip()
        sock = self.request[1]
        packet = DNSPacket()
        packet.rebuild(data)
        print '[DEBUG]From client IP:', self.client_address[0]
        print '[DEBUG]Receive DNS Request:'
        packet.debug_print()

        if packet.query.qtype == 1:
            domain = packet.query.qname
            if domain == self.server.name:
                ip = select_replica(self.client_address[0])
                # ip = select_replica_geo(self.client_address[0])
                print '[DEBUG]Select replica server: %s' % ip
                data = packet.build_answer(domain, ip)
                sock.sendto(data, self.client_address)
                print '[DEBUG]Send DNS Answer:'
                packet.debug_print()
            else:
                sock.sendto(data, self.client_address)
        else:
            sock.sendto(data, self.client_address)


class SimpleDNSServer(UDPServer):
    def __init__(self, cdn_name, server_address, handler_class=DNSUDPHandler):
        self.name = cdn_name
        UDPServer.__init__(self, server_address, handler_class)
        return


def parse(argvs):
    (port, name) = (0, '')
    opts, args = getopt.getopt(argvs[1:], 'p:n:')
    for o, a in opts:
        if o == '-p':
            port = int(a)
        elif o == '-n':
            name = a
        else:
            sys.exit('Usage: %s -p <port> -o <origin>' % argvs[0])
    return port, name


if __name__ == '__main__':
    (port_number, cdn_name) = parse(sys.argv)
    dns_server = SimpleDNSServer(cdn_name, ('', port_number))
    dns_server.serve_forever()
