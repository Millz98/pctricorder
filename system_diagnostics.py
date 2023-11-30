import platform
import psutil
import os
import logging
import time
import asyncio
import aiofiles
from tqdm import tqdm
import socket
import speedtest
import subprocess
import mmap
import csv
import zipfile
import patoolib
from py7zr import SevenZipFile 


# Define these variables at the module level
file_extensions_to_scan = ('.zip', '.rar', '.7z')
problem_files = []  # Define the problem_files list
scanned_files = []  # Define the scanned_files list
global_pbar = None  # Define the global progress bar

# Create a console handler with a custom log format
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('=== Hardware Information ===\nSystem: %(message)s'))

# Create a file handler to log to a file with timestamps
file_handler = logging.FileHandler('system_diagnostics.log')
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)

# Initialize the logging configuration with both handlers
logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])


# Function for scanning files within drives
def scan_files(self):
        available_drives = display_available_drives()
        if available_drives:
            drive_choice = input("Select drives to scan (e.g., 1,2,3): ").split(',')
            drives_to_scan = [available_drives[int(choice) - 1][0] for choice in drive_choice if 1 <= int(choice) <= len(available_drives)]
            if drives_to_scan:
                with tqdm(total=sum(len(os.listdir(drive)) for drive in drives_to_scan if os.path.isdir(drive))) as pbar:
                    problem_files = []  # Reset problem_files
                    scanned_files = []  # Reset scanned_files
                    asyncio.run(scan_selected_drives(drives_to_scan, file_extensions_to_scan, problem_files, scanned_files))

                    if not problem_files:
                        logging.info("No problems detected in files.")
                    else:
                        logging.info(f"Problems found in {len(problem_files)} files.")
                        for problem_file in problem_files:
                            logging.info(problem_file)


# Function for battery check
def check_battery_health():
    try:
        if platform.system() == "Windows":
            # Add code to check battery health on Windows if needed
            pass

        elif platform.system() == "Darwin":
            # Run a command to check battery health on macOS
            result = subprocess.run(['system_profiler', 'SPPowerDataType'], capture_output=True, text=True, check=True)

            # Extract battery health information from the result
            battery_health_info = extract_battery_health_info(result.stdout)
            logging.info(f"Battery Health: {battery_health_info}")

        else:
            logging.warning("Battery health check not supported on this operating system.")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error checking battery health: {e.stderr}")

def extract_battery_health_info(report):
    # Extract relevant information from the battery report
    # Modify this based on the actual output format of the system_profiler command
    cycle_count_line = [line for line in report.split('\n') if 'Cycle Count' in line]
    if cycle_count_line:
        cycle_count = int(cycle_count_line[0].split(':')[1].strip())
        return f"Cycle Count: {cycle_count}"
    else:
        return "Battery health information not found in the report."

# Function for historical data
def log_historical_data(cpu_usage, memory_percent, timestamp):
    historical_data_file = 'historical_data.csv'

    # Check if the file exists; create headers if not
    file_exists = os.path.isfile(historical_data_file)
    with open(historical_data_file, 'a', newline='') as file:
        fieldnames = ['Timestamp', 'CPU Usage', 'Memory Percent']
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        # Write the data to the CSV file
        writer.writerow({'Timestamp': timestamp, 'CPU Usage': cpu_usage, 'Memory Percent': memory_percent})


# Function for System recommendations
def system_recommendations(cpu_usage, memory_percent):
    recommendations = []

    # CPU Recommendations
    if cpu_usage > 90:
        recommendations.append("High CPU usage detected. Consider upgrading your CPU.")
    elif cpu_usage > 70:
        recommendations.append("Moderate CPU usage. Monitor performance for potential upgrades.")

    # Memory Recommendations
    if memory_percent > 90:
        recommendations.append("High memory usage detected. Consider adding more RAM.")
    elif memory_percent > 70:
        recommendations.append("Moderate memory usage. Monitor performance for potential upgrades.")

    return recommendations

# Example Usage
cpu_usage = 85  # Replace with actual CPU usage percentage
memory_percent = 80  # Replace with actual memory usage percentage

recommendations = system_recommendations(cpu_usage, memory_percent)

if recommendations:
    logging.info("System Recommendations:")
    for recommendation in recommendations:
        logging.info("- " + recommendation)
else:
    logging.info("No specific recommendations at the moment.")

# Function to start a scan
def start_scan(drives_to_scan):
    problem_files = []  # Define the problem_files list
    scanned_files = []  # Define the scanned_files list

    # Log that the scan is starting
    logging.info("Scan started for the following drives: " + ', '.join(drives_to_scan))

    # Scan the selected drives
    for drive in drives_to_scan:
        scan_drive(drive, problem_files, scanned_files)

    # Log that the scan is completed
    logging.info("Scan completed for all selected drives.")

    # Log the scan results for problem files
    if problem_files:
        logging.info("Problems found in files:")
        for problem_file in problem_files:
            logging.info(problem_file)

# Function to display storage information
def display_storage_info():
    storage_info = []
    storage_info.append("=== Storage Information ===")
    for partition in psutil.disk_partitions():
        usage = psutil.disk_usage(partition.mountpoint)
        storage_info.append(f"{partition.device} - Total: {usage.total / (1024 ** 3):.2f} GB, Free: {usage.free / (1024 ** 3):.2f} GB, Used: {usage.percent}%")
    return '\n'.join(storage_info)

# Function to perform network diagnostics
def perform_network_diagnostics():
    try:
        # Check network connectivity using ping
        target_host = "www.google.ca"
        response = subprocess.run(["ping", "-c", "4", target_host], capture_output=True, text=True, check=True)

        if "4 packets transmitted, 4 received" in response.stdout:
            logging.info("Ping Test: Network is reachable.")
        else:
            logging.warning("Ping Test: Network is unreachable.")

        # Measure network speed TODO: fix this for windows, works 100% fine on Mac
        st = speedtest.Speedtest()
        download_speed = st.download() / 10**6  # in Mbps
        upload_speed = st.upload() / 10**6  # in Mbps
        logging.info(f"Speed Test: Download Speed: {download_speed:.2f} Mbps, Upload Speed: {upload_speed:.2f} Mbps")

        # DNS resolution check
        try:
            socket.gethostbyname(target_host)
            logging.info("DNS Resolution: DNS is working properly.")
        except socket.error:
            logging.warning("DNS Resolution: Unable to resolve DNS.")

        # Traceroute
        target_ip = socket.gethostbyname(target_host)
        traceroute_output = subprocess.run(["traceroute", target_ip], capture_output=True, text=True)
        logging.info(f"Traceroute:\n{traceroute_output.stdout}")    

    except subprocess.CalledProcessError as e:
        logging.error(f"Error during network diagnostics: {e.stderr}")
        logging.warning("Ping Test: Network is unreachable. Check network configuration and firewall settings.")
    except Exception as e:
        logging.error(f"Unexpected error during network diagnostics: {str(e)}")

        

def perform_security_checks():
    try:
        # Check for antivirus status
        check_antivirus_status()

        # Scan for malware
        scan_for_malware()
        # For example, scan for malware or check antivirus status
        logging.info("Performing security checks...")
        

        # You can add more security checks here

        logging.info("Security checks completed.")
    # Check for software updates on Windows
        if platform.system() == "Windows":
            logging.info("Checking for software updates...")
            update_command = "winget upgrade --all"
            # Run the update command with tqdm progress bar
        with tqdm(total=100, desc="Updating", dynamic_ncols=True) as pbar:
            update_process = subprocess.Popen(update_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, bufsize=1, universal_newlines=True)

            for line in update_process.stdout:
                # Check if the line contains progress information
                # You need to adjust this based on the actual output format of the command
                if "progress" in line:
                    # Extract progress information and update the progress bar
                    progress_value = extract_progress_from_line(line)
                    pbar.update(progress_value)

            # Wait for the process to complete
            update_process.wait()

    except Exception as e:
        logging.error(f"Error performing security checks: {str(e)}")

def extract_progress_from_line(line):
    # Implement logic to extract progress information from the line
    # You need to adjust this based on the actual output format of the command
    # Return the progress value (percentage) as an integer
    return 10  # Placeholder value, replace with actual extraction logic   

def check_antivirus_status():
    if platform.system() == "Windows":
        try:
            # Run a command to check antivirus status on Windows
            result = subprocess.run(['powershell', 'Get-MpComputerStatus'], capture_output=True, text=True, check=True)
            logging.info(f"Antivirus Status: {result.stdout.strip()}")

            

        except subprocess.CalledProcessError as e:
            logging.error(f"Error checking antivirus status: {e.stderr}")

# You can add similar checks for other operating systems

# Malware scan code below
def scan_for_malware():
    try:
        if platform.system() == "Windows":
            # Run a command to scan for malware on Windows
            result = subprocess.run(['powershell', 'Start-MpScan'], capture_output=True, text=True, check=True)
            log_malware_scan_result(result.stdout)

        # Add conditions for other operating systems if needed

    except subprocess.CalledProcessError as e:
        logging.error(f"Error scanning for malware: {e.stderr}")

def log_malware_scan_result(scan_output):
    # Display the results of the malware scan
    if "No threats detected" in scan_output:
        logging.info("Malware Scan Result: No threats found.")
    else:
        logging.warning("Malware Scan Result: Potential threats detected.")
        logging.warning(f"Scan output:\n{scan_output}") 

#Function to check for software updates of the OS this is running on
def check_updates():
    try:
        system = platform.system()

        if system == "Darwin":  # macOS
            logging.info("Checking for macOS updates...")
            subprocess.run(["softwareupdate", "-l"])

        elif system == "Windows":
            logging.info("Checking for Windows updates...")
            subprocess.run(["choco", "upgrade", "all", "-y"])

        else:
            logging.warning("Update checks not supported on this operating system.")

    except Exception as e:
        logging.error(f"Error checking for updates: {str(e)}")                  

# Function to scan a single drive
def scan_drive(drive, problem_files, scanned_files):
    try:
        # Prepare the drive (e.g., list files and perform initial setup)
        for root, _, files in os.walk(drive):
            for file in files:
                file_path = os.path.join(root, file)
                # Handle file preparation tasks if needed
                if not file_path.endswith(tuple(file_extensions_to_scan)):
                    scan_file(file_path, problem_files, scanned_files)

        logging.info(f"Prepared drive: {drive}")



        # Perform the scan on the prepared drive
        scan_selected_drives([drive], problem_files, scanned_files)

    except Exception as e:
        logging.error(f"Error preparing and scanning drive {drive}: {str(e)}")

# Function to scan a single file for corruption (excluding ZIP archives)
def scan_file_for_corruption(file_path, problem_files):
    try:
        # Skip ZIP files
        if not file_path.lower().endswith('.zip'):
            with open(file_path, 'rb') as file:
                file_data = file.read()
                if b'corruption_pattern' in file_data:
                    problem_files.append(file_path)
                    logging.warning(f"Corruption detected in file: {file_path}")
                    logging.warning("This file is corrupted and needs to be repaired.")
    except IsADirectoryError:
        pass  # Skip directories
    except FileNotFoundError:
        pass  # Skip files not found
    except Exception as e:
        pass  # Handle any additional exceptions here

# Function to check CPU usage
def check_cpu_usage():
    cpu_usage = psutil.cpu_percent(interval=1)
    logging.info(f"CPU Usage: {cpu_usage}%")

# Function to check memory usage
def check_memory_usage():
    virtual_memory = psutil.virtual_memory()
    logging.info(f"Memory Usage: {virtual_memory.percent}%")

# Function to check CPU or GPU temperature based on the operating system
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

# Function to get RAM information
def get_ram_info():
    virtual_memory = psutil.virtual_memory()
    total_ram = virtual_memory.total / (1024 ** 3)  # Convert to GB
    logging.info(f"Total RAM: {total_ram:.2f} GB")

# Function to get GPU information based on the operating system
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

# Function to display hardware information
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

# Function to list available drives
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

# Function to display available drives
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

# Function to read a large file synchronously
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

# Function to read a large file asynchronously
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

# Function to memory-map a file
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

# Function to scan selected drives with specified file extensions
async def scan_selected_drives_wrapper(drives, extensions):
    await scan_selected_drives(drives, extensions)


# Function to scan a single file
async def scan_file(file_path, problem_files, scanned_files, file_extensions_to_scan):
    try:
        # Check file extension and skip if not in the list of allowed extensions
        if file_path.lower().endswith(tuple(file_extensions_to_scan)):
            read_large_file(file_path)  # Use the appropriate file reading function
        scanned_files.append(file_path)  # Add the scanned file to the list
    except IsADirectoryError:
        problem_files.append(f"Skipped directory: {file_path} (Not a file)")
    except FileNotFoundError:
        problem_files.append(f"File not found: {file_path}")
    except Exception as e:
        problem_files.append(f"Problem detected in file: {file_path} (Error: {str(e)}")
        logging.error(f"Problem detected in file: {file_path}")
        logging.error(f"Error: {str(e)}")
        # Handle any additional exceptions here

# Function to prepare and scan a single drive
async def prepare_and_scan_drive(drive, file_extensions_to_scan):
    try:
        problem_files = []  # Define the problem_files list
        scanned_files = []  # Define the scanned_files list

        # Prepare the drive (e.g., list files and perform initial setup)
        for root, dirs, files in os.walk(drive):
            for file in files:
                file_path = os.path.join(root, file)
                # ... Handle file preparation tasks if needed
                if not file_path.endswith(tuple(file_extensions_to_scan)):
                    await scan_file(file_path, problem_files, scanned_files)

        logging.info(f"Prepared drive: {drive}")

        # Perform the scan on the prepared drive
        await scan_selected_drives([drive], file_extensions_to_scan, problem_files, scanned_files)

    except Exception as e:
        logging.error(f"Error preparing and scanning drive {drive}: {str(e)}")

    # Log the scan results for all drives
    logging.info("Scanning completed for all selected drives.")

# Function to scan selected drives with specified file extensions
async def scan_selected_drives(drives_to_scan, file_extensions_to_scan, problem_files, scanned_files):
    for drive in drives_to_scan:
        if os.path.isdir(drive):
            for root, _, files in os.walk(drive):
                for file in files:
                    file_path = os.path.join(root, file)
                    if not any(file_path.lower().endswith(ext) for ext in file_extensions_to_scan):
                        continue  # Skip files with non-allowed extensions
                    await scan_file(file_path, problem_files, scanned_files, file_extensions_to_scan)
                    global_pbar.update(1)

# Function to get GPU temperature for NVIDIA GPUs on Linux
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

# the main loop
if __name__ == "__main__":
    # Display system recommendations at the beginning
    logging.info("=== System Recommendations ===")
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent

    recommendations = system_recommendations(cpu_usage, memory_percent)

     # Collect CPU usage and memory percent
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")  # current timestamp

    # Log historical data
    log_historical_data(cpu_usage, memory_percent, timestamp)

    if recommendations:
        for recommendation in recommendations:
            logging.info("- " + recommendation)
    else:
        logging.info("No specific recommendations at the moment.")

    while True:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Log historical data
        log_historical_data(cpu_usage, memory_percent, timestamp)

        logging.info(display_hardware_info())
        user_input = input("Choose an action (R: Refresh, S: Scan Files, D: Display Storage Info, B: Battery Check(Laptop), N: Perform Network Diagnostics, C: Windows Security Checks, U: Check for MacOS Updates, Q: Quit: ").lower()



        if user_input == 'r':
            continue  # Refresh
        elif user_input == 's':
            # Existing code for scanning files
            available_drives = display_available_drives()
            if available_drives:
                drive_choice = input("Select drives to scan (e.g., 1,2,3): ").split(',')
                drives_to_scan = [available_drives[int(choice) - 1][0] for choice in drive_choice if 1 <= int(choice) <= len(available_drives)]
                if drives_to_scan:
                    with tqdm(total=sum(len(os.listdir(drive)) for drive in drives_to_scan if os.path.isdir(drive))) as pbar:
                        problem_files = []  # Reset problem_files
                        scanned_files = []  # Reset scanned_files
                        asyncio.run(scan_selected_drives(drives_to_scan, file_extensions_to_scan, problem_files, scanned_files))
                        
                        # Check if any problems were detected and log accordingly
                        if not problem_files:
                            logging.info("No problems detected in files.")
                        else:
                            logging.info(f"Problems found in {len(problem_files)} files.")
                            for problem_file in problem_files:
                                logging.info(problem_file)
        elif user_input == 'd':
            # Display storage information
            logging.info(display_storage_info())
        elif user_input == 'n':
            # Perform network diagnostics
            perform_network_diagnostics()
        elif user_input == 'c':
            # Perform security checks
            perform_security_checks()
        elif user_input == 'u':
            # Perform Update check
            check_updates()
        elif user_input == 'b':
            # Perform battery check
            check_battery_health()    
        elif user_input == 'q':
            logging.info("Thank you for using PCtricorder!")
            break  # Quit
        else:
            logging.info("Invalid input. Please choose a valid action.")
        time.sleep(1)