#include "includes/headers.p4"
#include "includes/parser.p4"
#include "includes/paxos_headers.p4"
#include "includes/paxos_parser.p4"

#define INSTANCE_COUNT 65536
#define ACCEPTOR_COUNT 8
#define MAJORITY 3

header_type ingress_metadata_t {
    fields {
        round: ROUND_SIZE;
        set_drop: 1;
        count: ACCEPTOR_COUNT;
        acceptors: ACCEPTOR_COUNT;
    }
}
metadata ingress_metadata_t paxos_packet_metadata;

register rounds_register {
    width: ROUND_SIZE;
    instance_count: INSTANCE_COUNT;
}

register values_register {
    width: VALUE_SIZE;
    instance_count: INSTANCE_COUNT;
}

register vote_history {
    width: ACCEPTOR_COUNT;
    instance_count: INSTANCE_COUNT;
}

action read_round() {
    register_read(paxos_packet_metadata.round, rounds_register, paxos.instance);
    register_read(paxos_packet_metadata.acceptors, vote_history, paxos.instance);
}

action handle_2b() {
    register_write(rounds_register, paxos.instance, paxos.round);
    register_write(values_register, paxos.instance, paxos.value);

    modify_field(paxos_packet_metadata.acceptors, paxos_packet_metadata.acceptors | (1 << paxos.acceptor));
    register_write(vote_history, paxos.instance, paxos_packet_metadata.acceptors);
}

action handle_new_value() {
    register_write(rounds_register, paxos.instance, paxos.round);
    register_write(values_register, paxos.instance, paxos.value);
    register_write(vote_history, paxos.instance, 1 << paxos.acceptor);
    modify_field(paxos_packet_metadata.set_drop, 1);
}

action broadcast() {
    modify_field(intrinsic_metadata.mcast_grp, 1);
    modify_field(paxos_packet_metadata.set_drop, 0);
}

action _nop() { }
action _drop() { drop(); }

table rnd_tbl {
    actions { read_round; }
    size: 1;
}

table deliver_tbl {
    actions { broadcast; }
}

table learner_tbl {
    reads {
        paxos.msgtype: exact;
    }
    actions {
        handle_2b;
        _drop;
    }
}

table start_tbl {
    reads {
        paxos.msgtype: exact;
    }
    actions {
        handle_new_value;
        _drop;
    }
}

table drop_tbl {
    reads {
        paxos_packet_metadata.set_drop: exact;
    }
    actions {
        _drop;
        _nop;
    }
    size: 2;
}

control ingress {
    if (valid(paxos)) {
        apply(rnd_tbl);

        if (paxos.round > paxos_packet_metadata.round) {
            apply(start_tbl);
        } else if (paxos.round == paxos_packet_metadata.round) {
            apply(learner_tbl);
        }

        if (paxos_packet_metadata.acceptors >= MAJORITY) {
            apply(deliver_tbl);
        }
    }
}

control egress {
    apply(drop_tbl);
}
