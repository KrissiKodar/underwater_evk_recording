
import argparse
import time
import os
import shutil
import logging
from metavision_core.event_io.raw_reader import initiate_device
from metavision_core.event_io import EventsIterator

from helpfulFunctions import *

# Configuration parameters
RECORDING_TIME = 10               # seconds to record
WAITING_TIME = 5                  # seconds to wait between recordings
FOLDER_SIZE_CHECK_INTERVAL = 1    # seconds
MIN_FREE_SPACE_GB = 1             # Minimum free space in GB to keep recording safely
EVENT_RATE_CONTROL = 10e6          # Event rate control in events per second

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Metavision RAW file Recorder sample.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-b', '--biases', type=str, help='Path to the biases file')
    parser.add_argument('-d', '--data_size', type=float, default=None, help='Amount of data to record in MB')
    parser.add_argument('-p', '--print_logs', action='store_true', help='Print logs to console')
    args = parser.parse_args()
    return args


def initialize_device_with_biases(biases_dict, print_biases_message_once, logger, args):
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


def record_cycle(recording_counter, logger, biases_dict, output_dir, print_biases_message_once, args, data_size_mb=None):

        # Initialize device and set biases
        device = initialize_device_with_biases(biases_dict, print_biases_message_once, logger, args)


        # Start the recording
        if device.get_i_events_stream():
            log_path = os.path.join(output_dir, f"{recording_counter}.raw")
            log_and_print_info(logger, f'Recording to {log_path}', args)
            device.get_i_events_stream().start()
            device.get_i_events_stream().log_raw_data(log_path)

        start_time = time.time()
        last_check_time = start_time
        
        # limit the contrast detection event rate
        if device.get_i_erc_module():  # we test if the facility is available on this device before using it
            log_and_print_info(logger, "ERC module is available", args)
            device.get_i_erc_module().enable(True)
            device.get_i_erc_module().set_cd_event_rate(int(EVENT_RATE_CONTROL))


        mv_iterator = EventsIterator.from_device(device=device)


        for evs in mv_iterator:
            # Process events to keep the recording going
            current_time = time.time()
            if current_time - start_time >= RECORDING_TIME:
                device.get_i_events_stream().stop()
    
            #Periodically check folder size and free space
            if time.time() - last_check_time >= FOLDER_SIZE_CHECK_INTERVAL:
                folder_size, free_space = get_folder_size_and_free_space(output_dir)
                log_folder_size_and_free_space(logger, folder_size, free_space, args)
                
                last_check_time = time.time()  # reset last check time
    
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
    timestamp = time.strftime("%y%m%d_%H%M%S", time.localtime())
    log_filename = f"recording_log_{timestamp}.log"
    logging.basicConfig(filename=log_filename, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    logger = logging.getLogger()

    recording_counter = 1    
    # Default output directory  
    external_storage_dir = find_external_storage()
    if external_storage_dir:
        base_output_dir = os.path.join(external_storage_dir, "recordings")
        log_and_print_info(logger, f"External storage found: {external_storage_dir}", args)
    else:
        base_output_dir = "recordings"
        log_and_print_warning(logger, "No external storage found, using local directory.", args)


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
