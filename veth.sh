#!/bin/bash
no_of_veths=18
if [ $# -eq 1 ]; then
    no_of_veths=$1
fi
echo "No of Veths is $no_of_veths"
idx=0
let "vethpairs=$no_of_veths/2"
while [ $idx -lt $vethpairs ]
do
    intf0="veth$(($idx*2))"
    intf1="veth$(($idx*2+1))"
    idx=$((idx + 1))
    if ! ip link show $intf0 &> /dev/null; then
        echo "Interface0 is $intf0 and Interface1 is $intf1"
        ip link add name $intf0 type veth peer name $intf1
        ip link set dev $intf0 up
        ip link set dev $intf1 up
        TOE_OPTIONS="rx tx sg tso ufo gso gro lro rxvlan txvlan rxhash"
        for TOE_OPTION in $TOE_OPTIONS; do
           ethtool --offload $intf0 "$TOE_OPTION" off
           ethtool --offload $intf1 "$TOE_OPTION" off
        done
    fi
    sysctl net.ipv6.conf.$intf0.disable_ipv6=1
    sysctl net.ipv6.conf.$intf1.disable_ipv6=1
done