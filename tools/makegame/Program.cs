namespace DosBoxPureStandalone.MakeGame;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            var commandLine = CommandLine.Parse(args);
            if (commandLine.ShowHelp)
            {
                CommandLine.PrintHelp();
                return 0;
            }

            var package = PackageSpecification.Load(commandLine);
            var result = PackageBuilder.Build(package, commandLine.Overwrite, commandLine.ValidateOnly);

            Console.WriteLine(commandLine.ValidateOnly
                ? "Package inputs are valid. No executable was generated."
                : $"Created package: {result.OutputPath}");
            Console.WriteLine($"Package ID: {result.PackageId}");
            Console.WriteLine($"Startup: {result.Startup}");
            Console.WriteLine($"Archive: {result.ArchiveSize:N0} bytes ({result.ArchiveIdentity})");
            Console.WriteLine($"Archive storage: {(result.ArchiveStorage == ArchiveStorageMode.Resource ? "PE resource" : "appended mapped payload")}");
            Console.WriteLine($"Default configuration: {result.DefaultConfigCount} value(s)");
            Console.WriteLine($"Custom icon: {(result.HasCustomIcon ? "yes" : "no")}");
            return 0;
        }
        catch (PackageBuilderException ex)
        {
            Console.Error.WriteLine($"makegame: {ex.Message}");
            return 2;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"makegame: unexpected failure: {ex.Message}");
            return 3;
        }
    }
}

internal sealed class PackageBuilderException : Exception
{
    public PackageBuilderException(string message) : base(message) { }
    public PackageBuilderException(string message, Exception innerException) : base(message, innerException) { }
}
