# DOSBox Pure Standalone — Windows x64 Distribution

This archive contains production Windows x64 builds of:

- `DOSBoxPureStandAlone.exe` — clean runtime template;
- `makegame.exe` — self-contained .NET 8 package builder; and
- documentation, examples, upstream licenses, and third-party notices.

No game is included. `DOSBoxPureStandAlone.exe` is intentionally a clean
template; use `makegame.exe` to create a dedicated game executable.

## Start here

1. Extract the complete release ZIP.
2. Read `MAKEGAME-GUIDE.md`.
3. Prepare a ZIP/DOSZ containing a root `DOSBOX.BAT`, or select another startup
   `.EXE`, `.COM`, or `.BAT`.
4. Open PowerShell in the extracted directory.
5. Run a command such as:

```powershell
.\makegame.exe `
  --archive "C:\Games\MyGame\game.zip" `
  --output "C:\Games\MyGame\MyGame.exe" `
  --package-id "com.example.mygame" `
  --title "My Game"
```

The included `makegame.exe` carries its required .NET 8 runtime. Users do not
need to install .NET separately.

Large archives are streamed during validation and packaging instead of being
loaded into one managed byte array. The final dedicated game executable must
nevertheless remain smaller than 4 GiB because Windows rejects larger
executable files before application startup. `makegame --validate-only` reports
the exact available archive capacity for the selected options.

## Important files

```text
DOSBoxPureStandAlone.exe    Clean package runtime
makegame.exe                Package builder
MAKEGAME-GUIDE.md           Complete guide and option reference
RELEASE-NOTES.md            Changes and upgrade notes for this release
README-DISCLAIMER.md        Attribution, content warning, and disclaimer
BUILD-INFO.txt              Build revisions and checksums
examples\                   Manifest and defaults examples
licenses\                   Upstream and .NET license notices
```

Generated game executables are unsigned. Review the source and sign packages
after generation if your distribution process requires Authenticode.

Source code: <https://github.com/Buyukcaglar/DOSBoxPureStandalone>
