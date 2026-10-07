# Milestone 5 disk state contract (7 October 2026)

Production tracing found public save/load/rewind enters `retro_serialize_all`,
then `DBPSerialize_All`. Initialization also invokes `DBPSerialize_All` directly
in `MODE_ZERO` after shutdown. The former version-8 serializer restores mounts
before DOS/machine state, restores PIC late, and restores DOS handles after PIC.
Mounted VHD handles are independent of DOS `Files[]` and hold memory-file refs.

States made with a standard child use version 9. Their bounded envelope contains
the complete child bytes, current mount slot, canonical parent/child names and
exact 512-byte binding. A 64-bit content generation digest binds the disk bytes
to their snapshot header, independent of the host save publication generation.
All mounted children together are limited to 512 MiB
for this state feature; larger disks continue to mount/save normally but state
operations fail clearly. Ordinary packages retain version-8 compatibility.
Unrelated ordinary overlay files retain existing upstream save-state semantics.

Before any live restoration, validate version, running/configuration header,
total payload bounds and checksum, and a bounded directory of every machine
section's bounds, end marker and checksum. Validate the exact section count,
contiguous structure and snapshot-to-machine boundary before parsing disk
candidates into private
memory. Reject missing/different mounts, bindings, child UUIDs, codec faults and
invalid/truncated/oversized metadata before swapping any file contents. Validate
each private child with the production codec against the mounted immutable
parent. Old states without disk snapshots are refused while a child is mounted.
Invalid DOS/game running flags are also refused while a child is mounted;
the ordinary empty-rewind reset fallback cannot run package startup as a side
effect of a rejected disk-bearing state.

The section directory catches malformed machine layouts even when the outer
checksum is recomputed. CRC and the disk content digest are consistency guards,
not authentication; this increment does not make every upstream machine-state
decoder a security boundary against deliberately fabricated, fully rechecksummed
section contents. The new disk snapshot decoder independently bounds all of its
own fields and validates the disk format and identity through the production
codec.

After successful framing/disk preflight, capture a bounded, valid current
machine/disk state in memory before starting the restore. If a deeper upstream
decoder returns an error, restore that private backup before returning control
or resuming execution; rebase dirty save scheduling to the restored valid disk.
If backup rollback itself fails, stop child publication and require restart.
The fallback avoids committing a disk timeline combined with a partially loaded
machine. It adds another temporary state allocation (and its latency) on loads.

Version-9 loads require the same currently registered mount hashes, validated
before disk commit; the mount decoder then leaves their existing objects and
leases in place. V8 retains upstream mount-switch behavior. Version-9 DOS-handle
restoration also refuses missing files instead of recreating writable overlay
entries, so a deeper failed machine decode cannot publish a newly created file
outside the disk rollback snapshot. Ordinary overlay contents still retain their
upstream state semantics.

Version-9 handle records retain DOS date/time and pending timestamp intent.
Closing the old handle set suppresses its pending timestamp writes after the
disk swap, then reopens the target handles with their captured intent. Clear any
DOS FAT sector cache associated with a restored child before reopening handles.
The initial experimental mount interface remains `-fs none`; this defensive
cache/handle integration is not new FAT mounting or real guest acceptance.
These FAT cache and pending-timestamp safeguards are source-reviewed only;
the milestone-5 synthetic mount fixtures use `-fs none`.

Successful restore swaps child vectors in the existing memory files, retaining
mount ownership, immutable parent handles and leases; reopen each DOS adapter
and child codec to reset allocation/bitmap caches. Restore machine state and
PIC, then remove/rebase save events and mark the restored disk as a new dirty
timeline. Subsequent durable publication saves that timeline and its unchanged
binding together. Historical host writer handles are never serialized.

State size is recalculated for mounted children. A caller retaining an older
smaller buffer receives failure when allocation grows, with no out-of-bounds
write; it must query size again. The standalone state writer queries per save.
Third-party rewind buffers must refresh their allocation when disk size grows.
Complete child snapshots have memory/latency costs; optimization is milestone 6.

Lifecycle integration uses synchronous union-drive publication at ATA flush,
BIOS disk reset, BIOS poweroff/reboot, runtime shutdown/reset and disk unmount.
Host-time checkpoint polling runs only with the emulation thread stopped at a
frame boundary, including paused frames. Guest IDE reset flushes before reset.
Failures remain observable and codec faults continue to disable publication.
The fault fence is outside the snapshot: loading an earlier valid state cannot
clear it or restore publication. The isolated `fence` runtime exercise captures
a valid state, performs an actual partial child-source write, then requires the
state load and explicit flush to fail while the committed save remains intact.

Persistence refusal during initialization returns a failed content load and
requests frontend shutdown after freeing the initialized core. This path runs
before the DOS shell exists; it must not enter the runtime crash handler, which
requires that shell. The standalone frontend checks the load result before
querying video state or starting frames.
Failed-reinitialization guards also return before thread/PIC/render activity.
Initial lock/corrupt-save refusal is exercised by synthetic runtime tests;
the failed-reinitialization guards have source review without a dedicated
runtime failure fixture.

This checkout defines IDE CD-ROM support but leaves `C_DBP_ENABLE_IDE_ATA`
disabled. ATA FLUSH CACHE code is connected for builds that enable it, but the
native milestone-5 fixture must use BIOS hard-disk reset AH=0Dh (and AH=00h)
as its guest flush boundary. This work does not enable the ATA subsystem or
establish real Windows shutdown command coverage.

A BIOS reboot while a standard child is mounted re-runs the configured package
startup, including its explicit `IMGMOUNT -diff`, instead of Pure Menu's generic
base-image boot selection. Poweroff retains normal completion behavior and an
explicit user request for the menu still takes precedence. Synthetic reboot
coverage must confirm the reopened child/binding retains its UUID and no full
parent overlay is created.

Validation results belong in the milestone-5 validation record. These contracts
and synthetic tests do not establish real Windows 98 acceptance (milestone 6).
