# Differencing VHD package identity validation

Date: 2026-09-22. Branch: `Dev-Diff-Virtual-Disk-Support`.

Milestone 3 binds a standard child to the intended immutable parent and package.
All testing uses generated synthetic disks in ignored `work/diff-vhd-identity/`.
No Windows installation or existing user save was read or modified.

## Interface

Add this optional object to a format-1 makegame manifest:

```json
"differencing_vhd": {
  "disk_id": "win98",
  "parent": "BASE.VHD",
  "child": "CHILD.VHD"
}
```

The builder emits format-2 metadata, with computed `parent_sha256`, raw-byte
`parent_uuid` hex and decimal-string `parent_virtual_size`. The digest covers
the entire uncompressed VHD file, including metadata, not the ZIP encoding or
just allocated logical sectors. Identical parent bytes survive ZIP repacking;
logical equivalence with different VHD bytes is not sufficient.

Runtime templates advertise this feature with RCDATA 104 containing the ASCII
bytes `DBPVHD_IDENTITY_1` and a terminating NUL. The packager refuses older
templates for this declaration. Ordinary packages still emit format 1. Older
runtimes reject format 2 rather than ignoring the required identity fields.
Startup still explicitly uses `IMGMOUNT ... -diff ...`.

Before mounting, the Windows host computes SHA-256 with Windows CNG through the
read-only DOS archive source using a 64 KiB scratch buffer. This uses the
[BCrypt hash lifecycle](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptcreatehash).
No loose parent, child, or binding is created. Hashing reads the complete parent
on each mount; large-image startup cost remains to be measured. Existing ZIP
decompression and caching behavior is retained.

## Binding record

The child is stored with a 512-byte `.DBI` entry derived from its filename in
the same `.pure.zip`. This is writable save metadata, not an extracted host file.
The following fixed byte ranges define version 1; integers are big-endian and
strings are ASCII with zero-filled unused space.

| Offset | Length | Field |
| --- | --- | --- |
| 0 | 8 | `DBPVDI01` magic/version |
| 8 | 128 | Package ID |
| 136 | 64 | Disk ID |
| 200 | 12 | Canonical parent name |
| 212 | 12 | Canonical child name |
| 224 | 32 | Parent SHA-256 |
| 256 | 16 | Parent UUID, raw VHD bytes |
| 272 | 8 | Virtual disk size |
| 280 | 16 | Child UUID, raw VHD bytes |
| 296 | 4 | Original parent timestamp used by the child |
| 300 | 212 | Reserved, zero |

After verifying the actual parent fingerprint, reopening uses the timestamp
from this binding and then the codec checks it against the child's header.
This retains standard child metadata across changes to the ZIP entry timestamp.
All remaining bytes must match the current declared identity and child UUID.

Missing, corrupt, orphaned, copied or mismatched bindings fail without adopting
or overwriting saved disks. An undeclared mount cannot bypass a binding.
Unbound children from milestone 2 require explicit migration into this format.
Mounted binding names share the parent/child lease and cannot be overwritten by
ordinary DOS commands. New child/binding construction completes in memory before
the save timer can publish it. Transaction-safe ZIP publication remains separate
work; the current writer is still in-place.

## Automated checks

Release x64 runtime and Release makegame builds completed without warnings or
errors. `Test-DifferencingVhd.ps1 -AddressSanitizer -WindowsInterop` passed 34,251
checks, including binding-byte corruption, field changes, child substitution,
canonical paths, integer overflow and retained-timestamp codec semantics.
Windows independently opened generated type-4 chains without attaching disks.

The integration test builds its inputs and executables, reads PE metadata back,
seeds only isolated synthetic save roots, runs a small DOS BIOS-I/O program,
then independently inspects the child and binding inside the saved ZIP. The
program increments a sector counter and writes/reads an explicit zero override.
Every test host exits itself; no GUI automation or forced process close is
required for successful runs. Existing startup configuration initialization runs
this short batch twice per fresh process, so successful counters advance by 2.

The final 21-case matrix (`work/diff-vhd-identity/run2/report.json`) passed fixed
and dynamic parents, ordinary version-1 unbound mounts, a rejected new mount
leaving no child behind, a corrupt retained timestamp, and parent-byte changes with unchanged UUID/size,
package/disk/path changes, incorrect metadata fingerprints/UUIDs/sizes, missing
and orphaned bindings, corrupt bindings, swapped children and undeclared mounts.
Saved child/binding bytes remained unchanged after each rejected mount. A
renamed executable containing repacked identical parent bytes with a different
ZIP timestamp advanced the counter from 2 to 4 and retained identical binding
bytes. Older templates, a damaged parent and an invalid disk ID were rejected
by the builder. The mounted binding also resisted DOS redirection writes.

The ordinary Phase 3 DOS/internal-floppy smoke package was separately rebuilt
with the new template and packager, launched twice, and exited with code 0 both
times. Its saved ZIP contained the expected `PHASE3.OK` and `PHASE3.IMG` sentinels.
Logs and executable are under `work/diff-vhd-identity/`.

Reproduce with a rebuilt runtime and packager:

```powershell
python tools/test_vhd_identity_runtime.py `
  --packager <rebuilt-makegame.exe> `
  --template <rebuilt-DOSBoxPureStandAlone.exe> `
  --old-template <previous-runtime.exe> `
  --output work/diff-vhd-identity/new-run
```

The output directory must not already exist. `report.json` records case results
and process IDs; each process has separate stdout/stderr. Raw artifacts are
local test evidence, not committed game content.

## Remaining acceptance

Process Monitor capture is blocked by the host environment. After a fresh launch
and manual activation attempt, the user reported its error: "Another version of
the Process Monitor driver is already loaded. A reboot is required to run this
version." No reboot or driver manipulation was performed. The previous empty
PMLs do not prove no extraction. After the user reboots, capture a fresh test run
and inspect its file operations before closing this acceptance gate.

This is still an experimental feature. Recoverable migration, atomic save
publication, concurrent writers, disk/save-state generation consistency and real
Windows 98 boot/shutdown/reboot acceptance remain open. The standard child alone
does not carry the package binding; preserve both entries when backing up saves.
