"""Synthetic archive regression checks; all writes use a new isolated run root."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--template', required=True, type=Path)
    parser.add_argument('--packager', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    template = args.template.resolve()
    packager = args.packager.resolve()
    repo = Path(__file__).resolve().parents[1]
    source = repo / 'dosbox-pure-unleashed/embedded/phase3-smoke.dosz'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with zipfile.ZipFile(source) as archive:
        disk = archive.read('DISK.IMA')
    report = {'cases': {}, 'processes': [], 'scope': 'synthetic DOS/archive only'}
    report_path = output / 'report.json'

    def record():
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def launch(command, name, shared=None, expect_ok=True, settings=None):
        case = output / name
        case.mkdir()
        if settings is not None:
            (case / 'DOSBoxPure.cfg').write_text(json.dumps(settings), encoding='utf-8')
        persistent = shared or case
        for directory in ['localappdata', 'appdata', 'temp']:
            (persistent / directory).mkdir(exist_ok=True)
        env = dict(os.environ, LOCALAPPDATA=str(persistent / 'localappdata'),
                   APPDATA=str(persistent / 'appdata'), TEMP=str(persistent / 'temp'),
                   TMP=str(persistent / 'temp'))
        stdout_path, stderr_path = case / 'stdout.log', case / 'stderr.log'
        with stdout_path.open('wb') as stdout, stderr_path.open('wb') as stderr:
            process = subprocess.Popen([str(value) for value in command], cwd=case,
                env=env, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW)
            info = {'case': name, 'pid': process.pid, 'command': [str(x) for x in command],
                'persistence_root': str(persistent / 'localappdata'), 'temp_root': str(persistent / 'temp'),
                'allowed_roots': [str(persistent / 'localappdata'), str(case / 'saves'), str(case / 'system')],
                'allowed_files': [str(stdout_path), str(stderr_path), str(case / 'DOSBoxPure.cfg')]}
            report['processes'].append(info)
            record()
            try:
                code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise AssertionError('Owned synthetic process did not exit: ' + name)
        info['exit_code'] = code
        record()
        assert (code == 0) if expect_ok else (code != 0), (name, code, stderr_path.read_text(errors='replace'))
        assert not list((persistent / 'temp').rglob('*')), (name, 'unexpected temporary files')
        return case

    def read_saved(path):
        with zipfile.ZipFile(path) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    def archive_fixture(name, batch):
        path = output / (name + '.dosz')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('DOSBOX.BAT', batch.encode('ascii'))
            archive.writestr('GAME.CFG', b'BASE_CONFIG\r\n')
            archive.writestr('DISK.IMA', disk)
        return path

    first_batch = ('@echo off\r\necho CONFIG_UPDATED>GAME.CFG\r\n'
        'echo DOS_SAVE_OK>SAVE.DAT\r\nimgmount a c:\\DISK.IMA -t floppy\r\n'
        'if exist a:\\IMAGE.OK echo INTERNAL_IMAGE_OK>IMAGE.OK\r\nexit\r\n')
    second_batch = ('@echo off\r\ncopy C:\\SAVE.DAT C:\\READBACK.DAT\r\n'
        'copy C:\\GAME.CFG C:\\CFGBACK.DAT\r\n'
        'imgmount a c:\\DISK.IMA -t floppy\r\n'
        'if exist a:\\IMAGE.OK echo INTERNAL_IMAGE_RELOAD_OK>RELOAD.OK\r\nexit\r\n')
    first_archive = archive_fixture('smoke-write', first_batch)
    second_archive = archive_fixture('smoke-read', second_batch)
    defaults = output / 'defaults.json'
    defaults.write_text(json.dumps({'screen_width': '320', 'screen_height': '240',
        'dosbox_pure_cycles': '3000', 'dosbox_pure_menu_time': '0'}), encoding='utf-8')
    package_id = 'org.dbps.upstream.sync.smoke'

    def package(name, archive, expect_ok=True):
        manifest = output / (name + '.json')
        exe = output / (name + '.exe')
        manifest.write_text(json.dumps(dict(format_version=1, package_id=package_id,
            title='Synthetic upstream-sync smoke', template=str(template), archive=str(archive),
            output=str(exe), default_config=str(defaults))), encoding='utf-8')
        result = subprocess.run([str(packager), str(manifest)], capture_output=True, text=True, timeout=60)
        (output / (name + '.build.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        assert (result.returncode == 0) if expect_ok else (result.returncode != 0), result.stdout + result.stderr
        if not expect_ok:
            assert not exe.exists()
        return exe

    first_exe = package('embedded-write', first_archive)
    second_exe = package('embedded-read', second_archive)
    shared = output / 'shared'
    shared.mkdir()
    saved = shared / 'localappdata/DOSBoxPureStandalone' / package_id / 'embedded.pure.zip'
    launch([first_exe], 'embedded-first', shared)
    values = read_saved(saved)
    assert values['GAME.CFG'].strip() == b'CONFIG_UPDATED'
    assert values['SAVE.DAT'].strip() == b'DOS_SAVE_OK'
    assert values['IMAGE.OK'].strip() == b'INTERNAL_IMAGE_OK'
    report['cases']['embedded-first'] = {'config_write': True, 'save_write': True, 'internal_floppy': True}
    launch([first_exe], 'embedded-relaunch', shared)
    renamed = output / 'RenamedSmoke.exe'
    shutil.copyfile(second_exe, renamed)
    launch([renamed], 'embedded-read-after-rename', shared)
    values = read_saved(saved)
    assert values['READBACK.DAT'].strip() == b'DOS_SAVE_OK'
    assert values['CFGBACK.DAT'].strip() == b'CONFIG_UPDATED'
    assert values['RELOAD.OK'].strip() == b'INTERNAL_IMAGE_RELOAD_OK'
    assert 'DISK.IMA' not in values
    report['cases']['embedded-relaunch'] = {'same_package_persistence': True, 'rename': True, 'saved_file_read': True, 'saved_config_read': True}

    # A cwd configuration selects isolated normal-mode paths and immediate EXIT.
    def external_settings(name):
        case = output / name
        return {'path_saves': str(case / 'saves'), 'path_system': str(case / 'system'),
            'dosbox_pure_menu_time': '0', 'screen_width': '320', 'screen_height': '240'}

    for name, switch in [('external-file', []), ('external-memory', ['-memory-archive'])]:
        case = launch([template] + switch + [first_archive], name, settings=external_settings(name))
        saves = list((case / 'saves').glob('*.pure.zip'))
        assert len(saves) == 1, (name, saves)
        got = read_saved(saves[0])
        assert got['GAME.CFG'].strip() == b'CONFIG_UPDATED'
        assert got['SAVE.DAT'].strip() == b'DOS_SAVE_OK'
        assert got['IMAGE.OK'].strip() == b'INTERNAL_IMAGE_OK'
        report['cases'][name] = {'config_write': True, 'save_write': True, 'internal_floppy': True}

    corrupt = output / 'corrupt.dosz'
    corrupt.write_bytes(b'This is not a ZIP or DOSZ package.\r\n')
    package('corrupt-rejected', corrupt, expect_ok=False)
    empty = output / 'empty.dosz'
    empty.touch()
    launch([template, '-memory-archive', empty], 'empty-memory-rejected', expect_ok=False,
        settings=external_settings('empty-memory-rejected'))
    launch([template, '-memory-archive', output / 'missing.dosz'], 'missing-memory-rejected', expect_ok=False,
        settings=external_settings('missing-memory-rejected'))
    report['cases']['invalid-inputs'] = {'corrupt_builder_rejected': True, 'empty_memory_rejected': True, 'missing_memory_rejected': True,
        'corrupt_embedded_resource_runtime': 'not exercised; error dialog requires separate acceptance'}
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    report['source_fixture_sha256'] = source_hash
    report['result'] = 'PASS'
    record()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
