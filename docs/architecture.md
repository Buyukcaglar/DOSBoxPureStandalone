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

The Visual Studio build now embeds the development archive as a Windows PE resource.

Resource type:

```text
RCDATA
```

Current resource definition:

```rc
IDR_EMBEDDED_ARCHIVE RCDATA "embedded\\phase3-smoke.dosz"
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

## 4.1 Phase 3 resource loader

On Windows, Unleashed calls:

```text
FindResourceW
SizeofResource
LoadResource
LockResource
```

for `IDR_EMBEDDED_ARCHIVE`. The returned pointer addresses the resource bytes mapped with the executable image. It remains valid for the process lifetime and is supplied directly through `retro_game_info.data`; the resource is not copied into the Phase 2 `std::vector`.

The resource is given the logical path:

```text
embedded.dosz
```

This retains DOSBox Pure's path-based content identity and currently produces the writable overlay name `embedded.pure.zip`. Phase 4 will replace this development identity with a deterministic package-specific persistence path.

Startup selection is:

```text
explicit external content path
        -> preserve normal or -memory-archive behavior

no explicit content path + valid RCDATA
        -> use embedded memory pointer

no explicit content path + no RCDATA
        -> preserve configured/default frontend behavior
```

If the resource exists but is empty or cannot be locked, startup reports an error and returns a failure code. It does not fall back to archive extraction or reconstruction.

Phase 3 validation temporarily moved the build-source `phase3-smoke.dosz` away after linking. The Release executable still mounted the embedded archive, executed its `DOSBOX.BAT` and persisted `PHASE3.OK` through the normal writable overlay. This proves the linked executable does not require the source DOSZ at runtime.

The fixture was then extended with a deterministic, license-safe FAT12 floppy image generated by `embedded/phase3-smoke/make_floppy.py`. `DOSBOX.BAT` mounts `DISK.IMA` directly from the embedded DOSZ and checks for `A:\IMAGE.OK`. A successful internal-image read writes `PHASE3.IMG` to the existing overlay. Both Debug and Release runs produced:

```text
PHASE3.OK   = PHASE3_PE_RESOURCE_OK
PHASE3.IMG  = PHASE3_INTERNAL_DISK_IMAGE_OK
```

Process Monitor captured the Release run on 2026-08-20. The capture was filtered after collection to the single `DOSBoxPure.exe` process (PID 42060), yielding 64,555 events. Analysis found:

- no filesystem events under `%TEMP%`, `%LOCALAPPDATA%\Temp` or `C:\Windows\Temp`
- no physical path events for `DISK.IMA`, `IMAGE.OK`, `DOSBOX.BAT` or `embedded.dosz`
- no end-of-file, allocation, disposition, rename or delete operations
- one successful application-data write, to the intended `saves/embedded.pure.zip` overlay
- one unrelated successful 8-byte NVIDIA driver timestamp write under `C:/ProgramData/NVIDIA Corporation/Drs`

This confirms that the captured build did not reconstruct or extract the embedded archive or its floppy image during this fixture run. It is evidence for the tested Phase 3 path, not a substitute for the broader Phase 8 title and disk-format compatibility matrix.

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

After mounting drive C, `init_dosbox()` first checks for a validated embedded
metadata startup path. A custom `.EXE`, `.COM` or `.BAT` is added to the
generated in-memory autoexec sequence and followed by top-shell `exit` so the
dedicated executable closes after the program returns without consulting Pure
Menu's single-executable/autoboot completion heuristic. If metadata uses
the default `DOSBOX.BAT`, the existing combined-drive lookup and batch startup
path is retained. Otherwise, normal Pure Menu and auto-start behavior applies.

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

Primary persistence root:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\
```

The root contains package-specific data and a shared system-resource directory:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\<package_id>\
%LOCALAPPDATA%\DOSBoxPureStandalone\system\
```

The package-specific directory stores writable overlays, settings, controller
configuration and save states. The shared `system` directory stores optional
resources such as SoundFonts, MT-32 ROMs and system DOSZ files.

Startup must verify that the primary root can be created and written. If that
check fails, it must try the directory containing the running executable as a
fallback root and preserve the same child layout. If both roots are
unavailable, startup must report a clear persistence error rather than run
with silently discarded writes.

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

Each generated executable contains a small JSON metadata structure in
`IDR_EMBEDDED_METADATA` (`RCDATA`, numeric resource 102). Format version 1 is:

```json
{
  "format_version": 1,
  "package_id": "com.example.duke3d",
  "title": "Duke Nukem 3D",
  "startup": "DOSBOX.BAT",
  "archive_resource": 101,
  "archive_identity": "<fnv1a64>-<size-hex>",
  "default_config_resource": 103
}
```

The archive and metadata are separate PE resources. `package_id` is stable
package identity and determines persistence; `archive_identity` changes with
the linked archive and guards against an incomplete resource update. The
runtime reads metadata directly from the PE mapping and does not reconstruct
it as a physical file. `default_config_resource` is emitted only when the
package builder embeds a default DOSBox Pure configuration.

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
Execute metadata startup target
        |
        v
Game starts
```

No DOSBox file-selection UI should normally appear.

The recommended game archive either contains:

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

For archives without `DOSBOX.BAT`, metadata can instead name a safe relative
`.EXE`, `.COM` or `.BAT` that exists inside the mounted archive. The runtime
generates the command in memory and does not modify or reconstruct the archive.

## 10.1 Dedicated embedded-package presentation

The standalone frontend marks a launch as dedicated-package mode only when no explicit external content path was supplied and a valid embedded PE archive resource was selected.

In dedicated-package mode it:

1. overrides `dosbox_pure_menu_time` to `0` before `retro_load_game()` initializes DOSBox Pure
2. skips the Unleashed `DrawIntro()` logo animation
3. clears the window normally but does not draw the DOS framebuffer until `DBPS_IsStartupVideoReady()` reports a ready packaged-program display and three fresh core-video submissions have completed

The menu-time override allows the top-level `exit` command at the end of `DOSBOX.BAT` to shut down the standalone frontend immediately. Hiding the framebuffer prevents both the DOS shell and text-mode initialization emitted by a graphics game from flashing before the game establishes its first graphical frame. The additional frame-submission barrier handles the hardware-rendering handoff where the emulated mode changes before the shared surface stops containing its last DOS frame. The start-menu OSD remains available as a recovery surface if it is opened explicitly.

`DBPS_IsStartupVideoReady()` supports both graphical and text-mode games:

- embedded packages default to graphics presentation and reveal immediately once the packaged program enters a graphics video mode
- a package that intentionally uses a DOS text display opts in with an empty root-level `TEXTMODE.DBP` archive marker
- on entry to a text-mode program, the core snapshots the current visible character/attribute cells
- text readiness is ignored for the first second, preventing a graphics game's temporary text-page or text-resolution changes from exposing a transitional DOS frame
- after that dwell, a text-mode game reveals when at least one third of those cells have changed or the program changes the visible text page or text resolution
- a 15-second fallback reveals sparse text applications that intentionally update less than one third of the screen

This keeps Dune II's transitional `SET BLASTER` and memory-detection lines hidden regardless of their duration. A full-screen text game such as KROZ remains supported by including `TEXTMODE.DBP`; without that explicit marker an embedded package never exposes text mode during startup.

Explicit external content paths do not enable dedicated-package mode, preserving normal DOSBox Pure Unleashed behavior for development and ordinary use.

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
    |
    +-- DEFAULT_CONFIG (optional)
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

Phase 7 provides a separate .NET 8 Windows packager under `tools/makegame`.

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
  game-icon.png
  DOSBoxPure.defaults.cfg
  DOSBoxPureStandAlone.exe
```

Example command:

```text
makegame.exe package\package.json
```

The packager:

1. copy a clean DOSBox Pure runtime template
2. embed the DOSZ/ZIP archive
3. embed package metadata
4. optionally decode PNG and embed a multi-size Windows application icon
5. update PE version information
6. optionally embed a complete default `DOSBoxPure.cfg` as resource 103
7. reload and verify the generated executable before moving it into place

Archive validation reads every ZIP member, rejects unsafe or duplicate paths,
and requires the resolved startup file to exist. Startup resolves from CLI,
manifest, reserved defaults-JSON `package_startup`, then root `DOSBOX.BAT`.
Input archive bytes are stored directly as resource 101; packaging does not
extract them.

The PNG converter preserves aspect ratio and centers rectangular images on a
transparent square. It generates 16, 24, 32, 48, 64, 128 and 256-pixel PNG
icon frames, updates `RT_ICON` and the `ZL` `RT_GROUP_ICON`, and verifies that
Windows can extract the result.

The optional config is validated as a flat JSON object with string values,
normalized to UTF-8 without a BOM and embedded as resource 103. At runtime it
is parsed in place and stored in a separate fallback layer:

```text
ConfigOverrides        dedicated-package invariants
        >
persistent settings    user choices under the package persistence path
        >
ConfigDefaults         immutable resource 103
        >
core defaults
```

This permits a package author to supply every DOSBox Pure option recognized by
the bundled runtime without hardcoding a growing option list in the builder.
The reserved `package_startup` value is removed before resource 103 is written
and promoted into metadata only when CLI and manifest startup are absent.
Other path and content selection remains controlled by the runtime rather than
the defaults layer.

The builder can merge common presentation options without a separate config:

```text
--window-mode windowed|fullscreen  -> screen_fullscreen false|true
--scanlines                        -> interface_crtfilter 1, interface_crtscanline 3,
                                      interface_crtblur 7, interface_crtcurvature 0,
                                      interface_crtcorner 0
--crt-filter                       -> interface_crtfilter 2, interface_crtscanline 3,
                                      interface_crtblur 7, interface_crtcurvature 0,
                                      interface_crtcorner 0
```

CLI presentation values replace matching config-file values before resource
103 is serialized. When no window value is supplied by either source, the
runtime's windowed default remains in effect. Scanlines-only and full CRT mode
are mutually exclusive; the latter already includes scanlines.

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

## Phase 3 — completed

The development DOSZ is loaded from a Windows PE `RCDATA` resource.

Replace:

```text
disk ZIP -> RAM
```

with:

```text
PE RCDATA -> memory-backed DOS_File
```

Validated behavior:

- Debug and Release x64 builds contain `IDR_EMBEDDED_ARCHIVE`
- no-argument startup selects the embedded DOSZ automatically
- `LockResource()` bytes flow directly into the existing memory-backed `DOS_File`
- `DOSBOX.BAT` executes from the embedded archive
- `PHASE3.OK` persists in the existing `embedded.pure.zip` overlay
- the embedded DOSZ's `DISK.IMA` mounts without being extracted
- reading `A:\IMAGE.OK` produces `PHASE3.IMG` in the writable overlay
- the Release executable works while the source DOSZ is absent
- explicit normal and Phase 2 memory-backed external launches remain functional
- Process Monitor found no archive/image extraction or temp-directory access in the captured Release fixture run

The fixture's no-extraction and internal floppy-image checks are complete. Broader compatibility testing with representative ZIP/DOSZ titles and ISO, CUE/BIN, IMG/IMA and VHD images remains Phase 8 work.

## Phase 4 — completed

Dedicated embedded packages now initialize persistence before the core is
loaded. Packages with Phase 6 metadata use the human-defined `package_id`.
When metadata is absent for compatibility, the frontend derives an identity
from the FNV-1a 64-bit hash and byte size of the PE resource:

```text
archive-<fnv1a64>-<size-hex>
```

This prevents different legacy embedded archives from sharing an overlay and
remains stable when the executable is renamed. The archive-derived identity is
only compatibility behavior when resource `IDR_EMBEDDED_METADATA` is absent.

The primary layout is:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\<package_id>\embedded.pure.zip
%LOCALAPPDATA%\DOSBoxPureStandalone\<package_id>\DOSBoxPure.cfg
%LOCALAPPDATA%\DOSBoxPureStandalone\system\
```

Startup creates and write-tests the common root, package directory and shared
system directory. If any primary-path operation fails, it tries the directory
containing the running executable as the fallback root and preserves the same
child layout. If the fallback also fails, the application displays a clear
error and exits before loading the embedded game.

The frontend continues to return the package directory through
`RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY` and the shared directory through
`RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY`. DOSBox Pure therefore keeps using
its existing overlay writer and the embedded archive remains immutable.

Validation used an isolated writable Local AppData root for two consecutive
Release launches. The same package path was selected both times, its
`embedded.pure.zip` remained valid and contained `PHASE3.OK` and
`PHASE3.IMG`, and no `saves` or `system` directory appeared beside the
executable. Pointing `LOCALAPPDATA` at a regular file forced the executable-
directory fallback, which produced the same valid overlay. An explicit Phase
2 memory-archive launch retained ordinary Unleashed save/system paths.

## Phase 5 — completed

Automatic embedded-package presentation now:

- skips the DOSBox Pure Unleashed startup animation
- hides the DOS framebuffer until the packaged program has produced either a graphics frame or a substantially replaced text screen
- starts a root-level `DOSBOX.BAT` without showing the command shell
- permits its top-level `exit` command to close the standalone executable immediately
- leaves explicit external content launches unchanged

Validation used the license-safe Phase 3 smoke package and the local Dune II test package. The clean smoke run exited by itself with code `0` and did not emit the top-shell warning. Visual inspection of the Dune II build found its Westwood logo to be the first exposed application frame.

## Phase 6 — completed

The Windows executable now embeds package JSON as `IDR_EMBEDDED_METADATA`, a
second `RCDATA` resource independent of `IDR_EMBEDDED_ARCHIVE`. Startup reads
at most 64 KiB directly from the PE-mapped resource and accepts metadata format
version `1` with this schema:

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

`package_id` is validated as one 1-128 byte ASCII directory component. It may
contain letters and digits plus interior `.`, `-` and `_` characters, cannot
be the reserved `system` name, and becomes the package-specific Phase 4
persistence directory. This makes save identity stable across executable
renames and archive updates.

`archive_resource` must identify numeric resource `101`. `archive_identity`
must equal `<fnv1a64>-<size-hex>` for the archive resource currently linked
into the executable. The identity binds metadata and archive versions and
catches incomplete resource replacement; it is not an authentication or
tamper-resistance mechanism. A package update retains `package_id` but updates
`archive_identity`.

The optional `title` is validated as non-empty UTF-8 without control characters
and is limited to 256 bytes. It supplies both the initial window title and the
title retained after content loading. The optional `startup` value defaults to
`DOSBOX.BAT`; Phase 7 extends format version 1 to safe archive-relative `.EXE`,
`.COM` and `.BAT` targets that the builder verifies against archive contents.

Missing metadata retains Phase 3/4 compatibility by selecting
`archive-<fnv1a64>-<size-hex>`. A present but empty, oversized, malformed,
unsupported, unsafe or archive-mismatched metadata resource is a fatal package
error. Validation occurs before persistence initialization, so an unsafe
`package_id` cannot create or escape the persistence directory.

Release validation covered the metadata package path and title, a changed
archive retaining the same package ID, the missing-metadata fallback, unsafe
package-ID rejection and archive/metadata mismatch rejection.

## Phase 7 — completed

The `makegame` tool now supports manifest and direct CLI modes, safe output
replacement, validation-only runs, archive/metadata/config resources, PNG icon
conversion and Windows version resources. The runtime accepts optional
metadata field `default_config_resource: 103`, bounds the config at 1 MiB,
validates safe keys and string values, and applies the values below persisted
user settings.

End-to-end validation packaged the license-safe Phase 3 archive with eight
default values, a non-square PNG, Unicode title and custom version data. The
generated executable exposed the custom title and version fields, Windows
successfully extracted its icon, resource 103 loaded eight defaults, the
900x600 default produced a 916x639 decorated window, and a persisted 700x500
override produced a 716x539 decorated window. The game exited with code 0 and
wrote its normal package-specific overlay.

Startup-target validation also packaged the Dune II archive, which has no
`DOSBOX.BAT`, using both explicit `--startup DUNE2.EXE` and defaults-only
`package_startup`. The generated icon-bearing package opened a `Dune II`
window, reported `Program: DUNE2`, and loaded the three remaining emulator
defaults. A missing startup declaration and a nonexistent target were rejected;
the existing `DOSBOX.BAT` smoke package continued to execute and exit with code
0.

Automatic-shutdown regression validation used metadata-selected `START.BAT`
without an `exit` command. The batch returned normally after persisting
`RESULT.OK`; the generated top-shell `exit` then closed the process with code 0
in 1.12 seconds without key input. This specifically covers archives with no
root `DOSBOX.BAT` and prevents the Pure Menu completion prompt.

Presentation-switch validation originally confirmed that explicit windowed-only
output contained one default, a package without CLI or config presentation
values contained no resource 103, and all four presentation variants loaded
their defaults, executed metadata startup and exited with code 0. After adding
the shared CRT appearance defaults, two further packages were generated from a
config containing conflicting CRT values. Direct inspection of resource 103
confirmed that `--scanlines` produced CRT mode 1 and `--crt-filter` produced CRT
mode 2; both produced scanline intensity 3, sharpness 7, curvature 0 and rounded
corners 0 while preserving an unrelated memory setting.

## Phase 8

Test ZIP/DOSZ, ISO, CUE/BIN, IMG/IMA and VHD content with multiple
representative DOS games.

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
