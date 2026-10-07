"""Production-runtime differencing VHD persistence tests using synthetic disks.

Every executable, archive, save and environment directory belongs to a fresh
output tree. No existing installation, OS image or user save is read. Process
records match analyze_upstream_procmon.py's input schema. Fault/barrier hooks
are opt-in production-path seams, not a substitute filesystem implementation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib

sys.dont_write_bytecode = True
from create_vhd_mount_fixture import parent
from inspect_vhd_mount_save import read_sector
from test_vhd_identity_runtime import io_program


def continuous_program(ticks=0, flush=False):
    """DOS COM writes a monotonically increasing dword at BIOS-tick intervals.

    ticks=0 keeps the mounted child's handles open until the host terminates it.
    Optional ATA FLUSH CACHE uses the guest IDE command path after every write.
    """
    code, labels, fixups = bytearray(), {}, []

    def emit(hexadecimal):
        code.extend(bytes.fromhex(hexadecimal))

    def address(label, adjustment=0):
        fixups.append((len(code), label, adjustment, False))
        code.extend(bytes(2))

    def jump(label):
        emit('e9')
        fixups.append((len(code), label, 0, True))
        code.extend(bytes(2))

    def disk(operation):
        emit('be')
        address('dap')
        emit('ba 80 00 b8 00 ' + operation + ' cd 13 73 03')
        jump('fail')

    emit('0e 1f 0e 07 fc 8c c8 a3')
    address('dap', 6)
    disk('42')
    emit('c7 06 04 04 4d 35 c7 06 06 04 49 4f 31 c0 cd 1a 89 16')
    address('last_tick')
    labels['loop'] = len(code)
    emit('31 c0 cd 1a 3b 16')
    address('last_tick')
    emit('75 03')
    jump('loop')
    emit('89 16')
    address('last_tick')
    emit('66 ff 06 00 04')
    disk('43')
    if flush:
        emit('ba f7 01 b0 e7 ee')
    if ticks:
        emit('ff 06')
        address('elapsed')
        emit('81 3e')
        address('elapsed')
        code.extend(struct.pack('<H', ticks))
        emit('73 03')
        jump('loop')
        emit('b8 00 4c cd 21')
    else:
        jump('loop')
    labels['fail'] = len(code)
    emit('b8 01 4c cd 21')
    labels['dap'] = len(code)
    code.extend(struct.pack('<BBHHHQ', 16, 0, 1, 0x400, 0, 5000))
    labels['last_tick'] = len(code)
    code.extend(bytes(2))
    labels['elapsed'] = len(code)
    code.extend(bytes(2))
    for at, label, adjustment, relative in fixups:
        value = labels[label] - at - 2 if relative else 0x100 + labels[label] + adjustment
        struct.pack_into('<H', code, at, value & 0xffff)
    assert len(code) < 0x300
    return bytes(code)


def startup_delay(code, origin=0x100, prefix=bytes.fromhex('0e 1f 0e'), ticks=3):
    """Yield initial frames before a fast synthetic program can finish.

    The existing tiny startup can execute twice during initial frontend setup.
    Append a BIOS-tick wait stub without moving original code/data addresses.
    """
    code = bytearray(code)
    at = len(code)
    stub = bytearray(prefix) + bytes.fromhex('31 c0 cd 1a 89 d3')
    loop = len(stub)
    stub.extend(bytes.fromhex('31 c0 cd 1a 29 da 81 fa') + struct.pack('<H', ticks) + bytes.fromhex('72'))
    stub.append((loop - len(stub) - 1) & 255)
    stub.extend(b'\xe9' + struct.pack('<H', (len(prefix) - (at + len(stub) + 3)) & 0xffff))
    code[:3] = b'\xe9' + struct.pack('<H', at - 3)
    code.extend(stub)
    return bytes(code)


def delayed_parent(image):
    image = bytearray(image)
    start = 2560
    boot = image[start:start + 512]
    last_dap = boot.find(struct.pack('<BBHHHQ', 16, 0, 1, 0x800, 0, 1))
    assert last_dap >= 0
    end = last_dap + 16
    prefix = bytes.fromhex('fa 31 c0 8e d8 8e c0 8e d0 bc 00 7c fb fc')
    code = startup_delay(boot[:end], origin=0x7c00, prefix=prefix)
    assert len(code) < 446
    image[start:start + len(code)] = code
    return bytes(image)


def saved_entries(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, 'CRC-invalid committed save: ' + str(path)
        return {name: archive.read(name) for name in archive.namelist()}


def lifecycle_parent(mode):
    """Change only synthetic boot code; retain valid dynamic VHD structures."""
    image = bytearray(parent(True))
    start = 2560  # first allocated data sector in our generated dynamic parent
    boot = image[start:start + 512]
    poweroff = boot.find(bytes.fromhex('31 db b8 01 53 cd 15'))
    assert poweroff >= 0
    if mode == 'guest-flush':
        # This build does not enable ATA hard-disk devices. Exercise its actual
        # guest BIOS hard-disk reset/flush boundary, then keep the disk open.
        replacement = bytes.fromhex('b8 00 0d ba 80 00 cd 13 fb f4 eb fd')
        boot[poweroff:poweroff + len(replacement)] = replacement
    elif mode == 'reboot':
        # On the first boot, write the counter then enter the BIOS reset vector.
        # The reopened child increments it again and takes the normal APM path.
        scratch = boot.find(bytes.fromhex('31 c0 bf 00 08 b9 00 01 f3 ab'))
        assert 0 <= scratch < poweroff - 12
        replacement = bytes.fromhex('80 3e 00 06 02 73') + bytes([poweroff - scratch - 7]) + bytes.fromhex('ea f0 ff 00 f0')
        boot[scratch:poweroff] = replacement.ljust(poweroff - scratch, b'\x90')
    else:
        raise ValueError(mode)
    image[start:start + 512] = boot
    # Infinite HLT retains the first boot and its open child. It needs no
    # startup delay, and completes its guest flush before the frontend's 250ms
    # state/pause trigger. Finite APM/reset fixtures still yield initial frames.
    return bytes(image) if mode == 'guest-flush' else delayed_parent(image)


def inspect_save(path, base, continuous=False):
    values = saved_entries(path)
    assert 'BASE.VHD' not in values, 'immutable parent copied to writable save'
    child, binding = values['CHILD.VHD'], values['CHILD.DBI']
    assert child[:512] == child[-512:]
    assert struct.unpack_from('>I', child, 60)[0] == 4
    assert len(binding) == 512 and binding[:8] == b'DBPVDI01'
    assert binding[224:256] == hashlib.sha256(base).digest()
    assert binding[280:296] == child[68:84]
    data, present = read_sector(child, 5000, base)
    counter = struct.unpack_from('<I', data)[0] if continuous else data[0]
    return {'counter': counter, 'sector_present': bool(present),
            'sector_prefix': data[:16].hex(), 'child_bytes': len(child),
            'binding_sha256': hashlib.sha256(binding).hexdigest(),
            'save_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, values


class Runner:
    package_id = 'org.dbps.milestone5.synthetic'

    def __init__(self, args):
        self.args = args
        self.output = args.output.resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        # Freeze build inputs once so a concurrent native rebuild cannot mix
        # runtime generations between synthetic packages in one report.
        template_bytes, packager_bytes = args.template.read_bytes(), args.packager.read_bytes()
        self.template, self.packager = self.output / 'runtime-template.exe', self.output / 'makegame.exe'
        self.template.write_bytes(template_bytes)
        self.packager.write_bytes(packager_bytes)
        self.base = delayed_parent(parent(True))
        self.report = {'cases': {}, 'processes': [], 'scope': 'synthetic persistence and state runtime; no Windows 98 acceptance',
            'runtime_template': str(args.template.resolve()),
            'frozen_runtime_template': str(self.template), 'frozen_packager': str(self.packager),
            'runtime_sha256': hashlib.sha256(template_bytes).hexdigest(),
            'packager_sha256': hashlib.sha256(packager_bytes).hexdigest()}
        self.owned = []
        self.defaults = self.output / 'defaults.json'
        self.defaults.write_text(json.dumps({'screen_width': '320', 'screen_height': '240',
            'dosbox_pure_cycles': '3000', 'dosbox_pure_menu_time': '0'}), encoding='utf-8')

    def record(self):
        (self.output / 'report.json').write_text(json.dumps(self.report, indent=2), encoding='utf-8')

    def package(self, name, mode='once', package_id=None, stamp=(2026, 10, 7, 0, 0, 0), image=None,
                file_action=None):
        mount = 'imgmount 2 C:\\BASE.VHD -t hdd -fs none -diff C:\\CHILD.VHD>RESULT.TXT\r\n'
        batch = '@echo off\r\n'
        if file_action == 'delete':
            batch += 'del A\r\n'
        elif file_action == 'rename':
            batch += 'ren A B\r\n'
        if mode == 'premount-continuous':
            batch += 'echo PREMOUNT_DIRTY>PREMOUNT.TXT\r\n'
        batch += mount
        if mode == 'read':
            program = b''
        elif mode in ['poweroff', 'guest-flush', 'reboot']:
            batch += 'boot -l c\r\n'
            program = b''
        else:
            program = startup_delay(io_program()) if mode in ['once', 'unmount', 'drive-unmount'] else continuous_program(
                ticks=146 if mode == 'bounded' else 0, flush=mode == 'guest-flush')
            batch += 'IO.COM\r\nif errorlevel 1 goto end\r\necho IO_OK>IO.OK\r\n'
        if mode == 'unmount':
            batch += 'imgmount -u 2>UNMOUNT.TXT\r\n' + mount + 'imgmount -u 2>UNMOUNT2.TXT\r\n'
        elif mode == 'drive-unmount':
            # Z is DOSBox's internal immutable command drive, safe for the shell.
            batch += 'z:\r\nmount -u c\r\n'
        if file_action == 'check-delete':
            batch += 'if exist A goto end\r\necho DELETION_PERSISTED>FILE.OK\r\n'
        elif file_action == 'check-rename':
            batch += ('if exist A goto end\r\nif exist B goto rename_found\r\ngoto end\r\n'
                ':rename_found\r\ncopy B READBACK.TXT\r\necho RENAME_PERSISTED>FILE.OK\r\n')
        batch += ':end\r\nexit\r\n'
        archive = self.output / (name + '.dosz')
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            entries = [('BASE.VHD', image or self.base), ('DOSBOX.BAT', batch.encode('ascii')), ('IO.COM', program)]
            if file_action is not None:
                entries.append(('A', b'IMMUTABLE_FILE\r\n'))
            for path, data in entries:
                info = zipfile.ZipInfo(path, stamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        exe = self.output / (name + '.exe')
        spec = dict(format_version=1, package_id=package_id or self.package_id, title='Synthetic milestone 5',
                    template=str(self.template), archive=str(archive), output=str(exe),
                    default_config=str(self.defaults), differencing_vhd=dict(disk_id='synthetic', parent='BASE.VHD', child='CHILD.VHD'))
        manifest = self.output / (name + '.json')
        manifest.write_text(json.dumps(spec), encoding='utf-8')
        result = subprocess.run([str(self.packager), str(manifest)], capture_output=True, text=True, timeout=60)
        (self.output / (name + '.build.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        assert result.returncode == 0, result.stdout + result.stderr
        return exe

    def environment(self, root):
        for name in ['localappdata', 'appdata', 'temp']:
            (root / name).mkdir(parents=True, exist_ok=True)
        return dict(os.environ, LOCALAPPDATA=str(root / 'localappdata'), APPDATA=str(root / 'appdata'),
                    TEMP=str(root / 'temp'), TMP=str(root / 'temp'))

    def save_path(self, root, package_id=None):
        return root / 'localappdata/DOSBoxPureStandalone' / (package_id or self.package_id) / 'embedded.pure.zip'

    def start(self, exe, name, root=None, extra=None):
        case = self.output / name
        case.mkdir()
        root = root or case
        env = self.environment(root)
        env.update(extra or {})
        stdout, stderr = case / 'stdout.log', case / 'stderr.log'
        handles = (stdout.open('wb'), stderr.open('wb'))
        process = subprocess.Popen([str(exe)], cwd=case, env=env, stdout=handles[0], stderr=handles[1],
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        info = {'case': name, 'pid': process.pid, 'command': [str(exe)],
            'persistence_root': str(root / 'localappdata'), 'temp_root': str(root / 'temp'),
            'allowed_roots': [str(root / 'localappdata')], 'allowed_files': [str(stdout), str(stderr)],
            'fault_environment': extra or {}}
        self.report['processes'].append(info)
        self.owned.append((process, handles, info, root))
        self.record()

        return process, root, case

    def finish(self, process, timeout=30, killed=False, expect=0):
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise AssertionError('Owned synthetic runtime timed out: ' + str(process.pid))
        for owned, handles, info, root in self.owned:
            if owned is process:
                for handle in handles:
                    handle.close()
                info.update(exit_code=code, host_killed=killed)
                assert not list((root / 'temp').rglob('*')), 'unexpected temporary files'
                break
        self.record()
        assert killed or 0 <= code < 0x80000000, ('native exception exit', info['case'], hex(code & 0xffffffff))
        if expect is not None:
            assert code == expect, (info['case'], code)
        return code

    def kill(self, process):
        process.kill()
        self.finish(process, killed=True, expect=None)

    def run_exit(self, exe, name, root=None, extra=None, expect=0):
        process, root, case = self.start(exe, name, root, extra)
        self.finish(process, expect=expect)
        return root, case

    def until(self, predicate, process, description, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            got = predicate()
            if got:
                return got
            assert process.poll() is None, 'runtime exited before ' + description
            time.sleep(.025)
        raise AssertionError('Timed out waiting for ' + description)

    def lifecycle(self):
        once = self.package('lifecycle-once')
        root, _ = self.run_exit(once, 'lifecycle-first')
        first, values = inspect_save(self.save_path(root), self.base)
        assert first['counter'] == 1
        self.run_exit(once, 'lifecycle-relaunch', root=root)
        second, _ = inspect_save(self.save_path(root), self.base)
        assert second['counter'] == 2
        self.report['cases']['exit-relaunch'] = {'first': first, 'second': second}
        for mode in ['unmount']:
            exe = self.package('lifecycle-' + mode, mode=mode)
            root, _ = self.run_exit(exe, 'lifecycle-' + mode + '-run')
            result, _ = inspect_save(self.save_path(root), self.base)
            assert result['counter'] == 1, (mode, result)
            self.report['cases'][mode] = result
        # Removing the archive-backed C drive also removes the batch reader.
        # Its shell remains alive; verify the actual unmount publication before
        # terminating that owned shell, then reopen through a fresh reader.
        exe = self.package('lifecycle-drive-unmount', mode='drive-unmount')
        process, root, _ = self.start(exe, 'lifecycle-drive-unmount-run')
        try:
            def drive_unmounted():
                path = self.save_path(root)
                if not path.exists():
                    return False
                try:
                    got, _ = inspect_save(path, self.base)
                    return got if got['counter'] == 1 else False
                except (KeyError, OSError, zipfile.BadZipFile):
                    return False
            got = self.until(drive_unmounted, process, 'archive drive unmount publication')
            assert process.poll() is None
            self.report['cases']['drive-unmount'] = dict(got,
                shell_waited_after_batch_source_unmounted=True)
        finally:
            self.kill(process)
        reader = self.package('drive-unmount-reader', mode='read')
        self.run_exit(reader, 'drive-unmount-reopen', root=root)
        reopened, _ = inspect_save(self.save_path(root), self.base)
        assert reopened['counter'] == 1
        exe = self.package('lifecycle-poweroff', mode='poweroff')
        root, _ = self.seed('lifecycle-poweroff', None)
        process, _, case = self.start(exe, 'lifecycle-poweroff-run', root=root,
            extra=self.hook(root, DBP_TEST_VHD_LIFECYCLE='1'))
        try:
            def poweroff_saved():
                text = (case / 'stderr.log').read_text(errors='replace')
                path = self.save_path(root)
                if 'Power down by BIOS APM requested' not in text or not path.exists():
                    return False
                try:
                    got, _ = inspect_save(path, self.base)
                    return got if got['counter'] == 1 else False
                except (KeyError, OSError, zipfile.BadZipFile):
                    return False
            got = self.until(poweroff_saved, process, 'BIOS poweroff completed save')
            assert 'BIOS poweroff flush' in (case / 'stderr.log').read_text(errors='replace')
            self.report['cases']['bios-poweroff'] = dict(got,
                frontend_menu_remained_after_guest_poweroff=True)
        finally:
            self.kill(process)
        self.run_exit(reader, 'poweroff-reopen', root=root)
        assert inspect_save(self.save_path(root), self.base)[0]['counter'] == 1
        base = lifecycle_parent('reboot')
        exe = self.package('lifecycle-reboot', mode='reboot', image=base)
        root, _ = self.seed('lifecycle-reboot', None)
        process, _, case = self.start(exe, 'lifecycle-reboot-run', root=root,
            extra=self.hook(root, DBP_TEST_VHD_LIFECYCLE='1'))
        try:
            def reboot_saved():
                text = (case / 'stderr.log').read_text(errors='replace')
                path = self.save_path(root)
                if 'BIOS reboot flush' not in text or 'Power down by BIOS APM requested' not in text or not path.exists():
                    return False
                try:
                    got, _ = inspect_save(path, base)
                    return got if got['counter'] == 2 else False
                except (KeyError, OSError, zipfile.BadZipFile):
                    return False
            result = self.until(reboot_saved, process, 'BIOS reboot child reopen and poweroff save')
            self.report['cases']['bios-reboot'] = result
        finally:
            self.kill(process)
        base = lifecycle_parent('guest-flush')
        exe = self.package('lifecycle-guest-flush', mode='guest-flush', image=base)
        started = time.monotonic()
        flush_root, _ = self.seed('guest-flush', None)
        process, root, case = self.start(exe, 'lifecycle-guest-flush-run', root=flush_root,
            extra=self.hook(flush_root, DBP_TEST_VHD_LIFECYCLE='1'))
        try:
            def guest_flush_seen():
                path = self.save_path(root)
                if not path.exists():
                    return False
                try:
                    got, _ = inspect_save(path, base)
                    return got if got['counter'] == 1 else False
                except (KeyError, OSError, zipfile.BadZipFile):
                    return False
            got = self.until(guest_flush_seen, process, 'guest BIOS disk flush checkpoint', timeout=8)
            got['host_seconds_since_launch'] = round(time.monotonic() - started, 3)
            assert process.poll() is None
            text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
            assert 'BIOS hard disk reset flush complete' in text, text
            self.report['cases']['guest-flush-open'] = got
        finally:
            self.kill(process)
        exe = self.package('continuous', mode='continuous')
        process, root, case = self.start(exe, 'continuous-open')
        path = self.save_path(root)
        samples, previous, observed_stamp = [], None, None
        start = time.monotonic()
        try:
            def sample():
                nonlocal previous, observed_stamp
                if not path.exists():
                    return False
                try:
                    stamp = path.stat().st_mtime_ns
                    if stamp == observed_stamp:
                        return False
                    result, entries = inspect_save(path, self.base, continuous=True)
                except (OSError, KeyError, zipfile.BadZipFile):
                    return False
                observed_stamp = stamp
                if result['save_sha256'] != previous and result['sector_present']:
                    previous = result['save_sha256']
                    result['host_seconds'] = round(time.monotonic() - start, 3)
                    samples.append(result)
                return samples if len(samples) >= 3 else False
            self.until(sample, process, 'three complete open-child checkpoints', timeout=self.args.checkpoint_timeout)
            assert all(a['counter'] < b['counter'] for a, b in zip(samples, samples[1:])), samples
            self.report['cases']['continuous-open-checkpoints'] = {'samples': samples,
                'guest_handles_open': True, 'terminated_after_observation': True}
        finally:
            self.kill(process)
        # Relaunch read-only guest to exercise recovery/loading after process death.
        reader = self.package('reader', mode='read')
        self.run_exit(reader, 'continuous-recovery', root=root)
        recovered, _ = inspect_save(path, self.base, continuous=True)
        assert recovered['counter'] >= samples[-1]['counter']
        self.report['cases']['continuous-crash-recovery'] = recovered
        # A large ordinary overlay can already have a long scheduled delay
        # when the child mounts. Acquiring its lease must shorten that deadline.
        _, baseline = self.baseline('premount')
        root, path = self.seed('premount-large-save', baseline)
        entries = saved_entries(path)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
            archive.writestr('PADDING.BIN', bytes(7 * 1024 * 1024))
        large_bytes = path.stat().st_size
        baseline_stamp = path.stat().st_mtime_ns
        exe = self.package('premount-continuous', mode='premount-continuous')
        process, _, case = self.start(exe, 'premount-large-save', root=root)
        try:
            self.until(lambda: 'Experimental differencing VHD' in
                (case / 'stderr.log').read_text(errors='replace'), process, 'child lease after ordinary file dirtied')
            mounted_at = time.monotonic()
            self.until(lambda: 'Saving filesystem modifications' in
                (case / 'stderr.log').read_text(errors='replace'), process, 'shortened existing checkpoint deadline', timeout=6)
            publication_started = time.monotonic() - mounted_at
            assert publication_started < 5.5, publication_started
            def large_saved():
                if path.stat().st_mtime_ns == baseline_stamp:
                    return False
                got, values = inspect_save(path, self.base, continuous=True)
                return got if values.get('PREMOUNT.TXT') and got['sector_prefix'][8:16] == '4d35494f' else False
            got = self.until(large_saved, process, 'complete shortened large-overlay checkpoint', timeout=8)
            self.report['cases']['premount-dirty-deadline-shortened'] = {
                'preceding_zip_bytes': large_bytes, 'publication_start_seconds_after_mount': round(publication_started, 3),
                'observation_tolerance_seconds': .5, 'ordinary_write_before_child_mount': True, 'committed': got}
        finally:
            self.kill(process)
        exe = self.package('continuous-paused', mode='continuous')
        root, path = self.seed('frontend-paused', None)
        process, _, case = self.start(exe, 'frontend-paused', root=root,
            extra=self.hook(root, DBP_TEST_FRONTEND_PAUSE='1'))
        try:
            def paused():
                return 'TEST_FRONTEND_PAUSED' in (case / 'stderr.log').read_text(errors='replace')
            self.until(paused, process, 'real frontend pause')
            def paused_checkpoint():
                if not path.exists():
                    return False
                try:
                    got, _ = inspect_save(path, self.base, continuous=True)
                    return got if got['counter'] and got['sector_present'] else False
                except (KeyError, OSError, zipfile.BadZipFile):
                    return False
            got = self.until(paused_checkpoint, process, 'host-time checkpoint during frontend pause', timeout=8)
            time.sleep(1.2)
            later, _ = inspect_save(path, self.base, continuous=True)
            assert got['counter'] == later['counter'] and got['save_sha256'] == later['save_sha256']
            self.report['cases']['frontend-paused-checkpoint'] = {'guest_counter_frozen': True,
                'real_frontend_pause_branch': True, 'committed': got}
        finally:
            self.kill(process)
        self.run_exit(reader, 'frontend-paused-recovery', root=root)
        reopened, _ = inspect_save(path, self.base, continuous=True)
        assert reopened['counter'] == got['counter']
        self.frontend_close()
        self.frontend_reset()
        self.record()

    def close_window(self, process):
        """Post WM_CLOSE only to the Popen PID's single visible window."""
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.PostMessageW.restype = wintypes.BOOL
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        windows = []
        @callback_type
        def find_owned(hwnd, unused):
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == process.pid and user32.IsWindowVisible(hwnd):
                windows.append(hwnd)
            return True
        user32.EnumWindows(find_owned, 0)
        assert len(windows) == 1, ('expected one owned runtime window', process.pid, windows)
        assert user32.PostMessageW(windows[0], 0x0010, 0, 0), 'owned WM_CLOSE delivery failed'

    def frontend_close(self):
        """Post normal WM_CLOSE to this runner's owned open-child window."""
        exe = self.package('frontend-close-continuous', mode='continuous')
        process, root, case = self.start(exe, 'frontend-close-continuous')
        path = self.save_path(root)
        def initial_checkpoint():
            if not path.exists():
                return False
            try:
                got, _ = inspect_save(path, self.base, continuous=True)
                return got if got['counter'] and got['sector_present'] else False
            except (OSError, KeyError, zipfile.BadZipFile):
                return False
        prior = self.until(initial_checkpoint, process, 'steady continuous guest before ordinary frontend close')
        prior_stamp = path.stat().st_mtime_ns
        time.sleep(.3)
        assert path.stat().st_mtime_ns == prior_stamp, 'next periodic checkpoint preceded frontend close'
        self.close_window(process)
        self.finish(process)
        got, _ = inspect_save(path, self.base, continuous=True)
        assert got['counter'] > prior['counter'] and got['sector_present']
        reader = self.package('frontend-close-reader', mode='read')
        self.run_exit(reader, 'frontend-close-reader', root=root)
        reopened, _ = inspect_save(path, self.base, continuous=True)
        assert reopened['counter'] == got['counter']
        self.report['cases']['frontend-window-close'] = {'actual_WM_CLOSE_open_child': True,
            'new_dirty_guest_sectors_since_prior_checkpoint': True,
            'closed_before_next_periodic_checkpoint': True, 'prior': prior, 'committed': got, 'reopened': reopened}
        self.record()

    def frontend_reset(self):
        exe = self.package('frontend-reset-continuous', mode='continuous')
        root, path = self.seed('frontend-reset', None)
        process, _, case = self.start(exe, 'frontend-reset', root=root,
            extra=self.hook(root, DBP_TEST_FRONTEND_STATE='reset'))
        try:
            self.until(lambda: 'TEST_FRONTEND_RESET\n' in
                (case / 'stderr.log').read_text(errors='replace'), process, 'actual frontend retro_reset completion')
            text = (case / 'stderr.log').read_text(errors='replace')
            before, after = text.split('TEST_FRONTEND_RESET_BEGIN\n', 1)
            assert 'Saving filesystem modifications' not in before, 'periodic checkpoint preceded reset trigger'
            assert after.count('Saving filesystem modifications') == 1, 'reset shutdown did not publish exactly once'
            reset_saved, _ = inspect_save(path, self.base, continuous=True)
            assert reset_saved['counter'] > 0
            assert text.count('Experimental differencing VHD') == 2, 'reset did not reopen standard child'
            stamp = path.stat().st_mtime_ns
            def resumed_checkpoint():
                if path.stat().st_mtime_ns == stamp:
                    return False
                got, _ = inspect_save(path, self.base, continuous=True)
                return got if got['counter'] > reset_saved['counter'] else False
            resumed = self.until(resumed_checkpoint, process, 'continued open-child writes after frontend reset', timeout=8)
            assert resumed['binding_sha256'] == reset_saved['binding_sha256']
            self.close_window(process)
            self.finish(process)
            closed, _ = inspect_save(path, self.base, continuous=True)
            assert closed['counter'] >= resumed['counter']
        finally:
            if process.poll() is None:
                self.kill(process)
        reader = self.package('frontend-reset-reader', mode='read')
        self.run_exit(reader, 'frontend-reset-reader', root=root)
        reopened, _ = inspect_save(path, self.base, continuous=True)
        assert reopened['counter'] == closed['counter']
        self.report['cases']['frontend-reset'] = {'actual_frontend_retro_reset': True,
            'reset_before_first_periodic_checkpoint': True, 'shutdown_published_open_child': True,
            'standard_child_reopened': True, 'binding_preserved': True, 'reset_save': reset_saved,
            'resumed': resumed, 'window_closed': closed, 'reader_reopened': reopened}
        self.record()

    def baseline(self, prefix):
        exe = self.package(prefix + '-once')
        root, _ = self.run_exit(exe, prefix + '-baseline')
        info, _ = inspect_save(self.save_path(root), self.base)
        assert info['counter'] == 1
        return exe, self.save_path(root).read_bytes()

    def filemods(self):
        baseline = None
        for action in ['delete', 'rename']:
            exe = self.package('filemods-' + action, file_action=action)
            root, _ = self.run_exit(exe, 'filemods-' + action)
            path = self.save_path(root)
            first, values = inspect_save(path, self.base)
            assert first['counter'] == 1
            expected = b'DELETE|A\r\n' if action == 'delete' else b'REDIRECTFILE|B|A\r\n'
            assert expected in values['FILEMODS.DBP'], values['FILEMODS.DBP']
            baseline = baseline or path.read_bytes()
            reader = self.package('filemods-' + action + '-reader', mode='read', file_action='check-' + action)
            self.run_exit(reader, 'filemods-' + action + '-reader', root=root)
            reopened, values = inspect_save(path, self.base)
            assert reopened['counter'] == 1
            assert values['FILE.OK'].strip() == (b'DELETION_PERSISTED' if action == 'delete' else b'RENAME_PERSISTED')
            if action == 'rename':
                assert values['READBACK.TXT'] == b'IMMUTABLE_FILE\r\n'
            self.report['cases']['filemods-one-character-' + action] = {'serialized_metadata': expected.decode('ascii'),
                'ordinary_overlay_reopened': True, 'immutable_parent_absent_from_save': True, 'reopened': reopened}
            self.record()
        reader = self.package('filemods-invalid-reader', mode='read', file_action='check-delete')
        malformed = {
            'redirect-missing-source': b'REDIRECTFILE|ABC\r\n',
            'redirect-empty-source': b'REDIRECTFILE|ABC|\r\n',
            'redirect-empty-target': b'REDIRECTFILE||A\r\n',
            'redirect-extra-separator': b'REDIRECTFILE|B|A|C\r\n',
            'delete-extra-separator': b'DELETE|A|B\r\n',
            'redirect-cross-line-source': b'REDIRECTFILE|ABC\r\nDELETE|Z\r\n',
        }
        baseline_path = self.output / 'filemods-valid-baseline.pure.zip'
        baseline_path.write_bytes(baseline)
        entries = saved_entries(baseline_path)
        for name, metadata in malformed.items():
            root, path = self.seed('filemods-' + name, None)
            pending = Path(str(path) + '.pending')
            with zipfile.ZipFile(pending, 'w', zipfile.ZIP_STORED) as archive:
                for entry, content in entries.items():
                    archive.writestr(entry, metadata if entry == 'FILEMODS.DBP' else content)
            saved_entries(pending)  # All payload CRCs are valid; grammar must reject it.
            candidate = pending.read_bytes()
            _, case = self.run_exit(reader, 'filemods-' + name, root=root, expect=None)
            assert 'Persistence error:' in (case / 'stderr.log').read_text(errors='replace')
            assert not path.exists() and pending.read_bytes() == candidate
            self.report['cases']['filemods-' + name] = {'crc_valid_metadata_rejected': True,
                'candidate_preserved': True, 'no_committed_save_created': True}
            self.record()

    def seed(self, name, data):
        root = self.output / (name + '-persistence')
        self.environment(root)
        path = self.save_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        if data is not None:
            path.write_bytes(data)
        return root, path

    def hook(self, root, **values):
        return dict(DBP_TEST_SAVE_ROOT=str(root / 'localappdata'), **values)

    def faults(self):
        exe, baseline = self.baseline('fault')
        reader = self.package('fault-reader', mode='read')
        for fault in ['open', 'short_write', 'flush', 'close', 'backup_flush', 'replace', 'publish_flush']:
            name = 'fault-' + fault
            root, path = self.seed(name, baseline)
            _, case = self.run_exit(exe, name, root=root,
                extra=self.hook(root, DBP_TEST_SAVE_FAULT=fault))
            assert path.read_bytes() == baseline, (fault, 'preceding committed generation changed')
            text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
            assert 'sav' in text.casefold() and ('error' in text.casefold() or 'fail' in text.casefold()), (fault, text)
            before, _ = inspect_save(path, self.base)
            self.run_exit(reader, name + '-recovery', root=root)
            after, _ = inspect_save(path, self.base)
            assert after['counter'] == before['counter'] == 1
            # A clean later writer must not be poisoned by the previous host fault.
            self.run_exit(exe, name + '-retry', root=root)
            retried, _ = inspect_save(path, self.base)
            assert retried['counter'] == 2
            self.report['cases'][name] = {'prior_generation_byte_preserved': True,
                'failure_observable_in_runtime_log': True, 'recovered': after, 'retry': retried}
            self.record()
        # The retry in this case happens inside the same live process; dirty
        # state must survive the first failed checkpoint.
        continuous = self.package('fault-once-continuous', mode='continuous')
        root, path = self.seed('fault-once', baseline)
        process, _, case = self.start(continuous, 'fault-once', root=root,
            extra=self.hook(root, DBP_TEST_SAVE_FAULT='flush', DBP_TEST_SAVE_FAULT_ONCE='1'))
        baseline_stamp = path.stat().st_mtime_ns
        try:
            def retry_seen():
                try:
                    if path.stat().st_mtime_ns == baseline_stamp:
                        return False
                    result, _ = inspect_save(path, self.base, continuous=True)
                    return result if result['save_sha256'] != hashlib.sha256(baseline).hexdigest() else False
                except (KeyError, OSError, zipfile.BadZipFile):
                    return False
            result = self.until(retry_seen, process, 'same-session failed-save retry', timeout=self.args.checkpoint_timeout)
            text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
            assert 'sav' in text.casefold() and ('error' in text.casefold() or 'fail' in text.casefold()), text
            self.report['cases']['fault-once-same-session-retry'] = {'prior_dirty_state_retried': True, 'committed': result}
        finally:
            self.kill(process)
        self.record()

        # This fault changes real memory child bytes before failing; the codec's
        # fault fence must suppress shutdown publication of that partial child.
        root, path = self.seed('codec-short-write', baseline)
        _, case = self.run_exit(exe, 'codec-short-write', root=root,
            extra=self.hook(root, DBP_TEST_VHD_FAULT='short_write'))
        assert path.read_bytes() == baseline, 'codec fault published partially changed child'
        text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
        assert 'vhd' in text.casefold() and ('error' in text.casefold() or 'fail' in text.casefold()), text
        self.report['cases']['codec-short-write'] = {'prior_generation_byte_preserved': True, 'publication_disabled': True}
        self.record()
        root, path = self.seed('deflated-save', baseline)
        contents = saved_entries(path)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in contents.items():
                archive.writestr(name, data)
        self.run_exit(exe, 'deflated-save', root=root)
        got, _ = inspect_save(path, self.base)
        assert got['counter'] == 2
        self.report['cases']['deflated-existing-save'] = {'legacy_compression_preserved_on_read': True, 'committed': got}
        self.record()
        root, path = self.seed('first-publish-flush-fault', None)
        self.run_exit(exe, 'first-publish-flush-fault', root=root,
            extra=self.hook(root, DBP_TEST_SAVE_FAULT='publish_flush'))
        pending = Path(str(path) + '.pending')
        assert not path.exists() and pending.exists()
        preserved, _ = inspect_save(pending, self.base)
        assert preserved['counter'] == 1
        self.run_exit(reader, 'first-publish-flush-recover', root=root)
        recovered, _ = inspect_save(path, self.base)
        assert recovered['counter'] == 1
        self.report['cases']['first-publish-flush-fault'] = {'no_committed_partial': True,
            'complete_first_pending_preserved': True, 'pending': preserved, 'recovered': recovered}
        self.record()

    def crashes(self, refusals_only=False):
        exe, baseline = self.baseline('crash')
        reader = self.package('crash-reader', mode='read')
        for first_save in ([] if refusals_only else [False, True]):
            stages = ['open', 'write', 'flush', 'close', 'published', 'replace']
            if not first_save:
                stages[4:4] = ['backup_open', 'backup_write', 'backup_flush', 'backup']
            for stage in stages:
                name = 'crash-' + ('first-' if first_save else 'prior-') + stage
                root, path = self.seed(name, None if first_save else baseline)
                marker = Path(str(path) + '.test-stage')
                process, _, _ = self.start(exe, name, root=root,
                    extra=self.hook(root, DBP_TEST_SAVE_PAUSE=stage))
                try:
                    self.until(lambda: marker.exists() and marker.read_text() == stage,
                        process, 'publication barrier ' + stage)
                    artifacts = {}
                    for suffix in ['', '.pending', '.previous', '.previous.pending']:
                        candidate = Path(str(path) + suffix)
                        if not candidate.exists():
                            continue
                        try:
                            value, _ = inspect_save(candidate, self.base)
                            artifacts[suffix or 'committed'] = dict(value, valid_zip_and_pair=True)
                        except (AssertionError, KeyError, OSError, zipfile.BadZipFile) as error:
                            artifacts[suffix or 'committed'] = {'valid_zip_and_pair': False, 'error': str(error)}
                    self.kill(process)
                finally:
                    if process.poll() is None:
                        self.kill(process)
                if not first_save and stage not in ['published', 'replace']:
                    assert path.read_bytes() == baseline, (name, 'prior generation changed before replacement')
                if first_save and not artifacts.get('.pending', artifacts.get('committed', {})).get('valid_zip_and_pair', False):
                    pending = Path(str(path) + '.pending')
                    damaged_bytes = pending.read_bytes()
                    recovered_process, _, case = self.start(reader, name + '-recover', root=root)
                    code = self.finish(recovered_process, expect=None)
                    text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
                    assert 'Persistence error:' in text, (code, text)
                    assert not path.exists() and pending.read_bytes() == damaged_bytes
                    self.report['cases'][name] = {'process_terminated_at_stage': stage, 'first_save': True,
                        'artifacts_before_termination': artifacts, 'recovery_clear_error': True,
                        'unsupported_partial_bytes_preserved': True, 'recovery_exit_code': code,
                        'hardware_power_loss_exercised': False}
                    self.record()
                    continue
                self.run_exit(reader, name + '-recover', root=root)
                recovered, _ = inspect_save(path, self.base)
                if first_save:
                    assert recovered['counter'] == 1, (name, recovered)
                else:
                    assert recovered['counter'] == (2 if stage in ['published', 'replace'] else 1), (name, recovered)
                self.report['cases'][name] = {'process_terminated_at_stage': stage,
                    'first_save': first_save, 'artifacts_before_termination': artifacts,
                    'recovered': recovered, 'hardware_power_loss_exercised': False}
                self.record()

        # Startup validates candidates rather than accepting a malformed committed
        # ZIP, and restores the preceding valid generation where it exists.
        for corruption in ([] if refusals_only else ['truncate', 'crc']):
            root, path = self.seed('recover-' + corruption, baseline)
            Path(str(path) + '.previous').write_bytes(baseline)
            broken = bytearray(baseline)
            if corruption == 'truncate':
                broken = broken[:len(broken) // 2]
            else:
                # Corrupt a stored payload while preserving its central directory.
                with zipfile.ZipFile(path) as archive:
                    item = archive.getinfo('CHILD.VHD')
                    local = item.header_offset
                    name_length, extra_length = struct.unpack_from('<HH', broken, local + 26)
                    broken[local + 30 + name_length + extra_length + 1024] ^= 1
            path.write_bytes(broken)
            self.run_exit(reader, 'recover-' + corruption, root=root)
            recovered, _ = inspect_save(path, self.base)
            assert recovered['counter'] == 1
            self.report['cases']['recover-' + corruption] = {'valid_previous_selected': True, 'recovered': recovered}
            self.record()
        if refusals_only:
            for name, contents in [('empty-first-pending', b''), ('partial-first-pending', b'PK\x03\x04partial')]:
                root, path = self.seed(name, None)
                pending = Path(str(path) + '.pending')
                pending.write_bytes(contents)
                _, case = self.run_exit(reader, name, root=root, expect=None)
                assert 'Persistence error:' in (case / 'stderr.log').read_text(errors='replace')
                assert not path.exists() and pending.read_bytes() == contents
                self.report['cases'][name] = {'clean_refusal': True, 'candidate_preserved': True}
                self.record()
        root, path = self.seed('malformed-only', None)
        invalid = {path: b'not a save ZIP', Path(str(path) + '.pending'): b'PK\x03\x04partial'}
        for candidate, contents in invalid.items():
            candidate.write_bytes(contents)
        process, _, case = self.start(reader, 'malformed-only', root=root)
        code = self.finish(process, expect=None)
        text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
        assert 'Persistence error:' in text, (code, text)
        assert all(candidate.read_bytes() == contents for candidate, contents in invalid.items())
        self.report['cases']['malformed-only-recovery'] = {'clear_error': True, 'all_candidates_preserved': True, 'exit_code': code}
        self.record()
        unrelated = self.package('unrelated-identity', package_id=self.package_id + '.unrelated')
        foreign_root, _ = self.run_exit(unrelated, 'unrelated-baseline')
        foreign = self.save_path(foreign_root, self.package_id + '.unrelated').read_bytes()
        root, path = self.seed('unrelated-pending', None)
        pending = Path(str(path) + '.pending')
        pending.write_bytes(foreign)
        process, _, case = self.start(reader, 'unrelated-pending', root=root)
        code = self.finish(process, expect=None)
        text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
        assert 'Persistence error:' in text, (code, text)
        assert not path.exists() and pending.read_bytes() == foreign, 'unrelated pending generation adopted or altered'
        self.report['cases']['unrelated-pending-recovery'] = {'identity_rejected': True, 'candidate_preserved': True, 'exit_code': code}
        self.record()
        root, path = self.seed('malformed-filemods', None)
        pending = Path(str(path) + '.pending')
        baseline_path = self.output / 'filemods-baseline.pure.zip'
        baseline_path.write_bytes(baseline)
        entries = saved_entries(baseline_path)
        entries['FILEMODS.DBP'] = b'DELETE|' + b'A' * 300 + b'\r\n'
        with zipfile.ZipFile(pending, 'w', zipfile.ZIP_STORED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        invalid_metadata = pending.read_bytes()
        process, _, case = self.start(reader, 'malformed-filemods', root=root)
        code = self.finish(process, expect=None)
        text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
        assert 'Persistence error:' in text, (code, text)
        assert not path.exists() and pending.read_bytes() == invalid_metadata
        self.report['cases']['malformed-filemods-recovery'] = {'crc_valid_zip_rejected': True,
            'invalid_metadata_preserved': True, 'exit_code': code}
        self.record()

    def concurrency(self):
        writer = self.package('lock-writer', mode='continuous')
        second = self.package('lock-repacked', stamp=(2027, 1, 2, 3, 4, 6))
        renamed = self.output / 'RenamedSameIdentity.exe'
        shutil.copyfile(second, renamed)
        different = self.package('lock-different', package_id=self.package_id + '.another')
        process, root, _ = self.start(writer, 'lock-first')
        path = self.save_path(root)
        try:
            self.until(lambda: path.exists() and 'CHILD.VHD' in saved_entries(path),
                process, 'first writer checkpoint', timeout=self.args.checkpoint_timeout)
            # Pause the first process with an NT suspension to make a byte-level
            # comparison of second-writer rejection independent of ongoing writes.
            import ctypes
            api = ctypes.WinDLL('ntdll')
            api.NtSuspendProcess.argtypes = [ctypes.c_void_p]
            api.NtResumeProcess.argtypes = [ctypes.c_void_p]
            assert api.NtSuspendProcess(int(process._handle)) == 0
            try:
                baseline = path.read_bytes()
                contender, _, case = self.start(renamed, 'lock-same-renamed-repacked', root=root)
                code = self.finish(contender, expect=None)
                message = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
                assert 'Persistence error:' in message and 'save overlay is already in use' in message, message
                assert path.read_bytes() == baseline, 'rejected second writer altered committed save'
                self.run_exit(different, 'lock-different-identity', root=root)
                got, _ = inspect_save(self.save_path(root, self.package_id + '.another'), self.base)
                assert got['counter'] == 1
            finally:
                assert api.NtResumeProcess(int(process._handle)) == 0
            self.kill(process)
        finally:
            if process.poll() is None:
                self.kill(process)
        self.run_exit(second, 'lock-after-death', root=root)
        after_death, _ = inspect_save(path, self.base)
        self.run_exit(second, 'lock-after-orderly-exit', root=root)
        after_exit, _ = inspect_save(path, self.base)
        assert after_exit['counter'] == (after_death['counter'] + 1) & 255
        self.report['cases']['writer-exclusion'] = {'second_exit_code': code,
            'same_renamed_repacked_identity_rejected': True, 'committed_save_unchanged': True,
            'different_identity_runs_concurrently': True, 'death_releases_lock': True,
            'orderly_exit_releases_lock': True, 'after_death': after_death, 'after_orderly_exit': after_exit}
        self.record()

    def cleanup(self):
        for process, handles, _, _ in self.owned:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            for handle in handles:
                handle.close()

    def state(self):
        base = lifecycle_parent('guest-flush')
        exe = self.package('state-selftest', mode='guest-flush', image=base)
        root, path = self.seed('state-selftest', None)
        _, case = self.run_exit(exe, 'state-selftest', root=root,
            extra=self.hook(root, DBP_TEST_VHD_STATE='1'))
        text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
        expected = ['save/load machine+disk restore PASS', 'rewind machine+disk restore PASS',
            'malformed/binding/generation/cap/codec/machine-layout/mount/file preflight and decoder rollback PASS (save/load)',
            'malformed/binding/generation/cap/codec/machine-layout/mount/file preflight and decoder rollback PASS (rewind)',
            'growth buffer refusal and codec shrink reopen PASS',
            'PASS (35 production cases); resumed publication PASS']
        assert all(value in text for value in expected), text
        assert 'Milestone5 state test: FAIL' not in text
        result, values = inspect_save(path, base)
        assert read_sector(values['CHILD.VHD'], 5001, base)[0] == b'\x5A' * 512
        self.report['cases']['state-production-api'] = {'production_cases': 35,
            'normal_and_rewind_machine_disk_restore': True,
            'malformed_binding_generation_cap_codec_preflight': True,
            'machine_layout_mount_file_preflight_and_semantic_decoder_rollback_preserve_live_state': True,
            'growth_buffer_refusal_and_shrink_reopen': True,
            'resumed_publication_sector_verified': True, 'committed': result}
        self.record()
        root, path = self.seed('state-restart', None)
        _, case = self.run_exit(exe, 'state-restart-capture', root=root,
            extra=self.hook(root, DBP_TEST_VHD_STATE='write'))
        text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
        assert 'restart capture PASS' in text, text
        state_file = Path(str(path) + '.milestone5.state')
        assert state_file.exists()
        state_sha = hashlib.sha256(state_file.read_bytes()).hexdigest()
        captured, values = inspect_save(path, base)
        assert read_sector(values['CHILD.VHD'], 5001, base)[0] == b'\x5A' * 512
        repacked = self.package('state-repacked', mode='guest-flush', image=base,
            stamp=(2027, 1, 2, 3, 4, 6))
        renamed = self.output / 'RenamedStatePackage.exe'
        shutil.copyfile(repacked, renamed)
        _, case = self.run_exit(renamed, 'state-restart-restore', root=root,
            extra=self.hook(root, DBP_TEST_VHD_STATE='load'))
        text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
        assert 'restart restore machine+disk PASS' in text, text
        restored, values = inspect_save(path, base)
        assert read_sector(values['CHILD.VHD'], 5001, base)[0] == b'\xA5' * 512
        assert restored['binding_sha256'] == captured['binding_sha256']
        assert hashlib.sha256(state_file.read_bytes()).hexdigest() == state_sha
        reader = self.package('state-restart-reader', mode='read', image=base)
        self.run_exit(reader, 'state-after-restored-publication', root=root)
        reopened, values = inspect_save(path, base)
        assert read_sector(values['CHILD.VHD'], 5001, base)[0] == b'\xA5' * 512
        self.report['cases']['state-cross-restart'] = {'machine_disk_restore_across_rename_repack': True,
            'binding_preserved': True, 'state_file_sha256': state_sha, 'resumed_publication_reopened': True,
            'before_restore': captured, 'after_restore': restored, 'reopened': reopened}
        self.record()
        self.state_fence(base, path.read_bytes())
        self.frontend_state(exe, base)

    def state_fence(self, base, fence_prior=None):
        if fence_prior is None:
            baseline_exe = self.package('state-fence-baseline', image=base)
            root, _ = self.run_exit(baseline_exe, 'state-fence-baseline')
            fence_prior = self.save_path(root).read_bytes()
        root, path = self.seed('state-codec-fence', fence_prior)
        # A DOS writer reaches the stopped-frame hook before any guest BIOS
        # flush; the fault comparison starts from the seeded committed ZIP.
        exe = self.package('state-fence-selftest', mode='continuous', image=base)
        _, case = self.run_exit(exe, 'state-codec-fence', root=root,
            extra=self.hook(root, DBP_TEST_VHD_STATE='fence'))
        text = (case / 'stdout.log').read_text(errors='replace') + (case / 'stderr.log').read_text(errors='replace')
        assert 'partial child write injected' in text, text
        assert 'codec fault fences valid state restore and publication PASS' in text, text
        assert path.read_bytes() == fence_prior, 'faulted child published during state hook or shutdown'
        self.report['cases']['state-codec-fault-fence'] = {'actual_partial_child_write': True,
            'valid_state_restore_refused': True, 'shutdown_kept_committed_bytes': True}
        self.record()

    def frontend_state(self, exe, base):
        # Exercise actual RunSave's RZIP/RASTATE encoding and actual RunLoad's
        # bounds checks rather than calling only the core serializer test hook.
        root, path = self.seed('frontend-state', None)
        process, _, case = self.start(exe, 'frontend-state-save', root=root,
            extra=self.hook(root, DBP_TEST_FRONTEND_PAUSE='1', DBP_TEST_FRONTEND_STATE='save'))
        state_path = path.parent / 'embedded.state'
        try:
            def saved_state():
                if not state_path.exists():
                    return False
                data = state_path.read_bytes()
                if len(data) <= 20 or data[:8] != b'#RZIPv\x01#':
                    return False
                chunk_size, total = struct.unpack_from('<IQ', data, 8)
                offset, decoded = 20, bytearray()
                try:
                    while len(decoded) < total:
                        count = struct.unpack_from('<I', data, offset)[0]
                        offset += 4
                        if offset + count > len(data):
                            return False
                        decoded.extend(zlib.decompress(data[offset:offset + count]))
                        offset += count
                except (struct.error, zlib.error):
                    return False
                assert offset == len(data) and len(decoded) == total
                assert decoded[:12] == b'RASTATE\x01MEM '
                assert struct.unpack_from('<I', decoded, 12)[0] == len(decoded) - 16
                return {'compressed_bytes': len(data), 'uncompressed_bytes': total,
                    'chunk_bytes': chunk_size, 'state_sha256': hashlib.sha256(data).hexdigest()}
            state = self.until(saved_state, process, 'actual frontend RZIP/RASTATE save')
        finally:
            self.kill(process)
        before, _ = inspect_save(path, base)
        assert before['counter'] == 1
        before_stamp = path.stat().st_mtime_ns
        process, _, case = self.start(exe, 'frontend-state-load', root=root,
            extra=self.hook(root, DBP_TEST_FRONTEND_PAUSE='1', DBP_TEST_FRONTEND_STATE='load'))
        try:
            def newer_boot_write():
                # Poll metadata until namespace publication completes. Repeated
                # full ZIP opens can themselves deny a Windows replacement;
                # the final durability flush can briefly exclude readers too.
                try:
                    stamp = path.stat().st_mtime_ns
                    if stamp == before_stamp:
                        return False
                    got, _ = inspect_save(path, base)
                except (OSError, KeyError, zipfile.BadZipFile):
                    return False
                return dict(got, observed_mtime_ns=stamp) if got['counter'] == 2 else False
            newer = self.until(newer_boot_write, process, 'newer guest boot write before state rollback')
            newer_stamp = newer['observed_mtime_ns']
            def loaded_and_saved():
                if 'TEST_FRONTEND_PAUSED' not in (case / 'stderr.log').read_text(errors='replace'):
                    return False
                try:
                    if path.stat().st_mtime_ns == newer_stamp:
                        return False
                    got, _ = inspect_save(path, base)
                except (OSError, KeyError, zipfile.BadZipFile):
                    return False
                return got if got['counter'] == 1 else False
            restored = self.until(loaded_and_saved, process, 'actual frontend state disk rollback checkpoint', timeout=10)
            assert hashlib.sha256(state_path.read_bytes()).hexdigest() == state['state_sha256']
        finally:
            self.kill(process)
        self.report['cases']['frontend-state-rzip-roundtrip'] = {'actual_RunSave_RunLoad': True,
            'newer_boot_write_rolled_back': True, 'wrapper': state, 'newer': newer, 'restored': restored}
        self.record()

        def rzip(chunk, advertised, tail=b''):
            return b'#RZIPv\x01#' + struct.pack('<IQ', chunk, advertised) + tail
        malformed = {
            'rzip-zero-chunk': rzip(0, 16),
            'rzip-huge-chunk': rzip(0xffffffff, 16),
            'rzip-4g-advertised': rzip(131072, 0x100000000),
            'rzip-truncated-chunk': rzip(131072, 16),
            'rzip-huge-deflate-count': rzip(131072, 16, struct.pack('<I', 0xffffffff)),
            'rastate-oversized-MEM': b'RASTATE\x01MEM ' + struct.pack('<I', 0xffffffff),
            'rastate-missing-MEM': b'RASTATE\x01JUNK' + struct.pack('<I', 0),
        }
        for name, data in malformed.items():
            root, path = self.seed(name, None)
            state_path = path.parent / 'embedded.state'
            state_path.write_bytes(data)
            process, _, case = self.start(exe, name, root=root,
                extra=self.hook(root, DBP_TEST_FRONTEND_PAUSE='1', DBP_TEST_FRONTEND_STATE='load'))
            try:
                self.until(lambda: 'Invalid or unreadable state wrapper; live state unchanged' in
                    (case / 'stderr.log').read_text(errors='replace'), process, 'wrapper rejection ' + name)
                result, _ = inspect_save(path, base)
                assert result['counter'] == 1
                assert state_path.read_bytes() == data
                self.report['cases'][name] = {'actual_RunLoad_rejected_before_core_restore': True,
                    'guest_disk_preserved': True, 'invalid_input_preserved': True, 'committed': result}
            finally:
                self.kill(process)
            self.record()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packager', type=Path, required=True)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suite', choices=['all', 'lifecycle', 'frontend-close', 'frontend-reset', 'frontend-state',
        'faults', 'crash', 'crash-refusals', 'concurrency', 'state', 'state-fence', 'filemods', 'final-guards'], default='all')
    parser.add_argument('--checkpoint-timeout', type=float, default=30)
    args = parser.parse_args()
    runner = Runner(args)
    try:
        if args.suite in ['all', 'lifecycle']:
            runner.lifecycle()
        if args.suite == 'frontend-close':
            runner.frontend_close()
        if args.suite in ['frontend-reset', 'final-guards']:
            runner.frontend_reset()
        if args.suite == 'frontend-state':
            base = lifecycle_parent('guest-flush')
            exe = runner.package('frontend-state-only', mode='guest-flush', image=base)
            runner.frontend_state(exe, base)
        if args.suite == 'state-fence':
            runner.state_fence(lifecycle_parent('guest-flush'))
        if args.suite in ['all', 'faults']:
            runner.faults()
        if args.suite in ['all', 'filemods']:
            runner.filemods()
        if args.suite in ['all', 'crash']:
            runner.crashes()
        if args.suite in ['crash-refusals', 'final-guards']:
            runner.crashes(refusals_only=True)
        if args.suite in ['all', 'concurrency', 'final-guards']:
            runner.concurrency()
        if args.suite in ['all', 'state', 'final-guards']:
            runner.state()
        runner.report['result'] = 'PASS'
        runner.record()
        print(json.dumps({'result': runner.report['result'], 'cases': len(runner.report['cases']),
            'runtime_processes': len(runner.report['processes']), 'runtime_sha256': runner.report['runtime_sha256'],
            'report': str(runner.output / 'report.json')}))
    except BaseException as error:
        runner.report['result'] = 'FAIL'
        runner.report['error'] = repr(error)
        runner.record()
        raise
    finally:
        runner.cleanup()


if __name__ == '__main__':
    main()
