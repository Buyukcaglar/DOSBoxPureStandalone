# Windows 98 differencing VHD usage guide

This guide describes opt-in differencing VHD packaging in the current source.
The authoring recipe was prepared for the `Dev-Diff-Virtual-Disk-Support` build
installed on 2026-09-22; its installed paths are examples. Use a newly built
compatible runtime template for the milestone 5 behavior described below, and
keep `makegame.exe` and `DOSBoxPureStandAlone.exe` together. The general option
reference is [makegame-guide.md](makegame-guide.md), or `MAKEGAME-GUIDE.md` in an
installed distribution. Run `makegame.exe --help` for the command-line reference.

Milestone 5 is qualified for synthetic Windows tests, including bounded
checkpoints, recoverable save publication, writer exclusion and disk/state
consistency. [The validation record](differencing-vhd-persistence-validation.md)
records the tested build, Process Monitor evidence and limits. Real Windows 98
boot, shutdown, reboot and gameplay acceptance remains milestone 6. This recipe
does not establish that acceptance or update an already installed runtime.

## What the feature does

Put a completed Windows 98 installation in an immutable parent VHD inside the
source ZIP/DOSZ. On the first successful differencing mount, the runtime creates
a standard type-4 child VHD in its writable memory overlay. Subsequent guest
writes change that child. The save archive contains the child and a small
identity record instead of a copy of the full parent VHD.

```text
Win98.exe
  embedded win98.dosz
    DOSBOX.BAT
    BASE.VHD               completed, immutable Windows installation

%LOCALAPPDATA%\DOSBoxPureStandalone\org.onur.win98.diff.test1\
  embedded.pure.zip
    CHILD.VHD              disk changes
    CHILD.DBI              parent/package identity record
    ...                    other ordinary writable-overlay entries
```

There is no separate child-creation command in `makegame`. Packaging records
the parent identity; launching the package creates the child. The parent remains
inside the EXE, so this feature reduces saved disk data, not the need to include
the base installation in the distributable. The source archive, manifest and
loose parent used during authoring are not required beside the finished EXE.

## Create a package from your installed Windows 98 VHD

Use a completed fixed or dynamic `.vhd`, not a blank disk. Installing Windows
into a child of a blank parent puts the installation itself in the child and
therefore does not provide the intended saving.

The example reads this existing image without changing it:

```text
C:\Program Files\DosBoxPureStandalone\system\Windows 98 Second Edition.vhd
```

Close any emulator using the source before packaging so its bytes are stable.
This recipe includes exactly the contents of that VHD. Changes stored separately
in an existing `.sav` or full-VHD `.pure.zip` are not merged into it. Conversion
of those saves is not implemented in this build.

### 1. Prepare the authoring directory and archive

Run the following in PowerShell. It uses the installed examples and creates a
new directory under Documents. It refuses an existing directory to protect any
previous authoring files. Change `Win98Diff` if that directory already exists.

```powershell
$installDir = 'C:\Program Files\DosBoxPureStandalone'
$parentVhd = Join-Path $installDir 'system\Windows 98 Second Edition.vhd'
$packageDir = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Win98Diff'
$exampleDir = Join-Path $installDir 'examples\win98-differencing'

if (!(Test-Path -LiteralPath $parentVhd -PathType Leaf)) {
    throw "Parent VHD not found: $parentVhd"
}
if (Test-Path -LiteralPath $packageDir) {
    throw "Choose a new package directory: $packageDir"
}
New-Item -ItemType Directory -Path $packageDir | Out-Null
Copy-Item -LiteralPath (Join-Path $exampleDir 'package.json') -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $exampleDir 'defaults.json') -Destination $packageDir

Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$archivePath = Join-Path $packageDir 'win98.dosz'
$zip = [IO.Compression.ZipFile]::Open($archivePath, [IO.Compression.ZipArchiveMode]::Create)
try {
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, $parentVhd, 'BASE.VHD', [IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, (Join-Path $exampleDir 'DOSBOX.BAT'), 'DOSBOX.BAT',
        [IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
}
finally {
    $zip.Dispose()
}
Write-Host "Prepared $packageDir"
```

Only the archive entry is named `BASE.VHD`; the original file is not renamed or
modified. Do not put `CHILD.VHD` or `CHILD.DBI` in this source archive.

The included `DOSBOX.BAT` contains:

```bat
@echo off
imgmount 2 C:\BASE.VHD -t hdd -fs none -diff C:\CHILD.VHD
boot -l c
```

These `C:\` paths belong to the emulator's mounted archive, not the Windows
host filesystem. Disk number `2` selects the first BIOS hard disk, booted as C.
Keep `-t hdd -fs none`; do not add `-size`, because this path uses the validated
VHD geometry. The manifest does not generate or replace these startup commands.

### 2. Review the manifest and defaults

The copied `package.json` is:

```json
{
  "format_version": 1,
  "package_id": "org.onur.win98.diff.test1",
  "title": "Windows 98 - differencing VHD",
  "template": "C:\\Program Files\\DosBoxPureStandalone\\DOSBoxPureStandAlone.exe",
  "archive": "win98.dosz",
  "output": "Win98.exe",
  "default_config": "defaults.json",
  "differencing_vhd": {
    "disk_id": "windows98",
    "parent": "BASE.VHD",
    "child": "CHILD.VHD"
  }
}
```

Use a fresh package ID for this experiment, separate from existing Windows 98
packages. Keep it stable for subsequent builds that should retain these saves.
Manifest paths are relative to the manifest file, except the absolute template
path above. The input `format_version` remains `1`; the builder computes the
parent fingerprint and emits the required newer embedded metadata itself.
For a current-source build, change `template` to that clean runtime's path;
the older Program Files template does not gain milestone 5 behavior automatically.

The supplied `defaults.json` uses the settings from the earlier whole-VHD
Windows 98 boot verification:

```json
{
  "dosbox_pure_memory_size": "64",
  "dosbox_pure_cpu_type": "pentium_slow",
  "dosbox_pure_cpu_core": "dynamic",
  "dosbox_pure_cycles": "auto",
  "dosbox_pure_svgamem": "4"
}
```

These are starting defaults, not evidence of completed Windows 98 testing on
the new differencing path. All values in this configuration file are strings.

### 3. Validate and build

Continue in the same PowerShell session, or set `$packageDir` to the directory
created above:

```powershell
$makegame = 'C:\Program Files\DosBoxPureStandalone\makegame.exe'
$manifest = Join-Path $packageDir 'package.json'

& $makegame $manifest --validate-only
if ($LASTEXITCODE -ne 0) { throw 'Package validation failed.' }

& $makegame $manifest
if ($LASTEXITCODE -ne 0) { throw 'Package build failed.' }
```

Validation checks the archive, startup file, parent metadata and compatible
runtime. It does not boot Windows or create a child. For a later intentional
rebuild, append `--overwrite`; this replaces the output EXE, not its saved disk.
Keep parent bytes, package ID, disk ID and parent/child names unchanged to reopen
the same saved child.

### 4. Launch and use the child

```powershell
Start-Process -FilePath (Join-Path $packageDir 'Win98.exe')
```

This is the step that creates the child on its first successful mount. Complete
any Windows login, use Windows normally, and shut the guest down through its
Start menu before closing the emulator. Later launches mount the same saved
child automatically. The parent file in Program Files is not used at runtime.

The default save archive for this example is:

```powershell
Join-Path $env:LOCALAPPDATA 'DOSBoxPureStandalone\org.onur.win98.diff.test1\embedded.pure.zip'
```

The `CHILD.VHD` entry is a standard differencing VHD, and `CHILD.DBI` is a
512-byte record binding it to this package and exact parent. Back up the whole
save ZIP after a clean shutdown. Keep both entries together; copying only the
child into another package is not a supported import workflow.

If LocalAppData is unavailable, the runtime falls back to the generated EXE's
directory with the same package-ID child directory. Both locations being
unwritable produces a persistence error. Shared resources use the sibling
`DOSBoxPureStandalone\system` directory in LocalAppData, or `system` beside the
EXE under fallback. The Program Files source VHD above is an authoring input,
not a required shared system resource for this package.

## Create independent children of the same parent

To start another independent installation from the same immutable base, copy
the manifest under a second name and give it a new package ID and output:

```powershell
$second = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
$second.package_id = 'org.onur.win98.diff.test2'
$second.title = 'Windows 98 - second independent child'
$second.output = 'Win98-Second.exe'
$secondManifest = Join-Path $packageDir 'package-second.json'
if (Test-Path -LiteralPath $secondManifest) { throw 'Second manifest already exists.' }
[IO.File]::WriteAllText(
    $secondManifest, ($second | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false)
)
& $makegame $secondManifest
if ($LASTEXITCODE -ne 0) { throw 'Second package build failed.' }
```

Launch `Win98-Second.exe` to create its fresh child. Both manifests can use the
same archive, disk ID and VHD names: distinct package IDs isolate their save
directories. Each generated EXE still contains its own immutable parent.
Renaming the first EXE alone does not create a new child; its package ID and
saves stay the same. This workflow starts from the parent, not from changes
already saved in the first child's installation.

## Usage options and examples

Ordinary DOS packaging continues to work:

```powershell
$makegame = 'C:\Program Files\DosBoxPureStandalone\makegame.exe'
& $makegame 'C:\Games\MyGame\game.dosz' 'C:\Games\MyGame\MyGame.exe' `
  --package-id com.example.mygame --title 'My Game' `
  --startup DOSBOX.BAT --emu-perf 486dx2-66 --aspect-ratio padded
```

The template is found beside `makegame.exe`, or can be selected explicitly with
`--template`. These options also work with a manifest; CLI values override
matching manifest inputs. Differencing disk declaration is **manifest-only**;
there is no `makegame --diff`, `--create-child` or `--differencing-vhd` option.
`-diff` belongs to the DOS `IMGMOUNT` command in `DOSBOX.BAT`.

| Option | Values / purpose |
| --- | --- |
| `-h`, `--help`, `/?` | Print usage. |
| `--manifest` | Manifest JSON; alternatively give it as the single positional argument. |
| `--template`, `--archive`, `--output` | Runtime EXE, input ZIP/DOSZ and generated EXE paths. |
| `--package-id`, `--title` | Stable save identity and display title. |
| `--startup` | An existing archive-relative `.BAT`, `.COM` or `.EXE`; not a command with arguments. |
| `--icon` | PNG input for Windows application icons. |
| `--config` | Flat JSON configuration containing string values. |
| `--full-screen` | Fullscreen initial default; omission selects windowed. |
| `--lock-mouse` | Lock pointer on startup; default hotkey Ctrl+F11 toggles it. |
| `--aspect-ratio` | `off`, `on`, `doublescan`, `padded`, `padded-doublescan`, `fill`. |
| `--cycles` | `auto`, `max`, or an integer from `200` to `1000000`. |
| `--emu-perf` | `auto`, `max`, `8086-4.77`, `286-6`, `286-12.5`, `386-20`, `386dx-33`, `486dx-33`, `486dx2-66`, `pentium-100`, `pentium-ii-300`, `pentium-iii-600`, `athlon-1200`. |
| `--cpu-type` | `auto`, `386`, `386_slow`, `386_prefetch`, `486_slow`, `pentium_slow`. |
| `--text-mode` | Show intentional DOS text or interactive text startup screens. |
| `--scanlines`, `--crt-filter` | Select one effect; mutually exclusive. |
| `--validate-only` | Validate without publishing an output EXE; does not run the guest. |
| `--overwrite` | Permit replacing an existing output EXE. |

Choose only one of `--cycles`, `--emu-perf` and `--cpu-type`. For combined CPU
and cycle settings use the configuration JSON, as in the Windows 98 example.
Omitting fullscreen and mouse-lock flags writes windowed/unlocked defaults even
if the input config says otherwise. Existing persisted user settings take
precedence over package defaults on later launches.

For example, make the Windows 98 package default to fullscreen and mouse lock:

```powershell
& $makegame $manifest --full-screen --lock-mouse --aspect-ratio padded --overwrite
```

## Current restrictions and troubleshooting

- One child over one fixed (type 2) or dynamic (type 3) VHD parent; no VHDX or
  multi-level chains. Parent and child must have distinct root-level 8.3 `.VHD`
  names. Use letters, digits, `_` or `-` in their stems. Keep the generated
  `.DBI` name reserved for the runtime. Disk IDs use 1-64 ASCII letters, digits,
  `_` or `-`.
- The empty child is 3,072 bytes and grows in 2 MiB allocation blocks plus
  metadata. Changed sectors scattered across many blocks can still produce a
  large save. Current overlay ZIP entries are uncompressed. The writable child
  cannot exceed 2,147,483,647 physical bytes. Generated EXEs must be under 4 GiB.
- The complete parent is hashed at mount time; large parents can delay startup.
  Changing ZIP compression or timestamps is allowed if the parent file bytes
  stay identical. Changing any parent bytes rejects the existing child, even if
  its UUID and logical contents appear equivalent. Restore the exact matching
  parent or use a new package ID to start a fresh child; saved-data conversion
  is unsupported.
- A parent/binding mismatch is an error, not a request to reset the child.
  Restore the matching EXE/manifest and save backup. Do not delete the `.DBI`
  record to force mounting. Missing, corrupted and copied bindings are rejected.
- Existing full-parent overlay saves, earlier unbound experimental children
  and loose children created with external VHD utilities are not automatically
  adopted. This build has no supported migration, conversion, merge, compaction
  or standalone child export command.
- A lifetime writer lock permits one writable instance per persistence identity.
  Renamed or identically repacked EXEs with the same identity contend for that
  lock; separate package IDs can run independently. Save publication uses checked,
  flushed complete ZIP generations and retains a recoverable preceding generation.
  Host I/O failures remain errors and retain dirty changes for retry. Process-kill
  recovery is tested; physical power-loss survival is not established.
- Continued child writes cannot postpone the first-dirty checkpoint deadline,
  which is at most five host seconds and is polled at the next safe frame,
  including paused frames. Publication completion depends on storage and save
  size. Shutdown, reset and unmount synchronously attempt the same publisher.
- Mounted-child save states and rewind use version-9 machine/disk snapshots,
  limited to 512 MiB of aggregate child bytes. Larger children still mount and
  save normally, but state operations fail. Snapshots have full-copy memory and
  latency costs; callers must refresh state buffers after child growth. Ordinary
  packages retain version-8 states. Preserve known-good save backups.
- Synthetic fixed/dynamic disk, lifecycle, fault, recovery, concurrency and
  state checks have passed, with reviewed Process Monitor coverage of 139
  required launches and no observed loose fixture disks or archive extraction.
  Windows 98 boot/shutdown/reboot acceptance remains milestone 6; the earlier
  whole-VHD Windows 98 result does not close it. The tested build uses BIOS disk
  reset/flush boundaries and leaves hard-disk ATA emulation disabled.

Updating the clean runtime template does not update EXEs already generated
with an older template. Rebuild those deliberately with `makegame`; keep their
original packages and save backups. Legacy full-parent and unbound-child saves
remain rejected without modification; migration was discarded from this scope.
