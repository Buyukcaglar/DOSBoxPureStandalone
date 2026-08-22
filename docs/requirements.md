# requirements.md

# DOSBox Pure Single-Executable Requirements

## 1. Project Goal

Create a modified version of DOSBox Pure capable of running a complete DOS game from content embedded directly inside a single Windows executable.

The resulting package must launch by double-clicking the executable and must not require:

- installation
- external game files
- manual configuration
- archive extraction
- temporary extraction
- a separate launcher

Example final distribution:

```text
DUNE2.EXE
```

rather than:

```text
DUNE2\
  DOSBox.exe
  game.zip
  config.ini
  SDL.dll
  launch.bat
```

---

# 2. Terminology

## Host executable

The Windows executable launched by the user.

Example:

```text
DUNE2.EXE
```

## Embedded archive

The DOSZ or ZIP package containing the DOS game.

Example:

```text
game.dosz
```

## Base filesystem

The read-only filesystem provided by the embedded archive.

## Writable overlay

The persistent storage layer containing files changed or created by the DOS program.

## Package builder

The tool used to combine DOSBox Pure and a DOS game archive into the final executable.

---

# 3. Mandatory Distribution Requirements

## REQ-DIST-001 — Single distributable executable

The complete application must be distributable as one executable file.

Example:

```text
GAME.EXE
```

Status:

```text
MANDATORY
```

---

## REQ-DIST-002 — No installer

The application must run without an installation process.

The user should be able to:

```text
copy GAME.EXE
double-click GAME.EXE
play
```

Status:

```text
MANDATORY
```

---

## REQ-DIST-003 — No external game archive

The game ZIP/DOSZ archive must not need to exist beside the executable.

Invalid:

```text
GAME.EXE
GAME.DOSZ
```

Valid:

```text
GAME.EXE
```

Status:

```text
MANDATORY
```

---

## REQ-DIST-004 — Emulator contained in executable

DOSBox Pure and all project-specific runtime code must be contained within the distributed executable where technically and legally possible.

Status:

```text
MANDATORY
```

---

# 4. No-Extraction Requirements

## REQ-IO-001 — No archive extraction

The embedded DOSZ/ZIP archive must never be extracted to a physical directory.

Forbidden examples:

```text
%TEMP%\GAME\
%TEMP%\1234\game.zip
%APPDATA%\GAME\cache\
C:\Games\GAME\unpacked\
```

Status:

```text
MANDATORY
```

---

## REQ-IO-002 — No temporary archive reconstruction

The implementation must not write the embedded archive to disk merely so DOSBox Pure can open it using a filename.

This architecture is forbidden:

```text
embedded archive
       |
       v
%TEMP%\game.zip
       |
       v
DOSBox Pure
```

Status:

```text
MANDATORY
```

---

## REQ-IO-003 — Direct memory access

The embedded archive must be exposed to DOSBox Pure through a memory-backed random-access mechanism.

Target architecture:

```text
embedded PE resource
        |
        v
memory pointer + length
        |
        v
random-access data source
        |
        v
DOSBox Pure ZIP filesystem
```

Status:

```text
MANDATORY
```

---

## REQ-IO-004 — Lazy archive decompression

The complete uncompressed game must not need to be materialized in RAM before execution.

Individual ZIP members should be decompressed according to normal DOSBox Pure behavior.

Status:

```text
MANDATORY
```

---

## REQ-IO-005 — No hidden extraction

A solution that internally extracts files into a hidden or randomly named directory does not satisfy this requirement.

Examples that remain forbidden:

```text
%TEMP%\{GUID}\
%LOCALAPPDATA%\Temp\
hidden directory beside EXE
```

Status:

```text
MANDATORY
```

---

# 5. Embedded Archive Requirements

## REQ-ARCH-001 — ZIP support

The initial implementation must support ZIP-compatible DOS game archives.

Status:

```text
MANDATORY
```

---

## REQ-ARCH-002 — DOSZ support

DOSBox Pure DOSZ packaging behavior should remain supported.

Status:

```text
MANDATORY
```

---

## REQ-ARCH-003 — Directory hierarchy

The embedded archive must support arbitrary DOS directory structures.

Example:

```text
GAME\
  GAME.EXE
  DATA\
    MAPS\
    MUSIC\
  SAVE\
```

Status:

```text
MANDATORY
```

---

## REQ-ARCH-004 — Large archives

The archive implementation must not impose an artificially low package size limit.

At minimum it should be suitable for typical DOS CD-ROM games.

Status:

```text
MANDATORY
```

---

# 6. Disk Image Requirements

## REQ-DISK-001 — ISO support

ISO images contained inside the embedded archive should remain usable without extraction.

Status:

```text
MANDATORY
```

---

## REQ-DISK-002 — CUE/BIN support

CUE/BIN images contained inside the archive should remain usable where supported by DOSBox Pure.

Status:

```text
MANDATORY
```

---

## REQ-DISK-003 — IMG/IMA support

Floppy and raw disk-image formats already supported by DOSBox Pure should continue working when stored within the embedded package.

Status:

```text
MANDATORY
```

---

## REQ-DISK-004 — VHD support

VHD support already provided by DOSBox Pure should not be broken by the embedded-content changes.

Status:

```text
DESIRED
```

---

# 7. Startup Requirements

## REQ-START-001 — One-click launch

Double-clicking the generated executable should immediately start the configured game.

Status:

```text
MANDATORY
```

---

## REQ-START-002 — No frontend selection screen

The user should not normally be presented with:

- archive-selection UI
- executable-selection UI
- core-selection UI
- RetroArch UI

Status:

```text
MANDATORY
```

---

## REQ-START-003 — DOSBOX.BAT support

The project should preserve DOSBox Pure's startup-script behavior.

A package may contain:

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

Status:

```text
MANDATORY
```

---

## REQ-START-004 — Embedded package detection

At startup the executable must detect whether an embedded game package is present.

Conceptual behavior:

```text
if embedded package found:
    launch embedded game
else:
    normal DOSBox Pure behavior
```

Status:

```text
DESIRED
```

---

## REQ-START-005 — Seamless packaged-game presentation

When the executable automatically selects an embedded package, it must not show the DOSBox Pure startup animation, expose the DOS command shell, expose transitional text-mode initialization emitted by a graphics executable, or expose a stale DOS frame while the hardware-rendered surface transitions to the first graphical frames.

The reveal logic must also support DOS games that intentionally remain in text mode through an explicit package declaration. A text package declares this behavior with an empty root-level `TEXTMODE.DBP` marker, whether supplied by the source archive or generated by the package builder, and must become visible after a short text-mode dwell and replacement of the shell display, or after a bounded fallback. Without the marker, temporary text-page or text-resolution changes made by a graphics game during initialization must never expose a transitional DOS frame, regardless of their duration.

Explicit external content launches may retain the normal DOSBox Pure Unleashed presentation.

Status:

```text
MANDATORY
```

---

## REQ-START-006 — Automatic shutdown after game exit

For an embedded package, returning from the configured game to a top-level
`exit` command in `DOSBOX.BAT` must close the standalone executable without
showing the `Unable to exit top DOS shell` warning or returning to the Start
Menu. When metadata selects an `.EXE`, `.COM` or non-default `.BAT` directly,
the runtime must append the equivalent top-shell `exit` to its generated
in-memory autoexec sequence. It must not display the Pure Menu
`PRESS ANY KEY TO RETURN TO START MENU` completion prompt.

Status:

```text
MANDATORY
```

---

# 8. Persistence Requirements

## REQ-SAVE-001 — Persistent save games

Save games created by DOS software must remain available after the host executable is closed and reopened.

Status:

```text
MANDATORY
```

---

## REQ-SAVE-002 — Writable overlay

Changes made to the embedded filesystem should use DOSBox Pure's overlay mechanism or a compatible equivalent.

Status:

```text
MANDATORY
```

---

## REQ-SAVE-003 — Immutable embedded archive

Persistent changes must never alter the archive embedded inside the executable.

Status:

```text
MANDATORY
```

---

## REQ-SAVE-004 — Save location

The primary persistence root must be:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\
```

The package-specific and shared-system paths must use this common root:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\<package_id>\
%LOCALAPPDATA%\DOSBoxPureStandalone\system\
```

If the primary root cannot be created or is not writable, the application must
try the directory containing the running executable as its fallback root and
must preserve the same child layout. If both roots are unavailable, the
application must report a clear persistence error rather than silently lose
user changes.

The application must verify write access rather than relying only on directory
existence or attributes.

Phase 4 implementation status:

```text
COMPLETE
```

Status:

```text
MANDATORY
```

---

## REQ-SAVE-005 — Stable package identifier

Save data should be associated with an embedded package identifier rather than solely with the Windows executable filename.

Example:

```text
com.example.dune2
```

Renaming:

```text
DUNE2.EXE
```

to:

```text
DUNE2-PORTABLE.EXE
```

should therefore not lose access to existing save data.

Status:

```text
DESIRED
```

---

## REQ-SAVE-006 — No executable self-modification

The running executable must not modify itself to persist save games.

Status:

```text
MANDATORY
```

---

# 9. DOSBox Compatibility Requirements

## REQ-DBP-001 — Minimize upstream divergence

Changes to DOSBox Pure should be as small and isolated as reasonably possible.

Status:

```text
MANDATORY
```

---

## REQ-DBP-002 — Preserve existing ZIP filesystem

The existing DOSBox Pure ZIP filesystem implementation should be reused rather than replaced unless a technical analysis proves that replacement is necessary.

Status:

```text
MANDATORY
```

---

## REQ-DBP-003 — Preserve ordinary file-based loading

During development, normal loading of external ZIP/DOSZ packages should ideally continue working.

Status:

```text
DESIRED
```

---

## REQ-DBP-004 — Preserve DOS behavior

The embedded-content implementation must not intentionally change:

- DOS filesystem semantics
- CPU emulation
- sound emulation
- graphics emulation
- controller behavior
- memory behavior

Status:

```text
MANDATORY
```

---

# 10. Memory Data Source Requirements

## REQ-MEM-001 — Random access

The archive source abstraction must provide random access.

Required conceptual operation:

```cpp
Read(offset, destination, length)
```

Status:

```text
MANDATORY
```

---

## REQ-MEM-002 — Archive size

The data source must provide its total size.

Conceptually:

```cpp
uint64_t Size();
```

Status:

```text
MANDATORY
```

---

## REQ-MEM-003 — 64-bit offsets

Archive offsets and sizes should use 64-bit-safe types.

Status:

```text
MANDATORY
```

---

## REQ-MEM-004 — Bounds checking

Reads outside the embedded resource must fail safely.

Status:

```text
MANDATORY
```

---

## REQ-MEM-005 — No unnecessary memory copy

When possible, the Windows PE resource should be accessed directly from its mapped memory region.

The entire embedded archive should not be copied into another RAM allocation without a technical reason.

Status:

```text
DESIRED
```

---

# 11. Windows Resource Requirements

## REQ-PE-001 — Embedded archive resource

The first implementation should embed the game archive as a PE resource.

Recommended resource type:

```text
RCDATA
```

Status:

```text
MANDATORY FOR INITIAL IMPLEMENTATION
```

---

## REQ-PE-002 — Resource APIs

The runtime may use standard Windows APIs:

```cpp
FindResource
LoadResource
LockResource
SizeofResource
```

Status:

```text
RECOMMENDED
```

---

## REQ-PE-003 — Embedded metadata

Package metadata should also be stored inside the generated executable.

Phase 6 implementation:

```text
COMPLETE — IDR_EMBEDDED_METADATA RCDATA, numeric resource 102
```

Status:

```text
MANDATORY
```

---

# 12. Package Metadata Requirements

## REQ-META-001 — Format version

Each package must specify a package-format version.

Example:

```json
{
  "format_version": 1
}
```

Status:

```text
MANDATORY
```

Phase 6 accepts only numeric `format_version` `1`.

---

## REQ-META-002 — Package ID

Each package must have a stable identifier.

Example:

```json
{
  "package_id": "com.example.game"
}
```

Status:

```text
MANDATORY
```

The runtime must validate `package_id` as one safe directory component before
using it below the persistence root. Phase 6 permits 1-128 ASCII bytes made of
letters and digits with interior `.`, `-` and `_` characters. The reserved
shared-directory name `system` is not a valid package ID.

---

## REQ-META-003 — Display title

Packages should contain a human-readable game title.

Status:

```text
DESIRED
```

Phase 6 applies a present title to the native window. It must be non-empty,
valid UTF-8 without control characters and no longer than 256 bytes.

---

## REQ-META-004 — Startup configuration

Package metadata may identify the startup script or other launch behavior.

Status:

```text
DESIRED
```

For format version 1, the field is optional and defaults to `DOSBOX.BAT`. It
may identify a safe archive-relative `.EXE`, `.COM` or `.BAT`. The builder must
verify that the resolved startup target exists inside the archive. A defaults
JSON may supply reserved `package_startup` when CLI and manifest startup are
absent; that directive is package metadata and must not be passed to the core
as an emulator option.

---

## REQ-META-005 — Archive binding

Present metadata must identify the embedded archive resource and must carry an
identity matching the linked archive bytes. This prevents a resource-update
workflow from accidentally pairing one game's metadata and persistence ID with
another game's archive.

Format version 1 uses:

```json
{
  "archive_resource": 101,
  "archive_identity": "<fnv1a64>-<size-hex>"
}
```

The identity is a consistency guard, not a cryptographic signature. It must be
updated when archive content changes while `package_id` remains stable for the
same package.

Status:

```text
MANDATORY
```

Phase 6 implementation status:

```text
COMPLETE
```

---

## REQ-META-006 — Optional package defaults resource

When a package includes a default DOSBox Pure configuration, metadata must
identify it as numeric PE resource 103:

```json
{
  "default_config_resource": 103
}
```

The resource must be parsed from memory, limited to 1 MiB, and must not be
reconstructed as a physical config file. Persisted user settings must override
package defaults, while dedicated-package safety overrides remain authoritative.

Status:

```text
MANDATORY WHEN A DEFAULT CONFIG IS INCLUDED — PHASE 7 COMPLETE
```

---

# 13. Packaging Tool Requirements

## REQ-BUILD-001 — Automated package generation

A command-line tool must generate the final executable.

Example:

```text
makegame.exe game.dosz GAME.EXE
```

Status:

```text
MANDATORY — PHASE 7 COMPLETE
```

---

## REQ-BUILD-002 — Template executable

The packager operates by copying a clean runtime executable and adding package resources.

Conceptual process:

```text
runtime-template.exe
        +
game.dosz
        +
package.json
        +
game-icon.png
        +
DOSBoxPure.defaults.cfg (optional)
        =
GAME.EXE
```

Status:

```text
COMPLETE
```

---

## REQ-BUILD-003 — Custom icon

The package builder must accept PNG input, preserve its aspect ratio, convert
it to valid multi-size Windows icon resources and replace the application's
icon group.

Status:

```text
MANDATORY — PHASE 7 COMPLETE
```

---

## REQ-BUILD-004 — Version information

The package builder should support setting Windows PE version-resource information.

Example fields:

```text
ProductName
FileDescription
FileVersion
CompanyName
```

Status:

```text
DESIRED — PHASE 7 COMPLETE
```

---

## REQ-BUILD-005 — Archive validation

The package builder must validate the supplied game archive before generating the executable.
It must resolve startup using CLI, manifest, reserved defaults-JSON
`package_startup`, then root `DOSBOX.BAT`, and verify that the selected `.EXE`,
`.COM` or `.BAT` exists inside the archive.

Status:

```text
MANDATORY — PHASE 7 COMPLETE
```

---

## REQ-BUILD-006 — Optional default configuration

The package builder must accept an optional DOSBox Pure configuration file in
the flat JSON format written by `DOSBoxPure.cfg`. This avoids duplicating the
large and evolving core-option catalog in the package tool and supports values
such as:

```text
screen_fullscreen
dosbox_pure_aspect_correction
dosbox_pure_memory_size
dosbox_pure_cycles
dosbox_pure_machine
dosbox_pure_svga
interface_scaling
interface_crtfilter
interface_crtscanline
```

All config values must be JSON strings. The builder must validate and normalize
the data before embedding it as PE resource 103. Reserved `package_startup` is
promoted to package metadata when no CLI or manifest startup is present and is
not embedded as an emulator setting.

The builder must also expose common presentation defaults without requiring a
hand-edited config file:

```text
--window-mode windowed|fullscreen
--aspect-ratio off|on|doublescan|padded|padded-doublescan|fill
--scanlines
--crt-filter
```

Windowed is the default when neither CLI nor config specifies a mode.
`--aspect-ratio` must map to `dosbox_pure_aspect_correction`; friendly `off`
and `on` values become the core's `false` and `true` values, while the remaining
four values are embedded unchanged. The six modes are mutually exclusive, and
the builder must reject repeated `--aspect-ratio` arguments.
`--scanlines` maps to scanlines-only mode with normal intensity;
`--crt-filter` maps to TV-style phosphors with normal scanlines. Both effect
flags must also set blur/sharpness to Sharpest and disable curvature and rounded
corners. These effect flags are mutually exclusive. Explicit CLI window,
aspect-ratio, and effect values override matching values from the defaults JSON
before resource 103 is generated.

Status:

```text
MANDATORY — PHASE 7 COMPLETE
```

---

## REQ-BUILD-006A — Text-mode package declaration

The package builder must accept a `--text-mode` switch and an equivalent
boolean manifest field named `text_mode`. Enabling either must ensure that the
archive embedded as resource 101 contains exactly one root-level
`TEXTMODE.DBP` marker so the existing runtime text-presentation path is used.

The builder must add a missing marker entirely in memory. It must not modify
the source ZIP/DOSZ, extract archive members, or write a reconstructed archive
to disk. An input archive that already contains the marker must remain byte-for-
byte unchanged. Packages without the option or manifest field must retain their
ordinary graphical-presentation behavior.

Status:

```text
MANDATORY — PHASE 7 COMPLETE
```

---

## REQ-BUILD-007 — Safe output transaction

The builder must not leave a partially updated executable at the requested
output path. It must update a temporary copy, reload and verify required
resources, protect existing output unless overwrite was explicitly requested,
and remove temporary output on failure.

Status:

```text
MANDATORY — PHASE 7 COMPLETE
```

---

## REQ-BUILD-008 — Production distribution

The production `DOSBoxPureStandAlone.exe` template must not contain the
development smoke-test archive or metadata. Development fixture embedding must
be opt-in. The builder may accept either a clean template or a legacy template
with a complete archive/metadata pair, but must reject an incomplete pair.

The distributed Windows x64 `makegame.exe` must be a self-contained .NET 8
publish so users do not need to install .NET separately.

Status:

```text
MANDATORY — COMPLETE
```

---

# 14. Runtime Dependency Requirements

## REQ-DEP-001 — Minimize external dependencies

The distributed package should require no game-specific companion files.

Status:

```text
MANDATORY
```

---

## REQ-DEP-002 — Prefer static linking

Runtime libraries should be statically linked where technically and legally appropriate.

Status:

```text
DESIRED
```

---

## REQ-DEP-003 — Document unavoidable dependencies

Any external runtime dependency must be explicitly documented.

Status:

```text
MANDATORY
```

`makegame` targets the .NET 8 Windows Desktop runtime and uses Windows WPF/WIC
for PNG decoding. This is a package-builder dependency only. The generated DOS
game executable gains no .NET dependency and remains the native DOSBox Pure
Standalone runtime.

---

# 15. Performance Requirements

## REQ-PERF-001 — Reasonable startup time

Launching an embedded game should not require unpacking the entire compressed archive.

Status:

```text
MANDATORY
```

---

## REQ-PERF-002 — Seek performance

Random access to compressed archive members, particularly disk images, should remain comparable to ordinary DOSBox Pure behavior.

Status:

```text
DESIRED
```

---

## REQ-PERF-003 — Avoid duplicate full archive buffers

The implementation should avoid holding multiple complete copies of the embedded archive in RAM.

Status:

```text
DESIRED
```

---

# 16. Filesystem Side-Effect Requirements

## REQ-FS-001 — Permitted persistent writes

Persistent writes may occur only where required for user data, such as:

```text
save games
configuration
save states
controller settings
screenshots
logs if explicitly enabled
```

Status:

```text
MANDATORY
```

---

## REQ-FS-002 — No content cache

The runtime must not create a persistent uncompressed cache of the game package.

Status:

```text
MANDATORY
```

---

## REQ-FS-003 — No archive mirror

The runtime must not create a duplicate copy of the original DOSZ/ZIP archive in the save directory.

Status:

```text
MANDATORY
```

---

# 17. Testing Requirements

## REQ-TEST-001 — Basic game

Test at least one small DOS game that requires no CD-ROM.

Status:

```text
MANDATORY
```

---

## REQ-TEST-002 — Save-game test

Test a DOS game that creates persistent save files.

Procedure:

```text
launch
create save
exit
launch again
load save
```

Status:

```text
MANDATORY
```

---

## REQ-TEST-003 — Configuration-write test

Test a game that modifies configuration files.

Status:

```text
MANDATORY
```

---

## REQ-TEST-004 — CD-ROM test

Test at least one DOS CD-ROM title whose image remains inside the embedded archive.

Status:

```text
MANDATORY
```

---

## REQ-TEST-005 — Process Monitor validation

Use Sysinternals Process Monitor to verify that the runtime does not extract game content.

Monitor at least:

```text
CreateFile
WriteFile
SetEndOfFile
Rename
Delete
```

Status:

```text
MANDATORY
```

---

## REQ-TEST-006 — TEMP validation

Verify that no game archive or game files are created underneath:

```text
%TEMP%
```

Status:

```text
MANDATORY
```

---

## REQ-TEST-007 — AppData validation

Verify that AppData contains only legitimate persistence data and not unpacked copies of game content.

Status:

```text
MANDATORY
```

---

# 18. Error Handling Requirements

## REQ-ERR-001 — Missing embedded package

If an expected embedded package is missing, the executable must fail cleanly or fall back to normal DOSBox Pure behavior.

Status:

```text
MANDATORY
```

---

## REQ-ERR-002 — Corrupt package

A corrupted embedded archive must produce a clear error rather than crashing or accessing invalid memory.

Status:

```text
MANDATORY
```

---

## REQ-ERR-003 — Unsupported format

Unsupported package-format versions should be rejected explicitly.

Status:

```text
MANDATORY
```

---

## REQ-ERR-004 — Save directory failure

If the persistence directory cannot be created or written, the user should receive a meaningful error.

Status:

```text
MANDATORY
```

---

# 19. Security Requirements

## REQ-SEC-001 — Resource bounds validation

All reads from embedded executable resources must be checked against resource boundaries.

Status:

```text
MANDATORY
```

---

## REQ-SEC-002 — Archive parser safety

Existing DOSBox Pure archive validation and error handling should not be bypassed by the new memory source.

Status:

```text
MANDATORY
```

---

## REQ-SEC-003 — Package builder validation

Malformed metadata must not be allowed to create invalid executable structures.

Status:

```text
MANDATORY
```

---

# 20. Licensing Requirements

## REQ-LIC-001 — DOSBox Pure license compliance

Distributed binaries must comply with the applicable DOSBox Pure license.

Status:

```text
MANDATORY
```

---

## REQ-LIC-002 — Source availability

Any source-distribution obligations introduced by modifying DOSBox Pure must be satisfied.

Status:

```text
MANDATORY
```

---

## REQ-LIC-003 — Game licensing independence

The packaging system must not imply redistribution permission for the DOS software being embedded.

Status:

```text
MANDATORY
```

---

# 21. Explicit Non-Requirements

The initial implementation does not require:

```text
encryption
DRM
archive obfuscation
anti-debugging
cloud saves
online services
multi-game frontend
RetroArch
self-updating
automatic downloading
game database integration
save data stored inside EXE
portable save mode
```

These features may be considered after the core architecture is complete.

---

# 22. Acceptance Criteria

The first major implementation milestone is considered successful when all of the following are true:

```text
[1] A DOS game is embedded inside a Windows EXE.

[2] The original game ZIP/DOSZ does not exist separately.

[3] Double-clicking the EXE starts the game.

[4] The embedded ZIP/DOSZ is accessed directly from memory.

[5] No copy of the game archive is written to disk.

[6] Game files are not extracted into a directory.

[7] The game can read its files normally.

[8] The game can create or modify files.

[9] Modified files persist between runs.

[10] Persistent changes are stored separately from the EXE.

[11] A disk image inside the embedded archive can be mounted.

[12] Process Monitor confirms no hidden content extraction occurs.
```

---

# 23. Initial Development Milestone

The first coding milestone should intentionally be smaller than the complete package system.

Target:

```text
normal external game.zip
        |
        v
read archive into RAM
        |
        v
MemoryDataSource
        |
        v
DOSBox Pure ZIP filesystem
        |
        v
game runs
```

This proves that the DOSBox Pure archive layer can operate without a physical backing file.

Only after this succeeds should the source be changed to:

```text
PE embedded resource
        |
        v
MemoryDataSource
```

This separation makes debugging substantially easier.

---

# 24. Core Requirement Summary

The essential invariant of the project is:

```text
GAME.EXE
   |
   +-- DOSBox Pure
   |
   +-- compressed game archive
            |
            v
         memory
            |
            v
      DOSBox filesystem
```

and never:

```text
GAME.EXE
   |
   v
extract game.zip
   |
   v
temporary directory
   |
   v
DOSBox
```

Any implementation that reconstructs or extracts the embedded content to disk fails the primary project requirement.
