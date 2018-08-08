path=$1
port=$2
IP=`dig +short -p $port @cs5700cdnproject.ccs.neu.edu cs5700cdn.example.com | head -1`
wget -O /dev/null http://$IP:$port$path
