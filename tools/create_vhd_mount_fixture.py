"""Generate redistributable BIOS boot fixtures for experimental IMGMOUNT -diff.

No Windows/game installation is read. All images are generated directly into
ZIP entries; no loose image is needed by the packaged runtime.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

SIZE = 32 * 16 * 63 * 512
BLOCK = 2 * 1024 * 1024
COUNTER_LBA = 5000


def boot(wait_for_key=False):
    code, labels, fixups = bytearray(), {}, []

    def emit(value):
        code.extend(bytes.fromhex(value))

    def pointer(name):
        emit('be')
        fixups.append((len(code), name, 2))
        code.extend(b'\0\0')

    def check():
        emit('72')
        fixups.append((len(code), 'failure', 1))
        code.append(0)

    emit('fa 31 c0 8e d8 8e c0 8e d0 bc 00 7c fb fc')
    pointer('counter')
    emit('ba 80 00 b8 00 42 cd 13')
    check()
    emit('fe 06 00 06 c7 06 02 06 44 49 c7 06 04 06 46 46')
    pointer('counter')
    emit('ba 80 00 b8 00 43 cd 13')
    check()
    emit('31 c0 bf 00 08 b9 00 01 f3 ab')  # Zero buffer for nonzero parent LBA 1.
    pointer('zero')
    emit('ba 80 00 b8 00 43 cd 13')
    check()
    emit('c6 06 00 08 a5')
    pointer('zero')
    emit('ba 80 00 b8 00 42 cd 13')
    check()
    emit('80 3e 00 08 00 75')
    fixups.append((len(code), 'failure', 1))
    code.append(0)
    if wait_for_key:
        emit('31 c0 cd 16')  # Keep the disk open while the save timer runs.
    emit('31 db b8 01 53 cd 15 bb 01 00 b9 03 00 b8 07 53 cd 15')
    labels['failure'] = len(code)
    emit('fa f4 eb fc')
    for name, offset, lba in [('counter', 0x600, COUNTER_LBA), ('zero', 0x800, 1)]:
        labels[name] = len(code)
        code.extend(struct.pack('<BBHHHQ', 16, 0, 1, offset, 0, lba))
    for offset, name, width in fixups:
        value = labels[name] - offset - 1 if width == 1 else 0x7c00 + labels[name]
        if width == 1:
            assert -128 <= value <= 127
            code[offset] = value & 255
        else:
            struct.pack_into('<H', code, offset, value)
    assert len(code) < 446
    return bytes(code).ljust(510, b'\0') + b'\x55\xaa'


def parent(dynamic, wait_for_key=False):
    footer = bytearray(512)
    footer[:8] = b'conectix'
    struct.pack_into('>IIQI4sIIQQHBBI', footer, 8, 2, 0x10000,
                     512 if dynamic else 0xffffffffffffffff, 1, b'test',
                     0x10000, 0x5769326b, SIZE, SIZE, 32, 16, 63, 3 if dynamic else 2)
    footer[68:84] = bytes.fromhex('00112233445546778899aabbccddeeff')
    struct.pack_into('>I', footer, 64, ~sum(footer) & 0xffffffff)
    payload = boot(wait_for_key) + b'\xa5' * 512
    if not dynamic:
        return payload + bytes(SIZE - len(payload)) + footer
    header = bytearray(1024)
    header[:8] = b'cxsparse'
    struct.pack_into('>QQIII', header, 8, 0xffffffffffffffff, 1536, 0x10000,
                     (SIZE + BLOCK - 1) // BLOCK, BLOCK)
    struct.pack_into('>I', header, 36, ~sum(header) & 0xffffffff)
    table = bytearray(b'\xff' * 512)
    struct.pack_into('>I', table, 0, 4)
    bitmap = b'\xc0' + bytes(511)
    return footer + header + table + bitmap + payload + bytes(BLOCK - len(payload)) + footer


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    summary = {}
    for kind, dynamic in [('fixed', False), ('dynamic', True), ('checkpoint', True)]:
        data = parent(dynamic, wait_for_key=(kind == 'checkpoint'))
        with zipfile.ZipFile(output / (kind + '.dosz'), 'w', zipfile.ZIP_DEFLATED) as archive:
            # Fixed ZIP metadata makes the parent timestamp repeatable.
            for name, content in [('BASE.VHD', data), ('DOSBOX.BAT',
                    b'@echo off\r\necho DIFF_CONFIG_OK>CONFIG.CFG\r\necho DIFF_SAVE_OK>SAVE.DAT\r\n'
                    b'imgmount 2 C:\\BASE.VHD -t hdd -fs none -diff C:\\CHILD.VHD\r\nboot -l c\r\n')]:
                info = zipfile.ZipInfo(name, (2026, 9, 22, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
        summary[kind] = {'parent_bytes': len(data), 'virtual_bytes': SIZE,
                         'parent_sha256': hashlib.sha256(data).hexdigest(),
                         'counter_lba': COUNTER_LBA, 'zero_override_lba': 1}
    (output / 'fixture.json').write_text(json.dumps(summary, indent=2))
    generate_mount_cases(output)
    print(json.dumps(summary, indent=2))


def generate_mount_cases(output):
    data = parent(True)
    command = 'imgmount 2 C:\\BASE.VHD -t hdd -fs none -diff C:\\CHILD.VHD'
    cases = ['unmount', 'legacy', 'corrupt-child', 'empty-child', 'mismatch', 'corrupt-parent', 'missing-parent', 'collision']
    for name in cases:
        batch = '@echo off\r\n' + command + '>RESULT.TXT\r\n'
        if name == 'unmount':
            batch += ('echo FORBIDDEN>BASE.VHD\r\necho FORBIDDEN>CHILD.VHD\r\n'
                      'imgmount -u 2>UNMOUNT.TXT\r\n' + command + '>REOPEN.TXT\r\n'
                      'imgmount -u 2>UNMOUNT2.TXT\r\necho UNMOUNT_OK>DONE.TXT\r\n')
        batch += 'exit\r\n'
        with zipfile.ZipFile(output / (name + '.dosz'), 'w', zipfile.ZIP_DEFLATED) as archive:
            entries = {'DOSBOX.BAT': batch.encode('ascii')}
            if name != 'missing-parent':
                entries['BASE.VHD'] = b'X' + data[1:] if name == 'corrupt-parent' else data
            if name == 'collision':
                entries['CHILD.VHD'] = b'archive name collision'
            for path, contents in entries.items():
                info = zipfile.ZipInfo(path, (2026, 9, 22, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, contents)
        seed = {}
        if name == 'legacy':
            # A real legacy save differs from the base. An identical entry is
            # correctly discarded by the union writer's existing deduplication.
            legacy = bytearray(data)
            legacy[3072] ^= 1  # Allocated logical sector 1 in the dynamic parent.
            seed['BASE.VHD'] = legacy
        elif name in ['corrupt-child', 'empty-child']:
            seed['CHILD.VHD'] = b'broken child' if name == 'corrupt-child' else b''
        elif name == 'mismatch':
            footer = bytearray(data[:512])
            struct.pack_into('>I', footer, 60, 4)
            footer[68] ^= 0x80
            footer[64:68] = bytes(4)
            struct.pack_into('>I', footer, 64, ~sum(footer) & 0xffffffff)
            header = bytearray(data[512:1536])
            header[40:56] = b'Wrong parent ID!'
            header[36:40] = bytes(4)
            struct.pack_into('>I', header, 36, ~sum(header) & 0xffffffff)
            seed['CHILD.VHD'] = footer + header + b'\xff' * 512 + footer
        if seed:
            with zipfile.ZipFile(output / (name + '.seed.pure.zip'), 'w', zipfile.ZIP_STORED) as archive:
                for path, contents in seed.items():
                    archive.writestr(path, contents)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    generate(parser.parse_args().output)
