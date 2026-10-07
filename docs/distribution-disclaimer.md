# Upstream Projects, Licensing, and Disclaimer

DOSBox Pure Standalone is an independent downstream project. It is not an
official release of DOSBox, DOSBox Pure, DOSBox Pure Unleashed, ZillaLib,
Microsoft, or any DOS game publisher, and no endorsement is claimed.

## Upstream software

- **DOSBox Pure**, by Bernhard Schelling and contributors, incorporates DOSBox
  and is distributed under GNU GPL version 2 or later. Current upstream:
  <https://codeberg.org/schelling/dosbox-pure>. Downstream fork:
  <https://github.com/Buyukcaglar/dosbox-pure>.
- **DOSBox Pure Unleashed**, by Bernhard Schelling and contributors, is
  distributed under GNU GPL version 2 or later. Current upstream:
  <https://codeberg.org/schelling/dosbox-pure-unleashed>. Downstream fork:
  <https://github.com/Buyukcaglar/dosbox-pure-unleashed>.
- **ZillaLib**, by Bernhard Schelling, uses its accompanying zlib-style license:
  <https://github.com/schellingb/ZillaLib>.
- **Nuked-SC55**, copyright 2021, 2024 nukeykt, is integrated in the DOSBox Pure
  core under GNU GPL version 2 or later. Its notices remain in the corresponding
  source. No SC55 ROM is included.
- **Microsoft .NET 8 Desktop Runtime** and associated third-party components
  are bundled in the self-contained `makegame.exe`. Their license and notice
  texts accompany this distribution.

Exact source revisions and binary hashes are in `BUILD-INFO.txt`. Obtain the
complete corresponding source, including the recorded submodules, with:

```powershell
git clone --recurse-submodules --branch 2026.10.08 https://github.com/Buyukcaglar/DOSBoxPureStandalone.git
```

GitHub's automatic root source ZIP does not include the contents of submodules.
Use the recursive checkout or the exact component revision links in
`BUILD-INFO.txt`. Preserve source availability, upstream copyright notices and
all applicable license texts when redistributing the software.

## Content and names

This release contains no game, operating-system image, firmware, ROM, SoundFont,
real save or generated game executable. The builder does not download content
or grant redistribution rights. Package authors must have the rights required
for every input and preserve its notices. Project and game names identify
software and remain the property of their respective owners.

## AI assistance and warranty

This project has been developed with assistance from OpenAI ChatGPT and Codex
for analysis, implementation, documentation, builds and tests. Review and test
the software for your intended use and report reproducible problems through
GitHub Issues. The accompanying license texts control warranty exclusions and
redistribution conditions. No whole-game compatibility or real Windows 98
acceptance is implied by the synthetic milestone 5 results.
