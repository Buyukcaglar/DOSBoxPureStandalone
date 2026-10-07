# Milestone 5 persistence design (7 October 2026)

Source trace before implementation: `unionDriveImpl` loads the save in its
constructor, before any disk mount lease. `standardVhdDisk::WriteSector` marks
the union dirty after each successful codec operation. The old ZIP writer opens
the only save with `rb+`, modifies it in place, and ignores close errors. Its PIC
event is postponed by each write. Child DOS handles remain open independently
of the global DOS file table. Codec faults may leave partial memory bytes and
already suppress further saving; this protection remains.

The union obtains an exclusive operating-system handle on the sibling `.lock`
file before recovery or save loading. Its lifetime is the union lifetime,
including failure and teardown. The lock pathname follows the actual selected
save pathname, so renamed/repacked packages with the same package ID contend
for the same lock; distinct persistence directories remain independent. The
lock file is not deleted on release (unlinking would create a lock race).

Publication writes a complete stored ZIP to `.pending` in the save directory.
Checked stdio flush, operating-system file flush and close precede publication.
The previous committed save is copied in bounded buffers to `.previous.pending`,
flushed/closed, then replaced through native rename as `.previous`. Only afterward is the
complete `.pending` renamed over the committed save. The published file is
flushed again. Dirty state is cleared only after success. A failure retains the
preceding valid generation and schedules a retry; a codec fault disables saving.
The ZIP writer retains existing entry selection and metadata conventions,
without rewriting the immutable underlay or extracting disk/base content.

Recovery runs while holding the lock. Complete ZIP structure, exact local and
central entry agreement, bounded filenames/offsets and every entry CRC are
checked before selection. Stored entries are validated directly; deflated
entries use the existing ZIP reader with exact reads and CRC checking. Bounded
`FILEMODS.DBP` syntax is checked before loading or promotion. Upstream save ZIPs
do not use ZIP64, data descriptors or archive comments; those representations
are rejected by this transaction validator. A valid committed save wins over leftover staging.
If it is missing/corrupt, a valid previous generation is recovered first. Only
when neither the committed nor previous pathname exists may a complete pending
first generation recover.
Recovery flushes that candidate's bytes before namespace promotion, including
candidates left complete but cached by an interrupted pre-flush write.
Malformed-only candidates produce an observable persistence error and disable
writes. For declared differencing packages, recovery also requires the child
and binding together, validates the binding against package/disk/path/hash/UUID
identity, opens the child with the codec, and hashes/validates the immutable
parent directly from the underlay before namespace promotion. A candidate that
contains a full-parent entry is rejected. An existing CRC-valid committed
legacy or unbound save is loaded for the established mount rejection, without
conversion or rewriting. Recovery does not migrate saved data.

Dirty checkpoint deadlines are fixed on the first change, rather than moved by
later sectors, and are at most five seconds for leased VHD children. Mounting a
child also shortens an existing longer ordinary-overlay deadline to five
seconds without extending an earlier deadline. A PIC event preserves ordinary emulated-time scheduling; host
monotonic time is also checked on safely paused frontend frame boundaries.
Synchronous lifecycle flushes use the same complete-generation publisher.

File flushes request durable storage from the host OS. Windows rename metadata,
filesystem/device behavior and hardware power-loss guarantees remain practical
limits; a successful process-kill recovery test does not prove physical
power-loss survival. A failure of the final published-file flush attempts to
restore the exact previous committed bytes; the validated `.previous` remains
available if the underlying filesystem also prevents rollback. Host-save
failure keeps dirty state and retries after five seconds. Native transactions
are implemented for Windows and POSIX filesystems; only Windows standalone is
validated here. Opaque libretro storage URIs are explicitly rejected rather than
casting VFS handles to native file descriptors.

The unqualified POSIX branch derives the directory to flush by taking the text
before the final slash. A relative save pathname without a slash produces the
filename as that directory; a root-level pathname such as `/save.pure.zip`
produces an empty directory. In either case rename can succeed before the
directory flush reports failure. This path handling and non-Windows runtime
durability remain outside the Windows milestone qualification.

The isolated test seam requires `DBP_TEST_SAVE_ROOT` matching the selected save
path prefix. `DBP_TEST_SAVE_FAULT` selects open, short_write, flush, close,
backup_flush, replace or publish_flush, with optional
`DBP_TEST_SAVE_FAULT_ONCE=1`. `DBP_TEST_SAVE_PAUSE` selects open, write, flush,
close, backup_open, backup_write, backup_flush, backup, published or replace;
the process creates `<save>.test-stage` inside persistence and waits for the
test harness to terminate it. The write stages precede stdio flush and can
leave incomplete candidates. Ordinary package metadata and UI do not enable
these seams. `tools/Test-SaveTransaction.ps1` drives the production transaction
helper, including exact preceding-generation preservation after all seven
faults and same-process retry, lock exclusion/release, strict malformed ZIP
rejection, previous/first-save recovery and rejected recovery identity callback.
An initial publication whose final flush fails is retained as `.pending` for
validated recovery. Both native and AddressSanitizer suites passed 121 checks on
7 October 2026, including retained first-publication failure recovery.
Runtime production-call-path validation remains separate from those helper
checks, as does real Windows 98 milestone 6 acceptance.
