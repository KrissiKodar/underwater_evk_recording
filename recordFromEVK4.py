from constants import *
import argparse
import time
import os
import shutil
import logging
from metavision_core.event_io.raw_reader import initiate_device
from metavision_core.event_io import EventsIterator

from helpfulFunctions import *


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Metavision RAW file Recorder sample.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-b', '--biases', type=str, help='Path to the biases file')
    parser.add_argument('-d', '--data_size', type=float, default=None, help='Amount of data to record in MB')
    parser.add_argument('-p', '--print_logs', action='store_true', help='Print logs to console')
    args = parser.parse_args()
    return args

def initialize_device():
    """Initialize the device."""
    device = initiate_device("")
    return device


def set_device_bias_configuration(biases_dict, print_biases_message_once, logger, args):
    """Initialize the device and set biases if provided."""
    device = initiate_device("")
    if biases_dict:
        biases = device.get_i_ll_biases()
        if biases is not None:
            for bias_name, bias_value in biases_dict.items():
                try:
                    biases.set(bias_name, bias_value)
                    if print_biases_message_once:
                        log_and_print_info(logger, f'Successfully set {bias_name} to {bias_value}', args)
                except Exception as e:
                    if print_biases_message_once:
                        if args.print_logs:
                            log_and_print_warning(logger, f'Failed to set {bias_name}: {e}', args)

                    if args.print_logs:
                        log_and_print_warning(logger, "Using default biases instead", args)
                    break
        else:
            if print_biases_message_once:
                log_and_print_warning(logger, "Failed to access biases interface, using default biases", args)


    return device

def set_contrast_detection_rate_limit(logger, args, device):
    if device.get_i_erc_module():  # we test if the facility is available on this device before using it
        log_and_print_info(logger, "ERC module is available", args)
        device.get_i_erc_module().enable(True)
        device.get_i_erc_module().set_cd_event_rate(int(EVENT_RATE_CONTROL))

def get_device(recording_counter, logger, biases_dict, output_dir, print_biases_message_once, args):
    device = initialize_device()
    set_device_bias_configuration(biases_dict, print_biases_message_once, logger, args)
    start_device_recording(recording_counter, logger, output_dir, args, device)
    set_contrast_detection_rate_limit(logger, args, device)
    return device

def record_cycle(recording_counter, logger, biases_dict, output_dir, print_biases_message_once, args, data_size_mb=None):

        device = get_device(recording_counter, logger, biases_dict, output_dir, print_biases_message_once, args)


        start_time = time.time()
        last_check_time = start_time

        mv_iterator = EventsIterator.from_device(device=device)

        for evs in mv_iterator:

            if over_recording_time(start_time):
                device.get_i_events_stream().stop()
    
            #Periodically check folder size and free space
            if over_folder_size_check_time(last_check_time):
                folder_size, free_space = get_folder_size_and_free_space(output_dir)
                log_folder_size_and_free_space(logger, folder_size, free_space, args)
                
                last_check_time = time.time()  

                
                # Stop recording if free space is too low or if data size limit is specified and reached
                if free_space <= MIN_FREE_SPACE_GB or (data_size_mb is not None and folder_size >= data_size_mb):
                    log_folder_size_and_free_space(logger, folder_size, free_space, args, prepend="Stopping recording:")
                    device.get_i_events_stream().stop()
                    break

        
        device.get_i_events_stream().stop_log_raw_data()
        del device





def main():
    """ Main """
    args = parse_args()

    # Set up logging with a unique filename
    timestamp = get_current_timestamp()
    logger = create_logger(timestamp)

    recording_counter = 1    

    external_storage_dir = find_external_storage()
    base_output_dir = get_base_output_dir(args, logger, external_storage_dir)


    os.makedirs(base_output_dir, exist_ok=True)

    # Timestamped recording directory
    output_dir = os.path.join(base_output_dir, f"recording_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    # Read biases from file if provided
    biases_dict = None
    if args.biases:
        biases_dict = read_biases(args.biases)

    # Flag to print biases message only once
    print_biases_message_once = True
    
    try:
        while True:
            if record_cycle(recording_counter, logger, biases_dict, output_dir, print_biases_message_once, args, args.data_size):
                log_and_print_info(logger, "Data size limit reached. Stopping further recordings.", args)
                break
            folder_size, free_space = get_folder_size_and_free_space(output_dir)
            if free_space <= MIN_FREE_SPACE_GB:
                log_and_print_warning(logger, f"Free space is below the limit ({MIN_FREE_SPACE_GB} GB). Stopping the program.", args)
                break
            log_and_print_info(logger, f"Waiting for {WAITING_TIME} seconds...", args)
            recording_counter += 1
            print_biases_message_once = False  # Ensure the message is only printed once
            time.sleep(WAITING_TIME)
    except KeyboardInterrupt:
        log_and_print_info(logger, "Stopping the program...", args)




            

if __name__ == "__main__":
    main()
