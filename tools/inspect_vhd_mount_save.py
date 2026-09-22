"""Check the synthetic VHD runtime save without extracting any archive entry."""
import argparse
import json
import struct
import zipfile


def read_sector(image, sector, parent=None):
    footer = image[-512:]
    kind = struct.unpack_from('>I', footer, 60)[0]
    if kind == 2:
        return image[sector * 512:(sector + 1) * 512], True
    header = struct.unpack_from('>Q', footer, 16)[0]
    table, _, _, block = struct.unpack_from('>QIII', image, header + 16)
    sectors = block // 512
    entry = struct.unpack_from('>I', image, table + (sector // sectors) * 4)[0]
    within = sector % sectors
    present = entry != 0xffffffff and image[entry * 512 + within // 8] & (0x80 >> (within % 8))
    if not present:
        return (read_sector(parent, sector)[0] if parent is not None else bytes(512)), False
    bitmap = ((sectors + 7) // 8 + 511) // 512 * 512
    start = entry * 512 + bitmap + within * 512
    return image[start:start + 512], True


def inspect(archive_path, save_path, counter):
    with zipfile.ZipFile(archive_path) as archive:
        parent = archive.read('BASE.VHD')
    with zipfile.ZipFile(save_path) as saved:
        assert 'BASE.VHD' not in saved.namelist(), 'full parent was copied into save'
        child = saved.read('CHILD.VHD')
        assert saved.read('CONFIG.CFG').strip() == b'DIFF_CONFIG_OK'
        assert saved.read('SAVE.DAT').strip() == b'DIFF_SAVE_OK'
        entries = {entry.filename: entry.file_size for entry in saved.infolist()}
    assert child[:512] == child[-512:]
    assert struct.unpack_from('>I', child, 60)[0] == 4
    assert child[552:568] == parent[-512 + 68:-512 + 84]
    assert read_sector(parent, 1)[0] == b'\xa5' * 512
    assert read_sector(child, 1, parent) == (bytes(512), True), 'zero override was lost'
    data, present = read_sector(child, 5000, parent)
    assert present and data[0] == counter and data[2:6] == b'DIFF', (data[:8], counter)
    assert read_sector(child, 0, parent)[0] == read_sector(parent, 0)[0]
    return {'counter': data[0], 'zero_override': True, 'boot_sector_matches_parent': True,
            'parent_not_in_save': True, 'parent_bytes': len(parent), 'child_bytes': len(child), 'entries': entries}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('save')
    parser.add_argument('--counter', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.archive, args.save, args.counter), indent=2))
