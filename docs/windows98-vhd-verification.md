# Windows 98 in an embedded VHD: verification

Date: 2026-09-22. Runtime: the installed 2026.08.26 Windows x64 template.

## Result

An already-installed Windows 98 Second Edition dynamic VHD can remain inside a
deflated ZIP/DOSZ embedded in a single executable. The existing runtime booted it,
saved a file created inside Windows, and recovered that file after a clean guest
shutdown and launch of an identical executable with a different filename and
directory. No runtime source change was needed.

This satisfies single-file distribution and direct embedded-content access with
the project's permitted persistent overlay. It does **not** mean zero host files:
the current archive-file overlay stores the **entire modified VHD**, uncompressed,
inside `embedded.pure.zip`. It is not a small sector-difference file. Normal host
graphics-driver caches were also observed.

Windows installation into an embedded blank VHD was not exercised. The supplied
disk was already installed by the user. The existing Pure installed-OS wizard
creates/opens external system-directory VHDs; it is a different path from the
archive-contained disk mounted by the batch file below.

## Tested package

| Item | Value |
| --- | --- |
| Source | User-supplied `Windows 98 Second Edition.vhd` |
| VHD type | Dynamic, type 3; FAT16 partition |
| Physical VHD size | 276,895,232 bytes |
| Virtual disk size | 549,642,240 bytes |
| Geometry | 71 cylinders, 240 heads, 63 sectors, 512 bytes/sector |
| Deflated DOSZ size | 92,222,555 bytes |
| Packaged EXE size | 95,143,424 bytes |
| Package ID | `org.dbps.verify.win98.20260922` |
| Post-shutdown overlay size | 276,996,273 bytes |
| Fresh-run peak private memory | 1,516,216,320 bytes (about 1.41 GiB) |

Archive entries:

```text
DOSBOX.BAT
WIN98.VHD
```

`DOSBOX.BAT`:

```bat
@echo off
imgmount 2 C:\WIN98.VHD -t hdd -fs none -size 512,63,240,71
boot -l c
```

`C:\WIN98.VHD` here is the DOS archive filesystem path, not a Windows host path.
The numeric `2` selects BIOS hard disk 0, which becomes the guest's boot disk.
The geometry is specific to this VHD and must not be copied blindly to another.

Embedded configuration:

```json
{
  "dosbox_pure_memory_size": "64",
  "dosbox_pure_cpu_type": "pentium_slow",
  "dosbox_pure_cpu_core": "dynamic",
  "dosbox_pure_cycles": "auto",
  "dosbox_pure_svgamem": "4"
}
```

Build command, with these files in the current authoring directory:

```powershell
makegame.exe win98.dosz Win98.exe `
  --package-id org.dbps.verify.win98.20260922 `
  --title "Windows 98 embedded VHD verification" `
  --config defaults.json
```

Only `Win98.exe` was placed in its launch directory. The renamed test directory
likewise contained only `Win98-Renamed.exe`. No external archive, VHD, installation
ISO, batch file, or command-line content argument was supplied at runtime.

## Boot, write, shutdown, and relaunch

1. Launched the EXE with a new package save directory. Its embedded batch mounted
   the VHD and booted Windows without a DOSBox content/executable-selection menu.
2. Reached the Windows desktop. The user handled the first guest password prompt.
3. Created `C:\WINDOWS\Desktop\New Text Document.txt` inside Windows and saved
   `4:54 AM 9/22/26` using Notepad's Time/Date command.
4. Shut Windows down through Start > Shut Down. The runtime logged the BIOS APM
   power-down request and saved filesystem modifications. Then closed the host.
5. Copied the same EXE to a different directory as `Win98-Renamed.exe`, retaining
   its embedded package ID. It booted and reopened the document with exactly the
   saved contents. Performed a second clean guest shutdown.
6. Independently parsed the dynamic VHD and FAT16 filesystem directly from the
   overlay ZIP in memory. The document existed after both shutdowns. It did not
   exist in the original source VHD. No loose extracted VHD was needed for this
   inspection.
7. Built a separate fresh package ID with no existing overlay and traced another
   launch from process creation through Windows startup. This additional run
   reached the desktop and was closed using the host window's close button; it
   was a first-start I/O audit, not another clean guest-shutdown test.

The guest showed an NE2000 adapter warning during the renamed run. The direct
batch route bypasses the installed-OS helper's hardware setup. Network operation
was not tested. The observed guest password/network dialogs mean a completely
unattended desktop experience is not established by this test.

After either clean Windows shutdown, the host remained open at
`PRESS ANY KEY TO RETURN TO START MENU`. Automatic host exit after Windows shuts
down is therefore not provided by this package configuration.

## Persistence and source path

The package's writable directory is:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\org.dbps.verify.win98.20260922\
```

After shutdown, `embedded.pure.zip` contained:

| Entry | Uncompressed bytes | Stored bytes | ZIP method |
| --- | ---: | ---: | --- |
| `WIN98.SKC` | 100,831 | 100,831 | Store |
| `WIN98.VHD` | 276,895,232 | 276,895,232 | Store |

The seek-cache entry is small auxiliary decompression state. The VHD entry is the
whole writable replacement for the immutable base file. The base VHD remains
embedded in the EXE; later launches find the modified VHD in the overlay.

Relevant existing implementation:

- `dosbox-pure/dosbox_pure_libretro.cpp`: memory-backed content reaches the normal
  ZIP drive; archive disk-image paths use mounted DOS files.
- `dosbox-pure/src/dos/drives.cpp`, `FindAndOpenDosFile`: opens the internal DOS
  path without requiring a loose host disk image.
- `dosbox-pure/src/ints/bios_disk.cpp`, `sparseVhd`: dynamic VHD sector I/O uses
  the `DOS_File` abstraction.
- `dosbox-pure/src/dos/drive_union.cpp`, `Union_WriteHandle::Write`: the first
  modification copies the complete underlying file into the writable memory
  layer. Closing a dirty handle schedules persistence. This explains the full
  VHD save and its RAM/storage cost.
- `dosbox-pure/dosbox_pure_run.h`, `BootOS` / `MountOSIMG`: the installed-OS menu
  uses a system-directory filename and `fopen_wrap`; new-OS creation exports a
  blank image there. Its sector-difference option must not be confused with the
  archive-file overlay tested here.

## Process Monitor evidence

Local evidence is under `work/win98-vhd-verification-20260922/` (ignored by Git).
PML captures retain the original events; exported per-process CSVs and JSON
summaries permit inspection without loading whole-system traces.

| Capture | PID / target events | Scope |
| --- | --- | --- |
| `win98-first.pml` | 36388 / 3,959 | Initial boot after capture initialization; does not include process creation |
| `win98-save.pml` | 36388 / 80,616 | First session's saved-file/shutdown interval through process exit |
| `win98-second.pml` | 568 / 84,141 | Renamed EXE from process creation through desktop operation |
| `win98-fresh.pml` | 42820 / 75,419 | New package ID, no pre-existing overlay; complete process lifetime, exit status 0 |

The first capture alone is insufficient to prove the entire initial startup.
The separate fresh-package capture addresses that boundary. The analyzer checks
successful writes, creation-capable opens, resizing, rename/delete operations,
Temp paths, physical disk/archive paths, and access to the original installation
directory. Creation-capable opens are conservatively reported even when an
existing file was opened rather than newly created.

The fresh trace's process-exit event reports approximately 1.41 GiB peak private
memory despite 64 MiB of emulated guest RAM. Direct archive access therefore
avoids extraction but does not imply a small host-memory footprint for this
compressed, writable VHD route.

The runtime traces showed no loose VHD/DOSZ/ISO or `DOSBOX.BAT` host access, no
content in Temp, and no access to the original installed VHD. Package persistence
was written under the configured LocalAppData root. Additional observed writes
were the runtime's one-byte persistence-directory probes (deleted immediately),
explicitly redirected diagnostic logs, UI-automation pipes, NTFS metadata, and
NVIDIA driver cache/profile files. Those host-side writes are not archive or VHD
extraction, but prohibit describing the result as literally leaving no artifacts.

Visual evidence: `first-desktop.png`, `marker-first.png`, `marker-second.png`,
`first-shutdown.png`, `fresh-boot.png`, and `fresh-login.png` (the latter captures
the fresh run's desktop). `disk-inspection-first.json` and
`disk-inspection-second.json` record the independently decoded marker and ZIP
entry sizes.

## Integrity and coverage limits

Source VHD SHA-256 before and after the tests:

```text
2c7d89ae78504b73abe885d53515dc98cc3f94efddb4ebc8fea5418d9021196e
```

Original and renamed package SHA-256:

```text
1beada474c660803f9217938763b82c77aaab47675b8e7fbbfed155957465632
```

Runtime template SHA-256:

```text
685ed53fcd61eab30828315b807a772981cbdd6c8e75fc7683b288f625d5b349
```

Source revisions inspected: root `ea2d978675c66ff1def80464eb588a428fa7c805`,
core `2697af237c9f5b9ed1e96d6e3cdff9c97fddeb32`, frontend
`8c698bea263960e6284366bc03cfee97d6267572`. `final-integrity.json` records the
unchanged source/package hashes, single-file launch directories, and absence of
remaining test processes.

This is evidence for this VHD and the tested Windows build. It does not establish
compatibility with every Windows 98 installation, large VHDs, games, networking,
or power-loss recovery. A full Windows installation from ISO into an already
embedded blank VHD remains untested. Earlier synthetic fixed/dynamic VHD boot and
write tests are retained in `work/vhd-verification-20260921/`.
