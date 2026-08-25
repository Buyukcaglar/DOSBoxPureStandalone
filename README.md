# README.md

> **AI assistance disclaimer:** This project has been developed with assistance from OpenAI ChatGPT and Codex. AI was used for upstream code analysis, implementation, documentation, build automation and test support. Although the generated changes are reviewed and tested, AI-assisted work may still contain errors or compatibility issues. Users should independently validate the software for their intended use and report reproducible problems through the project's GitHub Issues page.

# DOSBox Pure Standalone

A downstream DOSBox Pure project for packaging a complete DOS game, DOSBox runtime, configuration and optional disk images into a **single standalone Windows executable**.

The defining goal is simple:

```text
GAME.EXE
```

should be all that is required to distribute and launch the game.

The embedded game package is accessed directly from memory and is **never extracted to disk**.

---

# Project Status

Phase 0 baseline validation, Phase 1 content-loading analysis, Phase 2 memory-backed loading, Phase 3 PE-resource loading, Phase 4 persistent overlays, Phase 5 automatic startup, Phase 6 package metadata and Phase 7 package generation are complete as of 2026-08-20.

Phase 3 embeds a license-safe smoke DOSZ as Windows `RCDATA`. When the executable starts without an explicit content path, Unleashed locates the resource with the Windows resource APIs and passes its memory-mapped pointer directly into the Phase 2 `memoryFile` path.

The Release executable continued to mount and execute the embedded DOSZ while the build-source `.dosz` was temporarily absent. Its `DOSBOX.BAT` wrote `PHASE3.OK`, and the existing union drive persisted the result in `embedded.pure.zip`. Explicit external content and the Phase 2 `-memory-archive` mode remain functional.

Phase 7 adds the `makegame` command-line builder. It validates and embeds a selected ZIP/DOSZ, generates matching metadata, converts an optional PNG into multi-size Windows application-icon resources, updates Windows version information, and can embed a complete `DOSBoxPure.cfg` as package defaults. Archives up to 1.5 GiB use PE resource 101; larger ZIP64 archives are validated, identified, appended, and byte-verified as streams, then mapped directly at runtime so they do not push the Windows PE image over its loader limit or require a complete in-memory copy. Because Windows rejects executable files of 4 GiB or larger before application startup, the finished single EXE must remain below that separate operating-system ceiling. The next milestone is Phase 8 compatibility testing.

Large nested ZIP virtual CDs are also supported. `IMGMOUNT D C:\CD.ZIP -t zip`
preserves 64-bit positions through local, ZIP, union-overlay and mirror file
handles before registering D with MSCDEX. Validation packaged a 3,106,790,056-byte
Ripper archive containing a 3,090,933,320-byte `CD.ZIP`; Ripper detected the
virtual CD-ROM and entered the game without reconstructing the nested ZIP on
disk. Individual DOS-visible ZIP members remain limited to 4 GiB minus one byte,
and the complete generated executable must still remain below 4 GiB.

---

# Goals

The final application should support:

- one-click DOS game launching
- one distributable `.exe`
- no installer
- no external game archive
- no extraction to `%TEMP%`
- no hidden archive reconstruction
- direct memory-backed ZIP/DOSZ access
- persistent DOS save games
- DOSBox Pure writable overlays
- embedded ISO/CUE/BIN/IMG/VHD content
- automatic configured `.EXE`, `.COM` or `.BAT` startup
- game-specific icon and metadata
- automated executable generation

---

# Non-Goals

The initial project does not aim to provide:

- DRM
- encryption
- copy protection
- anti-debugging
- archive obfuscation
- cloud saves
- online services
- a multi-game frontend
- RetroArch integration
- automated game downloads
- save data stored inside the executable

---

# Architecture

The target architecture is:

```text
+---------------------------------------------------+
|                    GAME.EXE                       |
|                                                   |
|   DOSBox Pure runtime                            |
|                                                   |
|   Embedded GAME.DOSZ / ZIP                       |
|      |                                            |
|      +-- DOSBOX.BAT                              |
|      +-- GAME.EXE                                |
|      +-- DATA\                                   |
|      +-- optional ISO/CUE/BIN/IMG/VHD           |
|                                                   |
|   Embedded package metadata                      |
|   Embedded game icon                             |
+-------------------------+-------------------------+
                          |
                          v
              memory-backed archive source
                          |
                          v
                DOSBox Pure ZIP filesystem
                          |
              +-----------+-----------+
              |                       |
              v                       v
       read-only base          writable overlay
                                     |
                                     v
                         %LOCALAPPDATA%\...
```

The embedded archive is immutable.

Files created or modified by the DOS program are persisted separately through a writable overlay.

---

# No Extraction

This project intentionally does **not** use a self-extracting archive design.

The following architecture is forbidden:

```text
GAME.EXE
   |
   v
extract game.zip to TEMP
   |
   v
DOSBox Pure
```

This remains forbidden even if the extracted archive is:

- hidden
- deleted immediately
- placed under AppData
- given a random filename
- created only for the duration of the process

The required model is:

```text
GAME.EXE
   |
   v
embedded archive memory
   |
   v
DOSBox Pure archive reader
```

---

# Why DOSBox Pure?

DOSBox Pure already provides much of the functionality required by this project:

- ZIP/DOSZ-based game packages
- DOS filesystem mounting
- writable archive overlays
- startup scripts
- disk-image handling
- integrated DOSBox emulation

The project therefore aims to modify the **archive backing source**, not replace DOSBox Pure's filesystem and emulation architecture.

---

# Why DOSBox Pure Unleashed?

The project uses DOSBox Pure Unleashed as the standalone Windows host.

DOSBox Pure itself is normally a libretro core.

DOSBox Pure Unleashed already supplies:

- standalone executable startup
- window handling
- audio
- graphics
- input
- frontend behavior

This avoids creating a new libretro frontend.

---

# Repository Layout

Expected layout:

```text
DOSBoxPureStandalone/
│
├── AGENTS.md
├── README.md
│
├── docs/
│   ├── architecture.md
│   └── requirements.md
│
├── dosbox-pure-unleashed/
├── dosbox-pure/
├── ZillaLib/
│
├── packaging/
│
└── tools/
    └── makegame/
```

## `dosbox-pure-unleashed`

Standalone frontend and host executable.

## `dosbox-pure`

Primary emulator source tree.

Most archive/filesystem modifications are expected to occur here.

## `ZillaLib`

Supporting library used by DOSBox Pure Unleashed.

It should remain unmodified unless necessary.

## `docs`

Project-level design documentation.

See:

```text
docs/architecture.md
docs/requirements.md
```

## `packaging`

Reserved for package templates, resource definitions and related files.

## `tools`

Contains the Phase 7 `makegame` executable packager, its Visual Studio/.NET
project, documentation and example manifest/default configuration.

---

# Initial Setup

Clone the three upstream repositories as sibling directories.

Example:

```text
D:\Projects\DOSBoxPureSingleExe\
```

with:

```text
D:\Projects\DOSBoxPureSingleExe\
    dosbox-pure-unleashed\
    dosbox-pure\
    ZillaLib\
```

Place this project's documentation at:

```text
D:\Projects\DOSBoxPureSingleExe\
    AGENTS.md
    README.md

    docs\
        architecture.md
        requirements.md
```

Open the parent directory as the Codex workspace:

```text
D:\Projects\DOSBoxPureSingleExe\
```

This allows Codex to see the project documentation and all three source trees.

---

# Build Baseline First

Before modifying anything:

1. build pristine DOSBox Pure Unleashed
2. run it successfully
3. load a normal DOS ZIP/DOSZ game
4. verify audio, video and input
5. verify normal save-game behavior

Do not begin the memory-backed archive work until a clean baseline build is confirmed.

---

# Development Roadmap

## Phase 0 — Baseline Build (complete)

Build and test unmodified DOSBox Pure Unleashed.

---

## Phase 1 — Content Loading Analysis (complete)

Trace how a game archive moves through the system.

Determine:

```text
Unleashed
    |
    v
content filename
    |
    v
DOSBox Pure
    |
    v
ZIP/DOSZ archive loader
```

Identify exactly where the physical filename becomes required.

No major source changes should be made during this phase.

The completed trace identified `zipDrive::MountWithDependencies()` as the physical-file boundary and the existing `DOS_File` interface as the smallest practical memory-backed integration point. Detailed findings are recorded in `docs/architecture.md`.

---

## Phase 2 — Memory-Backed Archive Proof of Concept (complete)

Start with an ordinary external ZIP.

Instead of letting DOSBox Pure reopen the file directly:

```text
game.zip
```

read it into memory:

```text
game.zip
   |
   v
RAM
```

and expose that memory to the existing ZIP filesystem through a random-access interface.

Target:

```text
external game.zip
        |
        v
RAM buffer
        |
        v
DOSBox Pure ZIP filesystem
```

The game should run normally.

This proves that a physical archive file is not required by the archive layer.

Run the Phase 2 mode with:

```powershell
DOSBoxPureStandAlone.exe -memory-archive "C:\Games\game.zip"
```

or:

```powershell
DOSBoxPureStandAlone.exe -memory-archive "C:\Games\game.dosz"
```

In this proof of concept, the standalone frontend performs the one permitted input-file read and owns the RAM buffer for the complete core lifetime. DOSBox Pure receives the original path only as logical metadata for naming, overlays, parent archives and sidecars; the outer ZIP/DOSZ bytes are read through `memoryFile`.

Without `-memory-archive`, ordinary external ZIP/DOSZ loading remains unchanged.

Phase 2 deliberately does not yet include:

- PE resource embedding
- automatic embedded-package detection
- stable package metadata or package IDs
- deterministic `%LOCALAPPDATA%` save paths
- a package-builder tool

Parent DOSZ archives and DOSC sidecars also remain path-backed during this proof of concept.

---

## Phase 3 — Windows PE Resource (complete)

Embed the game archive into the standalone executable.

Initial format:

```text
RCDATA
```

Load it using the Windows resource APIs:

```text
FindResource
LoadResource
LockResource
SizeofResource
```

Target:

```text
GAME.EXE
   |
   +-- RCDATA game.dosz
           |
           v
     memory pointer
           |
           v
     DOSBox Pure
```

No archive copy should be written to disk.

Normal Visual Studio builds produce a clean runtime template with no game
archive or package metadata. The license-safe development fixture remains
available through an explicit MSBuild property:

```powershell
MSBuild.exe dosbox-pure-unleashed\DOSBoxPure-vs.vcxproj `
  /p:Configuration=ReleaseGLCORE /p:Platform=x64 `
  /p:EmbedDevelopmentPackage=true
```

That opt-in build embeds:

```text
dosbox-pure-unleashed\embedded\phase3-smoke.dosz
```

as resource:

```text
IDR_EMBEDDED_ARCHIVE RCDATA
```

The fixture contains `DOSBOX.BAT` plus a generated 1.44 MB FAT12 floppy image named `DISK.IMA`. At startup, the batch file mounts the image from inside the embedded DOSZ, reads `A:\IMAGE.OK`, and writes `PHASE3.IMG` to the normal overlay only when that internal-image read succeeds.

Run the opt-in fixture executable without arguments to select the embedded archive automatically:

```powershell
DOSBoxPureStandAlone.exe
```

The runtime uses the logical path `embedded.dosz` for DOSBox Pure content identity and overlay naming. The build-source DOSZ is not needed after linking; runtime testing succeeded while that file was temporarily moved away.

The 2026-08-20 Release validation produced both fixture sentinels in `saves\embedded.pure.zip`:

```text
PHASE3.OK   = PHASE3_PE_RESOURCE_OK
PHASE3.IMG  = PHASE3_INTERNAL_DISK_IMAGE_OK
```

A Process Monitor capture of that same run contained 64,555 events for `DOSBoxPure.exe` (PID 42060). It recorded no access under `%TEMP%`, `%LOCALAPPDATA%\Temp` or `C:\Windows\Temp`, no physical access to `DISK.IMA`, `IMAGE.OK`, `DOSBOX.BAT` or `embedded.dosz`, and no truncate, rename or delete operations. The only successful application-data `WriteFile` was the expected `saves\embedded.pure.zip`; one additional successful 8-byte write was NVIDIA driver timestamp activity under `C:\ProgramData\NVIDIA Corporation\Drs`.

Development compatibility is preserved:

```powershell
DOSBoxPureStandAlone.exe "C:\Games\game.zip"
DOSBoxPureStandAlone.exe -memory-archive "C:\Games\game.zip"
```

An explicit content path takes precedence over the embedded resource. The first command uses the original file-backed path, and the second uses the Phase 2 external-file-to-RAM path.

Phase 3 did not provide package metadata or a final save location. Phase 4 supplied deterministic archive-derived package identity and the final persistence-root behavior; Phase 6 replaces that interim identity with a human-defined metadata `package_id` and applies the metadata display title. Phase 7 now automates resource and metadata generation through `makegame`. The Process Monitor result confirms no extraction for the development fixture and captured build; broader title and image-format compatibility remains Phase 8 testing work.

---

## Phase 4 — Persistent Overlay (complete)

Ensure files written by DOS programs survive between launches.

Primary persistence root:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\
```

Package-specific and shared-system paths:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\<package_id>\
%LOCALAPPDATA%\DOSBoxPureStandalone\system\
```

If this root cannot be created or is not writable, the application must try
the directory containing the running executable as its fallback root, using
the same child layout. Failure of both locations must produce a clear error.

The embedded archive remains read-only.

Phase 6 packages use the stable human-defined metadata `package_id`. For
compatibility with Phase 3/4 executables that have no metadata resource, the
standalone frontend still derives a rename-safe identity from the embedded
archive bytes and size:

```text
archive-<fnv1a64>-<size-hex>
```

For example, the Phase 3 smoke package uses:

```text
archive-edba7044deb62010-786
```

Startup creates and performs an actual write check on the common root, package
directory and shared `system` directory. When both the Local AppData location
and executable-directory fallback fail, the dedicated executable reports a
visible persistence error and exits instead of running without saves.

Release validation used an isolated Local AppData root and repeated the smoke
package launch. Both `PHASE3.OK` and the internal-disk `PHASE3.IMG` sentinel
remained in the valid package-specific `embedded.pure.zip`; no adjacent
`saves` or `system` directory was created. A second run with `LOCALAPPDATA`
pointing at a regular file selected the executable-directory fallback and
produced the same valid overlay there. An explicit external memory-archive
launch retained the original adjacent `saves` and `system` behavior.

---

## Phase 5 — Automatic Launch (complete)

The generated executable should start the configured DOS title immediately.

Packages can use a root startup script:

```text
DOSBOX.BAT
```

Example:

```bat
@echo off
cd GAME
GAME.EXE
exit
```

Alternatively, Phase 7 metadata can select an archive-relative `.EXE`, `.COM`
or `.BAT` directly. The runtime adds the selected command followed by `exit` to
the generated in-memory autoexec sequence; it does not create a physical batch
file. Returning from the selected program therefore closes the dedicated
standalone executable instead of opening the Pure Menu completion prompt.

No file-selection UI should appear for normal packaged games.

When content is selected from the embedded PE resource, the standalone frontend now applies dedicated-package defaults:

- the DOSBox Pure animated startup logo is skipped
- the DOS framebuffer remains hidden until DOSBox Pure reports that the packaged program has produced a ready game display
- the Start Menu behavior is overridden to exit the standalone executable immediately when the top-level `exit` in `DOSBOX.BAT` runs

Embedded packages default to graphics presentation and become visible only when they enter a graphics video mode. After readiness is detected, the frontend waits for three fresh core-video submissions before exposing the hardware-rendered surface, because the emulated video mode can change before the surface receives its new pixels. This deterministic default prevents both slow text initialization and a stale final DOS frame from flashing.

Packages that require visible DOS text opt in with `makegame --text-mode`, manifest `"text_mode": true`, or a legacy empty root-level `TEXTMODE.DBP` marker already present in the source archive. This covers both a game such as KROZ that remains in text mode and a graphical game such as Sid Meier's Civilization whose startup asks questions in text mode before entering graphics. It is not needed for noninteractive initialization text; Beneath a Steel Sky has no required text-mode interaction and therefore omits it. New packages record the choice in package metadata, so the builder embeds the source ZIP/DOSZ byte-for-byte unchanged. Text-mode screens become visible after remaining in text mode for one second and replacing at least one third of the original shell cells; sparse text applications use a 15-second safety fallback.

The embedded-package defaults also prevent the `Unable to exit top DOS shell` warning after the game returns to `DOSBOX.BAT`.

These defaults are scoped to automatic embedded-resource startup. Explicit external ZIP/DOSZ launches retain the ordinary DOSBox Pure Unleashed presentation and Start Menu behavior.

---

## Phase 6 — Package Metadata (complete)

The executable now embeds a separate JSON package description as Windows
resource `IDR_EMBEDDED_METADATA` (`RCDATA`, numeric ID `102`). Normal-size game
archives remain the independent `IDR_EMBEDDED_ARCHIVE` resource (`RCDATA`,
numeric ID `101`). The development fixture is:

```json
{
  "format_version": 1,
  "package_id": "org.dosboxpurestandalone.phase3-smoke",
  "title": "DOSBox Pure Standalone - Phase 3 Smoke Test",
  "startup": "DOSBOX.BAT",
  "archive_resource": 101,
  "archive_identity": "edba7044deb62010-786"
}
```

The runtime reads the metadata directly from the PE-mapped resource with a
64 KiB bound and requires a JSON object with `format_version` equal to `1`.
The `package_id` is a safe single directory component and supplies stable save
identity at:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\<package_id>\
```

Renaming the executable or updating the embedded archive therefore does not
disconnect existing saves as long as the package retains its `package_id`.
`archive_identity` binds this particular metadata payload to the archive bytes
using the existing `<fnv1a64>-<size-hex>` identity. This is a packaging
consistency check, not a cryptographic signature; a builder must update it when
the archive changes while retaining the stable `package_id`.

For archives larger than 1.5 GiB, metadata uses `"archive_storage": "appended"`
instead of `archive_resource`. The builder places the compressed archive after
the PE image with a bounds-checked 32-byte trailer. The runtime maps those bytes
read-only from its own executable and passes the mapped memory to DOSBox Pure;
it does not extract or reconstruct an archive file.

Phase 7-generated metadata may additionally use `default_config_resource: 103`
to identify an in-memory package-default configuration. The optional UTF-8
`title` becomes the native application window title. The optional `startup`
field defaults to `DOSBOX.BAT` and may identify a safe archive-relative
`.EXE`, `.COM` or `.BAT` file.

If resource `102` is absent, Phase 3/4 compatibility is preserved through the
archive-derived `archive-<fnv1a64>-<size-hex>` package ID. If metadata is
present but malformed, unsafe, unsupported or paired with the wrong archive,
startup displays an error and exits before creating persistence directories.

Release validation confirmed that the fixture selected
`org.dosboxpurestandalone.phase3-smoke`, created and reused its valid
`embedded.pure.zip`, and exposed the metadata title. A resource-updated archive
with a matching new `archive_identity` reused the same package directory. A
metadata-free executable used the Phase 4 compatibility ID, while an unsafe
package ID and an archive/metadata mismatch were both rejected before any
persistence root was created.

---

## Phase 7 — Package Builder (complete)

The .NET 8 Windows tool is located at:

```text
tools\makegame\makegame.csproj
```

Open the project in Visual Studio 2026 or build it with:

```powershell
dotnet build .\tools\makegame\makegame.csproj -c Release
```

The downloadable Windows x64 build is published as a self-contained,
single-file executable. It carries the required .NET 8 runtime, so package
authors do not need to install .NET separately:

```powershell
dotnet publish .\tools\makegame\makegame.csproj `
  -c Release -r win-x64 --self-contained true `
  -o .\tools\makegame\publish\win-x64
```

Manifest packaging:

```text
makegame.exe package.json
```

Direct packaging:

```powershell
makegame.exe game.dosz GAME.EXE --template DOSBoxPureStandAlone.exe `
  --package-id com.example.game --title "Example Game" `
  --startup GAME.EXE --emu-perf 486dx2-66 --full-screen --lock-mouse `
  --aspect-ratio padded --crt-filter
```

The builder performs:

```text
validated runtime template
  + validated ZIP/DOSZ and startup target
  + generated package metadata (including optional text-mode declaration)
  + optional PNG-derived Windows icon set
  + optional DOSBoxPure.cfg defaults
  + generated Windows version resource
  -> one verified GAME.EXE
```

PNG input is decoded and letterboxed without distortion into 16, 24, 32, 48,
64, 128 and 256-pixel `RT_ICON` frames. The `ZL` application icon group is
replaced and Windows icon extraction is used to verify the result.

The optional default config is the flat JSON format written by DOSBox Pure
Unleashed. It can carry the full recognized option set, including memory,
cycles, emulated graphics hardware, scaling, scanlines and CRT
filter parameters. Resource `103` is parsed directly from the executable and
is never reconstructed on disk. Its precedence is:

```text
dedicated-package safety overrides
  > persisted user settings
  > embedded package defaults
  > built-in defaults
```

Therefore the packaged configuration supplies first-launch defaults while
later user changes remain effective.

Frequently used presentation defaults are also available directly on the
command line:

```text
--full-screen
--lock-mouse
--aspect-ratio off|on|doublescan|padded|padded-doublescan|fill
--cycles auto|max|200..1000000
--emu-perf auto|max|8086-4.77|286-6|286-12.5|386-20|386dx-33|486dx-33|486dx2-66|pentium-100|pentium-ii-300|pentium-iii-600|athlon-1200
--cpu-type auto|386|386_slow|386_prefetch|486_slow|pentium_slow
--text-mode
--scanlines
--crt-filter
```

`--cycles`, `--emu-perf`, and `--cpu-type` are mutually exclusive, each may
appear only once, and explicit values override the matching key in `--config`.
Both `--cycles` and the abbreviated hardware presets exposed by `--emu-perf`
set `dosbox_pure_cycles`; `--cpu-type` sets `dosbox_pure_cpu_type`. Cycles accepts
`auto`, `max`, or a whole number from 200 through 1,000,000. The CPU-type list
matches the six types compiled into this runtime. Windowed is the native
package default when `--full-screen` is omitted; the builder writes
`screen_fullscreen: false` even if `--config` contains a conflicting value.
Supplying `--full-screen` writes `screen_fullscreen: true`. Similarly,
`--lock-mouse` writes `interface_lockmouse: true` so the pointer is captured at
startup; omitting it writes `false`. Ctrl+F11 continues to toggle mouse capture
during play. These command-line defaults replace conflicting `--config` values,
while persisted user settings can still take precedence on later launches. `--aspect-ratio`
sets `dosbox_pure_aspect_correction`; `off` and `on` map
to the core's `false` and `true` values, while the other four CLI values map
directly to their identically named core modes. The six modes are mutually
exclusive, and repeating `--aspect-ratio` is rejected. `--scanlines` selects scanlines-only mode with normal gaps;
`--crt-filter` selects TV-style CRT phosphors with normal scanlines. Both flags
also select the sharpest blur setting and disable curvature and rounded corners.
The two effect flags are mutually exclusive, and explicit CLI values override
matching values in `--config`.

Packages that need intentional DOS text to be visible can use `--text-mode`.
That includes fully text-mode games such as KROZ and graphical games with
interactive text-mode startup screens such as Civilization. The manifest
equivalent is `"text_mode": true`. The builder records the declaration in
package metadata and embeds the source ZIP/DOSZ byte-for-byte unchanged.
Existing archives with a manually supplied root-level `TEXTMODE.DBP` marker
remain compatible. Omit
the option for noninteractive transitional text, as with Beneath a Steel Sky.

The defaults JSON may also contain the reserved builder directive
`"package_startup": "GAME\\GAME.EXE"`. It is removed from the embedded option
set and used only when neither `--startup` nor manifest `startup` was supplied.
If no startup is specified through those three mechanisms, the builder retains
the root-level `DOSBOX.BAT` requirement. In every case the resolved target must
exist inside the archive.

The tool also validates safe archive paths, duplicate entries, readable ZIP
contents, metadata limits, config key/value structure, PNG decoding and PE
resource output. It writes through a temporary executable beside the requested
output and moves it into place only after resource verification. Existing
output requires `--overwrite`; `--validate-only` performs all input checks
without generating a package.

See [docs/makegame-guide.md](docs/makegame-guide.md) for the complete end-user
guide, every command-line option, manifest schema, configuration examples and
troubleshooting guidance. Developer-oriented notes remain in
[tools/makegame/README.md](tools/makegame/README.md).

---

# Example Final Package

Development input:

```text
Duke3DPackage\
│
├── package.json
├── duke3d.dosz
├── duke3d.png
├── DOSBoxPure.defaults.cfg
└── DOSBoxPureStandAlone.exe
```

Build command:

```text
makegame.exe Duke3DPackage\package.json
```

Output:

```text
DUKE3D.EXE
```

The executable is copied to another Windows machine.

The user performs:

```text
double-click DUKE3D.EXE
```

and the game starts.

No installation and no game extraction occurs.

---

# Save Data

Persistent user data is intentionally separate from the executable.

Example:

```text
DUKE3D.EXE
```

with runtime persistence under:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\com.example.duke3d\
```

Possible contents:

```text
game.pure.zip
settings.cfg
state1.state
```

This means the distributed application remains one file while user-created state persists correctly.

---

# Embedded Disk Images

A DOSZ package may contain disk images.

Example:

```text
GAME.DOSZ
│
├── DOSBOX.BAT
├── GAME\
└── CD\
    ├── GAME.CUE
    └── GAME.BIN
```

These disk images must remain inside the compressed embedded archive.

They must not be unpacked to a temporary directory before mounting.

The project should preserve DOSBox Pure's existing internal disk-image support where possible.

---

# Memory Source

A likely technical direction is a generic random-access archive source.

Conceptually:

```cpp
class IDataSource
{
public:
    virtual ~IDataSource() = default;

    virtual uint64_t Size() const = 0;

    virtual size_t Read(
        uint64_t offset,
        void* destination,
        size_t bytes) = 0;
};
```

Possible implementations:

```text
FileDataSource
MemoryDataSource
```

This is an architectural suggestion rather than a mandatory implementation.

The actual DOSBox Pure source should be studied first to identify the smallest reliable integration point.

---

# Runtime Validation

The no-extraction requirement must be verified at runtime.

Use Sysinternals Process Monitor.

Monitor at least:

```text
CreateFile
WriteFile
SetEndOfFile
Rename
Delete
```

Check:

```text
%TEMP%
%LOCALAPPDATA%\Temp
executable directory
save directory
```

The game archive and game files must never appear as extracted physical content.

Expected filesystem writes should consist only of legitimate persistent user data.

---

# Acceptance Criteria

The first major milestone is successful when:

- a game archive is embedded inside a Windows executable
- no external archive is needed
- double-clicking the executable starts the game
- the archive is accessed directly from memory
- no archive copy is written to disk
- no archive content is extracted
- DOS filesystem reads work normally
- DOS filesystem writes work normally
- save games survive restart
- the executable remains unchanged
- a disk image inside the embedded archive can be used
- Process Monitor confirms there is no hidden extraction

---

# Documentation

Detailed technical architecture:

```text
docs/architecture.md
```

Detailed requirements and acceptance criteria:

```text
docs/requirements.md
```

Instructions for Codex and other coding agents:

```text
AGENTS.md
```

If implementation behavior changes, update the documentation alongside the code.

---

# Licensing

This project is based on upstream open-source projects.

All applicable licensing requirements and notices must be preserved.

The emulator's license does not grant redistribution rights for DOS games.

Anyone building a package is responsible for ensuring they have the legal right to distribute the game content they embed.

---

# Project Principle

The central rule of this project is:

```text
embedded compressed archive
          |
          v
        memory
          |
          v
DOSBox Pure archive filesystem
```

not:

```text
embedded compressed archive
          |
          v
temporary physical archive
          |
          v
DOSBox Pure
```

If an implementation needs to extract or reconstruct the embedded archive on disk, it is not the architecture this project is intended to build.
