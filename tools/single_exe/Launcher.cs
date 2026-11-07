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
using Microsoft.Win32;

static class Program
{
    const string Build = "__BUILD__";
    const string Payload = "payload.zip";
    const string Exe = "Pulse+Local.exe";
    // the Evergreen WebView2 Runtime: its EdgeUpdate client id and Microsoft's link to its small online installer
    const string WebView2Client = @"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
    const string WebView2Download = "https://go.microsoft.com/fwlink/p/?LinkId=2124703";

    [STAThread]
    static int Main(string[] args)
    {
        string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PulsePlus");
        string app = Path.Combine(root, "app");
        string exe = Path.Combine(app, Exe);
        try
        {
            // started by an update from the old app, this process inherits its current folder, the app folder that is
            // replaced below: Windows does not delete a folder that a process stands in
            Environment.CurrentDirectory = Path.GetDirectoryName(Application.ExecutablePath);
            WaitFor(args);
            // without WebView2 the app cannot draw a window and closes silently: say so before unpacking anything
            if (!HasWebView2() && !RunWithoutWebView2()) return 2;
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

    // Microsoft's documented check: the runtime's version «pv» under its EdgeUpdate client, for all users (the 32-bit
    // view, WOW6432Node on 64-bit Windows; the 64-bit view as well) or for this user only
    static bool HasWebView2()
    {
        return HasVersion(RegistryHive.LocalMachine, RegistryView.Registry32)
            || HasVersion(RegistryHive.LocalMachine, RegistryView.Registry64)
            || HasVersion(RegistryHive.CurrentUser, RegistryView.Default);
    }

    static bool HasVersion(RegistryHive hive, RegistryView view)
    {
        try
        {
            using (RegistryKey root = RegistryKey.OpenBaseKey(hive, view))
            using (RegistryKey client = root.OpenSubKey(WebView2Client))
            {
                string version = client == null ? null : client.GetValue("pv") as string;
                return !string.IsNullOrEmpty(version) && version != "0.0.0.0";
            }
        }
        catch (Exception)
        {
            return false;
        }
    }

    // No WebView2 found: offer Microsoft's installer. True when the user still wants to start Pulse+ (the check may miss
    // an unusual install).
    static bool RunWithoutWebView2()
    {
        DialogResult answer = MessageBox.Show(
            "Для работы Pulse+ нужен Microsoft Edge WebView2 Runtime, а на этом компьютере он не найден.\n\n" +
            "Да — скачать установщик с сайта Microsoft (бесплатно). После установки запусти Pulse+ снова.\n" +
            "Нет — всё равно запустить Pulse+.\n" +
            "Отмена — выйти.",
            "Pulse+: нужен WebView2", MessageBoxButtons.YesNoCancel, MessageBoxIcon.Warning);
        if (answer == DialogResult.Yes)
        {
            try { Process.Start(new ProcessStartInfo(WebView2Download) { UseShellExecute = true }); }
            catch (Exception) { MessageBox.Show("Открой в браузере:\n" + WebView2Download, "Pulse+", MessageBoxButtons.OK, MessageBoxIcon.Information); }
            return false;
        }
        return answer == DialogResult.No;
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
