using System.IO.Compression;

namespace DosBoxPureStandalone.MakeGame;

internal sealed class GameArchive : IDisposable
{
    private const int BufferSize = 1024 * 1024;
    private FileStream? stream;

    private GameArchive(string path, FileStream stream, string identity)
    {
        Path = path;
        this.stream = stream;
        Identity = identity;
        Length = stream.Length;
    }

    public string Path { get; }
    public long Length { get; }
    public string Identity { get; }

    public static GameArchive OpenValidated(string path, string startup)
    {
        FileStream? stream = null;
        try
        {
            stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, BufferSize, FileOptions.RandomAccess);
            if (stream.Length <= 0) throw new PackageBuilderException("Game archive is empty.");

            ValidateZip(stream, startup);
            var identity = CalculateIdentity(stream);
            return new GameArchive(path, stream, identity);
        }
        catch (PackageBuilderException)
        {
            stream?.Dispose();
            throw;
        }
        catch (InvalidDataException ex)
        {
            stream?.Dispose();
            throw new PackageBuilderException($"Game archive is invalid or uses unsupported ZIP features: {ex.Message}", ex);
        }
        catch (Exception ex)
        {
            stream?.Dispose();
            throw new PackageBuilderException($"Unable to validate game archive: {ex.Message}", ex);
        }
    }

    public byte[] ReadAllBytes()
    {
        var source = RequireStream();
        if (Length > Array.MaxLength)
            throw new PackageBuilderException("Game archive selected for PE resource storage exceeds the supported in-memory size.");

        source.Position = 0;
        var result = new byte[checked((int)Length)];
        source.ReadExactly(result);
        return result;
    }

    public void CopyTo(Stream destination)
    {
        var source = RequireStream();
        source.Position = 0;
        source.CopyTo(destination, BufferSize);
        if (source.Position != Length)
            throw new PackageBuilderException("Unable to read the complete game archive while writing the package.");
    }

    public void VerifyEqual(Stream candidate, long candidateOffset)
    {
        var source = RequireStream();
        source.Position = 0;
        candidate.Position = candidateOffset;

        var expectedBuffer = new byte[BufferSize];
        var actualBuffer = new byte[BufferSize];
        long remaining = Length;
        while (remaining != 0)
        {
            var count = (int)Math.Min(BufferSize, remaining);
            source.ReadExactly(expectedBuffer.AsSpan(0, count));
            candidate.ReadExactly(actualBuffer.AsSpan(0, count));
            if (!expectedBuffer.AsSpan(0, count).SequenceEqual(actualBuffer.AsSpan(0, count)))
                throw new PackageBuilderException("Output verification failed: appended archive data does not match.");
            remaining -= count;
        }
    }

    public void Dispose()
    {
        stream?.Dispose();
        stream = null;
    }

    private FileStream RequireStream() => stream ?? throw new ObjectDisposedException(nameof(GameArchive));

    private static void ValidateZip(FileStream file, string startup)
    {
        file.Position = 0;
        using var archive = new ZipArchive(file, ZipArchiveMode.Read, true);
        if (archive.Entries.Count == 0) throw new PackageBuilderException("Game archive contains no entries.");

        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var files = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var buffer = new byte[BufferSize];
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
        if (files.Contains(archiveStartup)) return;
        if (startup.Equals("DOSBOX.BAT", StringComparison.OrdinalIgnoreCase))
            throw new PackageBuilderException("Game archive must contain exactly one root-level DOSBOX.BAT, or specify an existing .EXE, .COM or .BAT with --startup, manifest startup, or default-config package_startup.");
        throw new PackageBuilderException($"Configured startup file was not found in the game archive: {startup}");
    }

    private static void ValidateArchivePath(string path)
    {
        if (string.IsNullOrEmpty(path) || path[0] is '/' or '\\' || path.Contains(':') || path.Contains('\0'))
            throw new PackageBuilderException($"Archive contains an unsafe path: {path}");
        var segments = path.Split(['/', '\\'], StringSplitOptions.RemoveEmptyEntries);
        if (segments.Any(segment => segment is "." or ".."))
            throw new PackageBuilderException($"Archive contains a traversal path: {path}");
    }

    private static string CalculateIdentity(FileStream source)
    {
        const ulong offset = 14695981039346656037UL;
        const ulong prime = 1099511628211UL;
        var hash = offset;
        var buffer = new byte[BufferSize];

        source.Position = 0;
        int read;
        while ((read = source.Read(buffer, 0, buffer.Length)) != 0)
        {
            foreach (var value in buffer.AsSpan(0, read))
                hash = unchecked((hash ^ value) * prime);
        }
        if (source.Position != source.Length)
            throw new PackageBuilderException("Unable to read the complete game archive while calculating its identity.");
        return $"{hash:x16}-{source.Length:x}";
    }
}
