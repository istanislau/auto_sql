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
- Single consolidated log saved in script directory, filename includes CHANGE_NUMBER and timestamp
- Log contains start/end times for each .sql and total execution time of this script
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
from datetime import datetime


def sorted_sql_files(directory):
    sql_paths = glob.glob(os.path.join(directory, '*.sql'))
    def extract_prefix(path):
        name = os.path.basename(path)
        match = re.match(r"^(\d+)", name)
        return int(match.group(1)) if match else float('inf')
    return sorted(sql_paths, key=extract_prefix)


def execute_sql(sql_file):
    # Build input for sqlplus
    has_slash = False
    try:
        with open(sql_file) as f:
            has_slash = any(line.strip() == '/' for line in f)
    except Exception:
        pass
    input_lines = [f"@{sql_file}"]
    if not has_slash:
        input_lines.append('/')
    input_lines.append('exit')
    return subprocess.run(
        ['sqlplus', '-s', '/ as sysdba'],
        input='\n'.join(input_lines) + '\n',
        capture_output=True,
        text=True
    )


def validate_change(change_input):
    return re.fullmatch(r'CHG\w{7}', change_input) is not None


def main():
    parser = argparse.ArgumentParser(description='Execute .sql files in numeric order via sqlplus on AIX as SYSDBA')
    parser.add_argument('--sid', required=True, help='Oracle SID (e.g. ORCL)')
    parser.add_argument('--change', required=True, help="Change number (starts with 'CHG', 10 chars, uppercase)")
    parser.add_argument('--stop-on-error', action='store_true', help='Stop execution upon first error without prompt')
    args = parser.parse_args()

    # Set ORACLE_SID
    os.environ['ORACLE_SID'] = args.sid
    print(f"ORACLE_SID set to {args.sid}")

    # Validate change
    change = args.change
    if not validate_change(change):
        print("Invalid change number. Must start with 'CHG' and be exactly 10 characters.")
        if input("Abort execution? [y/N]: ").strip().lower() == 'y':
            sys.exit(1)
        print("Continuing with invalid change number.")

    # Directories and files
    sql_dir = os.path.join('/tmp/changes', change)
    if not os.path.isdir(sql_dir):
        print(f"Directory not found: {sql_dir}")
        sys.exit(1)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Prepare log
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(script_dir, f"{change}_{timestamp}_run.log")
    with open(log_path, 'w') as log:
        log.write(f"Script start: {datetime.now().isoformat()}\n")

        # Gather files
        sql_files = sorted_sql_files(sql_dir)
        if not sql_files:
            log.write(f"No .sql files found in {sql_dir}\n")
            sys.exit(1)
        log.write("Files to execute in order:\n")
        for f in sql_files:
            log.write(f"  {os.path.basename(f)}\n")

        # Confirm execution
        print("Found the following SQL files:")
        for f in sql_files:
            print(f"  {os.path.basename(f)}")
        if input("Proceed with execution? [y/N]: ").strip().lower() != 'y':
            log.write("Execution aborted by user.\n")
            sys.exit(0)

        overall_start = time.time()
        for sql_file in sql_files:
            file_start = datetime.now()
            log.write(f"\n=== Executing {os.path.basename(sql_file)} at {file_start.isoformat()} ===\n")
            result = execute_sql(sql_file)
            file_end = datetime.now()
            duration = (file_end - file_start).total_seconds()
            log.write(result.stdout + result.stderr)
            log.write(f"Exit code: {result.returncode}\n")
            log.write(f"Completed at {file_end.isoformat()}, duration {duration:.2f}s\n")

            print(f"{os.path.basename(sql_file)} executed in {duration:.2f}s (exit code {result.returncode})")
            if result.returncode != 0:
                if args.stop_on_error:
                    log.write("Stopping due to error.\n")
                    sys.exit(result.returncode)
                if input("Error encountered. Continue? [y/N]: ").strip().lower() != 'y':
                    log.write("Execution aborted by user after error.\n")
                    sys.exit(result.returncode)

        overall_end = time.time()
        total_duration = overall_end - overall_start
        log.write(f"\nScript end: {datetime.now().isoformat()}\n")
        log.write(f"Total duration: {total_duration:.2f}s\n")

    print(f"All SQL files executed. Consolidated log at {log_path}")

if __name__ == '__main__':
    main()
