"""Classify a Procmon CSV using only PIDs recorded by test_upstream_smoke.py."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path


def normalized(value):
    return value.replace('/', '\\').rstrip('\\').casefold()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = json.loads(args.report.read_text(encoding='utf-8'))
    processes = {str(value['pid']): value for value in reports['processes']}
    result = {'per_case': {}, 'successful_writes_outside_test_locations': [],
        'physical_game_member_paths': [], 'physical_archive_mutations': [], 'temporary_paths': []}
    result['pid_reuse_events_excluded'] = 0
    operations, writes, cases = Counter(), Counter(), Counter()
    members = {'disk.ima', 'image.ok', 'dosbox.bat', 'game.cfg', 'save.dat', 'readback.dat',
        'cfgback.dat', 'reload.ok', 'base.vhd', 'child.vhd', 'child.dbi', 'io.com', 'io.ok', 'result.txt'}
    process_csv = args.output.with_suffix('.process.csv')
    with args.csv.open(encoding='utf-8-sig', newline='') as source, process_csv.open('w', encoding='utf-8', newline='') as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            info = processes.get(row.get('PID', ''))
            if info is None:
                continue
            # Windows can reuse a short-lived runtime's PID during this capture.
            # Require the executable name as well as its recorded PID.
            expected_name = Path(info['command'][0]).name.casefold()
            if row.get('Process Name', '').casefold() != expected_name:
                result['pid_reuse_events_excluded'] += 1
                continue
            writer.writerow(row)
            case = info['case']
            cases[case] += 1
            operation, path, outcome, detail = (row.get(key, '') for key in ['Operation', 'Path', 'Result', 'Detail'])
            operations[operation] += 1
            path_key = normalized(path)
            basename = path_key.rsplit('\\', 1)[-1]
            item = {'case': case, 'pid': row['PID'], 'operation': operation, 'path': path, 'result': outcome, 'detail': detail}
            if basename in members:
                result['physical_game_member_paths'].append(item)
            temp = normalized(info['temp_root'])
            if path_key == temp or path_key.startswith(temp + '\\'):
                result['temporary_paths'].append(item)
            changed = outcome == 'SUCCESS' and (operation == 'WriteFile' or
                operation.startswith(('SetEndOfFile', 'SetAllocation', 'SetRename', 'SetDisposition')) or
                operation == 'CreateFile' and any(marker in detail for marker in
                    ['OpenResult: Created', 'OpenResult: Overwritten', 'OpenResult: Superseded']))
            if not changed:
                continue
            if operation == 'WriteFile':
                writes[path] += 1
            allowed = any(path_key == normalized(root) or path_key.startswith(normalized(root) + '\\') for root in info['allowed_roots'])
            allowed |= path_key in [normalized(value) for value in info['allowed_files']]
            if not allowed:
                result['successful_writes_outside_test_locations'].append(item)
            if basename.endswith(('.dosz', '.zip')) and not basename.endswith('.pure.zip'):
                result['physical_archive_mutations'].append(item)
    result['captured_runtime_events'] = sum(cases.values())
    result['per_case'] = {info['case']: {'pid': info['pid'], 'events': cases[info['case']]} for info in processes.values()}
    result['operations'] = dict(operations)
    result['successful_write_paths'] = dict(writes)
    result['capture_nonempty'] = result['captured_runtime_events'] > 0
    result['all_cases_captured'] = all(value['events'] > 0 for value in result['per_case'].values())
    result['review_required'] = bool(result['successful_writes_outside_test_locations'] or
        result['physical_game_member_paths'] or result['physical_archive_mutations'] or result['temporary_paths'])
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
