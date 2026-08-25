using System.Buffers.Binary;

namespace DosBoxPureStandalone.MakeGame;

internal static class AppendedArchivePayload
{
    public const string StorageName = "appended";
    public const int TrailerSize = 32;
    private static ReadOnlySpan<byte> Magic =>
    [
        (byte)'D', (byte)'B', (byte)'P', (byte)'S',
        (byte)'A', (byte)'R', (byte)'C', (byte)'H', (byte)'I', (byte)'V', (byte)'E', 1,
        (byte)'\r', (byte)'\n', 0x1a, 0,
    ];

    public static void Append(string executablePath, GameArchive archive)
    {
        using var stream = new FileStream(executablePath, FileMode.Open, FileAccess.Write, FileShare.None);
        stream.Position = stream.Length;
        var archiveOffset = stream.Position;
        archive.CopyTo(stream);

        Span<byte> trailer = stackalloc byte[TrailerSize];
        Magic.CopyTo(trailer);
        BinaryPrimitives.WriteUInt64LittleEndian(trailer[16..24], checked((ulong)archiveOffset));
        BinaryPrimitives.WriteUInt64LittleEndian(trailer[24..32], checked((ulong)archive.Length));
        stream.Write(trailer);
        stream.Flush(true);
    }

    public static void Verify(string executablePath, GameArchive expectedArchive)
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
        if (archiveOffset < 0 || archiveSize != expectedArchive.Length || archiveSize > stream.Length - TrailerSize || archiveOffset != stream.Length - TrailerSize - archiveSize)
            throw new PackageBuilderException("Output verification failed: appended archive bounds do not match.");

        expectedArchive.VerifyEqual(stream, archiveOffset);
    }
}
