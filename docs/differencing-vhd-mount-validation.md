# Experimental differencing VHD mount validation

Date: 2026-09-22. Branch: `Dev-Diff-Virtual-Disk-Support`.

This validates milestone 2 using generated BIOS guests only. No Windows
installation, installation media, or existing user save was opened or modified.
It does not establish Windows 98 acceptance for the new differencing path.

## Tested behavior

The x64 Release standalone runtime was built from the changed core and packaged
with the installed `makegame.exe`. Each executable embeds a deflated DOSZ with
`BASE.VHD` and a `DOSBOX.BAT` that mounts an experimental child and boots BIOS
disk C. Images are generated directly as ZIP entries by
`tools/create_vhd_mount_fixture.py`; the runtime needs no loose disk image.

The boot sector increments a persistent byte at logical sector 5000, writes a
`DIFF` marker, writes zeros over a nonzero parent sector, reads the zeros back,
then requests APM shutdown. The startup batch also writes ordinary configuration
and save files. `tools/inspect_vhd_mount_save.py` independently reads parent and
child from their ZIPs and checks their effective sectors and entry lists.

| Check | Result |
| --- | --- |
| Fixed and dynamic parent boot/write/APM shutdown | Passed |
| Relaunch counter advances from 1 to 2 | Passed for both parent types |
| Renamed executable retains dynamic child | Passed, same package ID |
| Explicit zero override survives relaunch | Passed for both parent types |
| Unchanged boot sector falls back to parent | Passed |
| Full parent absent from save ZIP | Passed |
| Save timer publishes child while guest waits with disk open | Passed |
| Relaunch after terminating host after a completed checkpoint | Passed |
| Configuration and ordinary save files | Passed alongside child |
| Numeric unmount, reopen, unmount and host exit | Passed |
| DOS attempts to overwrite mounted parent/child | Rejected; bytes preserved |
| Modified legacy full-parent save | Rejected; saved bytes preserved |
| Corrupt, empty or wrong-parent child | Rejected; saved bytes preserved |
| Corrupt/missing parent or child name collision | Rejected; no new child retained |
| Ordinary DOS/internal floppy fixture, twice | Passed, host exit code 0 |
| Release x64 build | Passed |
| AddressSanitizer and native Windows VHD interop | 33,714 checks passed |

The native Windows test opens synthetic fixed/dynamic parent chains with
`OpenVirtualDisk` and checks type-4 metadata. It never attaches a disk. Adapter
tests include short I/O, failed/truncated seeks, 64-bit parent reads and the child
size ceiling. Run `tools/Test-DifferencingVhd.ps1 -AddressSanitizer -WindowsInterop`.

## Size measurements

Both virtual disks contain 16,515,072 bytes. After the two sector writes, the
child contains two allocated 2 MiB blocks and occupies 4,198,400 bytes as a stored
ZIP entry. The fixed parent is 16,515,584 bytes; the dynamic parent is 2,100,224
bytes. An empty mounted child is 3,072 bytes. The fixed case demonstrates avoiding
a full-parent save. The deliberately tiny dynamic fixture is smaller than its
child, so this test does not establish universal savings. Windows 98 save size,
memory use and latency remain to be measured with the new path.

Parent SHA-256 values from the deterministic generator:

```text
fixed   7eb1aa52f4054f8a562c45a7985dc4e5f746cbc6660ae5afb457b058774b29d8
dynamic 39d24284610aa605479a6690f1534df66cf30465ca9b764e4caf2331e46da857
```

## Evidence and scope

Ignored local artifacts are under `work/diff-vhd-runtime/`: generated `inputs/`,
packaged executables, process stdout/stderr, `processes.jsonl` and isolated
`localappdata/DOSBoxPureStandalone/<test-package-id>/embedded.pure.zip` saves.
The test process's `LOCALAPPDATA` was deliberately scoped there. This is the
normal persistence mechanism with a test root, not an extraction destination.

The first dynamic guest completed APM shutdown and saved successfully, then its
host process was forcibly closed because its hidden window was inaccessible.
Renamed-dynamic and both fixed runs used normal host-window close. The unmount,
negative and ordinary DOS cases exited themselves with code 0.

The `checkpoint` fixture waits in BIOS keyboard input after its sector writes.
The child was independently inspected while that guest was still running, then
the host was terminated after the completed save. Relaunch advanced the counter
from 1 to 2, again persisted with the disk open, and normal host-window close
completed. This checks recovery of a completed checkpoint, not interruption
during archive writing. The final rebuild also passed the unmount/reopen case.

Process Monitor validation is pending. The first two PMLs were only 976 bytes
and their exported CSV contained no events; they are excluded as evidence.
After restoring the window, its status reported capture disabled. Automation
input did not enable capture in the elevated window, so manual Ctrl+E was
requested. Do not infer the runtime no-extraction result from code or archive
inspection alone. Keep this gate open until a nonempty capture covers process
startup, child writes and host exit and its file operations have been inspected.

This increment schedules saves while the child remains open, but continuous-write
checkpoint deadlines, crash/power-loss recovery, injected host-save failures,
concurrent processes, save-state behavior and guest reboot still require the
persistence lifecycle milestone. The ZIP writer updates in place. Package-level
strong parent identity and recoverable migration remain separate milestones.

## Reproduction

Generate the fixtures in an ignored directory, then use the current Release
template when packaging; an installed template predates this command.

```powershell
python tools/create_vhd_mount_fixture.py work/diff-vhd-runtime/inputs
makegame.exe work/diff-vhd-runtime/inputs/dynamic.dosz work/diff-vhd-runtime/Test.exe `
  --template <rebuilt-DOSBoxPureStandAlone.exe> --package-id org.dbps.diff.test.dynamic
```

For an isolated run set the launching process's `LOCALAPPDATA` to an absolute
test directory, start the executable, and let the synthetic guest shut down.
Inspect the save without unpacking any entries:

```powershell
python tools/inspect_vhd_mount_save.py work/diff-vhd-runtime/inputs/dynamic.dosz `
  <test-root>/DOSBoxPureStandalone/org.dbps.diff.test.dynamic/embedded.pure.zip --counter 1
```

Repeat with the same package ID and expect counter 2; repeat with `fixed.dosz`.
For `checkpoint.dosz`, inspect while its black-screen guest waits for a key.
Negative cases use their own package IDs and their matching generated
`*.seed.pure.zip` as the initial `embedded.pure.zip` where supplied. Never seed a
real user's save directory. `tools/inspect_vhd_mount_cases.py` checks results and
compares seeded bytes; its package prefix/suffix are configurable.
