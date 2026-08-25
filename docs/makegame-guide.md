# makegame Guide

`makegame.exe` turns a DOS game stored in a ZIP or DOSZ archive into one
dedicated Windows executable powered by DOSBox Pure Standalone. The generated
game executable reads its archive directly from memory backed by its own EXE.
It does not reconstruct or extract the packaged game archive to a temporary
directory.

The distributed Windows x64 `makegame.exe` is a self-contained .NET 8
application. A separate .NET installation is not required.

## Distribution contents

Keep these two programs together after extracting the release ZIP:

```text
makegame.exe
DOSBoxPureStandAlone.exe
```

`DOSBoxPureStandAlone.exe` is the clean runtime template. `makegame.exe`
automatically finds it beside itself, in the current directory, or beside a
package manifest. You can also select it explicitly with `--template`.

## Quick start

Prepare a game archive with one root-level `DOSBOX.BAT`:

```text
game.zip
├── DOSBOX.BAT
├── GAME.EXE
└── game files...
```

Example `DOSBOX.BAT`:

```bat
@ECHO OFF
GAME.EXE
```

Create the package from PowerShell:

```powershell
.\makegame.exe `
  --archive ".\game.zip" `
  --output ".\MyGame.exe" `
  --package-id "com.example.mygame" `
  --title "My Game"
```

The resulting `MyGame.exe` contains the emulator, package metadata, and the
complete compressed game archive. User-created state remains separate under:

```text
%LOCALAPPDATA%\DOSBoxPureStandalone\com.example.mygame\
```

If `%LOCALAPPDATA%\DOSBoxPureStandalone\` cannot be created or written, the
runtime falls back to `DOSBoxPureStandalone\` beside the packaged executable.

## Command forms

### Manifest mode

The recommended repeatable form is:

```powershell
.\makegame.exe ".\package.json"
```

The explicit equivalent is:

```powershell
.\makegame.exe --manifest ".\package.json"
```

Manifest-relative paths are resolved from the directory containing the
manifest.

### Direct positional mode

The archive and output can be the first two positional arguments:

```powershell
.\makegame.exe ".\game.dosz" ".\MyGame.exe" `
  --package-id "com.example.mygame" `
  --title "My Game"
```

If output is omitted, it defaults to the archive path with an `.exe`
extension.

### Direct named mode

Named paths are clearer in scripts:

```powershell
.\makegame.exe `
  --template ".\DOSBoxPureStandAlone.exe" `
  --archive ".\game.dosz" `
  --output ".\MyGame.exe" `
  --package-id "com.example.mygame" `
  --title "My Game"
```

Command-line values override matching manifest values. Command-line path
overrides are resolved from the current working directory, not from the
manifest directory.

## Every command-line option

| Option | Value | Purpose |
| --- | --- | --- |
| `-h`, `--help`, `/?` | none | Display built-in usage and exit. |
| `--manifest` | JSON path | Load a package manifest. A positional `.json` path has the same effect. |
| `--template` | EXE path | Select the clean `DOSBoxPureStandAlone.exe` runtime template. |
| `--archive` | ZIP/DOSZ path | Select the game archive to embed. |
| `--output` | EXE path | Select the generated executable path. |
| `--package-id` | identifier | Set the stable persistence identity. |
| `--title` | text | Set the package title and default Windows description. |
| `--startup` | archive path | Select an archive-relative `.EXE`, `.COM`, or `.BAT` startup file. |
| `--icon` | PNG path | Convert a PNG into the packaged application's Windows icon. |
| `--config` | JSON path | Embed DOSBox Pure defaults from a flat `DOSBoxPure.cfg`-style JSON object. |
| `--full-screen` | none | Start fullscreen; omission creates a windowed package default. |
| `--lock-mouse` | none | Lock the pointer at startup; Ctrl+F11 toggles the lock during play. |
| `--aspect-ratio` | aspect mode | Set the first-launch DOSBox Pure aspect-correction mode. |
| `--cycles` | cycle mode | Set automatic, maximum, or fixed emulated performance. |
| `--emu-perf` | named preset | Select one of the 13 Emulated Performance choices by abbreviated CPU and clock. |
| `--cpu-type` | CPU type | Select the emulated CPU compatibility model. |
| `--text-mode` | none | Reveal intentional DOS text, including interactive startup screens before graphics. |
| `--scanlines` | none | Enable scanlines-only mode with the project's CRT appearance defaults. |
| `--crt-filter` | none | Enable TV-style CRT filtering and scanlines with the project's appearance defaults. |
| `--validate-only` | none | Validate all inputs without creating an executable. |
| `--overwrite` | none | Allow replacement of an existing output executable. |

Option names are case-insensitive. Values are interpreted according to the
rules described below.

## Required identity and title

### `--package-id`

The package ID determines where persistent saves and settings are stored. It
must:

- contain 1 through 128 ASCII characters;
- start and end with a letter or digit;
- use only letters, digits, `.`, `-`, and `_` internally; and
- not equal the reserved name `system`.

Use a stable reverse-domain style ID:

```powershell
--package-id "org.example.publisher.game"
```

Do not change the ID merely because the output filename or package version
changes. Keeping it stable retains the same persistence directory.

### `--title`

The title becomes the native window title and supplies default Windows version
information. It must be non-empty, contain no control characters, and fit
within 256 UTF-8 bytes.

```powershell
--title "Beneath a Steel Sky"
```

In direct mode, title defaults to the archive filename, but specifying the
human-readable title is recommended.

## Runtime template

The release `DOSBoxPureStandAlone.exe` is a clean template and does not contain
a game. Template discovery checks:

1. the manifest directory;
2. the directory containing `makegame.exe`; and
3. the current directory in direct mode.

Use an explicit template when it is stored elsewhere:

```powershell
--template "C:\Tools\DOSBoxPureStandAlone.exe"
```

The builder validates the Windows image and expected `ZL` application icon.
Legacy development templates containing both archive and metadata resources
are accepted; a template containing only one of those resources is rejected.

## Archive requirements

`--archive` accepts `.zip` and `.dosz`. The builder:

- validates the ZIP directory and reads every file;
- rejects empty archives;
- rejects duplicate and unsafe paths;
- rejects absolute paths, drive-qualified paths, and `.` or `..` segments;
- verifies that the selected startup file exists; and
- validates, identifies, writes, and verifies large archives with bounded
  streaming buffers rather than loading the whole archive into memory.

The game archive remains compressed inside the generated executable. Disk
images such as ISO, CUE/BIN, IMG/IMA, and VHD can remain inside the archive and
use DOSBox Pure's normal image support.

Storage is selected automatically. Archives up to 1.5 GiB are embedded as PE
resource 101. Larger archives are appended after the PE image with a small
bounds trailer, then mapped read-only from the executable at runtime. This
avoids the Windows mapped-image size limit while preserving one executable and
the no-extraction design. The completed command prints the selected storage
mode.

ZIP64 inputs are supported by the Windows x64 release, but the runtime,
resources, archive, and trailer must together remain smaller than 4 GiB.
Windows rejects an executable of 4 GiB or larger before the runtime can start.
The builder calculates the exact capacity after resource updates and reports
the maximum archive size when a package cannot fit. Individual files inside
the ZIP must also remain compatible with DOSBox Pure's archive reader.

## Automatic startup

Startup is selected in this order:

```text
--startup
  > manifest startup
  > package_startup in --config/default_config
  > root-level DOSBOX.BAT
```

The selected target must be an archive-relative `.EXE`, `.COM`, or `.BAT` path.

### Starting an executable directly

```powershell
--startup "GAME.EXE"
```

Subdirectories are supported:

```powershell
--startup "GAME\GAME.EXE"
```

`--startup` identifies one file; it is not a DOS command line. Spaces,
parameters, drive-qualified paths, redirection, and shell operators are
intentionally rejected. For launch parameters or setup commands, use a batch
file.

### Starting with parameters

Put `START.BAT` at the archive root:

```bat
@ECHO OFF
SKY.EXE CFG=C:\
```

Then package with:

```powershell
--startup "START.BAT"
```

The dedicated runtime automatically exits after a custom startup program or
batch file returns. An explicit final `EXIT` is unnecessary.

### Mounting a nested ZIP as D:

For an installed game that still requires original CD files, store the original
archive as `SKY-CD.ZIP` inside the outer package and use:

```bat
@ECHO OFF
IMGMOUNT D C:\SKY-CD.ZIP -t zip
IF NOT EXIST D:\SKY.DSK GOTO MOUNTERROR
C:
SKY.EXE CFG=C:\
GOTO END

:MOUNTERROR
ECHO Required CD data could not be mounted.
PAUSE

:END
```

The DOSBox `IMGMOUNT` type value `zip` is case-sensitive in the bundled core;
use lowercase `-t zip`. Store a nested ZIP without further compression in the
outer ZIP when practical so random access does not repeatedly decompress it.
The Windows x64 runtime supports nested ZIP containers larger than 2 GiB while
individual files inside them remain limited to 4 GiB minus one byte. This was
validated with Ripper using a 3.09 GB nested `CD.ZIP`; the game detected D as a
CD-ROM drive and entered the game. The complete generated executable must still
remain smaller than 4 GiB.

## Packages that need visible DOS text mode

Dedicated graphical packages hide the DOS shell and transitional DOS text
frames. Pass `--text-mode` whenever the user must see an intentional DOS text
display. There are two main cases:

- the game remains in text mode, as KROZ does; or
- the game presents interactive text-mode questions before entering graphics,
  as Sid Meier's Civilization does.

The option is therefore not limited to games whose final display is text. For
Civilization, a representative command is:

```powershell
.\makegame.exe "CIV.zip" "Civilization.exe" `
  --template ".\DOSBoxPureStandAlone.exe" `
  --package-id "com.example.civilization" `
  --title "Sid Meier's Civilization" `
  --startup "CIV.EXE" `
  --text-mode
```

For KROZ, which remains in text mode:

```powershell
.\makegame.exe "KROZ.zip" "KROZ.exe" `
  --template ".\DOSBoxPureStandAlone.exe" `
  --package-id "com.example.kroz" `
  --title "Kroz" `
  --startup "KROZ.EXE" `
  --text-mode
```

The builder writes `"text_mode": true` to package metadata and stores the
source ZIP/DOSZ byte-for-byte unchanged. No reconstructed archive is written
to disk. A manually supplied root-level `TEXTMODE.DBP` remains supported for
compatibility. Do not use the option merely for noninteractive
initialization messages that should stay hidden. Beneath a Steel Sky has no
required text-mode interaction and does not need it; Civilization does because
the user must see and answer its startup questions.

## PNG application icon

Use `--icon` with a PNG file:

```powershell
--icon "C:\Artwork\game-icon.png"
```

The builder preserves aspect ratio, centers rectangular artwork on a
transparent square, and generates 16, 24, 32, 48, 64, 128, and 256-pixel
Windows icon frames. It replaces the template icon group and verifies that
Windows can extract the result.

The input must be a decodable PNG. For best results, use square artwork at
least 256 by 256 pixels with transparency where appropriate.

## Cycles, emulated performance, and CPU type

Choose at most one of these package defaults:

```powershell
--cycles 26800
```

or:

```powershell
--emu-perf 486dx2-66
```

or:

```powershell
--cpu-type 386_prefetch
```

`--cycles`, `--emu-perf`, and `--cpu-type` are mutually exclusive, and
repeating any option is rejected. An explicit CLI selection replaces its
matching value from `--config` before resource 103 is generated.

### Cycle and Emulated Performance values

`--cycles` accepts any whole number from 200 through 1,000,000. `--emu-perf`
provides readable names for the 13 choices highlighted by the bundled core:

| `--emu-perf` value | Generated cycles value | Bundled core meaning |
| --- | --- | --- |
| `auto` | `auto` | Detect the program's performance needs. |
| `max` | `max` | Emulate as many instructions as possible. |
| `8086-4.77` | `315` | 8086/8088, 4.77 MHz. |
| `286-6` | `1320` | 286, 6 MHz. |
| `286-12.5` | `2750` | 286, 12.5 MHz. |
| `386-20` | `4720` | 386, 20 MHz. |
| `386dx-33` | `7800` | 386DX, 33 MHz. |
| `486dx-33` | `13400` | 486DX, 33 MHz. |
| `486dx2-66` | `26800` | 486DX2, 66 MHz. |
| `pentium-100` | `77000` | Pentium, 100 MHz. |
| `pentium-ii-300` | `200000` | Pentium II, 300 MHz. |
| `pentium-iii-600` | `500000` | Pentium III, 600 MHz. |
| `athlon-1200` | `1000000` | AMD Athlon, 1.2 GHz. |

Both switches generate the resource key `dosbox_pure_cycles`.

### CPU-type values

| CLI value | Emulated CPU behavior |
| --- | --- |
| `auto` | Mixed feature set with maximum performance and compatibility. |
| `386` | 386 instruction set with fast memory access. |
| `386_slow` | 386 instruction set with memory privilege checks. |
| `386_prefetch` | 386 with prefetch-queue emulation; intended for the auto or normal CPU core. |
| `486_slow` | 486 instruction set with memory privilege checks. |
| `pentium_slow` | Pentium/586 instruction set with memory privilege checks. |

The generated resource key is `dosbox_pure_cpu_type`. These are all CPU types
compiled into the distributed runtime; Pentium MMX is unavailable because MMX
emulation is disabled in this build. This option selects the emulated CPU type,
not DOSBox Pure's separate CPU-core implementation.

## Window, aspect-ratio, and CRT options

### Windowed

Omit `--full-screen`. The builder writes `screen_fullscreen: false`, replacing
any conflicting value supplied through `--config`.

### Fullscreen

```powershell
--full-screen
```

This writes `screen_fullscreen: true`. Both values are first-launch package
defaults; a persisted user setting may take precedence on later launches.

### Mouse lock

```powershell
--lock-mouse
```

This writes `interface_lockmouse: true` and captures the mouse pointer at
startup, which is the state normally toggled with Ctrl+F11. Omitting the switch
writes `interface_lockmouse: false`. Either command-line result replaces a
conflicting value from `--config`; persisted user settings may still take
precedence on later launches. Ctrl+F11 remains available to unlock or relock
the pointer during play.

### Aspect ratio

```powershell
--aspect-ratio padded
```

The option accepts exactly one of the mutually exclusive aspect-correction
modes supported by the bundled core. Repeating `--aspect-ratio` is rejected:

| CLI value | Generated `dosbox_pure_aspect_correction` value | Effect |
| --- | --- | --- |
| `off` | `false` | Disable aspect correction. |
| `on` | `true` | Correct the aspect ratio with single-scan output. |
| `doublescan` | `doublescan` | Correct the aspect ratio with double-scan output when applicable. |
| `padded` | `padded` | Pad output to 4:3 with single-scan output. |
| `padded-doublescan` | `padded-doublescan` | Pad output to 4:3 with double-scan output when applicable. |
| `fill` | `fill` | Stretch output to fill the window, ignoring content aspect ratio. |

The CLI value overrides `dosbox_pure_aspect_correction` from `--config` before
the defaults resource is generated. It remains a first-launch package default,
so a user's persisted setting takes precedence on later launches.

### Scanlines only

```powershell
--scanlines
```

This generates:

```json
{
  "interface_crtfilter": "1",
  "interface_crtscanline": "3",
  "interface_crtblur": "7",
  "interface_crtcurvature": "0",
  "interface_crtcorner": "0"
}
```

### TV-style CRT filter

```powershell
--crt-filter
```

This generates the same sharpness, curvature, corner, and scanline defaults,
with `interface_crtfilter` set to `2`.

`--scanlines` and `--crt-filter` are mutually exclusive because the full CRT
filter already includes scanlines. Explicit CLI presentation options replace
conflicting keys loaded through `--config`.

## Complete default configuration

`--config` accepts the flat JSON format written by `DOSBoxPure.cfg`. Every
value must be a JSON string:

```json
{
  "package_startup": "START.BAT",
  "dosbox_pure_aspect_correction": "padded",
  "dosbox_pure_memory_size": "32",
  "dosbox_pure_cycles": "26800",
  "dosbox_pure_machine": "svga",
  "dosbox_pure_svga": "svga_s3",
  "interface_scaling": "default"
}
```

Package it with:

```powershell
--config ".\DOSBoxPure.defaults.cfg"
```

The file must be a JSON object no larger than 1 MiB. Keys can contain letters,
digits, `_`, `.`, and `-`; each string value can contain at most 4096 UTF-8
bytes. Comments and trailing commas are accepted.

`package_startup` is a builder directive. It is promoted into package metadata
and removed from the emulator defaults before embedding.

The safest way to build a defaults file is to configure the matching
`DOSBoxPureStandAlone.exe`, close it so settings are saved, copy its JSON file,
and remove machine-specific or personal values. Option names can evolve with
DOSBox Pure, so copying values from the same runtime version avoids guesswork.

Defaults are not permanent locks. Runtime precedence is:

```text
dedicated-package safety overrides
  > persisted user settings
  > embedded package defaults
  > built-in defaults
```

Thus the package controls first-launch defaults while later user choices can
persist.

## Manifest reference

A complete manifest using every manifest field is:

```json
{
  "format_version": 1,
  "package_id": "com.example.game",
  "title": "Example DOS Game",
  "startup": "START.BAT",
  "template": "DOSBoxPureStandAlone.exe",
  "archive": "game.dosz",
  "output": "ExampleGame.exe",
  "icon": "game-icon.png",
  "default_config": "DOSBoxPure.defaults.cfg",
  "text_mode": false,
  "version_info": {
    "file_version": "1.2.0.0",
    "product_version": "1.2.0.0",
    "company_name": "Example Publisher",
    "file_description": "Example DOS Game",
    "product_name": "Example DOS Game",
    "legal_copyright": "Copyright Example Publisher"
  }
}
```

Unknown manifest fields are rejected to catch spelling mistakes.

### Manifest fields

| Field | Required | Meaning |
| --- | --- | --- |
| `format_version` | yes | Must currently be numeric `1`. |
| `package_id` | yes | Stable persistence identity. |
| `title` | recommended | Human-readable package title. Defaults from the archive filename if omitted. |
| `startup` | no | Archive-relative startup target. |
| `template` | no if auto-discovered | Runtime template path. |
| `archive` | yes | ZIP/DOSZ input path. |
| `output` | no | Output EXE path; defaults from the archive path. |
| `icon` | no | PNG icon path. |
| `default_config` | no | Flat defaults JSON path. |
| `text_mode` | no | Boolean equivalent of `--text-mode`; defaults to `false`. |
| `version_info` | no | Windows application version strings. |

Performance and presentation switches are command-line features. To make
equivalent values fully manifest-driven, place the corresponding settings in
`default_config`.

### Version information

`file_version` and `product_version` accept one through four numeric components,
each from 0 through 65535. Missing components become zero. If absent, version
defaults to `1.0.0.0`. The string fields can contain up to 1024 characters and
cannot contain control characters.

Windows `InternalName` and `OriginalFilename` are generated from the output
filename. If no custom description or product name is supplied, the package
title is used.

## Full direct-mode example

```powershell
.\makegame.exe `
  --template ".\DOSBoxPureStandAlone.exe" `
  --archive "C:\Games\Dune2\dune2.zip" `
  --output "C:\Games\Dune2\DuneII.exe" `
  --package-id "com.westwood.dune2.personal" `
  --title "Dune II" `
  --startup "DOSBOX.BAT" `
  --icon "C:\Games\Dune2\Dune2.png" `
  --config "C:\Games\Dune2\DOSBoxPure.defaults.cfg" `
  --emu-perf 486dx2-66 `
  --full-screen `
  --lock-mouse `
  --aspect-ratio padded `
  --scanlines
```

## Validation and overwrite workflow

Validate first without producing output:

```powershell
.\makegame.exe ".\package.json" --validate-only
```

Validation also applies the selected metadata, icon, configuration, and version
resources to a short-lived runtime copy so the exact under-4-GiB capacity can
be checked. The temporary runtime copy is removed before the command returns;
the game archive is never copied into it during validation-only mode.

Build when validation succeeds:

```powershell
.\makegame.exe ".\package.json"
```

Existing output is protected. Replace it explicitly after reviewing your
inputs:

```powershell
.\makegame.exe ".\package.json" --overwrite
```

The builder writes a temporary executable beside the requested output, updates
its PE resources, streams a large appended payload when required, compares
every stored byte with the source, and only then moves it into place. Failed
packaging removes the temporary output.

## Generated package behavior

- The embedded base archive is immutable and read from memory.
- Save changes use DOSBox Pure's writable overlay under the stable package ID.
- Renaming the generated game EXE does not change its persistence location.
- The startup splash, shell, and content-selection menu remain hidden for a
  dedicated package.
- The runtime exits automatically when the configured startup target returns.
- The generated EXE is unsigned. Resource updates invalidate any signature on
  the template, so Authenticode signing must occur after packaging.

## Troubleshooting

### “Game archive must contain exactly one root-level DOSBOX.BAT”

Add a root `DOSBOX.BAT`, select an existing startup file with `--startup`, add
manifest `startup`, or use `package_startup` in the defaults JSON.

### “Too many positional arguments”

Only archive and output are positional. `--startup` accepts one file path, not
an executable plus its parameters. Move parameters into a `.BAT` file.

### “--cycles, --emu-perf, and --cpu-type are mutually exclusive”

Choose whether this package needs a raw cycle value, a readable Emulated
Performance preset, or a CPU compatibility type, and pass only that switch. To
configure other advanced CPU settings, use a matching `DOSBoxPure.cfg` defaults
file.

### A program cannot find CD data on D:

Preserve the original CD archive or image inside the package and mount it from
the startup batch. For a nested ZIP, use lowercase `-t zip` as shown earlier.

### A required DOS text screen remains hidden

Rebuild with `--text-mode`, set manifest `"text_mode": true`, or add an empty
root-level `TEXTMODE.DBP` marker manually for legacy compatibility. This applies
both to fully text-mode games such as KROZ and graphical games with required
interactive text startup screens such as Civilization. Omit it for
noninteractive transitional text.

### “Windows cannot launch an executable whose total file size is 4 GiB or larger”

This is a Windows loader limit, not an available-memory problem. The message
reports the exact maximum archive size after accounting for the selected
runtime, metadata, configuration, icon, and 32-byte trailer. Reduce the ZIP or
use a multi-file distribution. If a game uses single-track MODE1/2352 BIN/CUE
images, converting them to ISO can remove raw-sector error-correction overhead,
but only do so after confirming the title does not require audio tracks or raw
sector data. `makegame` never performs this game-specific conversion
automatically.

### Windows SmartScreen or antivirus warning

Locally generated executables are unsigned and uncommon. Review the source,
build from source if desired, and Authenticode-sign packages intended for
broader distribution. Do not disable security software globally.

### Package settings do not replace later user settings

This is intentional. Embedded configuration is a defaults layer; persisted
user choices have higher priority. Delete or adjust the package's persistence
directory only when intentionally resetting user configuration.

## Redistribution and licensing

`makegame` does not grant permission to redistribute DOS games, firmware,
operating-system images, fonts, sound ROMs, artwork, or other input content.
Package only material for which you have suitable rights. Preserve required
copyright notices and license files inside the game archive.

See `README-DISCLAIMER.md` and the `licenses` directory in the binary
distribution for upstream attribution, license terms, source locations, and
warranty disclaimers.
