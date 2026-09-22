# Differencing VHD development plan

Development branch: `Dev-Diff-Virtual-Disk-Support` (the requested display name
contained spaces, which Git refs cannot contain). Approved 2026-09-22.

## Objective and invariant

Keep a completed Windows 98 installation as an immutable fixed or dynamic VHD in
the embedded ZIP/DOSZ. Present a standard type-4 differencing VHD child to the
guest and persist that child inside `embedded.pure.zip`. Never extract either
image or reconstruct the embedded archive as a host file. Preserve existing
package persistence roots and ordinary DOSBox Pure behavior.

The [runtime verification](windows98-vhd-verification.md) established that the
current whole-file overlay works but stores 276,895,232 bytes for the VHD. A
subsequent read-only logical-sector comparison found only 493 changed sectors
(252,416 bytes), including five explicit zero overrides. A compacted standard
child with 2 MiB blocks is estimated at 29.4 MB before ZIP compression and minor
metadata; this estimate is not an implemented-runtime measurement.

## Ordered implementation milestones

1. **Disk-layer foundation:** correct original logical-sector reads and error
   handling; validate a read-only VHD parent; implement standard child headers,
   BAT, sector bitmaps and parent fallback. Start with one child over a fixed or
   dynamic parent, 512-byte sectors and 2 MiB child blocks. Test independently.
2. **Mount/overlay integration:** open parent content from the immutable underlay,
   create child state through the existing memory-backed writable overlay, and
   mount it before guest boot. Derive geometry from virtual size/metadata rather
   than child physical size. Keep the full base VHD out of save ZIPs.
3. **Identity/packaging:** declare disk identity and opt-in behavior in package
   metadata; calculate the strong parent fingerprint at build time. Bind children
   to package ID, canonical disk path, VHD UUID, virtual size and fingerprint.
   Repacking unchanged bytes and renaming an EXE must retain saves. Parent
   mismatches must fail clearly without replacing or silently ignoring saves.
4. **Migration:** detect legacy full-VHD overlay entries. Build a child from
   logical differences, prove parent-plus-child sector equivalence, then replace
   the old representation transactionally. Keep a recoverable original until
   verification succeeds; never silently reset a user's installation.
5. **Persistence lifecycle:** checkpoint dirty open children and flush on guest
   shutdown, emulator exit, reboot and unmount. Define failed-save recovery,
   concurrent-writer exclusion and save-state/rewind generation consistency.
   Any transaction staging contains writable save data only inside the allowed
   persistence directory, never extracted base content.
6. **Runtime acceptance/optimization:** exercise Windows 98 and the archive
   regression matrix with Process Monitor; measure memory, save size and latency.
   Assess smaller blocks, compression and compaction separately after correctness.

## Findings that constrain the implementation

- `bios_disk.cpp::differencingDisk` is the proprietary `FFDD` format written to
  an external `*-CDRIVE.sav`; it is not a standard differencing VHD.
- `imageDisk::Write_AbsoluteSector` compares a differencing write against a raw
  file offset. Dynamic VHD parents require logical-sector translation instead.
- `sparseVhd::Init` accepts only type 3. `SeeBlock` normalizes writable bitmaps;
  this must never run on a type-4 child, whose clear bits mean parent fallback.
- Writes of zeros over nonzero parent sectors must remain explicit overrides.
  Missing child sectors and explicitly zero child sectors are distinct states.
- `IMGMOUNT -fs none` uses physical file size to recognize hard disks; a valid
  empty child is small. It must use validated VHD metadata for this path.
- `Union_WriteHandle` clones an entire underlay file on first write, so the base
  VHD must only be opened read-only; create a separate child in the writable layer.
- The current ZIP writer stores entries uncompressed and updates saves in place.
  Existing file-close save scheduling alone is insufficient for open child disks.
- The parent must be a completed installation. Installing into a blank parent
  necessarily places the installation itself in the child.

## Acceptance criteria

- Independent sector tests: fixed/dynamic parent fallback, nonzero and zero
  overrides, return to original data, block boundaries and previously sparse
  parent blocks. All short reads/writes and malformed metadata fail explicitly.
- Validate bounds, checksums, parent mismatch, unsupported chains, truncated
  children, allocation limits and write failures. No silent memory-only fallback.
- Windows 98 file/registry changes survive shutdown, reboot, unmount and renamed
  EXE relaunch. Migrated disk contents match the legacy saved disk sector for sector.
- Archive regressions cover DOS boot, configuration writes, saves, internal disk
  images, repeated launch and corrupt/missing package behavior.
- Procmon captures prove no loose VHD/base archive writes and no content extraction
  into Temp or executable/cache directories. Persistence uses documented roots.
- Root and affected submodule commits must all be reachable on GitHub before
  publishing a parent commit that references them. ZillaLib remains unchanged.

## Status

The first experimental disk-layer increment is implemented in
`dosbox-pure/src/ints/vhd_differencing.h`. It reads immutable fixed/dynamic
parents and creates, validates, reads and writes standard type-4 children through
exact random-access source interfaces. It has no host-path or extraction code.
Parent fallback, explicit zero overrides and returning sectors to the parent
are implemented. The decoder bounds metadata and allocation tables, rejects
overlapping extents and unsupported chains, and stops child access on I/O errors.

Validation on 2026-09-22: the synthetic sector suite and its AddressSanitizer run
passed. Coverage includes fixed/dynamic parents, bitmap/block boundaries,
create/write/reopen equivalence, a 5 GiB virtual disk, malformed metadata, parent
mismatch and injected short reads/writes. Windows `OpenVirtualDisk` independently
opened generated parent/child fixtures for both parent types, resolved their
parents, and reported type 4 with the expected size, block size and timestamp.
The Windows test only creates synthetic fixtures under ignored test output and
never attaches a disk. Run `tools/Test-DifferencingVhd.ps1 -WindowsInterop` or
`-AddressSanitizer`; detailed limits are in `dosbox-pure/tests/README.vhd.md`.

Milestone 2 now connects `imageDisk`, `DOS_File` and the memory-backed ZIP overlay
through an explicit experimental command:

```text
imgmount 2 C:\BASE.VHD -t hdd -fs none -diff C:\CHILD.VHD
boot -l c
```

The parent opens directly from the immutable ZIP underlay; the child opens or
is created directly in the memory overlay, bypassing ordinary full-file
copy-on-write. Footer geometry is used rather than physical image size. The
initial contract is two distinct root-level DOS 8.3 `.VHD` names on the same
persistent union drive, with no `-size` argument or host-file fallback. Legacy
full-parent saves are rejected without modifying their contents. Existing
children, including empty/corrupt ones, are never silently reset.

The adapter bounds writable child storage to 2,147,483,647 bytes, validates exact
seeks and split DOS transfers, and protects mounted filenames from replacement.
Numeric unmount releases the disk while retaining the archive and child entry;
unmounting the containing drive releases the disk first. Sector updates schedule
existing ZIP persistence while the child is open. A codec I/O fault disables
subsequent overlay publication for that session. Save states and rewind are
refused while a child is mounted until generation consistency is implemented.

[Mount validation](differencing-vhd-mount-validation.md) records synthetic BIOS
boot/write/shutdown/relaunch, explicit zero overrides, a renamed executable,
unmount/reopen, failure preservation and ordinary DOS/internal-floppy regression
results. Release x64 builds and 33,714 AddressSanitizer/native-format checks pass.
The existing FFDD path and existing Windows 98 installations/saves are unchanged.

Milestone 3 implements package metadata opt-in and strong parent fingerprints,
as described below and in the [identity validation record](differencing-vhd-identity-validation.md).
Milestones 4-6 remain pending. Next: verified, recoverable migration of legacy
full-parent saves and unbound experimental children. There is no automatic
migration, cross-process lock or crash-safe ZIP transaction. These limits and
actual Windows 98 runtime acceptance must be resolved before the experimental
path becomes ordinary package behavior. Process Monitor acceptance remains open:
the host reports a conflicting loaded driver version and requires a reboot.

## Identity increment implementation

Milestone 3 adds one optional `differencing_vhd` manifest object (`disk_id`,
`parent`, `child`). The packager streams the selected ZIP entry through SHA-256,
validates its VHD footer, and emits its raw UUID, virtual size and digest in
version-2 embedded metadata. A runtime capability resource prevents packaging
this declaration with an older template; older runtimes also reject version 2.
Ordinary packages retain version 1. Startup still uses explicit `IMGMOUNT -diff`.

Before mounting a declared disk, the runtime hashes the immutable parent through
its DOS archive handle without extraction or a second whole-image allocation.
The child is accompanied by a fixed-size `CHILD.DBI` binding entry in `.pure.zip`.
It binds package ID, disk ID, canonical parent/child paths, SHA-256, parent UUID,
virtual size and child UUID. Missing, corrupt, orphaned or mismatched bindings
fail without replacing existing saves. Earlier unbound experimental children
require explicit migration; they are not adopted automatically.

The binding retains the parent timestamp used when the child was created. After
strong identity verification, reopening uses that timestamp instead of the new
ZIP entry timestamp. Thus repacking identical VHD bytes preserves saves without
weakening the codec's timestamp check. Parent bytes, paths and disk/package IDs
must still match. The binding entry shares the child's in-memory lifetime and
write protection. Its publication uses the existing save ZIP; atomic generation
publication and concurrency remain milestone 5 work.

Validation: Release runtime/packager builds, 34,251 sanitizer/native-format
checks, the 21-case generated-package identity matrix, and ordinary DOS/internal
floppy relaunch passed. Existing disk bytes were preserved on rejection. No
actual Windows 98 image or user save was used in this milestone.
