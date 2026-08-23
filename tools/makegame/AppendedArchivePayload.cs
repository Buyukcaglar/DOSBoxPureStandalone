using System.Buffers.Binary;

namespace DosBoxPureStandalone.MakeGame;

internal static class AppendedArchivePayload
{
    public const string StorageName = "appended";
    private const int TrailerSize = 32;
    private const int CopyBufferSize = 1024 * 1024;
    private static ReadOnlySpan<byte> Magic =>
    [
        (byte)'D', (byte)'B', (byte)'P', (byte)'S',
        (byte)'A', (byte)'R', (byte)'C', (byte)'H', (byte)'I', (byte)'V', (byte)'E', 1,
        (byte)'\r', (byte)'\n', 0x1a, 0,
    ];

    public static void Append(string executablePath, byte[] archive)
    {
        using var stream = new FileStream(executablePath, FileMode.Open, FileAccess.Write, FileShare.None);
        stream.Position = stream.Length;
        var archiveOffset = stream.Position;
        stream.Write(archive);

        Span<byte> trailer = stackalloc byte[TrailerSize];
        Magic.CopyTo(trailer);
        BinaryPrimitives.WriteUInt64LittleEndian(trailer[16..24], checked((ulong)archiveOffset));
        BinaryPrimitives.WriteUInt64LittleEndian(trailer[24..32], checked((ulong)archive.LongLength));
        stream.Write(trailer);
        stream.Flush(true);
    }

    public static void Verify(string executablePath, byte[] expectedArchive)
    {
        using var stream = new FileStream(executablePath, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (stream.Length < TrailerSize)
            throw new PackageBuilderException("Output verification failed: appended archive trailer is missing.");

        Span<byte> trailer = stackalloc byte[TrailerSize];
        stream.Position = stream.Length - TrailerSize;
        stream.ReadExactly(trailer);
        if (!trailer[..16].SequenceEqual(Magic))
            throw new PackageBuilderException("Output verification failed: appended archive trailer signature does not match.");

        var archiveOffset = checked((long)BinaryPrimitives.ReadUInt64LittleEndian(trailer[16..24]));
        var archiveSize = checked((long)BinaryPrimitives.ReadUInt64LittleEndian(trailer[24..32]));
        if (archiveOffset < 0 || archiveSize != expectedArchive.LongLength || archiveOffset + archiveSize + TrailerSize != stream.Length)
            throw new PackageBuilderException("Output verification failed: appended archive bounds do not match.");

        stream.Position = archiveOffset;
        var buffer = new byte[CopyBufferSize];
        var compared = 0;
        while (compared != expectedArchive.Length)
        {
            var count = Math.Min(buffer.Length, expectedArchive.Length - compared);
            stream.ReadExactly(buffer.AsSpan(0, count));
            if (!buffer.AsSpan(0, count).SequenceEqual(expectedArchive.AsSpan(compared, count)))
                throw new PackageBuilderException("Output verification failed: appended archive data does not match.");
            compared += count;
        }
    }
}
