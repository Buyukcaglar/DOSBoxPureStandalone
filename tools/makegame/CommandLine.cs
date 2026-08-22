using System.Globalization;

namespace DosBoxPureStandalone.MakeGame;

internal sealed class CommandLine
{
    public string? ManifestPath { get; private set; }
    public string? TemplatePath { get; private set; }
    public string? ArchivePath { get; private set; }
    public string? OutputPath { get; private set; }
    public string? PackageId { get; private set; }
    public string? Title { get; private set; }
    public string? Startup { get; private set; }
    public string? IconPath { get; private set; }
    public string? DefaultConfigPath { get; private set; }
    public string? WindowMode { get; private set; }
    public string? AspectRatio { get; private set; }
    public string? Cycles { get; private set; }
    public string? CpuType { get; private set; }
    public bool EnableTextMode { get; private set; }
    public bool EnableScanlines { get; private set; }
    public bool EnableCrtFilter { get; private set; }
    public bool Overwrite { get; private set; }
    public bool ValidateOnly { get; private set; }
    public bool ShowHelp { get; private set; }

    public static CommandLine Parse(string[] args)
    {
        var result = new CommandLine();
        var positional = new List<string>();

        for (var index = 0; index < args.Length; index++)
        {
            var argument = args[index];
            switch (argument.ToLowerInvariant())
            {
                case "-h":
                case "--help":
                case "/?":
                    result.ShowHelp = true;
                    break;
                case "--manifest": result.ManifestPath = ReadValue(args, ref index, argument); break;
                case "--template": result.TemplatePath = ReadValue(args, ref index, argument); break;
                case "--archive": result.ArchivePath = ReadValue(args, ref index, argument); break;
                case "--output": result.OutputPath = ReadValue(args, ref index, argument); break;
                case "--package-id": result.PackageId = ReadValue(args, ref index, argument); break;
                case "--title": result.Title = ReadValue(args, ref index, argument); break;
                case "--startup": result.Startup = ReadValue(args, ref index, argument); break;
                case "--icon": result.IconPath = ReadValue(args, ref index, argument); break;
                case "--config": result.DefaultConfigPath = ReadValue(args, ref index, argument); break;
                case "--window-mode": result.WindowMode = ReadValue(args, ref index, argument).Trim().ToLowerInvariant(); break;
                case "--aspect-ratio":
                    if (result.AspectRatio is not null)
                        throw new PackageBuilderException("--aspect-ratio may be specified only once; its six modes are mutually exclusive.");
                    result.AspectRatio = ReadValue(args, ref index, argument).Trim().ToLowerInvariant();
                    break;
                case "--cycles":
                    if (result.Cycles is not null)
                        throw new PackageBuilderException("--cycles may be specified only once.");
                    result.Cycles = ReadValue(args, ref index, argument).Trim().ToLowerInvariant();
                    break;
                case "--cpu-type":
                    if (result.CpuType is not null)
                        throw new PackageBuilderException("--cpu-type may be specified only once.");
                    result.CpuType = ReadValue(args, ref index, argument).Trim().ToLowerInvariant();
                    break;
                case "--text-mode": result.EnableTextMode = true; break;
                case "--scanlines": result.EnableScanlines = true; break;
                case "--crt-filter": result.EnableCrtFilter = true; break;
                case "--overwrite": result.Overwrite = true; break;
                case "--validate-only": result.ValidateOnly = true; break;
                default:
                    if (argument.StartsWith('-'))
                        throw new PackageBuilderException($"Unknown option '{argument}'. Use --help for usage.");
                    positional.Add(argument);
                    break;
            }
        }

        if (result.ShowHelp) return result;

        if (positional.Count != 0 && result.ManifestPath is null && positional[0].EndsWith(".json", StringComparison.OrdinalIgnoreCase))
        {
            result.ManifestPath = positional[0];
            positional.RemoveAt(0);
        }

        if (positional.Count != 0 && result.ArchivePath is null)
        {
            result.ArchivePath = positional[0];
            positional.RemoveAt(0);
        }
        if (positional.Count != 0 && result.OutputPath is null)
        {
            result.OutputPath = positional[0];
            positional.RemoveAt(0);
        }
        if (positional.Count != 0)
            throw new PackageBuilderException("Too many positional arguments. Use --help for usage.");

        if (result.WindowMode is not null && result.WindowMode is not ("windowed" or "fullscreen"))
            throw new PackageBuilderException("--window-mode must be 'windowed' or 'fullscreen'.");
        if (result.AspectRatio is not null && result.AspectRatio is not ("off" or "on" or "doublescan" or "padded" or "padded-doublescan" or "fill"))
            throw new PackageBuilderException("--aspect-ratio must be 'off', 'on', 'doublescan', 'padded', 'padded-doublescan', or 'fill'.");
        if (result.Cycles is not null && !IsValidCycles(result.Cycles))
            throw new PackageBuilderException("--cycles must be 'auto', 'max', or a whole number from 200 through 1000000.");
        if (result.CpuType is not null && result.CpuType is not ("auto" or "386" or "386_slow" or "386_prefetch" or "486_slow" or "pentium_slow"))
            throw new PackageBuilderException("--cpu-type must be 'auto', '386', '386_slow', '386_prefetch', '486_slow', or 'pentium_slow'.");
        if (result.Cycles is not null && result.CpuType is not null)
            throw new PackageBuilderException("--cycles and --cpu-type are mutually exclusive; specify only one performance default.");
        if (result.EnableScanlines && result.EnableCrtFilter)
            throw new PackageBuilderException("--scanlines and --crt-filter are mutually exclusive; the full CRT filter already includes scanlines.");

        if (result.ManifestPath is null && result.ArchivePath is null)
            throw new PackageBuilderException("Specify a package manifest or an archive. Use --help for usage.");

        return result;
    }

    private static string ReadValue(string[] args, ref int index, string option)
    {
        if (++index >= args.Length || string.IsNullOrWhiteSpace(args[index]))
            throw new PackageBuilderException($"Option '{option}' requires a value.");
        return args[index];
    }

    private static bool IsValidCycles(string value) =>
        value is "auto" or "max" ||
        int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out var cycles) && cycles is >= 200 and <= 1_000_000;

    public static void PrintHelp()
    {
        Console.WriteLine("DOSBox Pure Standalone package builder");
        Console.WriteLine();
        Console.WriteLine("Manifest mode:");
        Console.WriteLine("  makegame.exe package.json [--output GAME.exe] [--overwrite]");
        Console.WriteLine();
        Console.WriteLine("Direct mode:");
        Console.WriteLine("  makegame.exe game.dosz GAME.exe --template DOSBoxPureStandAlone.exe");
        Console.WriteLine("      --package-id com.example.game --title \"Example Game\"");
        Console.WriteLine("      [--startup GAME.EXE] [--icon game.png] [--config DOSBoxPure.cfg]");
        Console.WriteLine("      [--window-mode windowed|fullscreen] [--aspect-ratio <mode>]");
        Console.WriteLine("      [--cycles <value>|--cpu-type <type>]");
        Console.WriteLine("      [--text-mode] [--scanlines|--crt-filter]");
        Console.WriteLine("      [--overwrite]");
        Console.WriteLine();
        Console.WriteLine("Options:");
        Console.WriteLine("  --manifest <path>     Package JSON manifest");
        Console.WriteLine("  --template <path>     DOSBoxPureStandAlone.exe runtime template");
        Console.WriteLine("  --archive <path>      ZIP or DOSZ game archive");
        Console.WriteLine("  --output <path>       Output Windows executable");
        Console.WriteLine("  --package-id <id>     Stable persistence identity");
        Console.WriteLine("  --title <text>        Application and package title");
        Console.WriteLine("  --startup <path>      Archive-relative .EXE, .COM or .BAT startup file");
        Console.WriteLine("  --icon <path>         PNG converted to multi-size Windows icon resources");
        Console.WriteLine("  --config <path>       DOSBoxPure.cfg JSON embedded as package defaults");
        Console.WriteLine("  --window-mode <mode>  Startup mode: windowed (default) or fullscreen");
        Console.WriteLine("  --aspect-ratio <mode> off, on, doublescan, padded, padded-doublescan, or fill");
        Console.WriteLine("  --cycles <value>      auto, max, or a whole number from 200 through 1000000");
        Console.WriteLine("  --cpu-type <type>     auto, 386, 386_slow, 386_prefetch, 486_slow, or pentium_slow");
        Console.WriteLine("  --text-mode           Reveal intentional or interactive DOS text screens");
        Console.WriteLine("  --scanlines           Scanlines; sharpest image, no curvature/corners");
        Console.WriteLine("  --crt-filter          TV CRT; sharpest image, no curvature/corners");
        Console.WriteLine("  --validate-only       Validate inputs without producing an executable");
        Console.WriteLine("  --overwrite           Replace an existing output executable");
    }
}
