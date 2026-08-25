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
    ArchiveStorageMode ArchiveStorage,
    int DefaultConfigCount,
    bool HasCustomIcon);

internal enum ArchiveStorageMode
{
    Resource,
    Appended,
}

internal static partial class PackageBuilder
{
    private const int ArchiveResourceId = 101;
    private const int MetadataResourceId = 102;
    private const int DefaultConfigResourceId = 103;
    private const ushort ResourceLanguage = 1033;
    private const long MaxMappedResourceArchiveSize = 1536L * 1024 * 1024;
    private const long MaxWindowsExecutableSize = uint.MaxValue;

    [GeneratedRegex("^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$", RegexOptions.CultureInvariant)]
    private static partial Regex PackageIdPattern();

    public static PackageBuildResult Build(PackageSpecification package, bool overwrite, bool validateOnly)
    {
        ValidateSpecification(package, overwrite, validateOnly);
        var templateContainsArchive = ValidateTemplate(package.TemplatePath);
        var defaultConfig = DefaultConfig.Load(package.DefaultConfigPath, package.Fullscreen, package.LockMouse, package.AspectRatio, package.Cycles, package.CpuType, package.EnableScanlines, package.EnableCrtFilter);
        var startup = NormalizeAndValidateStartup(package.Startup ?? defaultConfig.PackageStartup ?? "DOSBOX.BAT");
        using var archive = GameArchive.OpenValidated(package.ArchivePath, startup);
        var archiveStorage = archive.Length > MaxMappedResourceArchiveSize
            ? ArchiveStorageMode.Appended
            : ArchiveStorageMode.Resource;
        var icon = package.IconPath is null ? null : IconResourceBuilder.FromPng(package.IconPath);
        var metadataBytes = CreateMetadata(package, startup, archive.Identity, archiveStorage, defaultConfig.Data is not null);
        var versionBytes = VersionResourceBuilder.Build(package);

        var outputDirectory = validateOnly ? Path.GetTempPath() : Path.GetDirectoryName(package.OutputPath)!;
        if (!validateOnly) Directory.CreateDirectory(outputDirectory);
        var temporaryPath = Path.Combine(outputDirectory, $".{Path.GetFileNameWithoutExtension(package.OutputPath)}.{Guid.NewGuid():N}.tmp.exe");

        try
        {
            File.Copy(package.TemplatePath, temporaryPath, false);
            using (var updater = new ResourceUpdater(temporaryPath))
            {
                if (archiveStorage == ArchiveStorageMode.Resource)
                    updater.SetNumeric(NativeResources.RtRcData, ArchiveResourceId, ResourceLanguage, archive.ReadAllBytes());
                else if (templateContainsArchive)
                    updater.DeleteNumeric(NativeResources.RtRcData, ArchiveResourceId, ResourceLanguage);
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

            VerifyOutputResources(temporaryPath, archive.Length, archiveStorage, metadataBytes, defaultConfig.Data, icon);
            if (archiveStorage == ArchiveStorageMode.Appended)
            {
                EnsureAppendedExecutableFitsWindows(temporaryPath, archive.Length);
                if (validateOnly)
                {
                    DeleteValidationTemporary(temporaryPath);
                    return new PackageBuildResult(package.OutputPath, package.PackageId, startup, archive.Length, archive.Identity, archiveStorage, defaultConfig.Count, icon is not null);
                }
                AppendedArchivePayload.Append(temporaryPath, archive);
                AppendedArchivePayload.Verify(temporaryPath, archive);
            }
            else if (validateOnly)
            {
                DeleteValidationTemporary(temporaryPath);
                return new PackageBuildResult(package.OutputPath, package.PackageId, startup, archive.Length, archive.Identity, archiveStorage, defaultConfig.Count, icon is not null);
            }
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

        return new PackageBuildResult(package.OutputPath, package.PackageId, startup, archive.Length, archive.Identity, archiveStorage, defaultConfig.Count, icon is not null);
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

    private static bool ValidateTemplate(string templatePath)
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
            return hasArchive;
        }
        catch (PackageBuilderException) { throw; }
        catch (Exception ex)
        {
            throw new PackageBuilderException($"Runtime template is not a usable Windows executable: {ex.Message}", ex);
        }
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

    private static byte[] CreateMetadata(PackageSpecification package, string startup, string archiveIdentity, ArchiveStorageMode archiveStorage, bool hasDefaultConfig)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = true, Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping }))
        {
            writer.WriteStartObject();
            writer.WriteNumber("format_version", package.FormatVersion);
            writer.WriteString("package_id", package.PackageId);
            writer.WriteString("title", package.Title);
            writer.WriteString("startup", startup);
            if (archiveStorage == ArchiveStorageMode.Resource)
                writer.WriteNumber("archive_resource", ArchiveResourceId);
            else
                writer.WriteString("archive_storage", AppendedArchivePayload.StorageName);
            writer.WriteString("archive_identity", archiveIdentity);
            if (hasDefaultConfig) writer.WriteNumber("default_config_resource", DefaultConfigResourceId);
            if (package.TextMode) writer.WriteBoolean("text_mode", true);
            if (!string.IsNullOrWhiteSpace(package.VersionInfo.CompanyName)) writer.WriteString("publisher", package.VersionInfo.CompanyName);
            if (!string.IsNullOrWhiteSpace(package.VersionInfo.ProductVersion)) writer.WriteString("version", package.VersionInfo.ProductVersion);
            writer.WriteEndObject();
        }
        return stream.ToArray();
    }

    private static void VerifyOutputResources(string outputPath, long archiveSize, ArchiveStorageMode archiveStorage, byte[] metadata, byte[]? defaultConfig, IconResources? icon)
    {
        using var module = ResourceModule.Load(outputPath);
        if (archiveStorage == ArchiveStorageMode.Resource)
        {
            if (module.GetNumericSize(NativeResources.RtRcData, ArchiveResourceId) != archiveSize)
                throw new PackageBuilderException("Output verification failed: embedded archive resource size does not match.");
        }
        else
        {
            if (module.HasNumeric(NativeResources.RtRcData, ArchiveResourceId))
                throw new PackageBuilderException("Output verification failed: a large package must not map its archive as a PE resource.");
        }
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

    private static void EnsureAppendedExecutableFitsWindows(string executablePath, long archiveSize)
    {
        var runtimeSize = new FileInfo(executablePath).Length;
        var maximumArchiveSize = MaxWindowsExecutableSize - runtimeSize - AppendedArchivePayload.TrailerSize;
        if (archiveSize <= maximumArchiveSize) return;

        var generatedSize = runtimeSize + archiveSize + AppendedArchivePayload.TrailerSize;
        throw new PackageBuilderException(
            $"Generated executable would be {generatedSize:N0} bytes. Windows cannot launch an executable whose total file size is 4 GiB or larger. " +
            $"With the selected runtime, metadata, configuration, and icon, the archive must be no larger than {maximumArchiveSize:N0} bytes. " +
            "Reduce the archive, convert raw MODE1/2352 CD images to ISO where compatible, or distribute the game in more than one file.");
    }

    private static void RequireFile(string path, string label)
    {
        if (!File.Exists(path)) throw new PackageBuilderException($"{label} not found: {path}");
    }

    private static void DeleteValidationTemporary(string path)
    {
        try { File.Delete(path); }
        catch (Exception ex) { throw new PackageBuilderException($"Validation succeeded, but its temporary runtime copy could not be removed: {ex.Message}", ex); }
    }

    private static void TryDelete(string path)
    {
        try { if (File.Exists(path)) File.Delete(path); } catch { }
    }
}
