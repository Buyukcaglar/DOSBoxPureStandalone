using System.IO;
using System.Text;

namespace DosBoxPureStandalone.MakeGame;

internal static class VersionResourceBuilder
{
    private const uint VsFfiSignature = 0xFEEF04BD;
    private const uint VsFfiStructVersion = 0x00010000;
    private const uint VsFfiFileFlagsMask = 0x0000003F;
    private const uint VosNtWindows32 = 0x00040004;
    private const uint VftApp = 0x00000001;

    public static void Validate(PackageVersionInfo versionInfo)
    {
        ParseVersion(versionInfo.FileVersion ?? "1.0.0.0", "file_version");
        ParseVersion(versionInfo.ProductVersion ?? versionInfo.FileVersion ?? "1.0.0.0", "product_version");
        ValidateString(versionInfo.CompanyName, "company_name");
        ValidateString(versionInfo.FileDescription, "file_description");
        ValidateString(versionInfo.ProductName, "product_name");
        ValidateString(versionInfo.LegalCopyright, "legal_copyright");
    }

    public static byte[] Build(PackageSpecification package)
    {
        var fileVersion = ParseVersion(package.VersionInfo.FileVersion ?? "1.0.0.0", "file_version");
        var productVersion = ParseVersion(package.VersionInfo.ProductVersion ?? package.VersionInfo.FileVersion ?? "1.0.0.0", "product_version");
        var outputName = Path.GetFileName(package.OutputPath);
        var strings = new List<KeyValuePair<string, string>>
        {
            new("FileDescription", package.VersionInfo.FileDescription ?? package.Title),
            new("FileVersion", FormatVersion(fileVersion)),
            new("ProductName", package.VersionInfo.ProductName ?? package.Title),
            new("ProductVersion", FormatVersion(productVersion)),
            new("InternalName", Path.GetFileNameWithoutExtension(outputName)),
            new("OriginalFilename", outputName),
        };
        if (!string.IsNullOrWhiteSpace(package.VersionInfo.CompanyName)) strings.Add(new("CompanyName", package.VersionInfo.CompanyName));
        if (!string.IsNullOrWhiteSpace(package.VersionInfo.LegalCopyright)) strings.Add(new("LegalCopyright", package.VersionInfo.LegalCopyright));

        using var stream = new MemoryStream();
        var writer = new VersionWriter(stream);
        writer.WriteNode("VS_VERSION_INFO", 52, 0,
            value: binary => WriteFixedInfo(binary, fileVersion, productVersion),
            children: binary =>
            {
                binary.WriteNode("StringFileInfo", 0, 1, null, stringFileInfo =>
                {
                    stringFileInfo.WriteNode("040904B0", 0, 1, null, table =>
                    {
                        foreach (var item in strings)
                        {
                            var valueLength = checked((ushort)(item.Value.Length + 1));
                            table.WriteNode(item.Key, valueLength, 1,
                                value => value.WriteUtf16(item.Value), null);
                        }
                    });
                });
                binary.WriteNode("VarFileInfo", 0, 1, null, varFileInfo =>
                {
                    varFileInfo.WriteNode("Translation", 4, 0,
                        value =>
                        {
                            value.Writer.Write((ushort)0x0409);
                            value.Writer.Write((ushort)0x04B0);
                        }, null);
                });
            });
        return stream.ToArray();
    }

    private static void WriteFixedInfo(VersionWriter writer, ushort[] fileVersion, ushort[] productVersion)
    {
        writer.Writer.Write(VsFfiSignature);
        writer.Writer.Write(VsFfiStructVersion);
        writer.Writer.Write(((uint)fileVersion[0] << 16) | fileVersion[1]);
        writer.Writer.Write(((uint)fileVersion[2] << 16) | fileVersion[3]);
        writer.Writer.Write(((uint)productVersion[0] << 16) | productVersion[1]);
        writer.Writer.Write(((uint)productVersion[2] << 16) | productVersion[3]);
        writer.Writer.Write(VsFfiFileFlagsMask);
        writer.Writer.Write(0u);
        writer.Writer.Write(VosNtWindows32);
        writer.Writer.Write(VftApp);
        writer.Writer.Write(0u);
        writer.Writer.Write(0u);
        writer.Writer.Write(0u);
    }

    private static ushort[] ParseVersion(string value, string field)
    {
        var parts = value.Split('.');
        if (parts.Length is < 1 or > 4)
            throw new PackageBuilderException($"version_info.{field} must contain one to four numeric components.");
        var result = new ushort[4];
        for (var index = 0; index < parts.Length; index++)
        {
            if (!ushort.TryParse(parts[index], out result[index]))
                throw new PackageBuilderException($"version_info.{field} component '{parts[index]}' is not between 0 and 65535.");
        }
        return result;
    }

    private static string FormatVersion(ushort[] version) => string.Join('.', version);

    private static void ValidateString(string? value, string field)
    {
        if (value is not null && (value.Length > 1024 || value.Any(char.IsControl)))
            throw new PackageBuilderException($"version_info.{field} must be at most 1024 characters without control characters.");
    }

    private sealed class VersionWriter
    {
        private readonly Stream stream;
        public BinaryWriter Writer { get; }

        public VersionWriter(Stream stream)
        {
            this.stream = stream;
            Writer = new BinaryWriter(stream, Encoding.UTF8, true);
        }

        public void WriteNode(string key, ushort valueLength, ushort type, Action<VersionWriter>? value, Action<VersionWriter>? children)
        {
            Align4();
            var start = checked((int)stream.Position);
            Writer.Write((ushort)0);
            Writer.Write(valueLength);
            Writer.Write(type);
            WriteUtf16(key);
            Align4();
            value?.Invoke(this);
            Align4();
            children?.Invoke(this);
            var end = checked((int)stream.Position);
            if (end - start > ushort.MaxValue) throw new PackageBuilderException("Generated Windows version resource is too large.");

            var current = stream.Position;
            stream.Position = start;
            Writer.Write((ushort)(end - start));
            stream.Position = current;
        }

        public void WriteUtf16(string value)
        {
            Writer.Write(Encoding.Unicode.GetBytes(value));
            Writer.Write((ushort)0);
        }

        private void Align4()
        {
            while ((stream.Position & 3) != 0) Writer.Write((byte)0);
        }
    }
}
