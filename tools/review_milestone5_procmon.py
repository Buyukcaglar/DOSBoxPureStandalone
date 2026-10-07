"""Attribute completed Procmon exports to exact recorded executable lifetimes.

Supply one or more inventories with processes recorded by the runtime runners.
Each process requires one absolute-image Process Start, one Process Exit, and
nonempty CreateFile/file-operation coverage. Selected CSVs add Original Process
Name and Attributed Image while remaining compatible with analyze_upstream_procmon.
Cached names require a matching executable Load Image before coverage is accepted.
Multiple completed CSV inputs must be provided in chronological order.
"""
import argparse
from collections import defaultdict
import csv
import json
import ntpath
from pathlib import Path
import re


def normalize(path):
    path = path.strip().replace('/', '\\')
    if path.startswith('\\\\?\\'):
        path = path[4:]
    return ntpath.normcase(ntpath.normpath(path))


def image_from_start(row):
    match = re.search(r'(?:^|,\s*)Command line:\s*(.*?)(?=,\s*(?:Current directory|Environment|Parent PID):|$)',
        row.get('Detail', ''), re.IGNORECASE | re.DOTALL)
    command_image = ''
    if match:
        command = match.group(1).strip()
        if command.startswith('"'):
            stop = command.find('"', 1)
            if stop > 1:
                command_image = command[1:stop]
        else:
            image_match = re.match(r'^(.*?\.exe)(?=\s|$)', command, re.IGNORECASE)
            if image_match:
                command_image = image_match.group(1)
    path_image = row.get('Path', '').strip()
    if not path_image.lower().endswith('.exe') or not ntpath.isabs(path_image):
        path_image = ''
    if command_image and not ntpath.isabs(command_image):
        command_image = ''
    if command_image and path_image and normalize(command_image) != normalize(path_image):
        return '', 'different absolute command and Path images'
    image = command_image or path_image
    return (normalize(image), '') if image else ('', 'no absolute command/image path')


def review(csv_paths, report_paths, output_dir):
    if isinstance(csv_paths, Path):
        csv_paths = [csv_paths]
    output_dir.mkdir(parents=True, exist_ok=True)
    expected, by_pid, datasets = {}, defaultdict(list), []
    for index, report_path in enumerate(report_paths):
        report = json.loads(report_path.read_text(encoding='utf-8-sig'))
        label = report_path.parent.name
        if any(value['label'] == label for value in datasets):
            raise ValueError('Duplicate inventory labels: ' + label)
        dataset = {'label': label, 'report': str(report_path.resolve()),
            'csv': str((output_dir / (label + '.selected.csv')).resolve()), 'keys': []}
        datasets.append(dataset)
        seen_pids = set()
        for process in report['processes']:
            pid = str(process['pid'])
            if pid in seen_pids:
                raise ValueError('Legacy analyzer cannot represent repeated PID within inventory: ' + label + '/' + pid)
            seen_pids.add(pid)
            image = normalize(process['command'][0])
            if not ntpath.isabs(image):
                raise ValueError('Expected executable must be absolute')
            key = label + '/' + process['case']
            if key in expected or any(expected[item]['image'] == image for item in by_pid[pid]):
                raise ValueError('Ambiguous inventory PID/image/case mapping: ' + key)
            expected[key] = {'key': key, 'dataset': index, 'pid': pid, 'case': process['case'],
                'image': image, 'name': ntpath.basename(image), 'starts': 0, 'exits': 0,
                'events': 0, 'file_operations': 0, 'create_file': 0, 'start_time': None,
                'exit_time': None, 'start_csv_row': None, 'exit_csv_row': None,
                'load_image_confirmations': 0, 'name_mismatch_events': 0, 'raw_process_names': {}}
            dataset['keys'].append(key)
            by_pid[pid].append(key)
    summary = {'source_csvs': [str(path.resolve()) for path in csv_paths], 'datasets': datasets,
        'input_exports': [],
        'total_csv_rows': 0, 'selected_events': 0, 'excluded_events': 0,
        'process_name_cache_corrected_events': 0,
        'excluded_examples': [], 'attribution_errors': []}
    active = {}
    outputs = []
    csv.field_size_limit(32 * 1024 * 1024)
    try:
        writers = []
        original_fields = None
        for csv_path in csv_paths:
            export = {'path': str(csv_path.resolve()), 'bytes': csv_path.stat().st_size,
                'rows': 0, 'first_time': None, 'last_time': None}
            summary['input_exports'].append(export)
            with csv_path.open(encoding='utf-8-sig', newline='') as source:
                reader = csv.DictReader(source)
                required = {'Process Name', 'PID', 'Operation', 'Path', 'Result', 'Detail'}
                if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                    raise ValueError('Unsupported Procmon CSV header: ' + repr(reader.fieldnames))
                if original_fields is None:
                    original_fields = reader.fieldnames
                    for dataset in datasets:
                        handle = Path(dataset['csv']).open('w', encoding='utf-8', newline='')
                        outputs.append(handle)
                        writer = csv.DictWriter(handle, fieldnames=original_fields + ['Original Process Name', 'Attributed Image'])
                        writer.writeheader()
                        writers.append(writer)
                elif reader.fieldnames != original_fields:
                    raise ValueError('CSV schemas differ across completed input files')
                for source_row, row in enumerate(reader, 2):
                    export['rows'] += 1
                    export['last_time'] = row.get('Time of Day', '')
                    if export['first_time'] is None:
                        export['first_time'] = export['last_time']
                    summary['total_csv_rows'] += 1
                    number = summary['total_csv_rows'] + 1
                    pid = row.get('PID', '')
                    if pid not in by_pid:
                        continue
                    name = row.get('Process Name', '').casefold()
                    operation = row.get('Operation', '')
                    if operation == 'Process Start':
                        previous = active.get(pid)
                        if previous and previous['key'] is not None:
                            summary['attribution_errors'].append({'pid': pid, 'row': number,
                                'error': 'new start before matching exit', 'case': previous['key']})
                        image, error = image_from_start(row)
                        # Procmon may retain a prior process's cached name for a reused
                        # PID. The absolute launch image establishes its new lifetime;
                        # a main-executable Load Image event must corroborate any
                        # mismatched name before coverage can be accepted.
                        matches = [key for key in by_pid[pid] if image == expected[key]['image']]
                        if len(matches) > 1:
                            summary['attribution_errors'].append({'pid': pid, 'row': number, 'error': 'ambiguous Process Start'})
                        key = matches[0] if len(matches) == 1 else None
                        active[pid] = {'key': key, 'image': image, 'name': name, 'error': error}
                        if key:
                            item = expected[key]
                            item['starts'] += 1
                            item['start_time'] = row.get('Time of Day', '')
                            item['start_csv_row'] = number
                    context = active.get(pid)
                    key = context['key'] if context else None
                    if key is not None:
                        item = expected[key]
                        item['raw_process_names'][name] = item['raw_process_names'].get(name, 0) + 1
                        if name != item['name']:
                            item['name_mismatch_events'] += 1
                            summary['process_name_cache_corrected_events'] += 1
                        if operation == 'Load Image' and normalize(row.get('Path', '')) == item['image'] and row.get('Result') == 'SUCCESS':
                            item['load_image_confirmations'] += 1
                        selected_row = dict(row, **{'Original Process Name': row.get('Process Name', ''),
                            'Process Name': ntpath.basename(item['image']), 'Attributed Image': item['image']})
                        writers[item['dataset']].writerow(selected_row)
                        summary['selected_events'] += 1
                        item['events'] += 1
                        if 'File' in operation or operation in {'QueryDirectory', 'QueryOpen', 'DeviceIoControl'}:
                            item['file_operations'] += 1
                        if operation == 'CreateFile':
                            item['create_file'] += 1
                        if operation == 'Process Exit':
                            item['exits'] += 1
                            item['exit_time'] = row.get('Time of Day', '')
                            item['exit_csv_row'] = number
                    else:
                        summary['excluded_events'] += 1
                        if len(summary['excluded_examples']) < 100:
                            summary['excluded_examples'].append({'pid': pid, 'name': name, 'operation': operation,
                                'path': row.get('Path', ''), 'row': number, 'source_csv': str(csv_path), 'source_row': source_row,
                                'active_image': context['image'] if context else None,
                                'reason': context['error'] if context and context['error'] else 'outside expected exact-image lifespan'})
                    if operation == 'Process Exit':
                        active.pop(pid, None)
    finally:
        for handle in outputs:
            handle.close()
    summary['per_case'] = expected
    summary['coverage_errors'] = []
    for item in expected.values():
        if (item['starts'] != 1 or item['exits'] != 1 or not item['create_file'] or not item['file_operations'] or
                item['name_mismatch_events'] and not item['load_image_confirmations']):
            summary['coverage_errors'].append({'case': item['key'], 'starts': item['starts'],
                'exits': item['exits'], 'create_file': item['create_file'], 'file_operations': item['file_operations'],
                'name_mismatch_events': item['name_mismatch_events'], 'load_image_confirmations': item['load_image_confirmations']})
    summary['complete'] = not summary['coverage_errors'] and not summary['attribution_errors']
    (output_dir / 'attribution.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


def self_test(output_dir):
    fields = ['Time of Day', 'Process Name', 'PID', 'Operation', 'Path', 'Result', 'Detail']
    executable = r'C:\owned\Game.exe'
    def event(operation, path='', name='Game.exe', command=None):
        return {'Time of Day': '22:00:00.0000000', 'Process Name': name, 'PID': '111',
            'Operation': operation, 'Path': path, 'Result': 'SUCCESS',
            'Detail': 'Parent PID: 123, Command line: "' + command + '", Current directory: C:\\owned\\, Environment: hidden' if command else ''}
    valid = [event('Process Start', command=executable), event('Load Image', executable), event('CreateFile', r'C:\owned\save.pure.zip'),
        event('WriteFile', r'C:\owned\save.pure.zip'), event('Process Exit')]
    cached = [dict(row, **{'Process Name': 'git.exe'}) for row in valid]
    scenarios = {
        'earlier-same-name-other-image': ([event('Process Start', command=r'C:\earlier\Game.exe'),
            event('WriteFile', r'C:\earlier\unexpected.zip'), event('Process Exit')] + valid, True),
        'different-name-reuse': ([event('Process Start', name='Other.exe', command=r'C:\elsewhere\Other.exe'),
            event('CreateFile', r'C:\elsewhere\unexpected.zip', name='Other.exe'), event('Process Exit', name='Other.exe')] + valid, True),
        'missing-start': (valid[1:], False),
        'missing-exit': (valid[:-1], False),
        'out-of-lifespan': ([event('WriteFile', r'C:\before\unexpected.zip')] + valid +
            [event('WriteFile', r'C:\after\unexpected.zip')], True),
        'ambiguous-repeat-same-image': (valid + valid, False),
        'cached-name-exact-image-confirmed': (cached, True),
        'cached-name-without-load-image': ([row for row in cached if row['Operation'] != 'Load Image'], False),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    outcomes = {}
    for name, (rows, expected_complete) in scenarios.items():
        root = output_dir / name
        root.mkdir()
        report = root / 'report.json'
        report.write_text(json.dumps({'processes': [{'case': 'owned', 'pid': 111, 'command': [executable]}]}))
        source = root / 'input.csv'
        with source.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        result = review(source, [report], root / 'selected')
        assert result['complete'] == expected_complete, name
        if expected_complete:
            with Path(result['datasets'][0]['csv']).open(newline='', encoding='utf-8') as handle:
                selected = list(csv.DictReader(handle))
            assert len(selected) == 5 and all('unexpected' not in row['Path'] for row in selected), name
            if name == 'cached-name-exact-image-confirmed':
                assert all(row['Original Process Name'] == 'git.exe' and row['Process Name'] == 'game.exe' for row in selected)
        outcomes[name] = {'expected_complete': expected_complete, 'observed_complete': result['complete'],
            'selected': result['selected_events'], 'excluded': result['excluded_events']}
    (output_dir / 'self-test.json').write_text(json.dumps(outcomes, indent=2))
    print(json.dumps({'self_test': 'PASS', 'scenarios': len(outcomes), 'output': str(output_dir.resolve())}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, action='append')
    parser.add_argument('--report', type=Path, action='append')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test(args.output_dir)
        return
    if not args.csv or not args.report:
        parser.error('--csv and at least one --report are required')
    result = review(args.csv, args.report, args.output_dir)
    print(json.dumps({'complete': result['complete'], 'selected_events': result['selected_events'],
        'total_rows': result['total_csv_rows'], 'coverage_errors': len(result['coverage_errors']),
        'attribution_errors': len(result['attribution_errors']), 'output': str(args.output_dir.resolve())}))
    if not result['complete']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
