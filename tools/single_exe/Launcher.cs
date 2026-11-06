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
    static int Main(string[] args)
    {
        string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PulsePlus");
        string app = Path.Combine(root, "app");
        string exe = Path.Combine(app, Exe);
        try
        {
            WaitFor(args);
            bool current = File.Exists(exe) && File.Exists(Path.Combine(app, "build.txt"))
                && File.ReadAllText(Path.Combine(app, "build.txt")).Trim() == Build;
            if (!current) Unpack(root, app);
            ProcessStartInfo start = new ProcessStartInfo(exe) { WorkingDirectory = app, UseShellExecute = false };
            // the app updates itself by replacing this file: it needs to know where it is
            start.EnvironmentVariables["PULSE_LAUNCHER"] = Application.ExecutablePath;
            Process.Start(start);
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
        DeleteDir(app); // an older build; fails if that copy is still running
        Directory.Move(files, app);
        Directory.Delete(work, true);
    }

    // «--wait <pid>»: an update started this file from the old copy of the app; that copy must be gone before its
    // folder is replaced (at most 30 s)
    static void WaitFor(string[] args)
    {
        int i = Array.IndexOf(args, "--wait");
        int pid;
        if (i < 0 || i + 1 >= args.Length || !int.TryParse(args[i + 1], out pid)) return;
        try
        {
            using (Process old = Process.GetProcessById(pid)) old.WaitForExit(30000);
        }
        catch (ArgumentException) { } // already gone
    }

    // the folder of a program that has just closed may stay locked for a moment: a few tries, then the error
    static void DeleteDir(string dir)
    {
        for (int attempt = 0; ; attempt++)
        {
            try
            {
                if (Directory.Exists(dir)) Directory.Delete(dir, true);
                return;
            }
            catch (Exception)
            {
                if (attempt >= 20) throw;
                System.Threading.Thread.Sleep(500);
            }
        }
    }
}
