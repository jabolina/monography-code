#!/bin/bash

# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# reference to bmv2 and p4c-bm2
##########################
base_path=$PWD/../environment
bmv2_path=$base_path/bmv2
p4c_bm_path=$base_path/p4c-bmv2
PYTHONPATH=/usr/bin/python2.7
##########################
p4c_bm_script=$p4c_bm_path/p4c_bm/__main__.py
switch_path=$bmv2_path/targets/simple_switch/simple_switch
bmv2_cli_path=$bmv2_path/targets/simple_switch/sswitch_CLI

$p4c_bm_script ./p4src/paxos_coordinator.p4 --json paxos_coordinator.json
$p4c_bm_script ./p4src/paxos_acceptor.p4 --json paxos_acceptor.json
$p4c_bm_script ./p4src/paxos_learner.p4 --json paxos_learner.json


sudo PYTHONPATH=$PYTHONPATH:$bmv2_path/mininet/ python2.7 topo.py \
    --behavioral-exe $bmv2_path/targets/simple_switch/simple_switch \
    --acceptor paxos_acceptor.json \
    --coordinator paxos_coordinator.json \
    --cli $bmv2_cli_path \
    --start-server
