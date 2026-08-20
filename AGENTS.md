# AGENTS.md

# DOSBox Pure Single-Executable Project Instructions

## Project Purpose

This repository creates a modified DOSBox Pure-based standalone Windows executable capable of running a complete DOS game from an archive embedded directly inside the executable.

The project must preserve the following core behavior:

- single distributable `.exe`
- no installation
- no extraction of the embedded game archive
- no temporary reconstruction of the archive on disk
- direct access to embedded game data from memory
- persistent save-game support through a writable overlay
- one-click startup
- support for disk images contained inside the embedded package

The detailed design and requirements are documented in:

```text
docs/architecture.md
docs/requirements.md
```

These documents are authoritative for project behavior.

---

# Repository Layout

Expected top-level structure:

```text
DOSBoxPureSingleExe/
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
```

Roles:

```text
dosbox-pure-unleashed/
    Standalone Windows frontend and executable host.

dosbox-pure/
    DOS emulation core and primary location for archive/filesystem changes.

ZillaLib/
    Supporting frontend/runtime library used by DOSBox Pure Unleashed.

docs/
    Project architecture and requirements.

packaging/
    Future package resources and runtime templates.

tools/
    Future tooling such as makegame.exe.
```

---

# Primary Development Rule

Do not implement any solution that extracts the embedded game package to disk.

The following is forbidden:

```text
embedded archive
        |
        v
%TEMP%\game.zip
        |
        v
DOSBox Pure
```

The required architecture is:

```text
embedded archive
        |
        v
memory-backed random-access source
        |
        v
DOSBox Pure archive filesystem
```

This requirement applies even if the temporary file is:

- hidden
- deleted immediately after opening
- stored under AppData
- stored in a randomly named directory
- created only for compatibility

If a physical copy of the embedded game archive is created, the implementation does not satisfy the project requirements.

---

# Development Philosophy

Prefer small, isolated changes over large rewrites.

The project should reuse existing DOSBox Pure functionality wherever possible.

In particular, preserve and reuse:

- ZIP/DOSZ handling
- DOS filesystem behavior
- writable overlay logic
- disk-image support
- startup-script handling
- emulator behavior
- existing decompression paths

The goal is to replace or abstract only the backing source used to read the archive.

Avoid replacing major DOSBox Pure subsystems unless source analysis shows that this is unavoidable.

---

# Upstream Code

The following directories originate from upstream projects:

```text
dosbox-pure-unleashed/
dosbox-pure/
ZillaLib/
```

Avoid unnecessary formatting, restructuring, mass renaming, or cleanup in upstream code.

Changes should remain easy to compare against upstream.

When modifying upstream-derived code:

1. understand the existing call path first
2. make the smallest practical change
3. avoid unrelated refactoring
4. document why the modification is necessary
5. preserve normal behavior when practical

---

# Initial Technical Target

The first implementation milestone is NOT PE resource embedding.

First prove that DOSBox Pure can operate on a memory-backed archive.

Target test flow:

```text
game.zip on disk
        |
        v
load game.zip into memory
        |
        v
memory-backed random-access source
        |
        v
existing DOSBox Pure ZIP filesystem
        |
        v
game launches
```

This separates archive-source work from Windows resource work.

Only after this works should the source become:

```text
Windows PE resource
        |
        v
memory-backed random-access source
        |
        v
DOSBox Pure ZIP filesystem
```

---

# Investigation Before Modification

Before changing archive-loading code, trace the complete existing content-loading path.

Identify:

- how DOSBox Pure Unleashed receives the selected content filename
- how the filename enters DOSBox Pure
- where ZIP/DOSZ content is opened
- whether standard C file APIs or custom wrappers are used
- which functions require a full path
- how archive seeking is implemented
- how ZIP indexes are created
- how disk images inside archives are read
- how `.pure.zip` writable overlays are associated with the source archive
- how `DOSBOX.BAT` is detected and executed
- how save paths are generated

Record important findings in project documentation before making significant structural changes.

---

# Preferred Data Abstraction

Where practical, introduce a generic random-access archive source.

Conceptual API:

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

Expected implementations:

```text
FileDataSource
MemoryDataSource
```

Possible future implementations:

```text
MappedFileDataSource
PEMemoryDataSource
```

Do not introduce abstraction merely for architectural elegance if the existing DOSBox Pure code offers a substantially smaller and safer integration point.

Source analysis takes precedence over this suggested interface.

---

# Memory Handling Rules

For embedded archives:

- support random access
- use 64-bit-safe sizes and offsets
- bounds-check every memory read
- avoid copying the complete archive unnecessarily
- do not decompress the entire archive at startup
- preserve DOSBox Pure's normal on-demand decompression behavior

For PE resources, prefer direct access to the memory mapped by Windows using:

```text
FindResource
LoadResource
LockResource
SizeofResource
```

Do not copy the entire resource unless required by an existing API.

---

# Writable Data

The embedded base archive is immutable.

Never:

- modify the running executable
- rewrite embedded ZIP data
- append saves to the executable
- regenerate the executable after each run

Persistent data should be stored separately.

Primary persistence root:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\
```

Required layout:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\<package_id>\
%LOCALAPPDATA%\DOSBoxPureStandalone\system\
```

The package directory contains package-specific writable data. The `system`
directory contains shared resources such as SoundFonts, MT-32 ROMs and system
DOSZ files.

If the primary root cannot be created or is not writable, fall back to the
directory containing the running executable and preserve the same child
layout. If neither location is writable, report a clear persistence error
rather than silently discarding changes.

Typical persistent data:

```text
game.pure.zip
settings
controller configuration
save states
```

The actual writable-overlay implementation should reuse DOSBox Pure's existing behavior where possible.

---

# Package Identity

Do not rely only on the Windows executable filename to identify save data.

Use a stable package identifier from embedded metadata.

Example:

```text
com.example.duke3d
```

Renaming:

```text
DUKE3D.EXE
```

to:

```text
MY_DUKE.EXE
```

should ideally retain the same save data.

---

# Embedded Package

The expected base game container is ZIP/DOSZ.

It may contain:

```text
DOSBOX.BAT
GAME.EXE
game data
configuration files
ISO
CUE/BIN
IMG
IMA
VHD
```

Disk images must remain inside the embedded archive.

Do not add an extraction stage for disk-image mounting.

---

# Startup Behavior

Generated packages should eventually behave as dedicated game executables.

Expected user experience:

```text
double-click GAME.EXE
        |
        v
game starts
```

Avoid exposing:

- content-selection menus
- RetroArch UI
- executable-selection menus
- emulator configuration UI

unless explicitly requested by the package configuration.

Preserve `DOSBOX.BAT` startup support.

---

# Windows Packaging

The initial embedded package format should use Windows PE resources.

Recommended resource type:

```text
RCDATA
```

The generated executable should eventually contain:

```text
DOSBox Pure runtime
game archive
package metadata
game icon
Windows version metadata
```

The runtime must detect an embedded package automatically.

A future packager may produce executables through a command such as:

```text
makegame.exe package.json
```

or:

```text
makegame.exe game.dosz GAME.EXE
```

---

# Build Priorities

Use this development order unless source investigation reveals a compelling reason to change it.

## Phase 0 — Baseline

Build pristine DOSBox Pure Unleashed successfully.

Run a normal external ZIP/DOSZ game.

Confirm baseline save behavior.

Do not modify source until baseline behavior is understood.

## Phase 1 — Trace Content Loading

Document the full content-loading path from Unleashed to the ZIP implementation.

## Phase 2 — Memory Archive Proof of Concept

Read an external ZIP fully into memory and run the archive through a memory-backed path.

No PE resources yet.

## Phase 3 — Embedded PE Resource

Replace the external source with an archive stored as a Windows resource.

## Phase 4 — Persistent Overlay

Ensure saves persist through a deterministic writable-overlay path.

## Phase 5 — Automatic Startup

Make an embedded package launch immediately.

## Phase 6 — Package Metadata

Add package ID and other metadata.

## Phase 7 — Packager

Create a tool that generates the final single executable.

## Phase 8 — Compatibility Testing

Test ZIP/DOSZ, ISO, CUE/BIN, IMG/IMA, VHD and representative DOS titles.

---

# Validation Requirements

Use Sysinternals Process Monitor during runtime validation.

Monitor file operations such as:

```text
CreateFile
WriteFile
SetEndOfFile
Rename
Delete
```

Verify that game content is not written to:

```text
%TEMP%
%LOCALAPPDATA%\Temp
the executable directory
other cache directories
```

Expected writes should be limited to explicit persistence locations.

Do not claim the no-extraction requirement is satisfied solely from code inspection. Validate actual runtime behavior.

---

# Testing Expectations

Every significant archive-source modification should test at least:

1. small ZIP-based DOS game
2. game that writes configuration data
3. game that creates save files
4. archive containing a disk image
5. repeated launch/save/relaunch cycle
6. corrupt or missing embedded package

Where relevant, compare behavior with unmodified DOSBox Pure.

---

# Error Handling

Do not silently fall back to extracting an archive if memory loading fails.

A failure should result in:

- clear error handling
- clean shutdown or normal DOSBox Pure fallback where intended

Never use extraction as an undocumented compatibility fallback.

Malformed package metadata or archive data must not cause out-of-bounds memory access.

---

# Compatibility

Preserve normal external archive loading during development where practical.

Preferred behavior:

```text
if embedded package exists:
    use embedded package

else:
    use normal DOSBox Pure behavior
```

This facilitates debugging and keeps the fork closer to upstream.

The final dedicated-package build may later disable external content selection if desired.

---

# Code Quality

Use the conventions already present in the source file being modified.

Avoid introducing:

- unnecessary dependencies
- unrelated abstractions
- large framework libraries
- C++ features inconsistent with the existing toolchain
- broad rewrites

Prefer:

- narrow interfaces
- deterministic ownership
- explicit error handling
- RAII where compatible with surrounding code
- 64-bit-safe file/archive offsets

---

# Changes to ZillaLib

Treat `ZillaLib` as effectively read-only unless analysis shows that a frontend/platform change absolutely requires modification.

Archive and persistence logic should normally belong in:

```text
dosbox-pure/
```

Standalone application integration may belong in:

```text
dosbox-pure-unleashed/
```

Do not put emulator filesystem logic into ZillaLib.

---

# Documentation Updates

When architectural behavior changes, update:

```text
docs/architecture.md
```

When requirements or acceptance criteria change, update:

```text
docs/requirements.md
```

Do not allow implementation and documentation to diverge significantly.

---

# Scope Control

Do not implement these unless explicitly requested:

- DRM
- encryption
- anti-debugging
- executable obfuscation
- online services
- cloud saves
- automatic game downloading
- game-library frontend
- RetroArch integration
- self-updating
- save data inside the executable
- commercial software redistribution mechanisms

These are outside the initial project scope.

---

# Licensing

Preserve all existing upstream licensing notices.

The project is a downstream modification and must comply with the licenses of:

- DOSBox Pure
- DOSBox Pure Unleashed
- ZillaLib
- any additional libraries introduced later

Do not remove copyright notices.

Do not assume that game-content licensing permits redistribution.

---

# Important Source-Control Rule

Keep project-specific commits focused.

Prefer commits such as:

```text
Trace Unleashed content loading path

Add memory-backed ZIP source proof of concept

Load embedded DOSZ from PE resource

Add deterministic overlay save location
```

Avoid commits combining unrelated formatting, cleanup and functional changes.

---

# Decision Rule for Codex

When choosing between two implementations, prefer the one that:

1. does not extract content
2. changes less upstream code
3. reuses existing DOSBox Pure archive behavior
4. preserves ordinary DOSBox Pure compatibility
5. has clear ownership and bounds safety
6. can be validated using Process Monitor
7. remains maintainable against future upstream changes

If an implementation conflicts with `docs/requirements.md`, do not proceed with it silently. Document the conflict first.

---

# Core Invariant

The project must always preserve this model:

```text
GAME.EXE
   |
   +-- DOSBox Pure
   |
   +-- embedded compressed archive
                 |
                 v
              memory
                 |
                 v
       DOSBox Pure filesystem
                 |
                 +----> persistent writable overlay
```

Never replace it with:

```text
GAME.EXE
   |
   v
temporary archive/file extraction
   |
   v
DOSBox Pure
```

The absence of hidden extraction is the defining technical requirement of this project.
