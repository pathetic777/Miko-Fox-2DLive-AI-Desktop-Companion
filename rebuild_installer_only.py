# -*- coding: utf-8 -*-
"""
Compiles the C# Single-File Windows GUI Setup Installer EXE (English Edition) with:
1. Smart writable default path (`D:\bilibili_animation_study\MikoFoxDesktopPet_EN` if present, else `%LOCALAPPDATA%\MikoFoxDesktopPet_EN`).
2. Clean `Path.GetFullPath` normalization.
3. Automatic UAC Administrator elevation (`Verb = "runas"`) if the user selects a write-protected drive root.
"""
import os
import shutil
import subprocess

ROOT_DIR = r"D:\bilibili_animation_study"
WORK_DIR = os.path.join(ROOT_DIR, "miko_fox_2dlive_en")
BUILD_WS = os.path.join(WORK_DIR, "release_build")
ASSETS_DIR = os.path.join(WORK_DIR, "miko_pet_assets")

CSC_EXE = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
ico_path = os.path.join(ASSETS_DIR, "miko_pet.ico")
payload_zip = os.path.join(BUILD_WS, "payload.zip")
setup_work = os.path.join(WORK_DIR, "Hidzuki_Miko_Fox_2DLive_Desktop_Companion_EN_Setup.exe")
setup_root = os.path.join(ROOT_DIR, "Hidzuki_Miko_Fox_2DLive_Desktop_Companion_EN_Setup.exe")
cs_installer_path = os.path.join(BUILD_WS, "MikoInstallerMain_EN.cs")

cs_code = r"""using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Diagnostics;
using System.Drawing;
using System.Security.Principal;
using System.Windows.Forms;

namespace MikoFoxInstallerEN
{
    public class SetupForm : Form
    {
        private Label lblTitle;
        private Label lblSub;
        private Label lblDir;
        private TextBox txtPath;
        private Button btnBrowse;
        private CheckBox chkDesktop;
        private CheckBox chkAutostart;
        private CheckBox chkLaunchNow;
        private Button btnInstall;
        private ProgressBar progressBar;
        private Label lblStatus;
        private string autoInstallTarget = null;

        public SetupForm(string[] args)
        {
            if (args != null && args.Length >= 2 && args[0] == "--elevated-install") {
                autoInstallTarget = args[1];
            }

            this.Text = "Shrine Maiden & Little White Fox (Hidzuki) — Setup Wizard";
            this.Size = new Size(560, 405);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.BackColor = Color.FromArgb(24, 18, 28);
            this.ForeColor = Color.FromArgb(255, 241, 242);
            this.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);

            try {
                this.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            } catch {}

            lblTitle = new Label();
            lblTitle.Text = "⛩️ Shrine Maiden & Little White Fox (Hidzuki)";
            lblTitle.Font = new Font("Segoe UI", 13.0f, FontStyle.Bold);
            lblTitle.ForeColor = Color.FromArgb(253, 164, 175);
            lblTitle.Location = new Point(24, 18);
            lblTitle.Size = new Size(500, 30);
            this.Controls.Add(lblTitle);

            lblSub = new Label();
            lblSub.Text = "2D Live Physics & AI Desktop Companion — English Edition Setup";
            lblSub.Font = new Font("Segoe UI", 9.0f, FontStyle.Regular);
            lblSub.ForeColor = Color.FromArgb(196, 175, 202);
            lblSub.Location = new Point(26, 52);
            lblSub.Size = new Size(505, 22);
            this.Controls.Add(lblSub);

            lblDir = new Label();
            lblDir.Text = "Installation Folder:";
            lblDir.Location = new Point(26, 86);
            lblDir.Size = new Size(490, 22);
            this.Controls.Add(lblDir);

            string defaultDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "MikoFoxDesktopPet_EN"
            );
            if (Directory.Exists(@"D:\bilibili_animation_study")) {
                defaultDir = @"D:\bilibili_animation_study\MikoFoxDesktopPet_EN";
            }
            if (!string.IsNullOrEmpty(autoInstallTarget)) {
                defaultDir = autoInstallTarget;
            }

            txtPath = new TextBox();
            txtPath.Text = defaultDir;
            txtPath.Location = new Point(26, 112);
            txtPath.Size = new Size(406, 28);
            txtPath.BackColor = Color.FromArgb(38, 28, 44);
            txtPath.ForeColor = Color.White;
            txtPath.BorderStyle = BorderStyle.FixedSingle;
            this.Controls.Add(txtPath);

            btnBrowse = new Button();
            btnBrowse.Text = "Browse...";
            btnBrowse.Location = new Point(440, 110);
            btnBrowse.Size = new Size(84, 28);
            btnBrowse.FlatStyle = FlatStyle.Flat;
            btnBrowse.BackColor = Color.FromArgb(62, 42, 68);
            btnBrowse.ForeColor = Color.White;
            btnBrowse.Click += (s, e) => {
                using (FolderBrowserDialog fbd = new FolderBrowserDialog()) {
                    fbd.Description = "Select the installation folder for Hidzuki Desktop Companion";
                    if (fbd.ShowDialog() == DialogResult.OK) {
                        string sel = fbd.SelectedPath.Trim();
                        if (!sel.EndsWith("MikoFoxDesktopPet_EN", StringComparison.OrdinalIgnoreCase)) {
                            sel = Path.Combine(sel, "MikoFoxDesktopPet_EN");
                        }
                        try { sel = Path.GetFullPath(sel); } catch {}
                        txtPath.Text = sel;
                    }
                }
            };
            this.Controls.Add(btnBrowse);

            chkDesktop = new CheckBox();
            chkDesktop.Text = "Create a Desktop shortcut";
            chkDesktop.Checked = true;
            chkDesktop.Location = new Point(28, 154);
            chkDesktop.Size = new Size(490, 24);
            this.Controls.Add(chkDesktop);

            chkAutostart = new CheckBox();
            chkAutostart.Text = "Run automatically at Windows Startup (bottom-right corner)";
            chkAutostart.Checked = true;
            chkAutostart.Location = new Point(28, 184);
            chkAutostart.Size = new Size(490, 24);
            this.Controls.Add(chkAutostart);

            chkLaunchNow = new CheckBox();
            chkLaunchNow.Text = "Launch Hidzuki immediately after installation";
            chkLaunchNow.Checked = true;
            chkLaunchNow.Location = new Point(28, 214);
            chkLaunchNow.Size = new Size(490, 24);
            this.Controls.Add(chkLaunchNow);

            progressBar = new ProgressBar();
            progressBar.Location = new Point(26, 250);
            progressBar.Size = new Size(498, 18);
            progressBar.Style = ProgressBarStyle.Continuous;
            this.Controls.Add(progressBar);

            lblStatus = new Label();
            lblStatus.Text = "Click the button below to begin installation.";
            lblStatus.Font = new Font("Segoe UI", 8.5f, FontStyle.Regular);
            lblStatus.ForeColor = Color.FromArgb(167, 243, 208);
            lblStatus.Location = new Point(26, 274);
            lblStatus.Size = new Size(498, 22);
            this.Controls.Add(lblStatus);

            btnInstall = new Button();
            btnInstall.Text = "⛩️ Install & Launch Hidzuki";
            btnInstall.Font = new Font("Segoe UI", 11f, FontStyle.Bold);
            btnInstall.Location = new Point(26, 304);
            btnInstall.Size = new Size(498, 42);
            btnInstall.FlatStyle = FlatStyle.Flat;
            btnInstall.BackColor = Color.FromArgb(225, 29, 72);
            btnInstall.ForeColor = Color.White;
            btnInstall.Cursor = Cursors.Hand;
            btnInstall.Click += BtnInstall_Click;
            this.Controls.Add(btnInstall);

            this.Shown += (s, e) => {
                if (!string.IsNullOrEmpty(autoInstallTarget)) {
                    BtnInstall_Click(this, EventArgs.Empty);
                }
            };
        }

        private bool IsRunningAsAdmin()
        {
            try {
                WindowsIdentity id = WindowsIdentity.GetCurrent();
                WindowsPrincipal principal = new WindowsPrincipal(id);
                return principal.IsInRole(WindowsBuiltInRole.Administrator);
            } catch {
                return false;
            }
        }

        private void BtnInstall_Click(object sender, EventArgs e)
        {
            string targetDir = txtPath.Text.Trim();
            if (string.IsNullOrEmpty(targetDir)) {
                MessageBox.Show("Please specify an installation folder.", "Notice", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            try { targetDir = Path.GetFullPath(targetDir); } catch {}
            txtPath.Text = targetDir;

            try {
                if (!Directory.Exists(targetDir)) {
                    Directory.CreateDirectory(targetDir);
                }
                string probeFile = Path.Combine(targetDir, "_write_test.tmp");
                File.WriteAllText(probeFile, "ok");
                File.Delete(probeFile);
            }
            catch (UnauthorizedAccessException) {
                if (!IsRunningAsAdmin()) {
                    try {
                        ProcessStartInfo elev = new ProcessStartInfo();
                        elev.FileName = Application.ExecutablePath;
                        elev.Arguments = "--elevated-install \"" + targetDir + "\"";
                        elev.Verb = "runas";
                        elev.UseShellExecute = true;
                        Process.Start(elev);
                        this.Close();
                        return;
                    } catch {
                        targetDir = Directory.Exists(@"D:\bilibili_animation_study")
                            ? @"D:\bilibili_animation_study\MikoFoxDesktopPet_EN"
                            : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MikoFoxDesktopPet_EN");
                        txtPath.Text = targetDir;
                    }
                }
            }

            btnInstall.Enabled = false;
            progressBar.Value = 10;
            lblStatus.Text = "Preparing installation directory...";
            Application.DoEvents();

            try {
                foreach (var proc in Process.GetProcessesByName("MikoFoxPet")) {
                    try { proc.Kill(); proc.WaitForExit(1500); } catch {}
                }

                if (!Directory.Exists(targetDir)) {
                    Directory.CreateDirectory(targetDir);
                }

                progressBar.Value = 30;
                lblStatus.Text = "Extracting files...";
                Application.DoEvents();

                string tempZip = Path.Combine(Path.GetTempPath(), "miko_pet_en_payload_" + Guid.NewGuid().ToString("N") + ".zip");
                using (Stream resStream = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")) {
                    if (resStream == null) {
                        throw new Exception("Embedded payload.zip resource not found!");
                    }
                    using (FileStream fs = new FileStream(tempZip, FileMode.Create, FileAccess.Write)) {
                        resStream.CopyTo(fs);
                    }
                }

                progressBar.Value = 65;
                Application.DoEvents();

                using (ZipArchive archive = ZipFile.OpenRead(tempZip)) {
                    int total = archive.Entries.Count;
                    int idx = 0;
                    foreach (ZipArchiveEntry entry in archive.Entries) {
                        idx++;
                        string fullPath = Path.Combine(targetDir, entry.FullName);
                        string dirName = Path.GetDirectoryName(fullPath);
                        if (!string.IsNullOrEmpty(dirName) && !Directory.Exists(dirName)) {
                            Directory.CreateDirectory(dirName);
                        }
                        if (!string.IsNullOrEmpty(entry.Name)) {
                            entry.ExtractToFile(fullPath, true);
                        }
                        if (idx % 20 == 0 && total > 0) {
                            progressBar.Value = 65 + (int)(25.0 * idx / total);
                            Application.DoEvents();
                        }
                    }
                }

                try { File.Delete(tempZip); } catch {}

                string exePath = Path.Combine(targetDir, "MikoFoxPet.exe");
                string icoPath = Path.Combine(targetDir, "miko_pet.ico");

                if (chkDesktop.Checked) {
                    string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                    string lnkPath = Path.Combine(desktopDir, "Hidzuki — Shrine Maiden & Fox.lnk");
                    CreateShortcut(lnkPath, exePath, targetDir, icoPath, "Launch Hidzuki — Shrine Maiden & Little White Fox Desktop Companion");
                }

                if (chkAutostart.Checked) {
                    string startupDir = Environment.GetFolderPath(Environment.SpecialFolder.Startup);
                    string vbsPath = Path.Combine(startupDir, "MikoFoxDesktopPet_AutoStart.vbs");
                    string vbsContent = "Set WshShell = CreateObject(\"WScript.Shell\")\r\n"
                        + "WshShell.CurrentDirectory = \"" + targetDir + "\"\r\n"
                        + "WshShell.Run \"\"\"" + exePath + "\"\"\", 0, False\r\n";
                    File.WriteAllText(vbsPath, vbsContent, System.Text.Encoding.Default);
                }

                progressBar.Value = 100;
                lblStatus.Text = "✅ Installation complete!";
                Application.DoEvents();

                if (chkLaunchNow.Checked && File.Exists(exePath)) {
                    ProcessStartInfo psi = new ProcessStartInfo();
                    psi.FileName = exePath;
                    psi.WorkingDirectory = targetDir;
                    psi.UseShellExecute = true;
                    Process.Start(psi);
                }

                string msg = "🎉 Installation complete! Hidzuki & Little White Fox are now in the bottom-right corner of your desktop!\n\n"
                    + "• Drag & drop unwanted files onto her bamboo broom -> Sweeps into Recycle Bin\n"
                    + "• Click the Little White Fox's tail -> Launches your bound app\n"
                    + "• Click her chest 5 times in a row -> Divine Slap & 20s Shutdown Easter Egg\n"
                    + "• Click '💬 Talk' at her feet to chat, or Right-Click her to open the Web Control Panel!";

                MessageBox.Show(msg, "Setup Complete", MessageBoxButtons.OK, MessageBoxIcon.Information);
                this.Close();
            }
            catch (Exception ex) {
                btnInstall.Enabled = true;
                lblStatus.Text = "❌ Error: " + ex.Message;
                MessageBox.Show(ex.ToString(), "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void CreateShortcut(string lnkPath, string targetExe, string workDir, string iconPath, string desc)
        {
            try {
                Type shellType = Type.GetTypeFromProgID("WScript.Shell");
                dynamic shell = Activator.CreateInstance(shellType);
                dynamic shortcut = shell.CreateShortcut(lnkPath);
                shortcut.TargetPath = targetExe;
                shortcut.WorkingDirectory = workDir;
                if (File.Exists(iconPath)) {
                    shortcut.IconLocation = iconPath;
                }
                shortcut.Description = desc;
                shortcut.Save();
            } catch {}
        }

        [STAThread]
        public static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new SetupForm(args));
        }
    }
}
"""

with open(cs_installer_path, "w", encoding="utf-8-sig") as f:
    f.write(cs_code)

csc_cmd = [
    CSC_EXE,
    "/target:winexe",
    "/optimize+",
    f"/out:{setup_root}",
    f"/win32icon:{ico_path}",
    f"/resource:{payload_zip},payload.zip",
    "/r:System.dll",
    "/r:System.Drawing.dll",
    "/r:System.Windows.Forms.dll",
    "/r:System.IO.Compression.dll",
    "/r:System.IO.Compression.FileSystem.dll",
    "/r:Microsoft.CSharp.dll",
    cs_installer_path,
]
subprocess.run(csc_cmd, cwd=BUILD_WS, check=True)
shutil.copy2(setup_root, setup_work)
print("Compiled English Setup.exe:", setup_root)
