import platform
import psutil
import os
import logging
import time
import asyncio
import aiofiles
import mmap
import shutil
from tqdm import tqdm
import patoolib
import py7zr
import subprocess

# Create a console handler with a custom log format
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('=== Hardware Information ===\nSystem: %(message)s'))

# Create a file handler to log to a file with timestamps
file_handler = logging.FileHandler('system_diagnostics.log')
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)

# Initialize the logging configuration with both handlers
logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])

def check_cpu_usage():
    cpu_usage = psutil.cpu_percent(interval=1)
    logging.info(f"CPU Usage: {cpu_usage}%")

def check_memory_usage():
    virtual_memory = psutil.virtual_memory()
    logging.info(f"Memory Usage: {virtual_memory.percent}%")

def check_temperature():
    if platform.system() == "Darwin":
        try:
            osx_cpu_temp_path = '/Users/davemills/Documents/Projects/diagnostics/osx-cpu-temp/osx-cpu-temp'
            temperature_output = os.popen(osx_cpu_temp_path).read().strip()
            # Extract the numeric temperature value (removing '°C')
            temperature = float(temperature_output.split(' ')[0])
            logging.info(f"CPU Temperature: {temperature}°C")
        except Exception as e:
            logging.error(f"Error checking temperature: {str(e)}")
    elif platform.system() == "Windows":
        try:
            import wmi
            w = wmi.WMI()
            temperature_info = w.Win32_TemperatureProbe()[0]
            logging.info(f"CPU Temperature: {temperature_info.CurrentReading}°C")
        except Exception as e:
            logging.error(f"Error checking temperature: {str(e)}")
    elif platform.system() == "Linux":
        temperature = get_gpu_temperature_nvidia()
        if temperature is not None:
            logging.info(f"GPU Temperature: {temperature}°C")
    else:
        logging.info("Temperature monitoring not supported on this OS")

def get_ram_info():
    virtual_memory = psutil.virtual_memory()
    total_ram = virtual_memory.total / (1024 ** 3)  # Convert to GB
    logging.info(f"Total RAM: {total_ram:.2f} GB")

def get_gpu_info():
    if platform.system() == "Darwin":
        try:
            gpu_info = os.popen('system_profiler SPDisplaysDataType').read()
            # Extract the active GPU information
            active_gpu_info = gpu_info.split("Graphics/Displays:", 1)[-1].split("Displays:", 1)[0].strip()
            logging.info(f"Active GPU: {active_gpu_info}")
        except Exception as e:
            logging.error(f"Error getting GPU information: {str(e)}")
    elif platform.system() == "Windows":
        try:
            import wmi
            w = wmi.WMI()
            gpu_info = w.Win32_VideoController()[0]
            logging.info(f"Active GPU: {gpu_info.Caption}")
        except Exception as e:
            logging.error(f"Error getting GPU information: {str(e)}")
    else:
        logging.info("GPU information not available on this OS")

def display_hardware_info():
    hardware_info = []
    hardware_info.append("=== Hardware Information ===")
    hardware_info.append(f"System: {platform.system()} {platform.release()} ({platform.architecture()[0]})")
    hardware_info.append(f"CPU: {platform.processor()}")

    # CPU, Memory, and GPU information
    check_cpu_usage()
    check_memory_usage()
    check_temperature()
    get_ram_info()
    get_gpu_info()

    return '\n'.join(hardware_info)

def list_available_drives():
    available_drives = []
    for partition in psutil.disk_partitions():
        # Check if the 'is_physical' attribute exists and is True
        if hasattr(partition, 'device') and hasattr(partition, 'fstype'):
            # Some versions of psutil might not have 'is_physical'
            is_physical = getattr(partition, 'is_physical', True)
            if is_physical:
                available_drives.append(partition.device)
    return available_drives

def display_available_drives():
    available_drives_info = []

    for drive in psutil.disk_partitions(all=True):
        drive_info = psutil.disk_usage(drive.mountpoint)
        available_drives_info.append((drive.device, drive_info))

    if available_drives_info:
        print("Available drives:")
        for idx, (drive, drive_info) in enumerate(available_drives_info, start=1):
            print(f"{idx}. {drive} - Size: {drive_info.total / (1024 ** 3):.2f} GB")
        return available_drives_info
    else:
        print("No drives found on the system.")
        return []

def read_large_file(file_path, buffer_size=1024 * 1024):
    try:
        with open(file_path, 'rb') as file:
            while True:
                data = file.read(buffer_size)
                if not data:
                    break
                # Process data here
    except Exception as e:
        logging.error(f"Error reading file: {file_path}")
        logging.error(f"Error: {str(e)}")

async def read_file_async(file_path):
    try:
        async with aiofiles.open(file_path, mode='rb') as file:
            buffer_size = 1024 * 1024  # 1 MB buffer size
            while True:
                data = await file.read(buffer_size)
                if not data:
                    break
                # Process data here
    except Exception as e:
        logging.error(f"Error reading file asynchronously: {file_path}")
        logging.error(f"Error: {str(e)}")

def memory_map_file(file_path):
    try:
        with open(file_path, 'rb') as file:
            with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                # Access mmapped_file as if it were an array in memory
                data = mmapped_file[:]
                # Process data here
    except Exception as e:
        logging.error(f"Error memory mapping file: {file_path}")
        logging.error(f"Error: {str(e)}")

def scan_files(drives_to_scan, file_extensions_to_scan):
    problem_files = []
    for drive in tqdm(drives_to_scan, desc="Scanning Drives", unit="drive"):
        for root, dirs, files in os.walk(drive):
            for file in tqdm(files, desc="Scanning Files", unit="file", leave=False):
                file_path = os.path.join(root, file)
                try:
                    # Check if the file is an archive (zip, rar, or 7z)
                    if file_path.endswith(('.zip', '.rar', '.7z')):
                        # Extract the archive to a temporary directory
                        temp_dir = "temp_extracted"
                        os.makedirs(temp_dir, exist_ok=True)

                        if file_path.endswith('.zip'):
                            patoolib.extract_archive(file_path, outdir=temp_dir)
                        elif file_path.endswith('.rar'):
                            patoolib.extract_archive(file_path, outdir=temp_dir)
                        elif file_path.endswith('.7z'):
                            with py7zr.SevenZipFile(file_path, mode='r') as archive:
                                archive.extractall(path=temp_dir)

                        # Scan the extracted files
                        for extracted_root, extracted_dirs, extracted_files in os.walk(temp_dir):
                            for extracted_file in extracted_files:
                                extracted_file_path = os.path.join(extracted_root, extracted_file)
                                # Check file extension and skip if not in the list of allowed extensions
                                if not extracted_file_path.lower().endswith(tuple(file_extensions_to_scan)):
                                    continue
                                read_large_file(extracted_file_path)  # Use the appropriate file reading function

                        # Clean up the temporary directory
                        shutil.rmtree(temp_dir)
                    else:
                        # Not an archive, scan the file directly
                        # Check file extension and skip if not in the list of allowed extensions
                        if file_path.lower().endswith(tuple(file_extensions_to_scan)):
                            read_large_file(file_path)  # Use the appropriate file reading function
                except Exception as e:
                    problem_files.append(file_path)
                    logging.error(f"Problem detected in file: {file_path}")
                    logging.error(f"Error: {str(e)}")
    if not problem_files:
        logging.info("No problems detected in files.")
    return problem_files

def get_gpu_temperature_nvidia():
    if platform.system() == "Linux" and "NVIDIA" in platform.processor():
        try:
            output = subprocess.check_output(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'])
            temperature = float(output.decode('utf-8').strip())
            return temperature
        except Exception as e:
            logging.error(f"Error getting NVIDIA GPU temperature: {str(e)}")
            return None
    else:
        logging.info("GPU temperature monitoring not supported on this system.")
        return None

if __name__ == "__main__":
    while True:
        logging.info(display_hardware_info())

        # Wait for user input to choose an action
        user_input = input("Choose an action (R: Refresh, S: Scan Files, Q: Quit): ").lower()

        if user_input == 'r':
            continue  # Refresh
        elif user_input == 's':
            available_drives = display_available_drives()
            if available_drives:
                drive_choice = input("Select drives to scan (e.g., 1,2,3): ").split(',')
                drives_to_scan = [available_drives[int(choice) - 1][0] for choice in drive_choice if 1 <= int(choice) <= len(available_drives)]
                if drives_to_scan:
                    scan_files(drives_to_scan, ('.zip', '.rar', '.7z'))  # Change the file extensions as needed
        elif user_input == 'q':
            break  # Quit
        else:
            logging.info("Invalid input. Please choose a valid action.")
        time.sleep(1)
