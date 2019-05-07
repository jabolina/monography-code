#include "includes/paxos_headers.p4"
#include "includes/paxos_parser.p4"
#include "l2_control.p4"

#define INSTANCE_COUNT 65536
#define ACCEPTOR_COUNT 8

header_type ingress_metadata_t {
    fields {
        round: ROUND_SIZE;
        count: ACCEPTOR_COUNT;
        acceptors: ACCEPTOR_COUNT;
        majority: INSTANCE_COUNT;
    }
}
metadata ingress_metadata_t paxos_packet_metadata;

register majority_value {
    width: INSTANCE_COUNT;
    instance_count: 1;
}

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
    register_read(paxos_packet_metadata.majority, majority_value, 0);
    modify_field(intrinsic_metadata_paxos.set_drop, 1);
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
}

action deliver() {
    modify_field(intrinsic_metadata_paxos.set_drop, 0);
}

table rnd_tbl {
    actions { read_round; }
    size: 1;
}

table deliver_tbl {
    actions { deliver; }
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

control ingress {
    apply(smac);

    if (valid(paxos)) {
        apply(rnd_tbl);

        if (paxos.round > paxos_packet_metadata.round) {
            apply(start_tbl);
        } else if (paxos.round == paxos_packet_metadata.round) {
            apply(learner_tbl);
        }

        if (paxos_packet_metadata.acceptors >= paxos_packet_metadata.majority) {
            apply(deliver_tbl);
            apply(dmac);
        }
    }
}
