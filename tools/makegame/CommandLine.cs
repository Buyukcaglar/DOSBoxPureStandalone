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

    public static void PrintHelp()
    {
        Console.WriteLine("DOSBox Pure Standalone package builder");
        Console.WriteLine();
        Console.WriteLine("Manifest mode:");
        Console.WriteLine("  makegame.exe package.json [--output GAME.exe] [--overwrite]");
        Console.WriteLine();
        Console.WriteLine("Direct mode:");
        Console.WriteLine("  makegame.exe game.dosz GAME.exe --template DOSBoxPure.exe");
        Console.WriteLine("      --package-id com.example.game --title \"Example Game\"");
        Console.WriteLine("      [--startup GAME.EXE] [--icon game.png] [--config DOSBoxPure.cfg]");
        Console.WriteLine("      [--window-mode windowed|fullscreen] [--scanlines|--crt-filter]");
        Console.WriteLine("      [--overwrite]");
        Console.WriteLine();
        Console.WriteLine("Options:");
        Console.WriteLine("  --manifest <path>     Package JSON manifest");
        Console.WriteLine("  --template <path>     Clean Phase 7 DOSBoxPure.exe runtime template");
        Console.WriteLine("  --archive <path>      ZIP or DOSZ game archive");
        Console.WriteLine("  --output <path>       Output Windows executable");
        Console.WriteLine("  --package-id <id>     Stable persistence identity");
        Console.WriteLine("  --title <text>        Application and package title");
        Console.WriteLine("  --startup <path>      Archive-relative .EXE, .COM or .BAT startup file");
        Console.WriteLine("  --icon <path>         PNG converted to multi-size Windows icon resources");
        Console.WriteLine("  --config <path>       DOSBoxPure.cfg JSON embedded as package defaults");
        Console.WriteLine("  --window-mode <mode>  Startup mode: windowed (default) or fullscreen");
        Console.WriteLine("  --scanlines           Enable scanlines-only CRT mode with normal gaps");
        Console.WriteLine("  --crt-filter          Enable TV-style CRT filter with normal scanlines");
        Console.WriteLine("  --validate-only       Validate inputs without producing an executable");
        Console.WriteLine("  --overwrite           Replace an existing output executable");
    }
}
