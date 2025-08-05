#!/usr/bin/env python3.9
"""
Script to execute all .sql files in a directory using sqlplus on AIX as SYSDBA.

Requirements:
- Run on Python 3.9
- Server OS: AIX
- SQL files start with numeric prefixes and must run in ascending numeric order
- Always connect as SYSDBA using OS authentication
- Change number input must start with 'CHG' (uppercase) and be exactly 10 characters
- Directory: /tmp/changes/<CHANGE_NUMBER>
- Log saved in script directory and filename must include CHANGE_NUMBER and timestamp
- ORACLE_SID environment variable must be set to the target SID before execution
- Code and messages in English

Usage:
    python exec_sqls.py --sid ORCL --change CHG1234567 [--stop-on-error]
"""
import os
import re
import glob
import subprocess
import time
import argparse
import sys


def sorted_sql_files(directory):
    """
    Find all .sql files in 'directory' and return a list sorted by their leading numeric prefix.
    """
    sql_paths = glob.glob(os.path.join(directory, '*.sql'))
    def extract_prefix(path):
        name = os.path.basename(path)
        match = re.match(r"^(\d+)", name)
        return int(match.group(1)) if match else float('inf')
    return sorted(sql_paths, key=extract_prefix)


def run_sql_file(sql_file, log_dir, change, timestamp):
    """
    Execute a single SQL file via sqlplus as SYSDBA, ensure PL/SQL blocks run even without trailing slash,
    capture output and measure duration.
    """
    start_time = time.time()
    sql_input = f"@{sql_file}\n/\nexit\n"
    result = subprocess.run(
        ['sqlplus', '-s', '/ as sysdba'],
        input=sql_input,
        capture_output=True,
        text=True
    )
    elapsed = time.time() - start_time

    log_filename = f"{change}_{timestamp}_{os.path.basename(sql_file)}.log"
    log_path = os.path.join(log_dir, log_filename)
    os.makedirs(log_dir, exist_ok=True)
    with open(log_path, 'w') as log_file:
        log_file.write(result.stdout)
        log_file.write(result.stderr)

    print(f"{os.path.basename(sql_file)} executed in {elapsed:.2f}s (exit code {result.returncode})")
    if result.returncode != 0:
        print(f"Error executing {sql_file}. See log at {log_path}")
    return result.returncode


def validate_change(change_input):
    """
    Ensure change number starts with 'CHG' (uppercase) and is exactly 10 characters.
    """
    return re.fullmatch(r'CHG\w{7}', change_input) is not None



def main():
    parser = argparse.ArgumentParser(
        description='Execute .sql files in numeric order via sqlplus on AIX as SYSDBA'
    )
    parser.add_argument('--sid', required=True, help='Oracle SID (e.g. ORCL)')
    parser.add_argument('--change', required=True, help="Change number (starts with 'CHG', 10 chars, uppercase)")
    parser.add_argument('--stop-on-error', action='store_true', help='Stop execution upon first error without prompt')
    args = parser.parse_args()

    # Set ORACLE_SID environment
    sid = args.sid
    os.environ['ORACLE_SID'] = sid
    print(f"ORACLE_SID set to {sid}")

    change = args.change
    if not validate_change(change):
        print("Invalid change number. Must start with 'CHG' and be exactly 10 characters.")
        choice = input("Abort execution? [y/N]: ").strip().lower()
        if choice == 'y':
            print("Aborting.")
            sys.exit(1)
        else:
            print("Continuing with invalid change number.")

    sql_dir = os.path.join('/tmp/changes', change)
    if not os.path.isdir(sql_dir):
        print(f"Directory not found: {sql_dir}")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = time.strftime('%Y%m%d_%H%M%S')

    # Gather and sort SQL files
    sql_files = sorted_sql_files(sql_dir)
    if not sql_files:
        print(f"No .sql files found in {sql_dir}")
        sys.exit(1)

    # Preview files and confirm execution
    print("Found the following SQL files in numeric order:")
    for f in sql_files:
        print(f"  {os.path.basename(f)}")
    choice = input("Proceed with execution? [y/N]: ").strip().lower()
    if choice != 'y':
        print("Execution aborted by user.")
        sys.exit(0)

    # Execute each file
    for sql_file in sql_files:
        rc = run_sql_file(sql_file, script_dir, change, timestamp)
        if rc != 0:
            if args.stop_on_error:
                print("Aborting due to error.")
                sys.exit(rc)
            choice = input("Error encountered. Continue executing remaining scripts? [y/N]: ").strip().lower()
            if choice != 'y':
                print("Aborting as requested.")
                sys.exit(rc)
            else:
                print("Continuing despite error.")

    print("All SQL files executed.")

if __name__ == '__main__':
    main()
