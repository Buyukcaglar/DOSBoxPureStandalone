# Differencing VHD milestone 5 implementation handoff

Implement the persistence lifecycle for the experimental standard type-4 VHD
child stored in a package's writable `.pure.zip` overlay. The user discarded
milestone 4 on 7 October 2026 because no current built package needs migration.
Milestone 5 is the next implementation task. This session updated the scope and
prepared this handoff; implementation belongs to the new session.

## User instructions and scope

The latest request supersedes the interrupted request to implement immediately:

1. Discard differencing VHD milestone 4.
2. Provide a handoff prompt for a new session implementing milestone 5.

Milestone 4 is discarded, rather than completed or deferred. Do not implement
legacy full-parent overlay conversion, unbound-child adoption, merge, export or
compaction as an implicit prerequisite. Preserve the current rejection behavior
and saved bytes for unsupported or mismatched representations.

Milestone 5 includes:

- Checkpoint dirty children while their DOS handles remain open. Continuous
  sector writes must not postpone a checkpoint indefinitely.
- Flush at the applicable guest flush/shutdown, BIOS poweroff, emulator exit,
  reboot/reset, numeric disk unmount and containing-drive unmount boundaries.
- Publish complete save generations durably, retaining the preceding valid
  generation on write, flush or replacement failure and on interrupted saves.
- Define recovery after a crash or power loss, including interrupted first-save
  publication and leftover transaction files.
- Exclude concurrent writers for the same persisted overlay, including renamed
  or repacked EXEs sharing the package ID. Separate packages must still run.
- Implement a coherent disk/save-state/rewind generation policy, with validation
  before state restoration can change live machine or disk state.

Do not call milestone 5 complete merely by retaining the existing blanket
save-state refusal or adding an atomic rename without flush and recovery tests.
Choose the smallest source-backed design and state any remaining limitations.
Real Windows 98 compatibility and optimization remain milestone 6. Synthetic
lifecycle tests are required here; they cannot establish full guest acceptance.

## Workspace and preservation

Workspace: `C:\Projects\DOSBoxPureStandalone`. Read the live `AGENTS.md`,
`docs/architecture.md`, `docs/requirements.md` and `docs/differencing-vhd-plan.md`
before editing. Live instructions and the user's requests override this handoff.

Source revisions checked on 7 October 2026:

| Repository | HEAD |
| --- | --- |
| Parent | `b18c6431dea5204ea89dae31c52b7bcf9aacaecc` |
| dosbox-pure | `eb16b624c7a94e03ec9dd7b7e3f707f1b836a56c` |
| dosbox-pure-unleashed | `e1bee0aa819fbfb45db6c966a8ca1367fcaf2182` |
| ZillaLib | `a2796bfe0faebe3e5de14b75d6b45866f1576f14` |

The parent, core and frontend are on `codex/upstream-sync-20261001`. Core and
frontend were clean before the handoff; verify again in the new session.
The parent already had local work in `.gitignore`, `docs/architecture.md`,
`docs/makegame-guide.md`, `docs/requirements.md` and `tools/makegame/README.md`.
Its pre-existing untracked work includes `docs/Voodoo2-Integration-Map.md`,
`docs/differencing-vhd-guide.md`, `tools/makegame/examples/win98-differencing/`
and `tools/win3-state-manager/`. Preserve all of it. This handoff adds scope edits
to three documents and creates this file. Do not reset or overwrite local work.

Before those scope edits, the three affected documents were copied byte-for-byte
and SHA-256 verified under
`work/milestone5-handoff-20261007/preexisting/docs/`. The sibling
`preexisting-manifest.json`, `preexisting.diff` and `preexisting-status.txt`
record the original state. These local backup files are ignored artifacts.

Keep changes focused. ZillaLib remains effectively read-only. Do not replace
installed Program Files executables, touch real user saves or OS images, create
a release, push, or deploy as part of this implementation unless requested.

## Architecture that must remain intact

The immutable parent stays inside the embedded compressed ZIP/DOSZ and is read
through the existing memory-backed archive filesystem. The standard child and
its 512-byte `CHILD.DBI` identity entry live together in the in-memory writable
overlay and are persisted in the package's `.pure.zip`. Preserve their identity
checks, parent SHA-256/UUID/virtual-size validation and renamed/repacked EXE
behavior. Preserve ordinary external ZIP/DOSZ loading and the separate FFDD path.

Persistence uses `%LOCALAPPDATA%\DOSBoxPureStandalone\<package_id>\`, with the
documented executable-directory fallback when the primary root is unwritable.
Shared resources use the sibling `system` directory. If both roots fail, report
an error rather than silently retaining writes only in memory.

Transaction staging may contain writable save data in the selected persistence
directory. Never extract the immutable base archive or parent VHD, create a loose
host copy of either disk for mounting, or reconstruct archive content in Temp,
AppData Temp or cache directories. Avoid unnecessary whole-archive copies.

## Source map and verified current behavior

Line numbers below locate the inspected revision; search by symbol after edits.

| Source | Starting points |
| --- | --- |
| `dosbox-pure/src/dos/drive_union.cpp` | `unionDriveImpl` around 152; constructor/destructor 174/198; `ReadSaveFile` 289; `WriteSaveFile` 352; `ScheduleSave` 581; VHD lease/binding methods 1184-1284 |
| `dosbox-pure/src/dos/drives.h` | `unionDrive` VHD methods around 856-860 |
| `dosbox-pure/src/ints/bios_disk.cpp` | `standardVhdDisk` 45; destructor 57; `Open` 77; sector read/write 140/146; `imageDisk` sector dispatch 1352/1399; differencing open and ownership 1537-1552 |
| `dosbox-pure/include/bios_disk.h` | `OpenDifferencingVHD`, `HasDifferencingVHD`, `UsesDifferencingVHDDrive` |
| `dosbox-pure/src/ints/vhd_differencing.h` | Standard type-4 parent/child codec and source interfaces |
| `dosbox-pure/src/ints/vhd_dos_source.h` | `VhdDOSSource` exact random-access DOS adapter |
| `dosbox-pure/src/ints/vhd_identity.h` | Package/disk identity and child binding representation |
| `dosbox-pure/dosbox_pure_libretro.cpp` | `DBP_Shutdown` 1277; BIOS reboot/poweroff callbacks nearby; `init_dosbox` 2675; `retro_unload_game` 3404; `retro_reset` 3417; `retro_serialize_all` 3786 |
| `dosbox-pure/src/dbp_serialize.cpp` | `DBPSerialize_All` 266 and mount/drive/file/PIC serialization ordering |
| `dosbox-pure/src/dos/dos_programs.cpp` | `IMGMOUNT -diff` and unmount paths; trace full ownership before changes |
| `dosbox-pure/src/hardware/ide.cpp` | Audit guest flush/reset semantics and paths to `imageDisk`; no flush guarantee established by this handoff |

`unionDriveImpl` loads the existing save in its constructor, before a VHD mount
lease is acquired. Its `vhd_leases` vector prevents conflicting DOS access in
one process; it does not exclude another process. Any host writer lock must cover
loading/recovery as well as publication, preventing a stale snapshot from later
overwriting another writer. Resolve actual persistence identity and handle
lifetime, including startup failure, reset and process death. Do not serialize
host lock handles or allow lock failure to become an unannounced writable mode.

`WriteSaveFile` currently opens the committed save with `rb+`, falls back to
`wb`, updates/truncates it in place, and closes it. It is not a crash-safe
transaction. It reuses matching existing data for speed. Its write-error path
notifies the user and schedules a retry, but publication already may have
modified the sole committed copy. Inspect the complete writer before replacing
that mechanism; preserve save ZIP semantics and bound all sizes/offsets.

`ScheduleSave` computes a size-based delay of roughly 1-60 seconds, removes the
existing PIC event and adds a new event on every call. `standardVhdDisk::WriteSector`
calls `VhdChanged`, which calls `ScheduleSave`. Thus continuous successful writes
can defer the deadline repeatedly. Track a bounded first-dirty deadline or an
equivalent policy while allowing appropriate batching. Check behavior during
pause, reboot and normal exit; PIC emulated time alone is not automatically a
host-time durability guarantee.

The union destructor attempts a save if dirty. The VHD destructor closes backing
handles and schedules a save when changed; `ReleaseVhdFiles` drops the lease.
These actions do not themselves prove synchronous checkpoint completion at
each lifecycle boundary. Audit destruction order and explicit unmount/reset
paths, then make failures observable without publishing partial memory state.

`VhdFailed` marks the session failed, removes the save event and disables later
publication, including shutdown publication. Preserve this protection: codec
I/O failure can leave partial child bytes in memory. Keep host publication
failure and codec fault handling distinct where recovery semantics differ.

`retro_serialize_all` currently refuses size/save/load/rewind operations whenever
an `imageDiskList` entry has a standard differencing VHD. The comment states that
child generations are absent from states. Do not just remove this guard. Trace
all public and internal serialization callers, including direct
`DBPSerialize_All` paths during initialization and shutdown. Design a validated
disk generation/snapshot policy that coordinates child bytes, binding, codec
metadata/caches, drive handles, PIC save events and resumed execution. Reject
incompatible restores before modifying live state. Bound malformed snapshot
data and specify how rewind changes the later persisted generation.

## Implementation sequence

1. Confirm source status and trace the full persistence, mount, shutdown/reset,
   guest flush and serialization paths. Record the chosen publication/recovery,
   locking, checkpoint and state-generation contracts in project documentation
   before significant structural changes.
2. Add narrow production-path test seams for I/O faults and interrupted saves.
   Keep failure injection out of ordinary product flows; avoid tests that merely
   mirror helper implementation.
3. Implement writer exclusion before loading writable state, a bounded dirty
   checkpoint policy, and complete durable ZIP generation publication. Define
   recovery selection for every possible interrupted publication stage; validate
   candidates rather than silently adopting malformed or unrelated save data.
4. Connect explicit lifecycle flush boundaries and implement disk/state/rewind
   consistency. Keep child and binding in the same committed generation and retain
   the preceding valid save until the replacement is durable.
5. Run focused fault/crash/concurrency/state tests and the existing codec,
   identity and archive regressions against the rebuilt runtime. Capture actual
   runtime file activity with Process Monitor for the changed paths.
6. Update architecture, requirements, plan and a dated validation record with
   exact results and limits. Report milestone 5 completion only if its required
   behavior and tests pass. Leave milestone 6 acceptance distinct.

The exact lock primitive, transaction layout and snapshot representation remain
design choices for the implementation session. Do not infer that an atomic
rename alone proves durable publication or that a process-kill test proves
hardware power-loss behavior. Use platform flush primitives and document their
practical guarantees and limits.

## Validation requirements

Use newly created ignored test directories with isolated `LOCALAPPDATA` and
temporary environment paths. Use synthetic fixed/dynamic parents and guest code;
no existing user OS installation or save should be seeded or modified.

Required lifecycle cases include:

- Continuous writes across multiple checkpoint intervals while the child remains
  open; inspect persisted sectors and generation consistency before guest exit.
- Guest flush, guest shutdown/poweroff, reboot/reset, numeric and containing-drive
  unmount, emulator exit and repeated relaunch. Include renamed and repacked EXEs.
- Failure injection for save open, short write, flush, close and final replacement;
  failure must preserve the preceding committed generation and report saving failure.
- Process termination during each publication stage, including the first save;
  relaunch must recover a complete validated generation or report a clear error.
- Two simultaneous instances sharing one package/persistence identity; the second
  writer is rejected without altering saves. Different identities can run, and
  lock ownership is released after orderly exit and process death.
- Save/load and rewind after subsequent disk writes, with coherent machine/disk
  results; malformed snapshots, mismatched bindings/generations and incompatible
  saved states reject before live mutation. Exercise restart and resumed saving.
- Codec faults retain the last valid generation, and host-save failure/retry does
  not falsely clear dirty state or persist incomplete child/binding pairs.
- DOS config/save writes, internal disk images, ordinary external loading,
  memory-archive loading, corrupt/missing packages and unsupported legacy saves.

Available runners and fixtures:

- `tools/Test-DifferencingVhd.ps1 -AddressSanitizer -WindowsInterop`, preferably
  with `-OutputDirectory` pointing at this implementation's fresh test directory.
- `tools/test_vhd_identity_runtime.py --packager <makegame.exe> --template <rebuilt-runtime.exe> --old-template <known-old-runtime.exe> --output <new-directory>`.
  The old template must actually lack identity capability resource 104. The
  26 August template was used successfully in the prior run; locate and verify it.
- `tools/test_upstream_smoke.py --template <rebuilt-runtime.exe> --packager <makegame.exe> --output <new-directory>`.
- `tools/create_vhd_mount_fixture.py <output-directory>` creates fixed/dynamic,
  checkpoint-wait, unmount and negative-case fixtures. The existing checkpoint
  fixture writes and waits; it does not establish continuous-write deadlines.
- `tools/inspect_vhd_mount_save.py` and `tools/inspect_vhd_mount_cases.py` inspect
  saved sectors and failure preservation. Read their argument schemas first.
- `tools/analyze_upstream_procmon.py` provides prior capture analysis; read its
  schema and capture setup before adapting it for new runtime processes.

The native Visual Studio solution is
`dosbox-pure-unleashed/DOSBoxPure-vs.sln`, configuration `ReleaseGLCORE|x64`.
Use the available Visual Studio developer environment; inspect the prior
`work/upstream-codeberg-20261006/build.log` for the build context and output
paths. The prior packager is at
`work/upstream-codeberg-20261006/release/makegame.exe`; rebuild it if affected.
Rebuild the runtime for new source changes. If new translation units are added,
check the explicit Visual Studio project lists and other supported build paths.

Process Monitor must capture nonempty events for every test PID/executable and
review `CreateFile`, `WriteFile`, truncation, rename and delete operations.
Validate newly introduced staging, recovery and lock paths inside allowed
persistence locations. Account explicitly for host driver cache writes rather
than attributing them to extracted game content.

## Prior evidence and open acceptance

`docs/upstream-migration.md` records the 6 October 2026 build/regression results:
zero native build warnings/errors, 132 patch-utility checks, 34,251 VHD
sanitizer/Windows interoperability checks, two Pentium probes, 21 VHD identity
cases and archive save/relaunch smoke coverage. A successful bounded Process
Monitor capture covered 27 runtime processes with 2,805,599 reviewed events.
No extraction was observed for those fixtures; 148 successful write-related
events outside test persistence/log locations were NVIDIA cache/timestamp writes.

Those results precede milestone 5 changes. They are baseline evidence, not proof
that the new lifecycle implementation works. Older VHD documents' Procmon driver
blocker is historical; recheck present tool availability rather than assuming
the host still needs rebooting. Never reboot or manipulate a driver implicitly.

Real Windows 98 boot/shutdown/reboot acceptance, full game/CD/disk coverage and
optimization are still open. Do not inflate synthetic success into acceptance
of real guest installations. Migration is discarded and must stay out of the
remaining backlog. Voodoo2 and State Manager work are separate tasks.

## Ready to paste continuation prompt

Implement differencing VHD milestone 5 in `C:\Projects\DOSBoxPureStandalone`.
Read `docs/handoffs/milestone5-persistence-20261007.md` in full, then the live
`AGENTS.md`, architecture, requirements and differencing VHD plan. Milestone 4
was discarded because no current built package needs migration; preserve legacy
save rejection and do not implement migration. Complete bounded checkpoints for
open children, lifecycle flushes, durable recoverable save publication,
concurrent-writer exclusion and disk/save-state/rewind generation consistency.
Preserve immutable memory-backed archive access, child/binding identity,
existing local work and ordinary archive behavior. Trace production call paths
before changes, use narrow patches, test synthetic fault/crash/concurrency/state
cases plus the existing regressions, and validate runtime writes with Process
Monitor. Update project documentation with exact evidence and limits. Keep real
Windows 98 acceptance separate as milestone 6. Do not replace installed binaries,
use real user saves or OS images, push, deploy or publish a release.
