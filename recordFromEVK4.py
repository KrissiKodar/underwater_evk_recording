from constants import *
import argparse
import time
import os
import shutil
import logging
from metavision_core.event_io.raw_reader import initiate_device
from metavision_core.event_io import EventsIterator

from helpfulFunctions import *

import RPi.GPIO as GPIO
import lgpio

# import RPi.GPIO as GPIO
# 
# # Pin Definition
# pressure_pin = 14
# 
# # Pin Setup
# GPIO.setwarnings(False)  # Disable GPIO warnings
# GPIO.setmode(GPIO.BCM)   # Broadcom pin-numbering scheme
# GPIO.setup(pressure_pin, GPIO.IN)  # Input pin set as input

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Metavision RAW file Recorder sample.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-b', '--biases', type=str, help='Path to the biases file')
    parser.add_argument('-d', '--data_size', type=float, default=None, help='Amount of data to record in MB')
    parser.add_argument('-p', '--print_logs', action='store_true', help='Print logs to console')
    args = parser.parse_args()
    return args


def set_device_bias_configuration(device, biases_dict, print_biases_message_once, logger, args):
    """Initialize the device and set biases if provided."""
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

def get_device(logger, biases_dict, print_biases_message_once, args):
    device = initiate_device("")
    set_device_bias_configuration(device, biases_dict, print_biases_message_once, logger, args)
    set_contrast_detection_rate_limit(logger, args, device)
    return device


def start_device_recording(recording_counter, logger, output_dir, args, device):
    if device.get_i_events_stream():
        name = get_current_timestamp()
        log_path = os.path.join(output_dir, f"{name}.raw")
        log_and_print_info(logger, f'Recording to {log_path}', args)
        device.get_i_events_stream().start()
        device.get_i_events_stream().log_raw_data(log_path)


def record_cycle(recording_counter, logger, biases_dict, output_dir, print_biases_message_once, args, data_size_mb=None):

        device = get_device(logger, biases_dict, print_biases_message_once, args)
        start_device_recording(recording_counter, logger, output_dir, args, device)

        start_time = time.time()
        last_check_time = start_time

        mv_iterator = EventsIterator.from_device(device=device)

        for evs in mv_iterator:

            if over_recording_time(start_time):
                device.get_i_events_stream().stop()
    
            #Periodically check folder size and free space
            if over_folder_size_check_time(last_check_time):
                folder_size, free_space = get_folder_size_and_free_space("/dev/shm")
                log_folder_size_and_free_space(logger, folder_size, free_space, args)
                
                last_check_time = time.time()  
                
                # Stop recording if free space is too low or if data size limit is specified and reached
                if free_space <= MIN_FREE_SPACE_GB or (data_size_mb is not None and folder_size >= data_size_mb):
                    log_folder_size_and_free_space(logger, folder_size, free_space, args, prepend="Stopping recording:")
                    device.get_i_events_stream().stop()
                    break

        
        device.get_i_events_stream().stop_log_raw_data()
        del device

def is_depth_more_than_10_meters() -> bool:
    pressure_pin = 4
    h = None

    try:
        h = lgpio.gpiochip_open(4)
        lgpio.gpio_claim_input(h, pressure_pin)
        time.sleep(0.1)
        status = lgpio.gpio_read(h, pressure_pin)
        return status == 1

    except lgpio.error as e:
        if 'GPIO busy' in str(e):
            print(f"GPIO pin {pressure_pin} is busy. Retrying in 1 second...")
            time.sleep(1)  # Wait for 1 second before retrying
            return is_depth()  # Retry the function
        else:
            # Handle other unexpected errors
            print(f"An unexpected error occurred: {e}")
            raise
    finally:
        if h:
            lgpio.gpiochip_close(h)  # Close the GPIO chip to free resources
            print(f"Closed GPIO chip handle: {h}")

def main():
    """ Main """
    args = parse_args()

    # Read biases from file if provided
    biases_dict = None
    if args.biases:
        biases_dict = read_biases(args.biases)

    # Flag to print biases message only once
    print_biases_message_once = True
    
    try:
        while True:

            if is_depth_more_than_10_meters():

                # Set up logging with a unique filename
                timestamp = get_current_timestamp()
                logger = create_logger(timestamp)

                recording_counter = 1    

                # external_storage_dir = find_external_storage()
                external_storage_dir = "/dev/shm"

                base_output_dir = get_base_output_dir(args, logger, external_storage_dir)

                os.makedirs(base_output_dir, exist_ok=True)

                # Timestamped recording directory
                output_dir = os.path.join(base_output_dir, f"recording_{timestamp}")
                os.makedirs(output_dir, exist_ok=True)

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
            else:
                time.sleep(5)

    except KeyboardInterrupt:
        log_and_print_info(logger, "Stopping the program...", args)




            

if __name__ == "__main__":
    main()
