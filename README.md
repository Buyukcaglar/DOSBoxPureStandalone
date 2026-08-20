# README.md

# DOSBox Pure Single-Executable

A downstream DOSBox Pure project for packaging a complete DOS game, DOSBox runtime, configuration and optional disk images into a **single standalone Windows executable**.

The defining goal is simple:

```text
GAME.EXE
```

should be all that is required to distribute and launch the game.

The embedded game package is accessed directly from memory and is **never extracted to disk**.

---

# Project Status

Early development / architecture stage.

The initial work focuses on understanding and modifying DOSBox Pure's archive-loading path so ZIP/DOSZ packages can be backed by memory rather than by a physical filename.

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
- automatic `DOSBOX.BAT` startup
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

Reserved for future build tools such as the executable packager.

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

## Phase 0 — Baseline Build

Build and test unmodified DOSBox Pure Unleashed.

---

## Phase 1 — Content Loading Analysis

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

---

## Phase 2 — Memory-Backed Archive Proof of Concept

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

---

## Phase 3 — Windows PE Resource

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

---

## Phase 4 — Persistent Overlay

Ensure files written by DOS programs survive between launches.

Suggested location:

```text
%LOCALAPPDATA%\DOSBoxPurePackages\<package_id>\
```

Example:

```text
%LOCALAPPDATA%\DOSBoxPurePackages\com.example.duke3d\
```

The embedded archive remains read-only.

---

## Phase 5 — Automatic Launch

The generated executable should start the configured DOS title immediately.

Packages can use:

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

No file-selection UI should appear for normal packaged games.

---

## Phase 6 — Package Metadata

Add an embedded package description.

Example:

```json
{
  "format_version": 1,
  "package_id": "com.example.duke3d",
  "title": "Duke Nukem 3D",
  "startup": "DOSBOX.BAT"
}
```

The `package_id` should provide stable identity for save storage.

---

## Phase 7 — Package Builder

Create a standalone packaging tool.

Possible interface:

```text
makegame.exe game.dosz GAME.EXE
```

or:

```text
makegame.exe package.json
```

Conceptually:

```text
DOSBoxPureTemplate.exe
        +
game.dosz
        +
package.json
        +
game.ico
        =
GAME.EXE
```

The builder should eventually support:

- embedded archive
- metadata
- custom icon
- Windows version resources
- package validation

---

# Example Final Package

Development input:

```text
Duke3DPackage\
│
├── package.json
├── duke3d.dosz
└── duke3d.ico
```

Build command:

```text
makegame.exe Duke3DPackage\
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
%LOCALAPPDATA%\DOSBoxPurePackages\com.example.duke3d\
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