using System.ComponentModel;
using System.Runtime.InteropServices;

namespace DosBoxPureStandalone.MakeGame;

internal static partial class NativeResources
{
    public static readonly IntPtr RtIcon = (IntPtr)3;
    public static readonly IntPtr RtRcData = (IntPtr)10;
    public static readonly IntPtr RtGroupIcon = (IntPtr)14;
    public static readonly IntPtr RtVersion = (IntPtr)16;

    internal const uint LoadLibraryAsDataFile = 0x00000002;
    internal const uint LoadLibraryAsImageResource = 0x00000020;

    [LibraryImport("kernel32.dll", EntryPoint = "BeginUpdateResourceW", SetLastError = true, StringMarshalling = StringMarshalling.Utf16)]
    internal static partial IntPtr BeginUpdateResource(string fileName, [MarshalAs(UnmanagedType.Bool)] bool deleteExistingResources);

    [LibraryImport("kernel32.dll", EntryPoint = "UpdateResourceW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool UpdateNumericResource(IntPtr update, IntPtr type, IntPtr name, ushort language, byte[] data, uint size);

    [LibraryImport("kernel32.dll", EntryPoint = "UpdateResourceW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool DeleteNumericResource(IntPtr update, IntPtr type, IntPtr name, ushort language, IntPtr data, uint size);

    [LibraryImport("kernel32.dll", EntryPoint = "UpdateResourceW", SetLastError = true, StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool UpdateNamedResource(IntPtr update, IntPtr type, string name, ushort language, byte[] data, uint size);

    [LibraryImport("kernel32.dll", EntryPoint = "EndUpdateResourceW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool EndUpdateResource(IntPtr update, [MarshalAs(UnmanagedType.Bool)] bool discard);

    [LibraryImport("kernel32.dll", EntryPoint = "LoadLibraryExW", SetLastError = true, StringMarshalling = StringMarshalling.Utf16)]
    internal static partial IntPtr LoadLibraryEx(string fileName, IntPtr file, uint flags);

    [LibraryImport("kernel32.dll", EntryPoint = "FreeLibrary", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool FreeLibrary(IntPtr module);

    [LibraryImport("kernel32.dll", EntryPoint = "FindResourceW", SetLastError = true)]
    internal static partial IntPtr FindNumericResource(IntPtr module, IntPtr name, IntPtr type);

    [LibraryImport("kernel32.dll", EntryPoint = "FindResourceW", SetLastError = true, StringMarshalling = StringMarshalling.Utf16)]
    internal static partial IntPtr FindNamedResource(IntPtr module, string name, IntPtr type);

    [LibraryImport("kernel32.dll", EntryPoint = "SizeofResource", SetLastError = true)]
    internal static partial uint SizeofResource(IntPtr module, IntPtr resourceInfo);

    [LibraryImport("kernel32.dll", EntryPoint = "LoadResource", SetLastError = true)]
    internal static partial IntPtr LoadResource(IntPtr module, IntPtr resourceInfo);

    [LibraryImport("kernel32.dll", EntryPoint = "LockResource")]
    internal static partial IntPtr LockResource(IntPtr resource);

    [LibraryImport("shell32.dll", EntryPoint = "ExtractIconExW", SetLastError = true, StringMarshalling = StringMarshalling.Utf16)]
    internal static partial uint ExtractIconEx(string fileName, int iconIndex, IntPtr[] largeIcons, IntPtr[] smallIcons, uint iconCount);

    [LibraryImport("user32.dll", EntryPoint = "DestroyIcon", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool DestroyIcon(IntPtr icon);

    public static bool CanExtractApplicationIcon(string fileName)
    {
        var large = new IntPtr[1];
        var small = new IntPtr[1];
        try
        {
            return ExtractIconEx(fileName, 0, large, small, 1) != 0 && (large[0] != IntPtr.Zero || small[0] != IntPtr.Zero);
        }
        finally
        {
            if (large[0] != IntPtr.Zero) DestroyIcon(large[0]);
            if (small[0] != IntPtr.Zero) DestroyIcon(small[0]);
        }
    }

    internal static PackageBuilderException Win32Failure(string operation) =>
        new($"{operation} failed with Windows error {Marshal.GetLastWin32Error()}: {new Win32Exception(Marshal.GetLastWin32Error()).Message}");
}

internal sealed class ResourceUpdater : IDisposable
{
    private IntPtr handle;

    public ResourceUpdater(string fileName)
    {
        handle = NativeResources.BeginUpdateResource(fileName, false);
        if (handle == IntPtr.Zero) throw NativeResources.Win32Failure("BeginUpdateResource");
    }

    public void SetNumeric(IntPtr type, int name, ushort language, byte[] data)
    {
        if (handle == IntPtr.Zero) throw new ObjectDisposedException(nameof(ResourceUpdater));
        if (!NativeResources.UpdateNumericResource(handle, type, (IntPtr)name, language, data, checked((uint)data.Length)))
            throw NativeResources.Win32Failure($"UpdateResource({name})");
    }

    public void SetNamed(IntPtr type, string name, ushort language, byte[] data)
    {
        if (handle == IntPtr.Zero) throw new ObjectDisposedException(nameof(ResourceUpdater));
        if (!NativeResources.UpdateNamedResource(handle, type, name, language, data, checked((uint)data.Length)))
            throw NativeResources.Win32Failure($"UpdateResource({name})");
    }

    public void DeleteNumeric(IntPtr type, int name, ushort language)
    {
        if (handle == IntPtr.Zero) throw new ObjectDisposedException(nameof(ResourceUpdater));
        if (!NativeResources.DeleteNumericResource(handle, type, (IntPtr)name, language, IntPtr.Zero, 0))
            throw NativeResources.Win32Failure($"UpdateResource(delete {name})");
    }

    public void Commit()
    {
        if (handle == IntPtr.Zero) throw new ObjectDisposedException(nameof(ResourceUpdater));
        var current = handle;
        handle = IntPtr.Zero;
        if (!NativeResources.EndUpdateResource(current, false)) throw NativeResources.Win32Failure("EndUpdateResource");
    }

    public void Dispose()
    {
        if (handle == IntPtr.Zero) return;
        var current = handle;
        handle = IntPtr.Zero;
        NativeResources.EndUpdateResource(current, true);
    }
}

internal sealed class ResourceModule : IDisposable
{
    private IntPtr handle;

    private ResourceModule(IntPtr handle) => this.handle = handle;

    public static ResourceModule Load(string fileName)
    {
        var handle = NativeResources.LoadLibraryEx(fileName, IntPtr.Zero,
            NativeResources.LoadLibraryAsDataFile | NativeResources.LoadLibraryAsImageResource);
        if (handle == IntPtr.Zero) throw NativeResources.Win32Failure("LoadLibraryEx");
        return new ResourceModule(handle);
    }

    public bool HasNumeric(IntPtr type, int name) => NativeResources.FindNumericResource(handle, (IntPtr)name, type) != IntPtr.Zero;
    public bool HasNamed(IntPtr type, string name) => NativeResources.FindNamedResource(handle, name, type) != IntPtr.Zero;

    public long GetNumericSize(IntPtr type, int name)
    {
        var info = NativeResources.FindNumericResource(handle, (IntPtr)name, type);
        if (info == IntPtr.Zero) return -1;
        return NativeResources.SizeofResource(handle, info);
    }

    public byte[] ReadNumeric(IntPtr type, int name)
    {
        var info = NativeResources.FindNumericResource(handle, (IntPtr)name, type);
        if (info == IntPtr.Zero) throw new PackageBuilderException($"Resource {name} was not found.");
        return Read(info);
    }

    public byte[] ReadNamed(IntPtr type, string name)
    {
        var info = NativeResources.FindNamedResource(handle, name, type);
        if (info == IntPtr.Zero) throw new PackageBuilderException($"Resource '{name}' was not found.");
        return Read(info);
    }

    private byte[] Read(IntPtr info)
    {
        var size = checked((int)NativeResources.SizeofResource(handle, info));
        var resource = NativeResources.LoadResource(handle, info);
        var data = resource == IntPtr.Zero ? IntPtr.Zero : NativeResources.LockResource(resource);
        if (size <= 0 || data == IntPtr.Zero) throw NativeResources.Win32Failure("LoadResource");
        var result = new byte[size];
        Marshal.Copy(data, result, 0, size);
        return result;
    }

    public void Dispose()
    {
        if (handle == IntPtr.Zero) return;
        NativeResources.FreeLibrary(handle);
        handle = IntPtr.Zero;
    }
}
