# Upstream migration verification

The 1 October 2026 migration merges the latest upstream `main` revisions into
the standalone forks on local branch `codex/upstream-sync-20261001`. The
memory-backed embedded archive, deterministic persistence, package identity,
large nested ZIP handling, and experimental differencing VHD implementation are
retained. ZillaLib was already current and its source was not changed.

## Source revisions

| Component | Before migration | Upstream revision merged | Resulting fork revision |
| --- | --- | --- | --- |
| DOSBox Pure | `06216698f689a65eb21fdc14924b914fe52fa5f9` | `73e03aa145e0549ed4d5a20f8e65532714da33f5` | `4a6d27baa6d22e19ceb1c871be25500c3f895e12` |
| Unleashed | `bb2f057e2f42b55e89d21cfa544c5e069b23e6da` | `f0453b42be0c66f244e83bec330934c0f9734764` | `e1bee0aa819fbfb45db6c966a8ca1367fcaf2182` |
| ZillaLib | `a2796bfe0faebe3e5de14b75d6b45866f1576f14` | Already current | Unchanged |

The core receives six upstream commits covering Nuked-SC55 MIDI emulation,
startup/restart performance, CGA and Hercules configuration, DOSZ variant
handling, uncommon CD sector sizes, and Tandy fast-forward audio. The frontend
receives two upstream commits adding the corresponding SC55 build integration
and correcting audio callback initialization order. The merges completed without
text conflicts and preserve upstream copyright and license notices.

## Utility variant correction

The incoming patch-drive fallback iterated with `IterateLayer == layerLast`.
When more than one patch layer exists, the loop never starts, so a utility with
no files loses the preceding game variant's files. The downstream correction
changes only the loop condition to `IterateLayer <= layerLast`.

The new [patch utility regression](../dosbox-pure/tests/README.md) constructs
standard stored ZIPs in memory and exercises the real `memoryFile`, `zipDrive`
and `patchDrive` implementations. All 132 checks pass for one, two and three
layers, including file precedence, retained utility metadata, repeated variant
transitions, utilities with their own files, and return to the default root.
Restoring the upstream loop in a temporary object passes the one-layer case and
fails the two-layer file-inheritance case. This demonstrates that the test catches
the actual filesystem defect.

## Build and runtime results

The `ReleaseGLCORE|x64` runtime was rebuilt with Visual Studio Professional 2026
18.10.2. The native build produced no warnings or errors. The Release makegame
build and self-contained single-file publish also passed.

- The AddressSanitizer VHD suite passed 34,251 checks, including Windows opening
  generated fixed/dynamic parent chains without attaching disks.
- The rebuilt runtime and packager passed all 21 package/VHD identity cases,
  including persistence, renamed/repacked packages, fixed/dynamic parents,
  binding rejection, saved-byte preservation, and old-template rejection.
- Generated DOS fixtures passed embedded launch, configuration/save writes,
  repeated launch, readback after repacking and renaming, and internal FAT12
  floppy mounting. Normal external loading and explicit memory-archive loading
  also passed. Corrupt archives were rejected by the builder; missing and empty
  explicit memory inputs exited with failure.
- The original development fixture hash was unchanged. All 36 pre-existing
  modified or untracked local files were backed up and verified unchanged.

All test inputs and package save roots are synthetic and isolated under ignored
`work/upstream-sync-20261001/`. No existing game saves or Windows installation
images were used. Generated runtime processes exited themselves.

## Process Monitor evidence

A fresh bounded Process Monitor capture succeeded with the installed v4.1 tool.
The previous host driver blockage therefore does not apply to this captured run.
The DOS/floppy smoke analysis includes 582,655 runtime events and nonempty
coverage for all seven recorded runtime processes. Process names and PIDs are
matched together because Windows reused one test PID for unrelated processes
during the collection window; 10,333 unrelated events were excluded.

The selected smoke events contain no physical game-member paths, no base archive
mutations, and no activity in the isolated temporary directories. Application
persistence writes remained in the explicit package/external save locations;
redirected stdout/stderr remained in the test logs. The trace also records 152
write-related events to NVIDIA-named `GLCache` files and `nvAppTimestamps`, outside
those locations. These observed cache/timestamp writes are retained in the raw
review report and are not counted as game content extraction. No other writes
outside the allowed test locations remain after process identity filtering.

The same capture also covers four successful VHD runs: dynamic-parent baseline,
repacked/renamed relaunch, fixed-parent mount, and ordinary unbound mount. Their
443,280 runtime events contain no physical parent/child/binding paths, base
archive mutations or temporary-directory activity. Their only outside writes
are 16 events to the NVIDIA-named timestamp file; child and binding persistence
uses the isolated package `embedded.pure.zip`.

This is runtime no-extraction evidence for these generated DOS/floppy/VHD
fixtures, not a whole-game compatibility claim. The raw capture, process-filtered
CSVs and review reports remain local in the ignored test directory.

## Reproducing the checks

From the repository root, build the native `ReleaseGLCORE|x64` configuration and
publish `tools/makegame/makegame.csproj` in Release. Then run:

```powershell
./tools/Test-DifferencingVhd.ps1 -AddressSanitizer -WindowsInterop

./dosbox-pure/tests/Test-PatchUtilityVariant.ps1 `
  -RuntimeObjectsDirectory ./dosbox-pure-unleashed/Release-vs2026x64 `
  -ZillaLibPath ./ZillaLib/Release-vs2026x64/ZillaLib.lib

python tools/test_vhd_identity_runtime.py `
  --packager <published-makegame.exe> `
  --template <rebuilt-DOSBoxPureStandAlone.exe> `
  --old-template <runtime-without-VHD-identity-support.exe> `
  --output <new-identity-test-directory>

python tools/test_upstream_smoke.py `
  --packager <published-makegame.exe> `
  --template <rebuilt-DOSBoxPureStandAlone.exe> `
  --output <new-smoke-test-directory>

python tools/analyze_upstream_procmon.py `
  --csv <unfiltered-procmon-export.csv> `
  --report <smoke-test-directory>/report.json `
  --output <trace-review.json>
```

The two runtime runners require new output directories and retain logs, PIDs and
JSON results. Export Process Monitor data without applying display filters. The
trace analyzer reports observations for manual review, including GPU cache
activity, and does not silently allow unexpected writes.

## Remaining acceptance scope

This migration does not establish real Windows 98 boot/shutdown compatibility,
SC55 audio correctness with actual ROMs, or renewed coverage of large appended
archives and every CD/disk format. Corrupt embedded-resource error dialogs were
not exercised. Existing differencing-VHD limits concerning crash-safe save
publication, concurrent writers, saved-state consistency and legacy-save
migration remain unchanged; see the existing VHD design and validation documents.

The rebuilt clean template and single-file packager are available locally in
`work/upstream-sync-20261001/release/`, with source revisions and executable SHA256
hashes in `BUILD-INFO.txt`. The source migration is committed locally; publishing
and installed application replacement are separate operations.
