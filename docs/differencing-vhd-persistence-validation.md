# Differencing VHD milestone 5 validation (7 October 2026)

This increment implements the scope in the
[milestone 5 handoff](handoffs/milestone5-persistence-20261007.md).
Milestone 4 is discarded: unsupported full-parent and unbound legacy saves stay
rejected, without migration. Real Windows 98 acceptance remains milestone 6.
Milestone 5 is complete and qualified for the synthetic Windows scope recorded
here, including the completed current-source Process Monitor review.

This record describes the validation stage completed on 7 October. Publication
and updating the installed tools were separately authorized on 8 October; see
the [2026.10.08 release notes](releases/2026.10.08.md). That authorization does
not extend the synthetic evidence to real Windows 98 acceptance.

## Source and scope

The implementation follows the production union constructor/load/save path,
mounted child sector writes and destruction, BIOS reset/poweroff/reboot,
frontend shutdown/reset/pause, and public state/rewind APIs. The
[persistence design](milestone5-persistence-design.md) and
[state contract](milestone5-state-design.md) describe those traces and the final
contracts. The immutable archive and parent still use their existing DOS memory
handles. Child/binding vectors stay inside the writable union; no loose disk or
base archive is introduced.

Tests use generated DOS programs, boot sectors and fixed/dynamic VHDs, with
isolated Local AppData/AppData/TEMP directories under
`work/milestone5-20261007/`. They do not read or modify installed packages,
Windows installations or real user saves. The unchanged local packager is used
only to generate synthetic executables. No push, deployment or release is part
of this work.

## Native and isolated checks

- Native Windows x64 `ReleaseGLCORE` build: **0 warnings, 0 errors**, 18.17 seconds
  in `work/milestone5-20261007/build.log` after the final source review.
  Clean template SHA-256:
  `935c137a788e430f73981f1e5a35c822b0a505338fcc2ab309b7da7073904769`.
  Unchanged packager SHA-256:
  `6bea90ca92375dcab0d9ffa95ac6c55ff50d0614edf63527bf5daf477c841e9f`.
- Codec AddressSanitizer plus Windows interoperability: **34,251 checks passed**.
  `OpenVirtualDisk` examines synthetic fixtures without attaching disks.
- Production save transaction helper: **121 checks passed** in native and
  AddressSanitizer runs, including checked I/O failures, retry, writer exclusion,
  strict ZIP validation, recovery selection and first-generation final-flush
  failure preservation.
- Existing patch/utility variant regression: **132 checks passed**, including
  one, two and three real patch layers.

The codec evidence is `codec-final/` and `codec-final.log`; final native/ASAN
transaction evidence is `transaction-native-parser-final/` and
`transaction-asan-parser-final/` (121 checks each).
The utility result is `patch-utility-final3.log`. The codec and utility checks
preceded the final review fixes in the union modification parser and rewind
fallback; their tested code was unchanged by those fixes. The transaction
helper was rerun after the parser fix; it does not exercise `FILEMODS.DBP`,
whose production runtime cases are recorded separately.

## Production runtime checks

The final runtime runner freezes its template and packager at startup, records
their hashes, and retains exact commands, process IDs, roots, fault flags and
exit/termination results. Native exception exit codes fail the run, including
cases that are supposed to refuse loading. Recovery/concurrency refusals must
exit cleanly with code 1. Each output directory and generated persistence root
is new; tests retain process handles to prevent PID reuse within an inventory.

`runtime-final-filemods/report.json` passes **8 cases / 10 runtime processes** on
the final template: actual DOS `DEL A` and `REN A B` preserve their results over
reopening, while six CRC-valid malformed modification records are rejected
without changing their candidate ZIPs. The parser permits emitted `DELETE|A`
and `REDIRECTFILE|B|A`, requires a redirect source, bounds its delimiter to the
current record, and rejects extra field delimiters. Generic ZIP names retain
their separate validation rules.

`runtime-final4/report.json` passes **64 case groups / 114 runtime processes**
on the final template. Its recorded run spans 22:15:25-22:23:42 local time and
begins after the current Process Monitor capture began. All 114 PIDs are unique within
that inventory. Exits are 68 code-0 and 46 code-1 results; the latter comprise
34 explicitly recorded harness terminations and 12 clean refusal cases, with
no native exception exits.

| Group | Cases / processes | Observed result |
| --- | --- | --- |
| Lifecycle | 12 / 19 | Exit/relaunch, numeric and containing-drive unmount, BIOS poweroff/reboot/flush, open continuous writes, process death, paused polling, late-mount deadline, window close and actual frontend reset preserve child/binding. |
| Faults | 11 / 27 | Seven host publication faults preserve the preceding ZIP; a one-shot fault retries in the same session; actual short child write fences saving; deflated existing save and failed first final-flush recovery pass. |
| Modification parser | 8 / 10 | Emitted one-character delete/rename survives reopening; six malformed-record candidates refuse cleanly and preserve bytes. |
| Crash/recovery | 21 / 39 | Ten prior-save and six first-save publication-stage terminations recover a complete allowed generation or reject an incomplete-only candidate; truncated/CRC saves fall back to previous, malformed-only/foreign-binding/malformed-modification candidates refuse. |
| Writer exclusion | 1 / 5 | Renamed/repacked same-identity contender exits 1 without changing the committed ZIP; another identity runs concurrently; death and orderly exit release the lock. |
| State/rewind | 11 / 14 | 35 core cases, renamed/repacked cross-restart machine+disk restore, actual partial-write fence, actual frontend RZIP roundtrip and seven malformed wrapper inputs pass. |

Continuous open writes produce committed counters 12, 67 and 115 at 7.290,
10.336 and 13.398 host seconds since launch (checkpoint intervals 3.046 and
3.062 seconds). These launch times include guest startup. For an existing
11,539,512-byte writable ZIP dirtied before mounting the child, publication
starts 4.998 seconds after the observed mount. The measured window-close case
flushes dirty counter 18 over checkpoint 11, then reopens counter 18. Actual
frontend reset flushes counter 10, reopens the same child/binding and reaches
counter 64; close and next reader both observe 65. These measurements establish
the tested safe-frame behavior, not a successful-publication deadline under
arbitrary slow storage or I/O failure.

The 35 core cases exercise normal save/load and rewind machine/disk equality,
truncation, CRC, old version, configuration, exact binding, content generation,
cap, child codec, machine section directory, reported deeper-decoder rollback,
mount mismatch, missing-file noncreation, both invalid-running flags, and
growth-buffer refusal followed by shrink/reopen. The cross-restart case retains
binding and restores captured A5 sector data plus EAX after a later 5A disk
publication and identical-byte repacking/EXE renaming. The real partial child
write permanently fences state load and publication; the preceding ZIP remains
byte-identical. The actual frontend wrapper roundtrip restores disk counter 1
over 2, using an 18,009-byte RZIP file containing 4,345,414 decoded bytes.

## Existing regressions

The final template passes `smoke-final3/report.json`: **5 case groups / 7 runtime
processes**, including embedded configuration/save writes, internal floppy
mounting, renamed-package relaunch/readback, external file and memory archive
loading, rejected corrupt builder input and empty/missing memory sources.
The smoke test explicitly does **not** exercise a corrupt embedded-resource
error dialog; package/overlay corruption tests do not establish that UI path.

`identity-final3/report.json` passes its **21 assertion cases / 18 runtime
processes** with command exit 0, including fixed/dynamic parents, identical-byte
repacking/renaming, altered identity rejection, missing/orphan/corrupt bindings,
unbound children, older unsupported templates and invalid manifests. That
existing report has no `result` field; success is the completed assertions and
command exit, not an added inferred field. Unsupported legacy rejection retains
the preceding save bytes; no conversion is introduced.

`cpu-final2/report.json` and its log pass both existing Pentium CMPXCHG8B guest
probes (default operand size and 66h prefix). This check used the preceding
`11cd1b7d4a859fdf43a7bd8b630ec4ec3e175f359607e0fd7b02c4bb10cec976`
template; the final changes did not touch CPU instructions.

Artifacts remain in the ignored work directory; test runners refuse to reuse an
existing output directory. Reproduction uses fresh output paths:

```powershell
MSBuild.exe dosbox-pure-unleashed/DOSBoxPure-vs.sln /m /t:Build /p:Configuration=ReleaseGLCORE /p:Platform=x64
./tools/Test-DifferencingVhd.ps1 -AddressSanitizer -WindowsInterop -OutputDirectory work/m5-codec-new
./tools/Test-SaveTransaction.ps1 -OutputDirectory work/m5-transaction-new
./tools/Test-SaveTransaction.ps1 -AddressSanitizer -OutputDirectory work/m5-transaction-asan-new
python tools/test_milestone5_runtime.py --template <clean-template.exe> --packager <makegame.exe> --output work/m5-runtime-new
```

## Process Monitor capture

The installed `C:\Windows\System32\Procmon64.exe` (version 4.1) was launched
hidden/minimized with `/AcceptEula /Quiet /Minimized /BackingFile` for
`work/milestone5-20261007/procmon/milestone5.pml`. The current shell has a medium
integrity token; Windows requires administrator consent to start the capture.
The owned launch is recorded in `procmon/session.json` (bootstrap PID 59312,
capture PID 12540). Consent was granted and capture began at 22:12:17 local,
before the complete final matrix. Stop was requested and the owned capture
process ended at 22:26:25. The raw backing log comprises `milestone5.pml` and
four numbered PML segments; all are preserved. File creation/close times do not
establish their event coverage.

The user reported that an operation was cancelled after an accidental spacebar
press during Process Monitor interaction. Subsequent exports
from the master and two numbered names completed with exit 0 and were
byte-identical, but ended at **22:19:48.0324172**, before the last final-matrix
processes. A fresh official portable Process Monitor 4.11 reader was downloaded
only into `work/milestone5-20261007/procmon-reader/`; the installed 4.1 binary
was unchanged. Its fresh `/NoConnect /NoFilter /OpenLog /SaveAs` export finished
at 23:08:14 with exit 0, 7,810,268,706 bytes and the same final event timestamp.
Thus successful export exit codes and PML segment timestamps do not prove
coverage of the later tests. The cause of the missing exported span is not
established; no raw log is altered to repair it.

Only the earlier 19 lifecycle and 27 publication-fault processes are selected
from the final matrix for this capture review, with an explicit inventory
retaining the original report hash and process indices 0-45. The original
64-group/114-process functional report remains unchanged. The ordinary smoke
and identity trace inventories contain another 7 and 18 processes. The attempted
supplementary launch (bootstrap PID 29000) ended without creating a PML; the user
confirmed that no Windows administrator prompt appeared. No test process was
launched for that failed recording attempt.

An explicit Windows `RunAs` launch then started the installed 4.1 capture as
PID 4496 at 23:31:31. Four separate, fresh `runtime-procmon-*` outputs reran only
the missing suites on the unchanged final template: modification parser **8
groups / 10 launches**, crash/recovery **21 / 39**, concurrent writers **1 / 5**,
and state/rewind **11 / 14**. All four reports pass with the final template hash;
these **41 groups / 68 launches** supplement the trace, rather than replacing
or adding distinct functional cases to the original 64-group matrix.

The elevated stop request returned a Windows cancellation error without
starting its stop process; its `stop.json` has null process/exit values and is
not success evidence. Standard `/Terminate /Quiet` (PID 20728) completed with
exit 0, and no Process Monitor or consent process remained. Both raw PML files
closed at 23:37:56: `supplement.pml` is 4,053,202,808 bytes and
`supplement-1.pml` is 2,579,599,240 bytes, under `procmon-supplement-visible/`.
The fresh 4.11 export completed at 23:40:53 with exit 0 and 2,431,000,873 bytes;
its event span is **23:31:31.7842266-23:37:56.5321399**.

`trace-supplement-qualified/attribution.json` verifies **68/68 launches** with
zero coverage or attribution errors and no cached-name corrections. It selects
**5,634,099 events** from 14,217,438 rows. The actual test lifetimes span
23:31:54.9963678-23:34:18.7393655, wholly inside the export. Combined with the
earlier verified inventories, the current-source scope is **139 launches /
12,260,786 attributed events**. The completed file-operation review and its
limits are recorded below.

The two reviewed captures establish runtime evidence for the listed
current-source synthetic processes, including checks for file operations and
successful changes in persistence, Temp, executable and cache locations.
The runner inventories support `tools/analyze_upstream_procmon.py`; the new
merge helper rejects duplicate PIDs across inventories instead of silently
combining reused process identities. PID 2924 was reused between separate
runners (`baseline.exe` versus `crash-once.exe`).
`tools/review_milestone5_procmon.py` requires an exact absolute executable
Process Start, matching lifetime, Process Exit and nonempty CreateFile/file
activity for every expected process. PID 51796's displayed name was stale
`git.exe` although the recorded start command and successful executable Load
Image identify the owned `fault-once.exe`. The selected output retains Original
Process Name and Attributed Image columns; raw CSVs are unchanged. Cached-name
attribution requires that image-load confirmation. Eight attribution guard
cases pass, including reused names/PIDs, missing start/exit, out-of-lifetime
events, ambiguous repeat starts and absent cached-name image confirmation.

`trace-reader411-qualified/attribution.json` verifies **71/71 launches**, each
with exactly one matching start/exit and nonempty CreateFile/file activity,
with zero coverage or attribution errors. It selects **6,626,687 events** from
41,225,411 exported rows. The cached-name case has 71,321 retained rows and one
matching successful executable Load Image. The unchanged analyzer's reports
and separate file-operation summaries are retained beside the attribution:

| Inventory | Launches / events | Successful writes outside test locations |
| --- | --- | --- |
| Final matrix lifecycle/fault subset | 46 / 3,962,092 | 650 NTFS `$LogFile`, 102 NVIDIA timestamp writes |
| Ordinary smoke | 7 / 604,225 | 87 `$LogFile`, 28 `$Mft`, 13 NVIDIA timestamp writes |
| Identity regression | 18 / 2,060,370 | 363 `$LogFile`, 8 `$Mft`, 53 NVIDIA timestamp writes |

All three reviews report zero physical fixture-member paths, immutable archive
mutations and isolated TEMP activity. They retain **1,304** raw successful
outside-write observations: 1,100 to `C:\$LogFile`, 36 to `C:\$Mft`, and 168 to
`C:\ProgramData\NVIDIA Corporation\Drs\nvAppTimestamps`. These are consistent
with NTFS metadata and graphics-driver application timestamps; this CSV review
classifies paths and operations, without exported caller stacks or payload
bytes. Raw `review_required` remains true; these observations are not silently
allowlisted and do not support a claim that every host write stays in AppData.

The summaries record **213 successful renames**, with no destination outside
the corresponding authorized roots, and actual complete-generation activity:
1,190 pending WriteFile operations, 125 pending FlushBuffersFile operations,
116 pending renames, 94 previous-pending flushes, 94 previous-generation
flushes, and 110 committed-generation flushes. There are 108 successful CreateFile
operations on the writer-lock paths; the Windows lease uses exclusive sharing
rather than a separate LockFile event. Ordinary NAME NOT FOUND candidate probes
and FAST IO DISALLOWED fallbacks remain recorded with their actual results;
they are not mislabeled as injected fault failures. These counts describe the
71-launch scope selected from the first capture.

The separate `*.file-activity-disk-audit.json` summaries also inspect every
absolute host path ending in `.vhd`, `.dbi`, `.ima`, `.img`, `.iso`, `.cue` or
`.bin`. The lifecycle/fault, smoke and identity inventories contain respectively
407, 406 and 406 distinct matching paths, all NVIDIA profile/GLCache `.bin`
paths with reads, opens, queries or reader locks and no successful file
mutation. There are zero physical `BASE.VHD`, `CHILD.VHD`, `CHILD.DBI` and
`DISK.IMA` paths. Ordinary external ZIP/DOSZ reads and absent legacy-save probes
are listed separately; smoke's actual external `smoke-write.dosz` has three
successful opens, twelve reads and three closes, with no mutation.

The completed supplement has the following independently attributed results:

| Inventory | Launches / events | Successful renames |
| --- | --- | --- |
| Modification parser | 10 / 785,296 | 10 |
| Crash/recovery | 39 / 3,467,884 | 77 |
| Concurrent writers | 5 / 352,308 | 6 |
| State/rewind | 14 / 1,028,611 | 26 |

All four reviews have zero physical fixture-member paths, immutable archive
mutations, isolated TEMP activity, outside rename destinations and successful
disk-suffix mutations. The 406-path suffix union contains only three NVIDIA DRS
profile and 403 GLCache `.bin` paths. There are zero `.vhd`, `.dbi`, `.ima`,
`.img`, `.iso` or `.cue` paths. The raw supplement retains **774** successful
outside WriteFile events: 651 `$LogFile`, 16 `$Mft` and 107 NVIDIA timestamps.

Supplement publication activity includes 814 pending writes, 78 pending
flushes, 70 pending renames, 3,680 previous-pending writes, 50 previous-pending
flushes, 49 previous-pending renames, 49 previous flushes and 68 committed
flushes. The writer lock has 86 successful opens and one sharing violation.
The first writer (PID 9112) opens the lock with `ShareMode: None` at
23:31:59.2645681; the same-identity renamed/repacked contender (PID 58720) gets
`SHARING VIOLATION` at 23:32:04.1642858. Another identity opens its own lock
successfully at 23:32:07.6231948; the original lock reopens after writer death
at 23:32:11.9060398. Functional tests also verify release after orderly exit.

`trace-qualified-combined-summary.json` combines the independently verified
71- and 68-launch scopes: **139 launches, 12,260,786 selected events from
55,442,849 rows, 332 successful renames and 194 successful lock opens plus the
one sharing violation**. Successful publisher observations total 2,004 pending
writes, 203 pending flushes, 186 pending renames, 9,449 previous-pending writes,
144 previous-pending flushes, 143 previous-pending renames, 143 previous flushes
and 178 committed flushes. No raw file or failed/partial report is rewritten
to create this qualification.

Across both captures, the **2,078** retained outside writes are 1,751 NTFS
`$LogFile`, 52 `$Mft` and 275 NVIDIA timestamps. The disk-suffix union is 407
read-only NVIDIA `.bin` paths (three DRS profiles, 404 GLCache); all other
listed disk suffixes and canonical loose disk paths are absent. There are zero
fixture-member physical paths, immutable archive mutations, isolated TEMP
events, disk-suffix mutations and outside rename destinations. The path-based
classification and lack of exported caller stacks/payloads remain explicit
limits. These observations qualify the synthetic milestone 5 Windows scope;
real Windows 98 acceptance remains milestone 6.

## Preserved local work

`preexisting/preservation-hashes.json` records 38 files present before this
task. The final comparison keeps **35 unrelated files byte-identical**; only
architecture, requirements and the VHD plan receive intended documentation
updates. In particular the existing guide, handoff, makegame drafts, Windows
3.x utility and Voodoo map are preserved. ZillaLib source and all four repository
HEADs remained unchanged throughout validation. Changes were local and unstaged
at that boundary; subsequent source publication is a separate release operation.

Earlier build/test directories are retained. Preliminary failures include a
startup refusal entering a shell-dependent crash handler, a rewind CRC test
mutating unused capacity padding, guest fixture timing and a test observer
holding the save ZIP open during Windows replacement. The production startup
refusal and final-review parser/rewind issues were fixed; fixture problems were
corrected separately. Failed reports remain failed, including `runtime-final2`
whose completed groups are listed in `accepted-groups.json`; they are not
substituted for a complete final result.

## Evidence limits

Host file flushes request durable storage; interrupted-process recovery does not
prove physical power-loss behavior of the filesystem, device or hardware. The
publisher retains complete previous/candidate generations, but simultaneous OS
failure of final flush and rollback can leave a complete newer committed file
alongside the previous one. Recovery selects a valid committed generation first.

The default build leaves hard-disk ATA emulation disabled. BIOS AH=00h/AH=0Dh are
the active guest flush/reset boundaries; ATA E7h/EAh and IDE reset hooks have
source integration only in this configuration. Real Windows 98 shutdown,
filesystem/registry durability, gameplay and performance are unaccepted.
The DOS FAT cache/pending-timestamp safeguards and failed-reinitialization
guards are source-reviewed and compiled, without dedicated runtime fixtures.
Mounted disk fixtures use `-fs none`; initial persistence refusals and ordinary
frontend reset do have runtime coverage.

Version-9 disk snapshots have a 512 MiB aggregate child limit and full-copy memory
and latency costs, including the private rollback state during load. Third-party
rewind callers must refresh buffers after child growth. CRCs/content generations
are consistency checks, not authentication of every upstream machine decoder.
Unrelated normal overlay contents keep upstream save-state semantics. Ordinary
packages keep version-8 states; opaque libretro storage URI transactions and
POSIX durability are not qualified by these Windows tests.
Child storage retains its 2,147,483,647-byte physical cap. Complete saved ZIPs
retain the classic ZIP 32-bit size/count format; the strict recovery validator
does not accept ZIP64, data descriptors or archive comments. These restrictions
apply to writable save generations, not the immutable game's ordinary archive
reader. Malformed or unsupported saves are not silently converted.
