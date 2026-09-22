"""Validate synthetic rejection/unmount cases and preservation of saved bytes."""
import argparse
import json
import struct
import zipfile
from pathlib import Path


def inspect(inputs, saves, package_prefix, package_suffix):
    expected = {
        'legacy': 'requires migration',
        'corrupt-child': 'VHD file size is not sector aligned',
        'empty-child': 'VHD file size is not sector aligned',
        'mismatch': 'parent identity mismatch',
        'corrupt-parent': 'VHD footer copies differ',
        'missing-parent': 'Cannot open immutable VHD parent',
        'collision': 'Child name conflicts',
    }
    results = {}
    for name, message in expected.items():
        saved_path = saves / (package_prefix + name + package_suffix) / 'embedded.pure.zip'
        with zipfile.ZipFile(saved_path) as saved:
            result = saved.read('RESULT.TXT').decode('ascii').strip()
            assert message in result, (name, result)
            seed_path = inputs / (name + '.seed.pure.zip')
            if seed_path.exists():
                with zipfile.ZipFile(seed_path) as seed:
                    for entry in seed.namelist():
                        assert saved.read(entry) == seed.read(entry), (name, entry, 'saved bytes changed')
            else:
                assert 'CHILD.VHD' not in saved.namelist(), (name, 'failed mount left a child')
            results[name] = {'rejected': True, 'seed_bytes_preserved': True, 'message': result}
    with zipfile.ZipFile(saves / (package_prefix + 'unmount' + package_suffix) / 'embedded.pure.zip') as saved:
        assert saved.read('DONE.TXT').strip() == b'UNMOUNT_OK'
        assert b'Experimental differencing VHD mounted' in saved.read('RESULT.TXT')
        assert b'Experimental differencing VHD mounted' in saved.read('REOPEN.TXT')
        assert 'BASE.VHD' not in saved.namelist()
        child = saved.read('CHILD.VHD')
        assert len(child) == 3072 and struct.unpack_from('>I', child, 60)[0] == 4
        assert child[:512] == child[-512:]
        assert 'FORBIDDEN'.encode() not in child
        results['unmount'] = {'reopen_passed': True, 'parent_and_child_write_protected': True, 'child_bytes': len(child)}
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', type=Path)
    parser.add_argument('saves', type=Path)
    parser.add_argument('--package-prefix', default='org.dbps.diff.test.')
    parser.add_argument('--package-suffix', default='.20260922')
    args = parser.parse_args()
    print(json.dumps(inspect(args.inputs, args.saves, args.package_prefix, args.package_suffix), indent=2))
