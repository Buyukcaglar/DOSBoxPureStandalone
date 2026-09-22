using System.Buffers.Binary;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Serialization;

namespace DosBoxPureStandalone.MakeGame;

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
internal sealed class DifferencingVhdSpecification
{
    [JsonPropertyName("disk_id")] public string? DiskId { get; set; }
    [JsonPropertyName("parent")] public string? Parent { get; set; }
    [JsonPropertyName("child")] public string? Child { get; set; }
}

internal sealed record DifferencingVhdIdentity(string DiskId, string Parent, string Child,
    string ParentSha256, string ParentUuid, ulong ParentVirtualSize);

internal static class DifferencingVhd
{
    public const int CapabilityResourceId = 104;
    public static readonly byte[] Capability = Encoding.ASCII.GetBytes("DBPVHD_IDENTITY_1\0");

    public static DifferencingVhdIdentity Inspect(Stream source, DifferencingVhdSpecification specification)
    {
        var diskId = specification.DiskId ?? string.Empty;
        if (diskId.Length is < 1 or > 64 || diskId.Any(c => !char.IsAsciiLetterOrDigit(c) && c is not '_' and not '-'))
            throw new PackageBuilderException("differencing_vhd.disk_id must contain 1-64 ASCII letters, digits, '_' or '-'.");
        var parent = NormalizeName(specification.Parent);
        var child = NormalizeName(specification.Child);
        if (parent == child) throw new PackageBuilderException("Differencing VHD parent and child must have distinct names.");
        var binding = Path.ChangeExtension(child, ".DBI");
        source.Position = 0;
        using var archive = new ZipArchive(source, ZipArchiveMode.Read, true);
        if (archive.Entries.Any(e => e.FullName.Equals(child, StringComparison.OrdinalIgnoreCase) || e.FullName.Equals(binding, StringComparison.OrdinalIgnoreCase)))
            throw new PackageBuilderException("The child VHD and its .DBI binding name must not exist in the base archive.");
        var entry = archive.Entries.SingleOrDefault(e => e.FullName.Equals(parent, StringComparison.OrdinalIgnoreCase))
            ?? throw new PackageBuilderException($"Differencing VHD parent not found: {parent}");
        if (entry.Length < 1024 || entry.Length % 512 != 0)
            throw new PackageBuilderException("Differencing VHD parent length is invalid.");

        // Stream the uncompressed entry. Never materialize a loose VHD or a
        // second complete image in memory just to calculate its identity.
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        using var input = entry.Open();
        var first = new byte[1536];
        var footer = new byte[512];
        var buffer = new byte[64 * 1024];
        long offset = 0;
        int count;
        while ((count = input.Read(buffer)) != 0)
        {
            hash.AppendData(buffer, 0, count);
            if (offset < first.Length)
                buffer.AsSpan(0, (int)Math.Min(count, first.Length - offset)).CopyTo(first.AsSpan((int)offset));
            var tail = Math.Max(offset, entry.Length - 512);
            if (tail < offset + count)
                buffer.AsSpan((int)(tail - offset), (int)(offset + count - tail)).CopyTo(footer.AsSpan((int)(tail - (entry.Length - 512))));
            offset += count;
        }
        if (offset != entry.Length) throw new PackageBuilderException("Short read of differencing VHD parent.");
        ValidateFooter(footer);
        var type = BinaryPrimitives.ReadUInt32BigEndian(footer.AsSpan(60));
        var size = BinaryPrimitives.ReadUInt64BigEndian(footer.AsSpan(48));
        var cylinders = BinaryPrimitives.ReadUInt16BigEndian(footer.AsSpan(56));
        if (size == 0 || size % 512 != 0 || size > 2040UL * 1024 * 1024 * 1024 ||
            cylinders == 0 || footer[58] == 0 || footer[59] is 0 or > 63 || (ulong)cylinders * footer[58] * footer[59] > size / 512)
            throw new PackageBuilderException("Differencing VHD parent virtual size or geometry is invalid.");
        if (type == 2)
        {
            if ((ulong)entry.Length != size + 512 || BinaryPrimitives.ReadUInt64BigEndian(footer.AsSpan(16)) != ulong.MaxValue)
                throw new PackageBuilderException("Fixed VHD parent size or data offset is invalid.");
        }
        else if (type == 3)
        {
            if (!first.AsSpan(0, 512).SequenceEqual(footer) || BinaryPrimitives.ReadUInt64BigEndian(footer.AsSpan(16)) != 512 ||
                !first.AsSpan(512, 8).SequenceEqual("cxsparse"u8) || !ValidChecksum(first.AsSpan(512, 1024), 36))
                throw new PackageBuilderException("Dynamic VHD parent footer copies or sparse header are invalid.");
        }
        else throw new PackageBuilderException("Differencing VHD parents must be fixed (type 2) or dynamic (type 3); chains are unsupported.");
        return new(diskId, parent, child, Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant(),
            Convert.ToHexString(footer.AsSpan(68, 16)).ToLowerInvariant(), size);
    }

    private static string NormalizeName(string? name)
    {
        name = (name ?? string.Empty).ToUpperInvariant();
        if (name.Length is < 5 or > 12 || !name.EndsWith(".VHD", StringComparison.Ordinal) ||
            name[..^4].Any(c => !char.IsAsciiLetterOrDigit(c) && c is not '_' and not '-'))
            throw new PackageBuilderException("Differencing VHD paths must be root-level 8.3 .VHD names using letters, digits, '_' or '-'.");
        return name;
    }

    private static bool ValidChecksum(ReadOnlySpan<byte> data, int checksumOffset)
    {
        uint sum = 0;
        for (var i = 0; i < data.Length; ++i)
            if (i < checksumOffset || i >= checksumOffset + 4) sum += data[i];
        return ~sum == BinaryPrimitives.ReadUInt32BigEndian(data[checksumOffset..]);
    }

    private static void ValidateFooter(byte[] footer)
    {
        if (!footer.AsSpan(0, 8).SequenceEqual("conectix"u8) || !ValidChecksum(footer, 64) ||
            BinaryPrimitives.ReadUInt32BigEndian(footer.AsSpan(8)) != 2 ||
            BinaryPrimitives.ReadUInt32BigEndian(footer.AsSpan(12)) != 0x10000 || footer[84] != 0 ||
            footer.AsSpan(68, 16).IndexOfAnyExcept((byte)0) < 0)
            throw new PackageBuilderException("Differencing VHD parent footer is invalid or unsupported.");
    }
}
