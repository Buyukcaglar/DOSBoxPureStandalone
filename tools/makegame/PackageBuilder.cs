using System.IO.Compression;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace DosBoxPureStandalone.MakeGame;

internal sealed record PackageBuildResult(
    string OutputPath,
    string PackageId,
    string Startup,
    long ArchiveSize,
    string ArchiveIdentity,
    int DefaultConfigCount,
    bool HasCustomIcon);

internal static partial class PackageBuilder
{
    private const int ArchiveResourceId = 101;
    private const int MetadataResourceId = 102;
    private const int DefaultConfigResourceId = 103;
    private const string TextModeMarker = "TEXTMODE.DBP";
    private const ushort ResourceLanguage = 1033;

    [GeneratedRegex("^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$", RegexOptions.CultureInvariant)]
    private static partial Regex PackageIdPattern();

    public static PackageBuildResult Build(PackageSpecification package, bool overwrite, bool validateOnly)
    {
        ValidateSpecification(package, overwrite, validateOnly);
        ValidateTemplate(package.TemplatePath);
        var defaultConfig = DefaultConfig.Load(package.DefaultConfigPath, package.Fullscreen, package.LockMouse, package.AspectRatio, package.Cycles, package.CpuType, package.EnableScanlines, package.EnableCrtFilter);
        var startup = NormalizeAndValidateStartup(package.Startup ?? defaultConfig.PackageStartup ?? "DOSBOX.BAT");
        var archiveBytes = ValidateAndReadArchive(package.ArchivePath, startup);
        if (package.TextMode) archiveBytes = EnsureTextModeMarker(archiveBytes);
        var archiveIdentity = CalculateArchiveIdentity(archiveBytes);
        var icon = package.IconPath is null ? null : IconResourceBuilder.FromPng(package.IconPath);
        var metadataBytes = CreateMetadata(package, startup, archiveIdentity, defaultConfig.Data is not null);
        var versionBytes = VersionResourceBuilder.Build(package);

        if (validateOnly)
            return new PackageBuildResult(package.OutputPath, package.PackageId, startup, archiveBytes.LongLength, archiveIdentity, defaultConfig.Count, icon is not null);

        var outputDirectory = Path.GetDirectoryName(package.OutputPath)!;
        Directory.CreateDirectory(outputDirectory);
        var temporaryPath = Path.Combine(outputDirectory, $".{Path.GetFileNameWithoutExtension(package.OutputPath)}.{Guid.NewGuid():N}.tmp.exe");

        try
        {
            File.Copy(package.TemplatePath, temporaryPath, false);
            using (var updater = new ResourceUpdater(temporaryPath))
            {
                updater.SetNumeric(NativeResources.RtRcData, ArchiveResourceId, ResourceLanguage, archiveBytes);
                updater.SetNumeric(NativeResources.RtRcData, MetadataResourceId, ResourceLanguage, metadataBytes);
                if (defaultConfig.Data is not null)
                    updater.SetNumeric(NativeResources.RtRcData, DefaultConfigResourceId, ResourceLanguage, defaultConfig.Data);
                if (icon is not null)
                {
                    foreach (var frame in icon.Frames)
                        updater.SetNumeric(NativeResources.RtIcon, frame.ResourceId, ResourceLanguage, frame.Data);
                    updater.SetNamed(NativeResources.RtGroupIcon, "ZL", ResourceLanguage, icon.GroupData);
                }
                updater.SetNumeric(NativeResources.RtVersion, 1, ResourceLanguage, versionBytes);
                updater.Commit();
            }

            VerifyOutputResources(temporaryPath, archiveBytes.Length, metadataBytes, defaultConfig.Data, icon);
            File.Move(temporaryPath, package.OutputPath, overwrite);
        }
        catch (PackageBuilderException)
        {
            TryDelete(temporaryPath);
            throw;
        }
        catch (Exception ex)
        {
            TryDelete(temporaryPath);
            throw new PackageBuilderException($"Unable to generate package '{package.OutputPath}': {ex.Message}", ex);
        }

        return new PackageBuildResult(package.OutputPath, package.PackageId, startup, archiveBytes.LongLength, archiveIdentity, defaultConfig.Count, icon is not null);
    }

    private static void ValidateSpecification(PackageSpecification package, bool overwrite, bool validateOnly)
    {
        if (!PackageIdPattern().IsMatch(package.PackageId) || package.PackageId.Equals("system", StringComparison.OrdinalIgnoreCase))
            throw new PackageBuilderException("package_id must be 1-128 ASCII characters, start and end with a letter or digit, use only letters, digits, '.', '-' or '_', and cannot be 'system'.");

        var titleBytes = Encoding.UTF8.GetByteCount(package.Title);
        if (titleBytes is < 1 or > 256 || package.Title.Any(char.IsControl))
            throw new PackageBuilderException("title must be 1-256 UTF-8 bytes and cannot contain control characters.");
        RequireFile(package.TemplatePath, "Runtime template");
        RequireFile(package.ArchivePath, "Game archive");
        if (package.IconPath is not null) RequireFile(package.IconPath, "PNG icon");
        if (package.DefaultConfigPath is not null) RequireFile(package.DefaultConfigPath, "Default configuration");

        var extension = Path.GetExtension(package.ArchivePath);
        if (!extension.Equals(".zip", StringComparison.OrdinalIgnoreCase) && !extension.Equals(".dosz", StringComparison.OrdinalIgnoreCase))
            throw new PackageBuilderException("Game archive must use the .zip or .dosz extension.");
        if (package.IconPath is not null && !Path.GetExtension(package.IconPath).Equals(".png", StringComparison.OrdinalIgnoreCase))
            throw new PackageBuilderException("Custom icon input must be a PNG file.");
        if (!Path.GetExtension(package.OutputPath).Equals(".exe", StringComparison.OrdinalIgnoreCase))
            throw new PackageBuilderException("Output path must use the .exe extension.");

        var templatePath = Path.GetFullPath(package.TemplatePath);
        var outputPath = Path.GetFullPath(package.OutputPath);
        if (templatePath.Equals(outputPath, StringComparison.OrdinalIgnoreCase))
            throw new PackageBuilderException("Output path cannot overwrite the runtime template.");
        if (!validateOnly && File.Exists(outputPath) && !overwrite)
            throw new PackageBuilderException($"Output already exists: {outputPath}. Pass --overwrite to replace it.");

        VersionResourceBuilder.Validate(package.VersionInfo);
    }

    private static void ValidateTemplate(string templatePath)
    {
        try
        {
            using var module = ResourceModule.Load(templatePath);
            var hasArchive = module.HasNumeric(NativeResources.RtRcData, ArchiveResourceId);
            var hasMetadata = module.HasNumeric(NativeResources.RtRcData, MetadataResourceId);
            if (hasArchive != hasMetadata)
                throw new PackageBuilderException("Runtime template contains an incomplete archive/metadata resource pair.");
            if (!module.HasNamed(NativeResources.RtGroupIcon, "ZL"))
                throw new PackageBuilderException("Runtime template does not contain the expected ZL application icon group.");
        }
        catch (PackageBuilderException) { throw; }
        catch (Exception ex)
        {
            throw new PackageBuilderException($"Runtime template is not a usable Windows executable: {ex.Message}", ex);
        }
    }

    private static byte[] ValidateAndReadArchive(string archivePath, string startup)
    {
        var info = new FileInfo(archivePath);
        if (info.Length <= 0) throw new PackageBuilderException("Game archive is empty.");
        if (info.Length > Array.MaxLength) throw new PackageBuilderException("Game archive is larger than the package builder's approximately 2 GiB in-memory resource limit.");

        try
        {
            using var file = File.Open(archivePath, FileMode.Open, FileAccess.Read, FileShare.Read);
            using var archive = new ZipArchive(file, ZipArchiveMode.Read, false);
            if (archive.Entries.Count == 0) throw new PackageBuilderException("Game archive contains no entries.");

            var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var files = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var buffer = new byte[1024 * 1024];
            foreach (var entry in archive.Entries)
            {
                ValidateArchivePath(entry.FullName);
                var normalizedName = entry.FullName.Replace('\\', '/');
                if (!names.Add(normalizedName))
                    throw new PackageBuilderException($"Game archive contains a duplicate path: {entry.FullName}");
                if (entry.FullName.EndsWith('/') || entry.FullName.EndsWith('\\')) continue;
                files.Add(normalizedName);

                using var entryStream = entry.Open();
                long bytesRead = 0;
                int read;
                while ((read = entryStream.Read(buffer, 0, buffer.Length)) != 0) bytesRead += read;
                if (bytesRead != entry.Length)
                    throw new PackageBuilderException($"Archive entry length mismatch: {entry.FullName}");
            }
            var archiveStartup = startup.Replace('\\', '/');
            if (!files.Contains(archiveStartup))
            {
                if (startup.Equals("DOSBOX.BAT", StringComparison.OrdinalIgnoreCase))
                    throw new PackageBuilderException("Game archive must contain exactly one root-level DOSBOX.BAT, or specify an existing .EXE, .COM or .BAT with --startup, manifest startup, or default-config package_startup.");
                throw new PackageBuilderException($"Configured startup file was not found in the game archive: {startup}");
            }
        }
        catch (PackageBuilderException) { throw; }
        catch (InvalidDataException ex)
        {
            throw new PackageBuilderException($"Game archive is invalid or uses unsupported ZIP features: {ex.Message}", ex);
        }
        catch (Exception ex)
        {
            throw new PackageBuilderException($"Unable to validate game archive: {ex.Message}", ex);
        }

        return File.ReadAllBytes(archivePath);
    }

    private static byte[] EnsureTextModeMarker(byte[] archiveBytes)
    {
        try
        {
            using (var source = new MemoryStream(archiveBytes, false))
            using (var archive = new ZipArchive(source, ZipArchiveMode.Read, false))
            {
                if (archive.Entries.Any(entry => entry.FullName.Equals(TextModeMarker, StringComparison.OrdinalIgnoreCase)))
                    return archiveBytes;
            }

            const int markerOverheadAllowance = 4096;
            if (archiveBytes.Length > Array.MaxLength - markerOverheadAllowance)
                throw new PackageBuilderException("Game archive is too large to add the text-mode marker in memory.");

            using var output = new MemoryStream(archiveBytes.Length + markerOverheadAllowance);
            output.Write(archiveBytes);
            output.Position = 0;
            using (var archive = new ZipArchive(output, ZipArchiveMode.Update, true))
            {
                var marker = archive.CreateEntry(TextModeMarker, CompressionLevel.NoCompression);
                marker.LastWriteTime = new DateTimeOffset(1980, 1, 1, 0, 0, 0, TimeSpan.Zero);
            }
            return output.ToArray();
        }
        catch (PackageBuilderException) { throw; }
        catch (Exception ex)
        {
            throw new PackageBuilderException($"Unable to add the text-mode marker to the embedded archive: {ex.Message}", ex);
        }
    }

    private static void ValidateArchivePath(string path)
    {
        if (string.IsNullOrEmpty(path) || path[0] is '/' or '\\' || path.Contains(':') || path.Contains('\0'))
            throw new PackageBuilderException($"Archive contains an unsafe path: {path}");
        var segments = path.Split(['/', '\\'], StringSplitOptions.RemoveEmptyEntries);
        if (segments.Any(segment => segment is "." or ".."))
            throw new PackageBuilderException($"Archive contains a traversal path: {path}");
    }

    private static string NormalizeAndValidateStartup(string startup)
    {
        startup = startup.Trim().Replace('/', '\\');
        if (startup.Length is < 1 or > 255 || startup[0] == '\\' || startup.Contains(':') || startup.Contains('\0'))
            throw new PackageBuilderException("Startup must be a safe archive-relative DOS path no longer than 255 characters.");

        foreach (var character in startup)
        {
            if (char.IsAsciiLetterOrDigit(character) || character is '.' or '_' or '-' or '\\' or '$' or '!' or '#' or '%' or '\'' or '(' or ')' or '@' or '^' or '{' or '}' or '~')
                continue;
            throw new PackageBuilderException($"Startup contains an unsafe command character: {character}");
        }

        var segments = startup.Split('\\');
        if (segments.Any(segment => segment.Length == 0 || segment is "." or ".."))
            throw new PackageBuilderException("Startup must not contain empty, current-directory or parent-directory path segments.");

        var extension = Path.GetExtension(startup);
        if (!extension.Equals(".exe", StringComparison.OrdinalIgnoreCase)
            && !extension.Equals(".com", StringComparison.OrdinalIgnoreCase)
            && !extension.Equals(".bat", StringComparison.OrdinalIgnoreCase))
            throw new PackageBuilderException("Startup must identify an .EXE, .COM or .BAT file inside the game archive.");
        return startup;
    }

    private static byte[] CreateMetadata(PackageSpecification package, string startup, string archiveIdentity, bool hasDefaultConfig)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = true, Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping }))
        {
            writer.WriteStartObject();
            writer.WriteNumber("format_version", package.FormatVersion);
            writer.WriteString("package_id", package.PackageId);
            writer.WriteString("title", package.Title);
            writer.WriteString("startup", startup);
            writer.WriteNumber("archive_resource", ArchiveResourceId);
            writer.WriteString("archive_identity", archiveIdentity);
            if (hasDefaultConfig) writer.WriteNumber("default_config_resource", DefaultConfigResourceId);
            if (!string.IsNullOrWhiteSpace(package.VersionInfo.CompanyName)) writer.WriteString("publisher", package.VersionInfo.CompanyName);
            if (!string.IsNullOrWhiteSpace(package.VersionInfo.ProductVersion)) writer.WriteString("version", package.VersionInfo.ProductVersion);
            writer.WriteEndObject();
        }
        return stream.ToArray();
    }

    private static string CalculateArchiveIdentity(byte[] bytes)
    {
        const ulong offset = 14695981039346656037UL;
        const ulong prime = 1099511628211UL;
        var hash = offset;
        foreach (var value in bytes) hash = unchecked((hash ^ value) * prime);
        return $"{hash:x16}-{bytes.LongLength:x}";
    }

    private static void VerifyOutputResources(string outputPath, int archiveSize, byte[] metadata, byte[]? defaultConfig, IconResources? icon)
    {
        using var module = ResourceModule.Load(outputPath);
        if (module.GetNumericSize(NativeResources.RtRcData, ArchiveResourceId) != archiveSize)
            throw new PackageBuilderException("Output verification failed: embedded archive resource size does not match.");
        if (!module.ReadNumeric(NativeResources.RtRcData, MetadataResourceId).SequenceEqual(metadata))
            throw new PackageBuilderException("Output verification failed: embedded metadata does not match.");
        if (defaultConfig is not null && !module.ReadNumeric(NativeResources.RtRcData, DefaultConfigResourceId).SequenceEqual(defaultConfig))
            throw new PackageBuilderException("Output verification failed: embedded default configuration does not match.");
        if (icon is not null)
        {
            if (!module.ReadNamed(NativeResources.RtGroupIcon, "ZL").SequenceEqual(icon.GroupData))
                throw new PackageBuilderException("Output verification failed: Windows icon group does not match.");
            if (!NativeResources.CanExtractApplicationIcon(outputPath))
                throw new PackageBuilderException("Output verification failed: Windows could not extract the application icon.");
        }
        if (!module.HasNumeric(NativeResources.RtVersion, 1))
            throw new PackageBuilderException("Output verification failed: version resource is missing.");
    }

    private static void RequireFile(string path, string label)
    {
        if (!File.Exists(path)) throw new PackageBuilderException($"{label} not found: {path}");
    }

    private static void TryDelete(string path)
    {
        try { if (File.Exists(path)) File.Delete(path); } catch { }
    }
}
