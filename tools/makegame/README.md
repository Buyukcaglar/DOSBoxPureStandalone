# makegame

`makegame` generates a dedicated DOSBox Pure Standalone Windows executable
from a clean runtime template and a ZIP/DOSZ game package. It updates PE
resources directly; it never extracts the game archive.

## Build

Open `makegame.csproj` in Visual Studio 2026 and build the `Release`
configuration, or run:

```powershell
dotnet build .\tools\makegame\makegame.csproj -c Release
```

The development build is placed under:

```text
tools\makegame\bin\Release\net8.0-windows\win-x64\
```

The tool targets .NET 8 for Windows and uses the Windows Presentation Imaging
Codec through WPF to decode and resize PNG icons. Production publishing is
self-contained and single-file, so target computers do not need a separately
installed .NET runtime:

```powershell
dotnet publish .\tools\makegame\makegame.csproj `
  -c Release -r win-x64 --self-contained true `
  -o .\tools\makegame\publish\win-x64
```

The self-contained and single-file settings are also recorded in the project
file, making the explicit publish properties unnecessary for ordinary Release
publishing.

## Package manifest

The recommended invocation is:

```powershell
makegame.exe package.json
```

Example:

```json
{
  "format_version": 1,
  "package_id": "com.example.game",
  "title": "Example DOS Game",
  "template": "DOSBoxPureStandAlone.exe",
  "archive": "game.dosz",
  "output": "ExampleGame.exe",
  "icon": "game-icon.png",
  "default_config": "DOSBoxPure.defaults.cfg",
  "version_info": {
    "file_version": "1.0.0.0",
    "product_version": "1.0.0.0",
    "company_name": "Example Publisher",
    "file_description": "Example DOS Game",
    "product_name": "Example DOS Game",
    "legal_copyright": "Copyright Example Publisher"
  }
}
```

Paths in a manifest are resolved relative to the manifest file. Command-line
paths are resolved relative to the current directory and override manifest
paths.

The runtime template is the `DOSBoxPureStandAlone.exe` produced by the
`dosbox-pure-unleashed` Release build. The archive must be a valid ZIP/DOSZ.
Automatic startup can come from a root-level `DOSBOX.BAT`, manifest `startup`,
`--startup`, or `package_startup` in the defaults JSON.

Direct command-line packaging is also supported:

```powershell
makegame.exe game.dosz GAME.exe `
  --template DOSBoxPureStandAlone.exe `
  --package-id com.example.game `
  --title "Example DOS Game" `
  --icon game-icon.png `
  --config DOSBoxPure.defaults.cfg `
  --window-mode fullscreen `
  --crt-filter
```

Use `--validate-only` to validate every input without writing an executable.
Existing output is protected unless `--overwrite` is supplied.

## Window and display-effect switches

The builder exposes common first-launch presentation choices directly:

```text
--window-mode windowed     Start windowed
--window-mode fullscreen   Start fullscreen
--scanlines                Scanlines only, sharpest, without curvature/corners
--crt-filter               TV-style CRT, sharpest, without curvature/corners
```

If neither the command line nor the supplied defaults JSON specifies
`screen_fullscreen`, startup defaults to windowed. CRT effects remain off when
neither a CLI effect flag nor corresponding config value is supplied.

`--scanlines` and `--crt-filter` are mutually exclusive because the full CRT
filter already includes scanlines. Their generated settings are:

| CLI option | CRT mode | Scanlines | Blur/sharpness | Curvature | Rounded corner |
| --- | --- | --- | --- | --- | --- |
| `--scanlines` | `1` (Only Scanlines) | `3` (Normal gaps) | `7` (Sharpest) | `0` (Disabled) | `0` (Disabled) |
| `--crt-filter` | `2` (TV style phosphors) | `3` (Normal gaps) | `7` (Sharpest) | `0` (Disabled) | `0` (Disabled) |

Explicit CLI presentation options override matching values loaded through
`--config`. They remain package defaults: persisted user settings still take
precedence on later launches.

## PNG application icon

The optional `icon` input must be PNG. Rectangular images are centered on a
transparent square without distortion. The builder produces 16, 24, 32, 48,
64, 128 and 256-pixel PNG icon frames, writes them as Windows `RT_ICON`
resources, and replaces the runtime's `ZL` `RT_GROUP_ICON`. It then asks
Windows to extract the resulting application icon as an output verification.

## Default package configuration

The optional `default_config` input uses the same flat JSON structure as
DOSBox Pure Unleashed's `DOSBoxPure.cfg`; every value must be a JSON string.
The easiest workflow is to configure an ordinary Unleashed build, close it so
its settings are saved, copy that file, remove machine-specific values you do
not want to distribute, and reference the copy from the manifest.

Examples include:

```json
{
  "package_startup": "GAME\\GAME.EXE",
  "screen_fullscreen": "true",
  "dosbox_pure_memory_size": "32",
  "dosbox_pure_cycles": "26800",
  "dosbox_pure_machine": "svga",
  "dosbox_pure_svga": "svga_s3",
  "interface_scaling": "default",
  "interface_crtfilter": "1",
  "interface_crtscanline": "3"
}
```

`package_startup` is a package-builder directive rather than an emulator
option. The builder removes it from resource 103 and promotes it into package
metadata. It must identify an existing archive-relative `.EXE`, `.COM` or
`.BAT`. Startup selection precedence is:

```text
--startup
  > manifest startup
  > default-config package_startup
  > root DOSBOX.BAT
```

This is the package equivalent of an Unleashed auto-start selection. Ordinary
Unleashed stores that selection in the writable `AUTOBOOT.DBP`, not in
`DOSBoxPure.cfg`.

After removing `package_startup`, any remaining configuration values are
embedded as PE resource `103` and parsed directly from memory. They form a
defaults layer, not a forced override:

```text
dedicated-package safety overrides
        > persisted user settings
        > embedded package defaults
        > DOSBox Pure built-in defaults
```

Consequently, a user's saved choice remains effective on later launches.
Persistence paths and the embedded archive selection are controlled by the
runtime and are not redirected by values copied from a development config.

## Validation and output behavior

Before writing output, the builder validates:

- manifest schema and package ID
- the runtime template and its expected application icon group
- any pre-existing archive and metadata resources form a complete pair
- ZIP/DOSZ structure, entry paths and readable contents
- resolved startup target exists inside the archive
- default configuration JSON and string values
- PNG decoding and dimensions
- Windows version numbers

The builder writes a temporary executable beside the requested output, updates
resources, reloads the result as a Windows image, compares resource contents,
and only then moves it into place. A failed build removes the temporary file.

The resulting game executable is unsigned. Updating PE resources invalidates
any Authenticode signature on the template, so code signing—if required—must
be performed after packaging.

## Showcase output

`sample-output/BASS.exe` is a completed Beneath a Steel Sky showcase package.
Its source game permits free redistribution when the accompanying readme and
copyright notices are preserved; the original redistribution readme is stored
beside the executable and remains embedded in the package. See
`sample-output/README.md` for package details and its SHA-256 checksum.
