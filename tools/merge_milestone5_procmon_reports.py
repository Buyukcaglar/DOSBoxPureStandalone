"""Merge runtime PID inventories for analyze_upstream_procmon.py.

Reject duplicate PIDs rather than silently dropping a captured process. Use
fresh captures/inventories if Windows reused a PID across separate runners.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    merged = {'processes': [], 'source_reports': []}
    pids = {}
    for report_path in args.report:
        report = json.loads(report_path.read_text(encoding='utf-8-sig'))
        merged['source_reports'].append(str(report_path.resolve()))
        prefix = report_path.parent.name
        for raw in report['processes']:
            process = dict(raw)
            for key in ['case', 'pid', 'command', 'temp_root', 'allowed_roots', 'allowed_files']:
                assert key in process, (str(report_path), 'missing ' + key)
            assert process['command'] and Path(process['command'][0]).is_absolute()
            pid = int(process['pid'])
            assert pid not in pids, ('duplicate PID cannot be safely classified', pid,
                pids.get(pid), str(report_path))
            pids[pid] = str(report_path)
            process['case'] = prefix + '/' + process['case']
            process['source_report'] = str(report_path.resolve())
            merged['processes'].append(process)
    args.output.write_text(json.dumps(merged, indent=2), encoding='utf-8')
    print(json.dumps({'processes': len(merged['processes']), 'reports': len(args.report),
        'output': str(args.output.resolve())}))


if __name__ == '__main__':
    main()
