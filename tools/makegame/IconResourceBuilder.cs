using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace DosBoxPureStandalone.MakeGame;

internal sealed record IconFrame(int Size, int ResourceId, byte[] Data);
internal sealed record IconResources(IReadOnlyList<IconFrame> Frames, byte[] GroupData);

internal static class IconResourceBuilder
{
    private static readonly int[] Sizes = [16, 24, 32, 48, 64, 128, 256];
    private const int FirstResourceId = 201;

    public static IconResources FromPng(string path)
    {
        var signature = new byte[8];
        using (var stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            if (stream.Read(signature, 0, signature.Length) != signature.Length ||
                !signature.SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }))
                throw new PackageBuilderException("Custom icon is not a valid PNG file.");
        }

        BitmapSource source;
        try
        {
            using var stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read);
            var decoder = new PngBitmapDecoder(stream, BitmapCreateOptions.PreservePixelFormat, BitmapCacheOption.OnLoad);
            if (decoder.Frames.Count == 0) throw new PackageBuilderException("PNG icon contains no image frame.");
            source = decoder.Frames[0];
            source.Freeze();
        }
        catch (PackageBuilderException) { throw; }
        catch (Exception ex)
        {
            throw new PackageBuilderException($"Unable to decode PNG icon: {ex.Message}", ex);
        }

        if (source.PixelWidth is < 1 or > 16384 || source.PixelHeight is < 1 or > 16384)
            throw new PackageBuilderException("PNG icon dimensions must be between 1 and 16384 pixels.");

        var frames = new List<IconFrame>(Sizes.Length);
        for (var index = 0; index < Sizes.Length; index++)
        {
            var size = Sizes[index];
            frames.Add(new IconFrame(size, FirstResourceId + index, RenderPngFrame(source, size)));
        }
        return new IconResources(frames, BuildGroup(frames));
    }

    private static byte[] RenderPngFrame(BitmapSource source, int size)
    {
        var visual = new DrawingVisual();
        RenderOptions.SetBitmapScalingMode(visual, BitmapScalingMode.HighQuality);
        using (var context = visual.RenderOpen())
        {
            var scale = Math.Min((double)size / source.PixelWidth, (double)size / source.PixelHeight);
            var width = source.PixelWidth * scale;
            var height = source.PixelHeight * scale;
            context.DrawImage(source, new Rect((size - width) / 2, (size - height) / 2, width, height));
        }

        var rendered = new RenderTargetBitmap(size, size, 96, 96, PixelFormats.Pbgra32);
        rendered.Render(visual);
        rendered.Freeze();
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(rendered));
        using var output = new MemoryStream();
        encoder.Save(output);
        return output.ToArray();
    }

    private static byte[] BuildGroup(IReadOnlyList<IconFrame> frames)
    {
        using var stream = new MemoryStream();
        using var writer = new BinaryWriter(stream);
        writer.Write((ushort)0);
        writer.Write((ushort)1);
        writer.Write(checked((ushort)frames.Count));
        foreach (var frame in frames)
        {
            writer.Write((byte)(frame.Size == 256 ? 0 : frame.Size));
            writer.Write((byte)(frame.Size == 256 ? 0 : frame.Size));
            writer.Write((byte)0);
            writer.Write((byte)0);
            writer.Write((ushort)1);
            writer.Write((ushort)32);
            writer.Write(checked((uint)frame.Data.Length));
            writer.Write(checked((ushort)frame.ResourceId));
        }
        return stream.ToArray();
    }
}
