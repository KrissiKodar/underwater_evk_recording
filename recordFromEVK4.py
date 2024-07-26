import argparse
import time
import os
import shutil
from metavision_core.event_io.raw_reader import initiate_device
from metavision_core.event_io import EventsIterator

# Configuration parameters
RECORDING_TIME = 5  # seconds to record
WAITING_TIME = 5    # seconds to wait between recordings
FOLDER_SIZE_CHECK_INTERVAL = 1  # seconds
MIN_FREE_SPACE_GB = 1  # Minimum free space in GB to keep recording safely

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Metavision RAW file Recorder sample.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-b', '--biases', type=str, help='Path to the biases file')
    parser.add_argument('-d', '--data_size', type=float, default=None, help='Amount of data to record in MB')
    args = parser.parse_args()
    return args

def read_biases(file_path):
    """Read biases from the given file."""
    biases = {}
    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split()
            bias_value = int(parts[0].strip())
            bias_name = parts[2].strip()
            biases[bias_name] = bias_value
            
    return biases

def get_folder_size(folder):
    """Get the size of the folder."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

def find_external_storage():
    """Find an external storage device."""
    with open('/proc/mounts', 'r') as f:
        for line in f:
            if '/media/' in line:
                parts = line.split()
                mount_dir = parts[1]
                return mount_dir
    return None

def initialize_device_with_biases(biases_dict, print_biases_message_once):
    """Initialize the device and set biases if provided."""
    device = initiate_device("")
    if biases_dict:
        biases = device.get_i_ll_biases()
        if biases is not None:
            for bias_name, bias_value in biases_dict.items():
                try:
                    biases.set(bias_name, bias_value)
                    if print_biases_message_once:
                        print(f'Successfully set {bias_name} to {bias_value}')
                except Exception as e:
                    if print_biases_message_once:
                        print(f'Failed to set {bias_name}: {e}')
                    print("Using default biases instead")
                    break
        else:
            if print_biases_message_once:
                print("Failed to access biases interface, using default biases")
    return device

def main():
    """ Main """
    args = parse_args()

    # Default output directory
    external_storage_dir = find_external_storage()
    if external_storage_dir:
        base_output_dir = os.path.join(external_storage_dir, "recordings")
        print(f"External storage found: {external_storage_dir}")
    else:
        base_output_dir = "recordings"
        print("No external storage found, using local directory.")

    os.makedirs(base_output_dir, exist_ok=True)

    # Timestamped recording directory
    timestamp = time.strftime("%y%m%d_%H%M%S", time.localtime())
    output_dir = os.path.join(base_output_dir, f"recording_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    # Read biases from file if provided
    biases_dict = None
    if args.biases:
        biases_dict = read_biases(args.biases)

    # Flag to print biases message only once
    print_biases_message_once = True

    def record_cycle(data_size_mb=None):
        nonlocal biases_dict, output_dir, print_biases_message_once

        # Initialize device and set biases
        device = initialize_device_with_biases(biases_dict, print_biases_message_once)
        print_biases_message_once = False  # Ensure the message is only printed once

        # Start the recording
        if device.get_i_events_stream():
            log_path = os.path.join(output_dir, f"recording_{time.strftime('%y%m%d_%H%M%S', time.localtime())}.raw")
            print(f'Recording to {log_path}')
            device.get_i_events_stream().log_raw_data(log_path)

        start_time = time.time()
        last_check_time = start_time
        mv_iterator = EventsIterator.from_device(device=device)

        while True:
            for evs in mv_iterator:
                # Process events to keep the recording going
                current_time = time.time()
                if current_time - start_time >= RECORDING_TIME:
                    break

                # Periodically check folder size and free space
                if time.time() - last_check_time >= FOLDER_SIZE_CHECK_INTERVAL:
                    folder_size = get_folder_size(output_dir) / (1024 ** 2)  # Convert to MB
                    total, used, free = shutil.disk_usage(output_dir)
                    free_space = free / (1024 ** 3)  # Convert to GB
                    print(f"Folder size: {folder_size:.2f} MB, Free space: {free_space:.2f} GB")
                    last_check_time = time.time()  # reset last check time

                    # Stop recording if free space is too low or if data size limit is specified and reached
                    if free_space <= MIN_FREE_SPACE_GB or (data_size_mb is not None and folder_size >= data_size_mb):
                        print(f"Stopping recording: folder size {folder_size:.2f} MB, free space {free_space:.2f} GB")
                        device.get_i_events_stream().stop_log_raw_data()
                        return data_size_mb is not None and folder_size >= data_size_mb  # Return True if data size limit is reached

            if current_time - start_time >= RECORDING_TIME:
                break
                
        # Stop the recording
        device.get_i_events_stream().stop_log_raw_data()
        del device

    try:
        while True:
            if record_cycle(args.data_size):
                print("Data size limit reached. Stopping further recordings.")
                break
            total, used, free = shutil.disk_usage(output_dir)
            free_space = free / (1024 ** 3)  # Convert to GB
            if free_space <= MIN_FREE_SPACE_GB:
                print(f"Free space is below the limit ({MIN_FREE_SPACE_GB} GB). Stopping the program.")
                break
            print(f"Pausing for {WAITING_TIME} seconds...")
            time.sleep(WAITING_TIME)
    except KeyboardInterrupt:
        print("Stopping the program...")

if __name__ == "__main__":
    main()
