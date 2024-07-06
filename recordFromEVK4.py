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

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Metavision RAW file Recorder sample.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-b', '--biases', type=str, help='Path to the biases file')
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


# TODO
# Abort if storage is about to fill up
# instead of recording for x seconds, record y amount of data, then pause

def get_folder_size(folder):
    """Get the size of the folder."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

def main():
    """ Main """
    args = parse_args()

    # Default output directory
    base_output_dir = "recordings"
    os.makedirs(base_output_dir, exist_ok=True)

    # Timestamped recording directory
    timestamp = time.strftime("%y%m%d_%H%M%S", time.localtime())
    output_dir = os.path.join(base_output_dir, f"recording_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    # Read biases from file if provided
    biases_dict = None
    if args.biases:
        biases_dict = read_biases(args.biases)

    

    def record_cycle():
        nonlocal biases_dict, output_dir

        # HAL Device on live camera
        device = initiate_device("")

        # Set biases if provided
        if biases_dict:
            biases = device.get_i_ll_biases()
            if biases is not None:
                for bias_name, bias_value in biases_dict.items():
                    try:
                        biases.set(bias_name, bias_value)
                        print(f'Successfully set {bias_name} to {bias_value}')
                    except Exception as e:
                        print(f'Failed to set {bias_name}: {e}')
                        print("Using default biases instead")
                        break
            else:
                print("Failed to access biases interface, using default biases")

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
            if current_time - start_time >= RECORDING_TIME:
                break
                
        # Stop the recording
        device.get_i_events_stream().stop_log_raw_data()
        del device

    try:
        while True:
            record_cycle()
            print(f"Pausing for {WAITING_TIME} seconds...")
            time.sleep(WAITING_TIME)
    except KeyboardInterrupt:
        print("Stopping the program...")

if __name__ == "__main__":
    main()
