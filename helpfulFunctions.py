
import argparse
import time
import os
import shutil
import logging
from metavision_core.event_io.raw_reader import initiate_device
from metavision_core.event_io import EventsIterator

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

def log_and_print_info(logger, message, args):
    logger.info(message)
    if args.print_logs:
        print(message)

def log_and_print_warning(logger, message, args):
    logger.warning(message)
    if args.print_logs:
        print(message)



def get_folder_size_and_free_space(output_dir):
    folder_size = get_folder_size(output_dir) / (1024 ** 2)  # Convert to MB
    total, used, free = shutil.disk_usage(output_dir)
    free_space = free / (1024 ** 3)  # Convert to GB
    return folder_size, free_space


def log_folder_size_and_free_space(logger, folder_size, free_space, args, prepend=""):
    """Log the folder size and free space."""
    log_and_print_info(logger, f"{prepend} Folder size: {folder_size:.2f} MB, Free space: {free_space:.2f} GB", args)
