#include "includes/paxos_headers.p4"
#include "includes/paxos_parser.p4"
#include "l2_control.p4"

// INSTANCE_SIZE is the width of the instance field in the Paxos header.
// INSTANCE_COUNT is number of entries in the registers.
// So, INSTANCE_COUNT = 2^INSTANCE_SIZE.

#define INSTANCE_COUNT 65536

header_type ingress_metadata_t {
    fields {
        round : ROUND_SIZE;
        invalid_instance: INSTANCE_SIZE;
        valid_instance: INSTANCE_SIZE;
        new_instance: INSTANCE_SIZE;
    }
}

metadata ingress_metadata_t paxos_packet_metadata;

register datapath_id {
    width: DATAPATH_SIZE;
    instance_count : 1;
}

register rounds_register {
    width : ROUND_SIZE;
    instance_count : INSTANCE_COUNT;
}

register vrounds_register {
    width : ROUND_SIZE;
    instance_count : INSTANCE_COUNT;
}

register values_register {
    width : VALUE_SIZE;
    instance_count : INSTANCE_COUNT;
}

register instances_register {
    width: INSTANCE_SIZE;
    instance_count: INSTANCE_COUNT;
}

field_list resubmit_field_list {
    paxos_packet_metadata.invalid_instance;
    paxos_packet_metadata.valid_instance;
    paxos_packet_metadata.new_instance;
    paxos.instance; 
}

// Copying Paxos-fields from the register to meta-data structure. The index
// (i.e., paxos instance number) is read from the current packet. Could be
// problematic if the instance exceeds the bounds of the register.
action read_round() {
    register_read(paxos_packet_metadata.round, rounds_register, paxos.instance);
}

action read_instance() {
    register_read(paxos_packet_metadata.invalid_instance, instances_register, 0);
    register_read(paxos_packet_metadata.valid_instance, instances_register, 1);
    register_read(paxos_packet_metadata.new_instance, instances_register, 2);
}

action slide_window() {
    add_to_field(paxos_packet_metadata.invalid_instance, 1);
    add_to_field(paxos_packet_metadata.valid_instance, 1);
    add_to_field(paxos_packet_metadata.new_instance, 1);

    register_write(instances_register, 0, paxos_packet_metadata.invalid_instance);
    register_write(instances_register, 1, paxos_packet_metadata.valid_instance);
    register_write(instances_register, 2, paxos_packet_metadata.new_instance);

    resubmit(resubmit_field_list);
}

action start_windows() {
    register_write(instances_register, 1, 0x0005);
    register_write(instances_register, 2, 0x0008);
}

// Receive Paxos 1A message, send Paxos 1B message
action handle_1a() {
    modify_field(paxos.msgtype, PAXOS_1B);                                        // Create a 1B message
    register_read(paxos.vround, vrounds_register, paxos.instance);                // paxos.vround = vrounds_register[paxos.instance]
    register_read(paxos.value, values_register, paxos.instance);                  // paxos.value  = values_register[paxos.instance]
    register_read(paxos.acceptor, datapath_id, 0);                                // paxos.acceptor = datapath_id
    register_write(rounds_register, paxos.instance, paxos.round);                 // rounds_register[paxos.instance] = paxos.round
}

// Receive Paxos 2A message, send Paxos 2B message
action handle_2a() {
    modify_field(paxos.msgtype, PAXOS_2B);				                          // Create a 2B message
    register_write(rounds_register, paxos.instance, paxos.round);                 // rounds_register[paxos.instance] = paxos.round
    register_write(vrounds_register, paxos.instance, paxos.round);                // vrounds_register[paxos.instance] = paxos.round
    register_write(values_register, paxos.instance, paxos.value);                 // values_register[paxos.instance] = paxos.value
    register_read(paxos.acceptor, datapath_id, 0);                                // paxos.acceptor = datapath_id
}

table tbl_rnd {
    actions { read_round; }
}

table tbl_inst {
    actions { read_instance; }
}

table tbl_slide_window {
    actions { slide_window; }
}

table tbl_first_window {
    actions { start_windows; }
}

table tbl_acceptor {
    reads   { paxos.msgtype : exact; }
    actions { handle_1a; handle_2a; _drop; }
}

control ingress {
    apply(smac);                 /* MAC learning, from l2_control.p4... */
    apply(dmac);                 /* ...not doing Paxos logic */
    
    if (valid(paxos)) {          /* check if we have a paxos packet */
        apply(tbl_inst);
        apply(tbl_rnd);
        
        if (paxos_packet_metadata.invalid_instance == 0 and
            paxos_packet_metadata.valid_instance == 0 and
            paxos_packet_metadata.new_instance == 0) {
                apply(tbl_first_window);
                if (paxos_packet_metadata.round <= paxos.round) {
                    apply(tbl_acceptor);
                } else {
                    apply(drop_tbl);
                }
        } else {
            if (paxos_packet_metadata.invalid_instance >= paxos.instance) {
                apply(drop_tbl);
            } else if (paxos_packet_metadata.valid_instance >= paxos.instance) {
                if (paxos_packet_metadata.round <= paxos.round) {
                    apply(tbl_acceptor);
                } else {
                    apply(drop_tbl);
                }
            } else {
                apply(tbl_slide_window);
            }
        }
    }
}
