#include "includes/paxos_headers.p4"
#include "includes/paxos_parser.p4"
#include "l2_control.p4"

// INSTANCE_SIZE is the width of the instance field in the Paxos header.
// INSTANCE_COUNT is number of entries in the registers.
// So, INSTANCE_COUNT = 2^INSTANCE_SIZE.

#define INSTANCE_COUNT 65536

field_list resubmit_field_list {
    paxos_packet_metadata.invalid_instance;
    paxos_packet_metadata.valid_instance;
    paxos_packet_metadata.new_instance;
    paxos.instance; 
}

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

register invalid_instance_register {
    width: INSTANCE_SIZE;
    instance_count: 1;
}

register valid_instance_register {
    width: INSTANCE_SIZE;
    instance_count: 1;
}

register future_instance_register {
    width: INSTANCE_SIZE;
    instance_count: 1;
}

// When the window slides, the register must be cleaned in for the
// inactive instance
action clean_register() {
    register_write(rounds_register, paxos_packet_metadata.invalid_instance, 0);
    register_write(vrounds_register, paxos_packet_metadata.invalid_instance, 0);
    register_write(values_register, paxos_packet_metadata.invalid_instance, 0);
}

// Copying Paxos-fields from the register to meta-data structure. The index
// (i.e., paxos instance number) is read from the current packet. Could be
// problematic if the instance exceeds the bounds of the register.
action read_round() {
    register_read(paxos_packet_metadata.round, rounds_register, paxos.instance);
    modify_field(intrinsic_metadata_paxos.set_drop, 1);
}

// This will read the values accepted by the window into the packet metadata
action read_instance() {
    register_read(paxos_packet_metadata.invalid_instance, invalid_instance_register, 0);
    register_read(paxos_packet_metadata.valid_instance, valid_instance_register, 0);
    register_read(paxos_packet_metadata.new_instance, future_instance_register, 0);
}

// This will slide the window in 1 and resubmit the package
action slide_window() {
    add_to_field(paxos_packet_metadata.invalid_instance, 1);
    add_to_field(paxos_packet_metadata.valid_instance, 1);
    add_to_field(paxos_packet_metadata.new_instance, 1);

    register_write(invalid_instance_register, 0, paxos_packet_metadata.invalid_instance);
    register_write(valid_instance_register, 0, paxos_packet_metadata.valid_instance);
    register_write(future_instance_register, 0, paxos_packet_metadata.new_instance);

    resubmit(resubmit_field_list);
}

// Receive Paxos 1A message, send Paxos 1B message
action handle_1a() {
    modify_field(intrinsic_metadata_paxos.set_drop, 0);
    modify_field(paxos.msgtype, PAXOS_1B);                                        // Create a 1B message
    register_read(paxos.vround, vrounds_register, paxos.instance);                // paxos.vround = vrounds_register[paxos.instance]
    register_read(paxos.value, values_register, paxos.instance);                  // paxos.value  = values_register[paxos.instance]
    register_read(paxos.acceptor, datapath_id, 0);                                // paxos.acceptor = datapath_id
    register_write(rounds_register, paxos.instance, paxos.round);                 // rounds_register[paxos.instance] = paxos.round
}

// Receive Paxos 2A message, send Paxos 2B message
action handle_2a() {
    modify_field(intrinsic_metadata_paxos.set_drop, 0);
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

table tbl_clean_register {
    actions { clean_register; }
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

        /**
         * Here we have 3 cases, the default case, when the window is sliding from left to right.
         * When the first margin of the window restart and when only the invalid instances not
         * restarted again.
         * 
         * In the next comments, i is for the left margin of the invalid instances, j for the start of
         * valid instances and k for the start of new instances, x is used for the current instance.
         */

        if (
            // i < j < k
            (paxos_packet_metadata.invalid_instance < paxos_packet_metadata.valid_instance and
                paxos_packet_metadata.valid_instance < paxos_packet_metadata.new_instance)
            or
            // k < i < j
            (paxos_packet_metadata.new_instance < paxos_packet_metadata.invalid_instance and
                paxos_packet_metadata.invalid_instance < paxos_packet_metadata.valid_instance)
            or
            // j < k < i
            (paxos_packet_metadata.valid_instance < paxos_packet_metadata.new_instance and
                paxos_packet_metadata.new_instance < paxos_packet_metadata.invalid_instance)
        ) {

            if (
                // i < x and j <= x and x < k
                (paxos_packet_metadata.invalid_instance < paxos.instance and
                    paxos_packet_metadata.valid_instance <= paxos.instance and
                    paxos.instance < paxos_packet_metadata.new_instance)
                or
                // (j <= x and k < j) or (x < k and k < j)
                ((paxos_packet_metadata.valid_instance <= paxos.instance and
                    paxos_packet_metadata.new_instance < paxos_packet_metadata.valid_instance) or
                    (paxos.instance < paxos_packet_metadata.new_instance and
                    paxos_packet_metadata.new_instance < paxos_packet_metadata.valid_instance))
                or
                // j <= x and x < k
                (paxos_packet_metadata.valid_instance <= paxos.instance and
                    paxos.instance < paxos_packet_metadata.new_instance)
            ) {
                apply(tbl_acceptor);
            } else if (
                // k <= x and i < x
                (paxos_packet_metadata.new_instance <= paxos.instance and
                    paxos_packet_metadata.invalid_instance < paxos.instance)
                or
                // k <= x and x < i
                (paxos_packet_metadata.new_instance <= paxos.instance and
                    paxos.instance < paxos_packet_metadata.invalid_instance)
            ) {
                apply(tbl_clean_register);
                apply(tbl_slide_window);
            }
        }

        
    }
}
