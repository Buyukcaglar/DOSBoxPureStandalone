"""Windows integration test for generated packages; never reads user OS images.

All inputs and persistence live in a newly created output directory. A tiny DOS
program exercises BIOS sectors and exits, so the test needs no UI automation.
"""
import argparse
import ctypes
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path
sys.dont_write_bytecode = True
from create_vhd_mount_fixture import parent, SIZE
from inspect_vhd_mount_save import read_sector


def io_program():
    code, labels, fixups = bytearray(), {}, []

    def emit(s):
        code.extend(bytes.fromhex(s))

    def address(label, adjustment=0):
        fixups.append((len(code), label, adjustment, False))
        code.extend(b'\0\0')

    def check():
        emit('73 03 e9')
        fixups.append((len(code), 'fail', 0, True))
        code.extend(b'\0\0')

    def disk(label, operation):
        emit('be')
        address(label)
        emit('ba 80 00 b8 00 ' + operation + ' cd 13')
        check()

    emit('0e 1f 0e 07 fc 8c c8 a3')
    address('counter', 6)
    emit('a3')
    address('zero', 6)
    disk('counter', '42')
    emit('fe 06 00 04 c7 06 02 04 44 49 c7 06 04 04 46 46')
    disk('counter', '43')
    emit('31 c0 bf 00 06 b9 00 01 f3 ab')
    disk('zero', '43')
    emit('c6 06 00 06 a5')
    disk('zero', '42')
    emit('80 3e 00 06 00 74 03 e9')
    fixups.append((len(code), 'fail', 0, True))
    code.extend(b'\0\0')
    emit('b8 00 4c cd 21')
    labels['fail'] = len(code)
    emit('b8 01 4c cd 21')
    for name, buffer, lba in [('counter', 0x400, 5000), ('zero', 0x600, 1)]:
        labels[name] = len(code)
        code.extend(struct.pack('<BBHHHQ', 16, 0, 1, buffer, 0, lba))
    for at, label, adjustment, relative in fixups:
        value = labels[label] - (at + 2) if relative else 0x100 + labels[label] + adjustment
        struct.pack_into('<H', code, at, value & 0xffff)
    assert len(code) < 0x300
    return code


def resource(path, replacement=None):
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    if replacement is not None:
        api.BeginUpdateResourceW.argtypes = [ctypes.c_wchar_p, ctypes.c_int]
        api.BeginUpdateResourceW.restype = ctypes.c_void_p
        api.UpdateResourceW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ushort, ctypes.c_void_p, ctypes.c_uint]
        api.EndUpdateResourceW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        handle = api.BeginUpdateResourceW(str(path), False)
        assert handle, ctypes.get_last_error()
        data = json.dumps(replacement).encode()
        buffer = ctypes.create_string_buffer(data)
        ok = api.UpdateResourceW(handle, 10, 102, 1033, buffer, len(data))
        assert api.EndUpdateResourceW(handle, not ok), ctypes.get_last_error()
        assert ok, ctypes.get_last_error()
        return
    api.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint]
    api.LoadLibraryExW.restype = ctypes.c_void_p
    api.FindResourceW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    api.FindResourceW.restype = ctypes.c_void_p
    api.SizeofResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    api.LoadResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    api.LoadResource.restype = ctypes.c_void_p
    api.LockResource.argtypes = [ctypes.c_void_p]
    api.LockResource.restype = ctypes.c_void_p
    api.FreeLibrary.argtypes = [ctypes.c_void_p]
    module = api.LoadLibraryExW(str(path), None, 0x22)
    assert module, ctypes.get_last_error()
    try:
        info = api.FindResourceW(module, 102, 10)
        assert info
        size = api.SizeofResource(module, info)
        data = api.LockResource(api.LoadResource(module, info))
        return json.loads(ctypes.string_at(data, size))
    finally:
        api.FreeLibrary(module)


def entries(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def save_entries(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as z:
        for name, data in values.items():
            z.writestr(name, data)


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    packager, template = str(args.packager.resolve()), str(args.template.resolve())
    base = parent(True)
    package_id = 'org.dbps.diff.identity.test'
    report = {'cases': {}, 'processes': []}

    def build(name, image=base, stamp=(2026, 9, 22, 0, 0, 0), disk_id='win98', parent_name='BASE.VHD', declared=True, template_path=template, expect_error=None):
        archive = output / (name + '.dosz')
        batch = ('@echo off\r\nimgmount 2 C:\\' + parent_name + ' -t hdd -fs none -diff C:\\CHILD.VHD>RESULT.TXT\r\n'
                 'IO.COM\r\nif errorlevel 1 goto end\r\necho IO_OK>IO.OK\r\n'
                 'echo FORBIDDEN>CHILD.DBI\r\n:end\r\nexit\r\n').encode()
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for path, data in [(parent_name, image), ('DOSBOX.BAT', batch), ('IO.COM', io_program())]:
                info = zipfile.ZipInfo(path, stamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        spec = dict(format_version=1, package_id=package_id, title='Synthetic VHD identity test',
                    template=template_path, archive=str(archive), output=str(output / (name + '.exe')))
        if declared:
            spec['differencing_vhd'] = dict(disk_id=disk_id, parent=parent_name.lower(), child='child.vhd')
        manifest = output / (name + '.json')
        manifest.write_text(json.dumps(spec))
        result = subprocess.run([packager, str(manifest)], capture_output=True, text=True, timeout=60)
        (output / (name + '.build.log')).write_text(result.stdout + result.stderr)
        if expect_error:
            assert result.returncode and expect_error in result.stderr, result.stdout + result.stderr
            assert not Path(spec['output']).exists()
            report['cases'][name] = {'rejected_at_build': True}
            return None
        assert result.returncode == 0, result.stdout + result.stderr
        return Path(spec['output'])

    def launch(exe, name, seed=None, root=None, expected=None, image=base):
        root = root or output / (name + '.localappdata')
        metadata = resource(exe)
        saved = root / 'DOSBoxPureStandalone' / metadata['package_id'] / 'embedded.pure.zip'
        if seed is not None:
            save_entries(saved, seed)
        env = dict(os.environ, LOCALAPPDATA=str(root))
        root.mkdir(parents=True, exist_ok=True)
        with (output / (name + '.stdout.log')).open('wb') as stdout, (output / (name + '.stderr.log')).open('wb') as stderr:
            process = subprocess.Popen([str(exe)], env=env, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
            report['processes'].append(dict(case=name, pid=process.pid))
            try:
                assert process.wait(timeout=30) == 0, name
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise AssertionError('Synthetic test did not exit: ' + name)
        got = entries(saved)
        message = got['RESULT.TXT'].decode('ascii').strip()
        if expected:
            assert expected in message, (name, message)
            for entry, contents in (seed or {}).items():
                if entry in ['CHILD.VHD', 'CHILD.DBI']:
                    assert got[entry] == contents, (name, entry, 'changed on rejection')
            if seed is not None and 'CHILD.VHD' not in seed:
                assert 'CHILD.VHD' not in got, (name, 'failed new child retained')
            report['cases'][name] = dict(rejected=True, existing_disk_bytes_preserved=True, message=message)
        else:
            assert 'Experimental differencing VHD mounted' in message, (name, message)
            assert got['IO.OK'].strip() == b'IO_OK'
            assert 'BASE.VHD' not in got
            child = got['CHILD.VHD']
            assert read_sector(child, 1, image) == (bytes(512), True)
            counter = read_sector(child, 5000, image)[0][0]
            binding = got.get('CHILD.DBI', b'')
            if metadata['format_version'] == 2:
                assert len(binding) == 512 and binding[:8] == b'DBPVDI01'
                assert binding[224:256] == hashlib.sha256(image).digest()
                assert binding[256:272] == image[-512 + 68:-512 + 84]
                assert binding[280:296] == child[68:84]
                assert struct.unpack_from('>Q', binding, 272)[0] == SIZE
            else:
                assert not binding
            report['cases'][name] = dict(counter=counter, child_bytes=len(child), binding_bytes=len(binding), zero_override=True)
        (output / 'report.json').write_text(json.dumps(report, indent=2))
        return got

    baseline_exe = build('baseline')
    metadata = resource(baseline_exe)
    assert metadata['format_version'] == 2
    assert metadata['differencing_vhd']['parent_sha256'] == hashlib.sha256(base).hexdigest()
    baseline = launch(baseline_exe, 'baseline')
    assert report['cases']['baseline']['counter'] >= 1
    repacked = build('repacked', stamp=(2027, 1, 2, 3, 4, 6))
    renamed = output / 'RenamedPackage.exe'
    shutil.copyfile(repacked, renamed)
    result = launch(renamed, 'repacked-renamed', root=output / 'baseline.localappdata')
    assert report['cases']['repacked-renamed']['counter'] > report['cases']['baseline']['counter']
    assert result['CHILD.DBI'] == baseline['CHILD.DBI']
    fixed = parent(False)
    launch(build('fixed', image=fixed), 'fixed', image=fixed)
    launch(build('ordinary', declared=False), 'ordinary')

    seed = {n: baseline[n] for n in ['CHILD.VHD', 'CHILD.DBI']}
    changed = bytearray(base)
    changed[3072] ^= 1  # Same UUID/size, different parent bytes.
    launch(build('changed-parent', image=changed), 'changed-parent', seed, expected='binding mismatch')
    launch(build('changed-disk-id', disk_id='another'), 'changed-disk-id', seed, expected='binding mismatch')
    launch(build('changed-path', parent_name='OTHER.VHD'), 'changed-path', seed, expected='binding mismatch')
    for field, value, message in [('package_id', 'org.dbps.diff.copied', 'binding mismatch'),
                                  ('parent_sha256', '1' * 64, 'SHA-256 does not match'),
                                  ('parent_uuid', '2' * 32, 'UUID or virtual size'),
                                  ('parent_virtual_size', str(SIZE + 512), 'UUID or virtual size')]:
        exe = output / ('changed-' + field + '.exe')
        shutil.copyfile(baseline_exe, exe)
        modified = json.loads(json.dumps(metadata))
        if field == 'package_id':
            modified[field] = value
        else:
            modified['differencing_vhd'][field] = value
        resource(exe, modified)
        launch(exe, 'changed-' + field, seed, expected=message)
    launch(output / 'changed-parent_sha256.exe', 'new-bad-fingerprint', {}, expected='SHA-256 does not match')
    launch(baseline_exe, 'missing-binding', {'CHILD.VHD': seed['CHILD.VHD']}, expected='explicit migration')
    launch(baseline_exe, 'orphan-binding', {'CHILD.DBI': seed['CHILD.DBI']}, expected='explicit migration')
    launch(baseline_exe, 'corrupt-binding', dict(seed, **{'CHILD.DBI': b'corrupt'}), expected='binding is corrupt')
    timestamp_binding = bytearray(seed['CHILD.DBI'])
    timestamp_binding[296] ^= 1
    launch(baseline_exe, 'corrupt-timestamp', dict(seed, **{'CHILD.DBI': timestamp_binding}), expected='parent identity mismatch')
    child = bytearray(seed['CHILD.VHD'])
    for start in [0, len(child) - 512]:
        child[start + 68] ^= 1
        child[start + 64:start + 68] = bytes(4)
        struct.pack_into('>I', child, start + 64, ~sum(child[start:start + 512]) & 0xffffffff)
    launch(baseline_exe, 'swapped-child', dict(seed, **{'CHILD.VHD': child}), expected='binding mismatch')
    launch(build('undeclared', declared=False), 'undeclared', seed, expected='explicit migration')
    if args.old_template:
        build('old-template', template_path=str(args.old_template.resolve()), expect_error='does not support differencing VHD identity')
    build('bad-parent', image=b'X' + base[1:], expect_error='footer copies or sparse header')
    build('bad-disk-id', disk_id='../bad', expect_error='disk_id must contain')
    (output / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--packager', type=Path, required=True)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--old-template', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args())
