// Pulse+ as one file: this program carries the whole app (Pulse+Local.exe and data, as a zip resource). On start it
// unpacks them once into %LOCALAPPDATA%\PulsePlus\app and then only starts the app from there. The unpacked copy is
// replaced when this file's build id differs (a new build), so an update is one new file.
// Built by tools/single_exe/build_single_exe.ps1, which puts the build id in place of __BUILD__.
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

static class Program
{
    const string Build = "__BUILD__";
    const string Payload = "payload.zip";
    const string Exe = "Pulse+Local.exe";

    [STAThread]
    static int Main()
    {
        string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PulsePlus");
        string app = Path.Combine(root, "app");
        string exe = Path.Combine(app, Exe);
        try
        {
            bool current = File.Exists(exe) && File.Exists(Path.Combine(app, "build.txt"))
                && File.ReadAllText(Path.Combine(app, "build.txt")).Trim() == Build;
            if (!current) Unpack(root, app);
            Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = app, UseShellExecute = false });
            return 0;
        }
        catch (Exception e)
        {
            MessageBox.Show("Не удалось запустить Pulse+:\n" + e.Message, "Pulse+", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    // Unpacks into a fresh folder first and moves it into place: a broken unpack never leaves a half app behind.
    static void Unpack(string root, string app)
    {
        Directory.CreateDirectory(root);
        string work = Path.Combine(root, "unpack-" + Guid.NewGuid().ToString("N"));
        string zip = Path.Combine(work, Payload);
        string files = Path.Combine(work, "files");
        Directory.CreateDirectory(work);
        using (Stream src = Assembly.GetExecutingAssembly().GetManifestResourceStream(Payload))
        using (Stream dst = File.Create(zip))
        {
            src.CopyTo(dst);
        }
        ZipFile.ExtractToDirectory(zip, files);
        File.Delete(zip);
        File.WriteAllText(Path.Combine(files, "build.txt"), Build);
        if (Directory.Exists(app)) Directory.Delete(app, true); // an older build; fails if that copy is still running
        Directory.Move(files, app);
        Directory.Delete(work, true);
    }
}
