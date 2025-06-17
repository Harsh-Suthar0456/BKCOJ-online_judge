import os
import time
import csv
import subprocess
import json

# could put these in a config file
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SUB_DIR = os.path.join(BASE_DIR, 'submissions')
CSV_FILE = os.path.join(BASE_DIR, 'submissions.csv')
PROB_DIR = os.path.join(BASE_DIR, 'problems')


def load_submissions():
    with open(CSV_FILE, newline='') as f:
        return list(csv.DictReader(f))


def save_submissions(rows):
    tmp = CSV_FILE + '.tmp'
    with open(tmp, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id','problem','status','timestamp'])
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, CSV_FILE)

while True:
    rows = load_submissions()
    for row in rows:
        if row['status'] != 'pending':
            continue
        sub_id = row['id']

        # 'running' in CSV
        row['status'] = 'running'
        save_submissions(rows)

        sub_path = os.path.join(SUB_DIR, sub_id)
        pid = row['problem']
        tests_dir = os.path.join(PROB_DIR, pid, 'tests')

        # config for the problem
        config_file = os.path.join(PROB_DIR, pid, 'config.json')
        if not os.path.exists(config_file):
            TIME_LIMIT = 2
            MEMORY_LIMIT = 256
        else:
            with open(config_file) as f:
                config = json.load(f)
            TIME_LIMIT = config.get('TIME_LIMIT', 2)
            MEMORY_LIMIT = config.get('MEMORY_LIMIT', 256)

        # get total testcases beforehand, else issues with compiling etc.
        if not os.path.exists(tests_dir):
            total = 0
        else:
            total = len([f for f in os.listdir(tests_dir) if f.startswith('input') and f.endswith('.txt')])
        

        passed = 0

        # compile
        comp = subprocess.run([
            'docker','run','--rm','--network','none',
            '-v',f"{sub_path}:/usr/src:rw",
            'code-runner:latest',
            'bash','-c','g++ /usr/src/main.cpp -O2 -o /usr/src/main'
        ], capture_output=True, text=True)
        if comp.returncode != 0:
            result = f"Compile Error:{comp.stderr or comp.stdout}"
        else:
            # execute each test with {TIME_LIMIT}s timeout and {MEMORY_LIMIT}MB memory limit
            # passed = 0
            result = f"Running tests for {pid}:\n"

            for fn in sorted(os.listdir(tests_dir)):
                if not fn.startswith('input') or not fn.endswith('.txt'):
                    continue
                idx = fn[len('input'):-4]
                # total += 1
                proc = subprocess.run([
                    'docker','run','--rm','--network','none',
                    '-m',f'{MEMORY_LIMIT}m','--cpus','0.5',
                    '-v',f"{sub_path}:/usr/src:rw",
                    '-v',f"{tests_dir}:/tests:ro",
                    'code-runner:latest',
                    'bash','-c',f"timeout {TIME_LIMIT}s /usr/src/main < /tests/input{idx}.txt > /usr/src/actual{idx}.txt"
                ], capture_output=True, text=True)

                # check timeout or memory limit separately
                if proc.returncode == 124:
                    result += f"Test {idx} timed out after {TIME_LIMIT}s.\n"
                    continue
                elif proc.returncode == 137:
                    result += f"Test {idx} exceeded memory limit of {MEMORY_LIMIT}MB.\n"
                    continue
                elif proc.returncode != 0:
                    result += f"Unexpected error on Test {idx}, other than timeout and memory limit exceeded\n"
                
                ####### can replace below code with any general checking script

                # token checker
                exp = open(os.path.join(tests_dir,f'output{idx}.txt')).read().split()
                act = open(os.path.join(sub_path,f'actual{idx}.txt')).read().split()
                if act == exp:
                    passed += 1
                    result += f"Test {idx} passed.\n"
                else:
                    result += f"Wrong answer on Test{idx}\n"
                
                #######

            result += f"Passed {passed}/{total} tests."

        # write result and mark 'completed'
        open(os.path.join(sub_path,'result.txt'),'w').write(result)

        if(passed == total):
            row['status'] = 'accepted'
        else:
            row['status'] = 'failed'
        save_submissions(rows)

        # remove the binary file
        binary_path = os.path.join(sub_path, 'main')
        if os.path.exists(binary_path):
            os.remove(binary_path)

        # could also remove the code outputs, but maybe keep for when debugging on hidden testcases
        # is allowed. will think later
        
    time.sleep(5)