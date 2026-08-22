using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace DosBoxPureStandalone.MakeGame;

internal sealed record DefaultConfigResult(byte[]? Data, int Count, string? PackageStartup);

internal static partial class DefaultConfig
{
    private const int MaximumConfigBytes = 1024 * 1024;

    [GeneratedRegex("^[A-Za-z0-9_.-]{1,128}$", RegexOptions.CultureInvariant)]
    private static partial Regex ConfigKeyPattern();

    public static DefaultConfigResult Load(string? path, bool fullscreen, bool lockMouse, string? aspectRatio, string? cycles, string? cpuType, bool enableScanlines, bool enableCrtFilter)
    {
        var settings = new List<KeyValuePair<string, string>>();
        string? packageStartup = null;
        if (path is not null)
        {
            var source = File.ReadAllBytes(path);
            if (source.Length == 0 || source.Length > MaximumConfigBytes)
                throw new PackageBuilderException("Default configuration must be between 1 byte and 1 MiB.");

            try
            {
                using var document = JsonDocument.Parse(source, new JsonDocumentOptions
                {
                    AllowTrailingCommas = true,
                    CommentHandling = JsonCommentHandling.Skip,
                    MaxDepth = 8,
                });
                if (document.RootElement.ValueKind != JsonValueKind.Object)
                    throw new PackageBuilderException("Default configuration must be a JSON object like DOSBoxPure.cfg.");

                var keys = new HashSet<string>(StringComparer.Ordinal);
                foreach (var property in document.RootElement.EnumerateObject())
                {
                    if (!ConfigKeyPattern().IsMatch(property.Name))
                        throw new PackageBuilderException($"Default configuration contains an unsafe key: {property.Name}");
                    if (!keys.Add(property.Name))
                        throw new PackageBuilderException($"Default configuration contains a duplicate key: {property.Name}");
                    if (property.Value.ValueKind != JsonValueKind.String)
                        throw new PackageBuilderException($"Default configuration value '{property.Name}' must be a JSON string.");
                    var value = property.Value.GetString()!;
                    if (System.Text.Encoding.UTF8.GetByteCount(value) > 4096)
                        throw new PackageBuilderException($"Default configuration value '{property.Name}' is larger than 4096 UTF-8 bytes.");
                    if (property.Name.Equals("package_startup", StringComparison.Ordinal))
                    {
                        packageStartup = value;
                        continue;
                    }
                    settings.Add(new(property.Name, value));
                }
            }
            catch (PackageBuilderException) { throw; }
            catch (JsonException ex)
            {
                throw new PackageBuilderException($"Default configuration is not valid JSON: {ex.Message}", ex);
            }
        }

        SetSetting(settings, "screen_fullscreen", fullscreen ? "true" : "false");
        SetSetting(settings, "interface_lockmouse", lockMouse ? "true" : "false");
        if (aspectRatio is not null)
            SetSetting(settings, "dosbox_pure_aspect_correction", aspectRatio switch
            {
                "off" => "false",
                "on" => "true",
                _ => aspectRatio,
            });
        if (cycles is not null)
            SetSetting(settings, "dosbox_pure_cycles", cycles);
        if (cpuType is not null)
            SetSetting(settings, "dosbox_pure_cpu_type", cpuType);
        if (enableScanlines)
        {
            SetSetting(settings, "interface_crtfilter", "1");
            SetSetting(settings, "interface_crtscanline", "3");
        }
        else if (enableCrtFilter)
        {
            SetSetting(settings, "interface_crtfilter", "2");
            SetSetting(settings, "interface_crtscanline", "3");
        }
        if (enableScanlines || enableCrtFilter)
        {
            SetSetting(settings, "interface_crtblur", "7");
            SetSetting(settings, "interface_crtcurvature", "0");
            SetSetting(settings, "interface_crtcorner", "0");
        }

        if (settings.Count == 0) return new(null, 0, packageStartup);

        using var output = new MemoryStream();
        using (var writer = new Utf8JsonWriter(output, new JsonWriterOptions { Indented = true, Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping }))
        {
            writer.WriteStartObject();
            foreach (var setting in settings) writer.WriteString(setting.Key, setting.Value);
            writer.WriteEndObject();
        }
        return new(output.ToArray(), settings.Count, packageStartup);
    }

    private static void SetSetting(List<KeyValuePair<string, string>> settings, string key, string value)
    {
        var index = settings.FindIndex(setting => setting.Key.Equals(key, StringComparison.Ordinal));
        var replacement = new KeyValuePair<string, string>(key, value);
        if (index == -1) settings.Add(replacement);
        else settings[index] = replacement;
    }
}
