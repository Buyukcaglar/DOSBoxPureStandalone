using System.Text.Json;
using System.Text.Json.Serialization;

namespace DosBoxPureStandalone.MakeGame;

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
internal sealed class PackageManifest
{
    [JsonPropertyName("format_version")] public int FormatVersion { get; set; }
    [JsonPropertyName("package_id")] public string? PackageId { get; set; }
    [JsonPropertyName("title")] public string? Title { get; set; }
    [JsonPropertyName("startup")] public string? Startup { get; set; }
    [JsonPropertyName("template")] public string? Template { get; set; }
    [JsonPropertyName("archive")] public string? Archive { get; set; }
    [JsonPropertyName("output")] public string? Output { get; set; }
    [JsonPropertyName("icon")] public string? Icon { get; set; }
    [JsonPropertyName("default_config")] public string? DefaultConfig { get; set; }
    [JsonPropertyName("version_info")] public PackageVersionInfo? VersionInfo { get; set; }
}

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
internal sealed class PackageVersionInfo
{
    [JsonPropertyName("file_version")] public string? FileVersion { get; set; }
    [JsonPropertyName("product_version")] public string? ProductVersion { get; set; }
    [JsonPropertyName("company_name")] public string? CompanyName { get; set; }
    [JsonPropertyName("file_description")] public string? FileDescription { get; set; }
    [JsonPropertyName("product_name")] public string? ProductName { get; set; }
    [JsonPropertyName("legal_copyright")] public string? LegalCopyright { get; set; }
}

internal sealed class PackageSpecification
{
    public int FormatVersion { get; private init; }
    public required string PackageId { get; init; }
    public required string Title { get; init; }
    public string? Startup { get; init; }
    public required string TemplatePath { get; init; }
    public required string ArchivePath { get; init; }
    public required string OutputPath { get; init; }
    public string? IconPath { get; init; }
    public string? DefaultConfigPath { get; init; }
    public string? WindowMode { get; init; }
    public bool EnableScanlines { get; init; }
    public bool EnableCrtFilter { get; init; }
    public PackageVersionInfo VersionInfo { get; init; } = new();

    public static PackageSpecification Load(CommandLine commandLine)
    {
        PackageManifest manifest;
        string manifestDirectory;

        if (commandLine.ManifestPath is not null)
        {
            var manifestPath = Path.GetFullPath(commandLine.ManifestPath);
            if (!File.Exists(manifestPath)) throw new PackageBuilderException($"Manifest not found: {manifestPath}");
            if (new FileInfo(manifestPath).Length > 1024 * 1024) throw new PackageBuilderException("Package manifest is larger than 1 MiB.");
            manifestDirectory = Path.GetDirectoryName(manifestPath)!;
            try
            {
                manifest = JsonSerializer.Deserialize<PackageManifest>(File.ReadAllBytes(manifestPath), new JsonSerializerOptions
                {
                    AllowTrailingCommas = true,
                    ReadCommentHandling = JsonCommentHandling.Skip,
                    PropertyNameCaseInsensitive = false,
                }) ?? throw new PackageBuilderException("Package manifest is empty.");
            }
            catch (JsonException ex)
            {
                throw new PackageBuilderException($"Invalid package manifest: {ex.Message}", ex);
            }
        }
        else
        {
            manifest = new PackageManifest { FormatVersion = 1 };
            manifestDirectory = Environment.CurrentDirectory;
        }

        if (manifest.FormatVersion != 1)
            throw new PackageBuilderException($"Unsupported package manifest format_version '{manifest.FormatVersion}'. Expected 1.");

        var archivePath = ResolveOverride(commandLine.ArchivePath, manifest.Archive, manifestDirectory);
        var outputPath = ResolveOverride(commandLine.OutputPath, manifest.Output, manifestDirectory);
        var templatePath = ResolveOverride(commandLine.TemplatePath, manifest.Template, manifestDirectory);
        var iconPath = ResolveOverride(commandLine.IconPath, manifest.Icon, manifestDirectory);
        var defaultConfigPath = ResolveOverride(commandLine.DefaultConfigPath, manifest.DefaultConfig, manifestDirectory);

        if (archivePath is null) throw new PackageBuilderException("Package archive is required.");
        outputPath ??= Path.ChangeExtension(archivePath, ".exe");
        templatePath ??= FindDefaultTemplate(manifestDirectory);
        if (templatePath is null)
            throw new PackageBuilderException("Runtime template is required. Set 'template' in the manifest or pass --template.");

        var title = commandLine.Title ?? manifest.Title ?? Path.GetFileNameWithoutExtension(archivePath);
        return new PackageSpecification
        {
            FormatVersion = manifest.FormatVersion,
            PackageId = commandLine.PackageId ?? manifest.PackageId ?? string.Empty,
            Title = title,
            Startup = commandLine.Startup ?? manifest.Startup,
            TemplatePath = templatePath,
            ArchivePath = archivePath,
            OutputPath = outputPath,
            IconPath = iconPath,
            DefaultConfigPath = defaultConfigPath,
            WindowMode = commandLine.WindowMode,
            EnableScanlines = commandLine.EnableScanlines,
            EnableCrtFilter = commandLine.EnableCrtFilter,
            VersionInfo = manifest.VersionInfo ?? new PackageVersionInfo(),
        };
    }

    private static string? ResolveOverride(string? commandLinePath, string? manifestPath, string manifestDirectory)
    {
        if (!string.IsNullOrWhiteSpace(commandLinePath)) return Path.GetFullPath(commandLinePath);
        if (string.IsNullOrWhiteSpace(manifestPath)) return null;
        return Path.GetFullPath(Path.Combine(manifestDirectory, manifestPath));
    }

    private static string? FindDefaultTemplate(string manifestDirectory)
    {
        var candidates = new[]
        {
            Path.Combine(manifestDirectory, "DOSBoxPure.exe"),
            Path.Combine(AppContext.BaseDirectory, "DOSBoxPure.exe"),
        };
        return candidates.FirstOrDefault(File.Exists);
    }
}
