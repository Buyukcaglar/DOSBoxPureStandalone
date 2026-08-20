# architecture.md

# DOSBox Pure Single-Executable Architecture

## 1. Purpose

This project modifies DOSBox Pure so that a complete DOS game package can be embedded directly inside a Windows executable and accessed from memory at runtime without extracting the game, disk images, emulator assets, or configuration files to disk.

The final distributable should look like this:

```text
GAME.EXE
```

The executable contains:

- DOSBox Pure runtime
- Embedded DOS game archive
- Optional CD-ROM or floppy disk images
- Game-specific configuration
- Startup script
- Metadata and icon resources

The user launches the game by double-clicking the executable.

No installer is required.

No game data is extracted to `%TEMP%`, `%APPDATA%`, the executable directory, or another staging directory.

Persistent changes such as save games are stored separately using DOSBox Pure's writable overlay mechanism.

---

# 2. High-Level Architecture

```text
+------------------------------------------------------+
|                     GAME.EXE                         |
|                                                      |
|  +------------------------------------------------+  |
|  | DOSBox Pure executable code                   |  |
|  +------------------------------------------------+  |
|                                                      |
|  +------------------------------------------------+  |
|  | Embedded game archive                         |  |
|  |                                                |  |
|  | GAME.DOSZ / ZIP                               |  |
|  |                                                |  |
|  |   DOSBOX.BAT                                  |  |
|  |   GAME.EXE                                    |  |
|  |   DATA\                                       |  |
|  |   SOUND\                                      |  |
|  |   SAVE\                                       |  |
|  |   GAME.ISO / GAME.CUE / GAME.IMG (optional) |  |
|  +------------------------------------------------+  |
|                                                      |
|  +------------------------------------------------+  |
|  | Embedded configuration / metadata             |  |
|  +------------------------------------------------+  |
+--------------------------+---------------------------+
                           |
                           |
                           v
                  Embedded resource loader
                           |
                           v
                  Memory-backed data source
                           |
                           v
                DOSBox Pure ZIP filesystem
                           |
              +------------+------------+
              |                         |
              v                         v
       Read-only base              Writable overlay
       game archive                     |
                                        v
                           %LOCALAPPDATA%\...
                               GAME.pure.zip
```

---

# 3. Core Design Principle

The embedded game package must be treated as a read-only base filesystem.

Runtime changes must not alter:

```text
GAME.EXE
```

or the embedded archive.

Instead, modifications made by the emulated DOS environment are written into a separate persistent overlay.

Conceptually:

```text
Embedded archive
        +
Writable overlay
        =
Effective DOS filesystem
```

Example:

```text
Embedded archive:

C:\
  GAME\
    GAME.EXE
    CONFIG.CFG
    DATA\
    SAVE\

Writable overlay:

CONFIG.CFG
SAVE\SAVE1.DAT

Combined DOS view:

C:\
  GAME\
    GAME.EXE
    CONFIG.CFG        <- overlay version
    DATA\
    SAVE\
      SAVE1.DAT       <- overlay file
```

The embedded archive remains immutable.

---

# 4. Embedded Game Storage

The game archive should initially be embedded as a Windows PE resource.

Recommended resource type:

```text
RCDATA
```

Example resource definition:

```rc
IDR_GAME_ARCHIVE RCDATA "game.dosz"
```

At runtime the archive can be accessed using:

```cpp
FindResource()
LoadResource()
LockResource()
SizeofResource()
```

The result is:

```cpp
const void* data;
size_t size;
```

representing the compressed game archive directly inside the executable image.

No temporary file should be created.

---

# 5. Memory-Backed Archive Interface

Source inspection completed on 2026-08-20 shows that DOSBox Pure already has a suitable random-access abstraction: `DOS_File`.

The current native-file implementation is `rawFile`. It wraps a `FILE*` and implements the `DOS_File` read and seek operations. The ZIP reader does not retain or use the native `FILE*` directly. Instead, `Zip_Archive` owns a `DOS_File*` and performs archive access through:

```text
DOS_File::Read
DOS_File::Seek64
```

Phase 2 therefore uses a read-only memory-backed `DOS_File` implementation rather than a new parallel `IDataSource` hierarchy.

Conceptually, the implementation needs:

```text
memory pointer
64-bit byte length
64-bit current position
bounds-checked Read
bounds-checked Seek and Seek64
rejected writes
explicit lifetime ownership
```

The memory-backed file must remain valid for the complete lifetime of the mounted ZIP drive. It must not copy or own the embedded resource unless an existing API makes a copy unavoidable.

If later investigation finds a consumer that cannot use `DOS_File`, a separate generic data-source interface can be reconsidered. It should not be introduced during the proof of concept solely for architectural symmetry.

The logical content path must remain separate from the archive byte source. DOSBox Pure still uses that path for:

- content identity and window title
- drive labels
- save-overlay naming
- adjacent `.conf` lookup
- `.DOSC` patch lookup
- parent `.DOSZ` resolution
- content-browser state

Memory backing replaces only the physical read source. It does not remove logical path metadata.

## 5.1 Phase 2 implementation

The standalone frontend recognizes:

```text
-memory-archive <path>
--memory-archive <path>
```

For ZIP and DOSZ inputs it:

1. opens the selected external archive
2. determines its size with 64-bit file operations
3. reads it once into a frontend-owned `std::vector<Bit8u>`
4. supplies the stable pointer and length through `retro_game_info.data` and `retro_game_info.size`
5. keeps the vector alive until after `retro_unload_game()`

The core associates the memory source with the unchanged logical content path. `DBP_Mount()` supplies a new `memoryFile` only when the mounted path matches that association. All other content continues through the original native-file path.

`memoryFile` is non-owning and read-only. It tracks a 64-bit size and cursor, clamps seeks to the available range, bounds-checks reads and rejects writes. Ownership of the `DOS_File` object follows the existing `Zip_Archive` reference-count lifecycle; ownership of the bytes remains with the frontend.

There is no silent fallback to disk-backed mounting when the explicit mode cannot read or validate its input. The frontend reports the failure and exits the load attempt.

---

# 6. ZIP / DOSZ Integration

The preferred design is to modify the minimum possible portion of DOSBox Pure.

The existing ZIP drive implementation should retain:

- ZIP decompression
- random access
- directory enumeration
- DOS filesystem behavior
- internal disk-image handling
- seek indexing
- writable overlay functionality

Only the physical archive source should change.

## 6.1 Confirmed upstream loading path

The external ZIP/DOSZ path in the current checkout is:

```text
dosbox-pure-unleashed/main.cpp
    OnLoad()
        -> retro_game_info.path
        -> retro_load_game()

dosbox-pure/dosbox_pure_libretro.cpp
    retro_load_game()
        -> dbp_content_path
        -> init_dosbox()
        -> DBP_Mount()
        -> zipDrive::MountWithDependencies()

dosbox-pure/src/dos/drive_zip.cpp
    MountWithDependencies()
        -> fopen_wrap(path, "rb")
        -> rawFile(FILE*)
        -> zipDriveImpl(DOS_File*)
        -> Zip_Archive(DOS_File*)
```

The physical-filename requirement is localized to the outermost archive open in `zipDrive::MountWithDependencies()`. Once `rawFile` has been constructed, ZIP indexing, seeking, decompression and file reads operate on `DOS_File`.

`Zip_Archive` determines the archive size with `Seek64(..., DOS_SEEK_END)`, scans backward for the end-of-central-directory record, loads the central directory and performs bounded random reads. Existing on-demand entry decompression should remain unchanged.

`MountWithDependencies()` also supports:

- opening a ZIP already exposed through a mounted DOS path beginning with `$`
- resolving parent DOSZ archives
- loading an adjacent or explicitly selected DOSC patch

The memory-backed integration must preserve those behaviors. The first proof of concept may inject memory only for the outermost ordinary ZIP while leaving dependency and sidecar loading file-backed.

## 6.2 Confirmed writable-overlay path

During `init_dosbox()` the mounted ZIP drive becomes the read-only underlay of a `unionDrive`:

```text
zipDrive underlay
       +
memoryDrive writable layer
       |
       v
unionDrive
       |
       v
<content-name>.pure.zip
```

The standalone frontend supplies the save directory through `RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY`. `DBP_GetSaveFile()` derives the overlay name from the logical content name. `unionDrive` loads an existing save ZIP into its memory layer, schedules writes after changes and writes pending changes on destruction.

The embedded base archive must continue to be passed only as the underlay. The existing save ZIP remains an ordinary writable file outside the base archive.

## 6.3 Confirmed startup behavior

After mounting drive C, `init_dosbox()` checks the combined drive for `DOSBOX.BAT`. If present, it adds `DOSBOX.BAT` to the generated autoexec sequence. Otherwise, normal Pure Menu and auto-start behavior applies.

Because the lookup is performed through the mounted DOS drive, `DOSBOX.BAT` will continue to work when the base ZIP is memory-backed.

## 6.4 Confirmed disk-image behavior

DOSBox Pure recursively scans the mounted C drive for supported disk images. Entries inside the ZIP are registered as virtual paths such as:

```text
$C:\GAME\GAME.ISO
$C:\GAME\DISK.IMG
```

`FindAndOpenDosFile()` resolves these paths against the mounted DOS drive and returns a `DOS_File`. The FAT image reader and CD-ROM image reader then seek and read that `DOS_File` directly. CUE files and their referenced BIN tracks use the same mounted-path mechanism.

Consequently, changing the outer ZIP from `rawFile` to a memory-backed `DOS_File` should preserve internal ISO, CUE/BIN, IMG, IMA and VHD access without extraction.

## 6.5 Integration boundary

The implemented Phase 2 seam is `zipDrive::MountWithDependencies()`, immediately before it would construct `rawFile` for the outer archive. Its optional `DOS_File*` parameter is used only for the initial ZIP/DOSZ. When no source is supplied, the existing `$`-path and `fopen_wrap()` behavior is unchanged.

The standalone `vfs_implementation.cpp` is not the primary archive integration point. It remains relevant to frontend filesystem operations but does not need to be replaced to prove memory-backed ZIP loading.

---

# 7. Read-Only Base Archive

The embedded archive is always read-only.

DOSBox Pure must never attempt to:

- overwrite it
- resize it
- replace it
- rewrite ZIP metadata
- update entries in place

All changed DOS files must be redirected into the writable overlay.

This is important because modifying the PE executable containing the currently running process would be unsafe and unnecessary.

---

# 8. Save Persistence

Persistent data should be stored outside the executable.

Recommended location:

```text
%LOCALAPPDATA%\<Vendor>\<Game>\
```

Example:

```text
%LOCALAPPDATA%\DOSBoxPurePackages\Duke3D\
```

Possible files:

```text
game.pure.zip
settings.json
controller.cfg
state1.state
```

The minimum required persistent file is normally:

```text
game.pure.zip
```

The exact filename should not depend on the name of an internal temporary archive because no temporary archive exists.

The application should derive the save location from stable embedded metadata such as:

```text
package_id
game_id
```

Example:

```text
package_id = com.example.duke3d
```

This allows the outer executable to be renamed without losing save-game association.

---

# 9. Package Metadata

Each generated executable should contain a small metadata structure.

Suggested fields:

```json
{
  "format_version": 1,
  "package_id": "com.example.duke3d",
  "title": "Duke Nukem 3D",
  "archive_resource": "IDR_GAME_ARCHIVE",
  "startup": "DOSBOX.BAT"
}
```

Additional optional fields may include:

```text
publisher
year
version
icon
default_cpu
default_cycles
machine
memory
joystick_profile
window_mode
aspect_ratio
```

The architecture should avoid hardcoding game-specific settings in the emulator source.

---

# 10. Startup Behavior

The executable must behave like a native game launcher.

Expected flow:

```text
User double-clicks GAME.EXE
        |
        v
Load embedded package metadata
        |
        v
Locate embedded DOSZ/ZIP resource
        |
        v
Create memory-backed DOS_File
        |
        v
Mount embedded archive
        |
        v
Attach writable overlay
        |
        v
Execute DOSBOX.BAT
        |
        v
Game starts
```

No DOSBox file-selection UI should normally appear.

The recommended game archive contains:

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

The exact startup script is game-specific.

---

# 11. Disk Images

The embedded archive may itself contain:

```text
ISO
CUE/BIN
IMG
IMA
VHD
```

Example:

```text
GAME.DOSZ
|
+-- DOSBOX.BAT
+-- GAME\
+-- CD\
    +-- GAME.CUE
    +-- GAME.BIN
```

These images must remain inside the embedded archive.

They must not be extracted before mounting.

The existing DOSBox Pure capability to access disk images contained inside ZIP/DOSZ packages should be retained.

---

# 12. Executable Layout

A generated Windows PE executable may conceptually contain:

```text
PE headers
.text
.rdata
.data
.rsrc
    |
    +-- ICON
    |
    +-- VERSION
    |
    +-- PACKAGE_METADATA
    |
    +-- GAME_ARCHIVE
```

The game archive should preferably be appended as an RCDATA resource during the initial implementation.

Later versions may evaluate alternative formats such as:

```text
custom PE section
appended package container
memory-mapped package segment
```

The first implementation should favor simplicity and maintainability over exotic packaging techniques.

---

# 13. Packaging Tool

The long-term project should contain a separate packager.

Conceptual usage:

```text
makegame.exe game.dosz output.exe
```

or:

```text
makegame.exe package.json
```

Example project directory:

```text
package\
  package.json
  game.dosz
  game.ico
```

Example command:

```text
makegame.exe package\ output\GAME.EXE
```

The packager should:

1. copy a clean DOSBox Pure runtime template
2. embed the DOSZ/ZIP archive
3. embed package metadata
4. embed application icon
5. update PE version information
6. generate the final executable

Eventually the packager may support compression and validation.

---

# 14. Runtime Components

The preferred final executable should statically contain or statically link everything required to start the game.

Avoid runtime dependencies where practical.

Target:

```text
GAME.EXE
```

Not:

```text
GAME.EXE
dosbox-pure.dll
SDL.dll
config.ini
game.zip
```

If a dependency cannot reasonably be statically linked, it must be documented explicitly.

The project should investigate all licenses before deciding how runtime libraries are linked.

---

# 15. Compatibility With Normal DOSBox Pure

The modification should be minimally invasive.

Normal filesystem-based launch behavior should preferably remain functional.

For example:

```text
dosbox-pure.exe game.zip
```

should continue to work during development.

The new embedded mode should be additive rather than replacing ordinary content loading.

Suggested logic:

```text
if embedded package exists:
    launch embedded package
else:
    use normal DOSBox Pure startup path
```

This provides easier debugging and reduces divergence from upstream.

---

# 16. Project Source Layout

Suggested repository structure:

```text
/
├── AGENTS.md
├── README.md
│
├── docs/
│   ├── architecture.md
│   └── requirements.md
│
├── dosbox-pure/
│   └── upstream / modified DOSBox Pure source
│
├── src/
│   ├── embedded/
│   │   ├── embedded_resource.cpp
│   │   ├── embedded_resource.h
│   │   ├── memory_data_source.cpp
│   │   └── memory_data_source.h
│   │
│   └── package/
│       ├── package_metadata.cpp
│       └── package_metadata.h
│
├── tools/
│   └── makegame/
│
└── tests/
```

The final structure can change after studying the upstream source tree.

Avoid restructuring upstream DOSBox Pure unnecessarily.

---

# 17. Development Strategy

Implementation should proceed incrementally.

## Phase 0 — Baseline completed

Baseline validation was completed on 2026-08-20 with:

```text
Visual Studio Professional 2026 18.9.1
Release | x64
Debug | x64
Windows SDK 10.0.26100.0
```

Validated upstream revisions:

```text
dosbox-pure             7f6e8fb7385fa446d1444d671063268520bf9b54
dosbox-pure-unleashed   4a11412248ca4c862751a7d9e6818023795031e9
ZillaLib                a2796bfe0faebe3e5de14b75d6b45866f1576f14
```

The pristine Unleashed solution built successfully in both configurations. The Release executable ran successfully and launched DOS games from ordinary external ZIP files. The normal external-content behavior remains the reference baseline for later comparisons.

## Phase 1 — Source trace completed

The existing DOSBox Pure content path was traced on 2026-08-20 without changing runtime behavior.

Confirmed findings:

- the external archive filename enters through `retro_game_info.path`
- `retro_load_game()` retains it as `dbp_content_path`
- `DBP_Mount()` dispatches ZIP/DOSZ content to `zipDrive::MountWithDependencies()`
- the physical archive is opened with `fopen_wrap()` and wrapped in `rawFile`
- ZIP reads use the existing `DOS_File` random-access interface
- the base ZIP is the underlay of the existing `unionDrive`
- persistent modifications are stored in `<content-name>.pure.zip`
- `DOSBOX.BAT` is discovered through the combined mounted C drive
- internal disk images are opened as `DOS_File` objects through `$C:\...` paths

The source trace identifies a memory-backed `DOS_File` as the smallest practical Phase 2 integration. No runtime behavior was changed during Phase 1.

## Phase 2 — completed

A read-only memory-backed `DOS_File` archive source was implemented and tested with an in-memory copy of a normal ZIP.

The goal is:

```text
disk ZIP
 -> read fully into RAM
 -> memory-backed DOS_File
 -> existing ZIP filesystem
```

This isolates memory-loading changes from PE resource handling.

The automated fixture validation confirmed:

- the frontend loaded the complete external ZIP into RAM
- the core selected the memory-backed mount path
- ZIP directory and file reads succeeded
- `DOSBOX.BAT` executed from the mounted archive
- a DOS write created `PHASE2.OK`
- the existing writable overlay persisted it as `phase2-test.pure.zip`
- launching the same ZIP without the switch continued through the normal path

The proof-of-concept test did not include an internal disk image or Process Monitor capture. Those runtime checks remain required before the later compatibility/no-extraction acceptance claims are complete.

## Phase 3

Load the archive from a Windows PE resource.

Replace:

```text
disk ZIP -> RAM
```

with:

```text
PE RCDATA -> memory-backed DOS_File
```

Verify that no archive file is created on disk.

## Phase 4

Implement deterministic writable overlay paths.

Ensure game saves persist after closing and reopening the executable.

## Phase 5

Implement automatic startup behavior.

## Phase 6

Create the package builder.

## Phase 7

Test ISO/CUE/IMG/VHD content.

## Phase 8

Test multiple representative DOS games.

---

# 18. Testing Strategy

At minimum test:

```text
small floppy-era game
large installed hard-disk game
CD-ROM game
CUE/BIN game
game that writes configuration
game that writes save files
game with long filenames in package
large compressed archive
```

Tests should verify:

- game launches
- files are readable
- files can seek correctly
- DOS filesystem semantics are unchanged
- save files persist
- original executable remains unchanged
- no extraction directory is created
- no archive appears in `%TEMP%`
- no full copy of the archive is written elsewhere

Process Monitor should be used during validation.

Useful monitored operations:

```text
CreateFile
WriteFile
SetEndOfFile
Rename
Delete
```

Expected writes should be restricted to legitimate persistence locations.

---

# 19. Security Considerations

Embedded DOS content should be treated as untrusted input by the package builder.

The packager should validate:

- archive format
- archive size
- metadata length
- malformed resource data
- integer overflow conditions
- invalid package versions

The runtime must perform bounds checking when reading the embedded resource.

A corrupted resource must fail cleanly.

---

# 20. Licensing Considerations

DOSBox Pure licensing requirements must remain satisfied.

Modifications to DOSBox Pure must retain required notices and source availability obligations.

Third-party libraries must be evaluated before they are statically incorporated into distributed executables.

Game content is independent from emulator licensing.

The package builder must not assume that a user has redistribution rights for arbitrary commercial DOS software.

---

# 21. Non-Goals

The first implementation does not need to provide:

- DRM
- encryption
- anti-debugging
- copy protection
- game-content obfuscation
- self-modifying executables
- save data inside the executable
- embedded Windows compatibility layers
- a RetroArch frontend
- multi-game library management
- cloud saves
- networking infrastructure

These may be considered separately later if needed.

---

# 22. Primary Architectural Rule

The most important rule for this project is:

> The game package must be consumed directly from memory as an immutable archive. The archive must never be reconstructed as a temporary physical file merely to satisfy an existing filesystem API.

If a proposed implementation requires:

```text
embedded resource
    ->
temporary game.zip
    ->
DOSBox Pure
```

it does not satisfy the project's architecture.

The desired implementation is:

```text
embedded resource
    ->
memory-backed random-access source
    ->
DOSBox Pure archive filesystem
```

This distinction must remain intact throughout development.
