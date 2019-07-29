import os
import platform
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections import namedtuple
from configparser import ConfigParser
from pathlib import Path

from bcml import data, install, merge, pack, rstable, texts, util
from bcml.Ui_about import Ui_AboutDialog
from bcml.Ui_install import Ui_InstallDialog
from bcml.Ui_main import Ui_MainWindow
from bcml.Ui_progress import Ui_dlgProgress
from bcml.Ui_settings import Ui_SettingsDialog
from bcml.util import BcmlMod
from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtCore import Qt


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)

        self.btnSettings = QtWidgets.QToolButton(self.statusBar())
        settings_icon = QtGui.QIcon()
        settings_icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'settings.png')))
        self.btnSettings.setIcon(settings_icon)
        self.btnSettings.setToolTip('Settings')
        self.btnAbout = QtWidgets.QToolButton(self.statusBar())
        about_icon = QtGui.QIcon()
        about_icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'about.png')))
        self.btnAbout.setIcon(about_icon)
        self.btnAbout.setToolTip('About')
        self.statusBar().addPermanentWidget(
            QtWidgets.QLabel('Version ' + util.get_bcml_version()))
        self.statusBar().addPermanentWidget(self.btnSettings)
        self.statusBar().addPermanentWidget(self.btnAbout)

        logo_path = str(util.get_exec_dir() / 'data' / 'logo-smaller.png')
        self._logo = QtGui.QPixmap(logo_path)
        self.lblImage.setPixmap(self._logo)
        self.lblImage.setFixedSize(256, 104)

        # Bind events
        self.listWidget.setDragDropMode(
            QtWidgets.QAbstractItemView.InternalMove)
        self.listWidget.itemSelectionChanged.connect(self.SelectItem)
        self.listWidget.installEventFilter(self)
        self.btnInstall.clicked.connect(self.InstallClicked)
        self.btnRemerge.clicked.connect(self.RemergeClicked)
        self.btnChange.clicked.connect(self.ChangeClicked)
        self.btnUninstall.clicked.connect(self.UninstallClicked)
        self.btnExplore.clicked.connect(self.ExploreClicked)
        self.btnSettings.clicked.connect(self.SettingsClicked)
        self.btnAbout.clicked.connect(self.AboutClicked)

        self.SetupChecks()
        self.LoadMods()

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.ChildRemoved and not self.btnChange.isEnabled():
            self.btnChange.setEnabled(True)
        return False

    def SetupChecks(self):
        try:
            util.get_cemu_dir()
        except FileNotFoundError:
            QtWidgets.QMessageBox.information(
                self, 'First Time', 'It looks like this may be your first time running BCML. Please select the directory where Cemu is installed.')
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                self, 'Select Cemu Directory')
            if folder:
                util.set_cemu_dir(Path(folder))
            else:
                sys.exit(0)
        try:
            util.get_game_dir()
        except FileNotFoundError:
            QtWidgets.QMessageBox.information(
                self, 'First Time', 'BCML needs to know the location of your game dump. Please select the "content" directory in your dumped copy of Breath of the Wild.')
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                self, 'Select Game Dump Directory')
            if folder:
                util.set_game_dir(Path(folder))
            else:
                sys.exit(0)
        
        ver = platform.python_version_tuple()
        if int(ver[0]) < 3 or (int(ver[0]) >= 3 and int(ver[1]) < 7):
            QtWidgets.QMessageBox.warning(
                self, 'Error', f'BCML requires Python 3.7 or higher, but your Python version is {ver[0]}.{ver[1]}')
            sys.exit(0)

        is_64bits = sys.maxsize > 2**32
        if not is_64bits:
            QtWidgets.QMessageBox.warning(
                self, 'Error', 'BCML requires 64 bit Python, but it looks like you\'re running 32 bit.')
            sys.exit(0)

    def LoadMods(self):
        self.statusBar().showMessage('Loading mods...')
        self.listWidget.clear()
        mods = sorted(util.get_installed_mods(), key=lambda mod: mod.priority)
        for mod in mods:
            mod_item = QtWidgets.QListWidgetItem()
            mod_item.setText(mod.name)
            mod_item.setData(QtCore.Qt.UserRole, mod)
            self.listWidget.addItem(mod_item)
        self._mod_infos = {}
        self.lblModInfo.setText('No mod selected')
        self.lblImage.setPixmap(self._logo)
        self.lblImage.setFixedSize(256, 104)
        self.statusBar().showMessage(f'{len(mods)} mods installed')

    def SelectItem(self):
        if len(self.listWidget.selectedItems()) == 0:
            return
        mod = self.listWidget.selectedItems()[0].data(QtCore.Qt.UserRole)

        if not mod in self._mod_infos:
            rules = ConfigParser()
            rules.read(str(mod.path / 'rules.txt'))
            font_metrics = QtGui.QFontMetrics(self.lblModInfo.font())
            path = str(mod.path)
            while font_metrics.width(f'Path: {path}.....') >= self.lblModInfo.width():
                path = path[:-1]
            changes = []
            if len(rstable.get_mod_rstb_values(mod)) > 0:
                changes.append('RSTB')
            if util.is_pack_mod(mod):
                changes.append('packs')
            if len(texts.get_modded_languages(mod.path)) > 0:
                changes.append('texts')
                if 'RSTB' not in changes:
                    changes.insert(0, 'RSTB')
            if util.is_gamedata_mod(mod):
                changes.append('game data')
            if util.is_savedata_mod(mod):
                changes.append('save data')
            if util.is_actorinfo_mod(mod):
                changes.append('actor info')
            if util.is_deepmerge_mod(mod):
                changes.append('deep merge')
            mod_info = [
                f'<b>Name</b>: {mod.name}',
                f'<b>Priority:</b> {mod.priority}',
                f'<b>Path:</b> {path}...',
                '<b>Description:</b> {}'.format(
                    str(rules["Definition"]["description"]).strip(' "\'')),
                f'<b>Changes:</b> {", ".join(changes)}'
            ]
            if 'url' in rules['Definition']:
                url = str(rules['Definition']['url'])
                link = url
                while font_metrics.width(f'Link: {link}.....') >= self.lblModInfo.width():
                    link = link[:-1]
                mod_info.insert(3, f'<b>Link:</b> <a href="{url}">{link}</a>')
            if 'image' in rules['Definition']:
                try:
                    image_path = str(rules['Definition']['image'])
                    if image_path.startswith('http'):
                        response = urllib.request.urlopen(image_path)
                        data = response.read()
                        preview = QtGui.QPixmap()
                        preview.loadFromData(data)
                    else:
                        preview = QtGui.QPixmap(
                            str(mod.path / str(rules['Definition']['image'])))
                except (FileNotFoundError, urllib.error.HTTPError):
                    preview = self._logo
            else:
                preview = self._logo
            self._mod_infos[mod] = (mod_info, preview)
        else:
            mod_info, preview = self._mod_infos[mod]

        self.lblModInfo.setText('<br><br>'.join(mod_info))
        self.lblImage.setFixedSize(
            256, 256 // (preview.width() / preview.height()))
        self.lblImage.setPixmap(preview)
        self.lblModInfo.setWordWrap(True)

        if not self.btnUninstall.isEnabled():
            self.btnUninstall.setEnabled(True)
        if not self.btnExplore.isEnabled():
            self.btnExplore.setEnabled(True)

    def PerformOperation(self, func, *args):
        self.btnInstall.setEnabled(False)
        self.btnRemerge.setEnabled(False)
        self.btnUninstall.setEnabled(False)
        self.btnExplore.setEnabled(False)
        t = ProgressThread(self, func, *args)
        t.start()
        t.signal.sig.connect(self.OperationFinished)

    def OperationFinished(self):
        self.btnInstall.setEnabled(True)
        self.btnRemerge.setEnabled(True)
        self.LoadMods()
        QtWidgets.QMessageBox.information(
            self, 'Complete', 'Operation finished!')

    # Button handlers

    def InstallClicked(self):
        dialog = InstallDialog(self)
        result = dialog.GetResult()
        if result:
            if result.path.exists():
                self.PerformOperation(install.install_mod,
                                      result.path,
                                      False,
                                      result.no_packs,
                                      result.no_texts,
                                      result.no_gamedata,
                                      result.no_savedata,
                                      result.no_actorinfo,
                                      result.leave,
                                      result.shrink,
                                      result.wait_merge,
                                      result.deep_merge
                                      )
            else:
                QtWidgets.QMessageBox.warning(
                    self, 'Error', f'The file {str(result.path)} does not exist.')

    def RemergeClicked(self):
        self.PerformOperation(install.refresh_merges, ())

    def ChangeClicked(self):
        def resort_mods(self):
            fix_packs = False
            fix_gamedata = False
            fix_savedata = False
            fix_actorinfo = False
            fix_deepmerge = False
            fix_texts = []
            mods_to_change = []
            for i in range(self.listWidget.count()):
                mod = self.listWidget.item(i).data(QtCore.Qt.UserRole)
                if mod.priority != i + 100:
                    fix_packs = fix_packs or util.is_pack_mod(mod)
                    fix_gamedata = fix_gamedata or util.is_gamedata_mod(mod)
                    fix_savedata = fix_savedata or util.is_savedata_mod(mod)
                    fix_actorinfo = fix_actorinfo or util.is_actorinfo_mod(mod)
                    fix_deepmerge = fix_deepmerge or util.is_deepmerge_mod(mod)
                    for lang in texts.get_modded_languages(mod.path):
                        if lang not in fix_texts:
                            fix_texts.append(lang)
                    mods_to_change.append((mod, i + 100))
            for mod in mods_to_change:
                new_path = util.get_modpack_dir(
                ) / util.get_mod_id(mod[0].name, mod[1])
                shutil.move(str(mod[0].path), str(new_path))
                rules = ConfigParser()
                rules.read(str(new_path / 'rules.txt'))
                rules['Definition']['fsPriority'] = str(mod[1])
                with (new_path / 'rules.txt').open('w') as rf:
                    rules.write(rf)
            rstable.generate_master_rstb()
            if fix_packs:
                pack.merge_installed_packs(
                    no_injection=not (fix_gamedata or fix_savedata))
            if fix_gamedata:
                data.merge_gamedata()
            if fix_savedata:
                data.merge_savedata()
            if fix_actorinfo:
                data.merge_actorinfo()
            if fix_deepmerge:
                merge.deep_merge()
            for lang in fix_texts:
                texts.merge_texts(lang)
            self.LoadMods()

        self.btnChange.setEnabled(False)
        self.PerformOperation(resort_mods, (self))

    def UninstallClicked(self):
        mod = self.listWidget.selectedItems()[0].data(QtCore.Qt.UserRole)
        self.PerformOperation(install.uninstall_mod, (mod.path))

    def ExploreClicked(self):
        path = self.listWidget.selectedItems()[0].data(QtCore.Qt.UserRole).path
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def SettingsClicked(self):
        if SettingsDialog(self).exec_() == QtWidgets.QDialog.Accepted:
            self.LoadMods()

    def AboutClicked(self):
        AboutDialog(self).exec_()

# Install Dialog


class InstallDialog(QtWidgets.QDialog, Ui_InstallDialog):

    def __init__(self, *args, **kwargs):
        super(InstallDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)
        self.btnBrowse.clicked.connect(self.BrowseClicked)

    def BrowseClicked(self):
        file_name = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Select a Mod', '', 'Mod Archives (*.zip; *.rar; *.7z);;All Files (*)')[0]
        if file_name:
            self.txtFile.setText(file_name)

    def GetResult(self):
        if self.exec_() == QtWidgets.QDialog.Accepted:
            return InstallResult(
                Path(self.txtFile.text()),
                self.chkRstbLeave.isChecked(),
                self.chkRstbShrink.isChecked(),
                self.chkDisablePack.isChecked(),
                self.chkDisableTexts.isChecked(),
                self.chkDisableGamedata.isChecked(),
                self.chkDisableSavedata.isChecked(),
                self.chkDisableActorInfo.isChecked(),
                self.chkEnableDeepMerge.isChecked(),
                self.chkDelayMerge.isChecked()
            )
        else:
            return None


# Settings Dialog

class SettingsDialog(QtWidgets.QDialog, Ui_SettingsDialog):

    def __init__(self, *args, **kwargs):
        super(SettingsDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)

        self.txtCemu.setText(str(util.get_cemu_dir()))
        self.txtGameDump.setText(str(util.get_game_dir()))
        self.txtMlc.setText(str(util.get_mlc_dir()))

        self.btnBrowseCemu.clicked.connect(self.BrowseCemuClicked)
        self.btnBrowseGame.clicked.connect(self.BrowseGameClicked)
        self.btnBrowseMlc.clicked.connect(self.BrowseMlcClicked)

    def BrowseCemuClicked(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select Cemu Directory')
        if folder:
            self.txtCemu.setText(folder)

    def BrowseGameClicked(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select Game Dump Directory')
        if folder:
            self.txtGameDump.setText(folder)

    def BrowseMlcClicked(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select Cemu MLC Directory')
        if folder:
            self.txtMlc.setText(folder)

    def accept(self):
        cemu_path = Path(self.txtCemu.text())
        if cemu_path.exists():
            util.set_cemu_dir(cemu_path)
        else:
            QtWidgets.QMessageBox.warning(
                self, 'Error', 'The specified Cemu directory does not exist.')
            return
        game_path = Path(self.txtGameDump.text())
        if game_path.exists():
            util.set_game_dir(game_path)
        else:
            QtWidgets.QMessageBox.warning(
                self, 'Error', 'The specified game dump directory does not exist.')
            return
        mlc_path = Path(self.txtMlc.text())
        if mlc_path.exists():
            util.set_mlc_dir(mlc_path)
        else:
            QtWidgets.QMessageBox.warning(
                self, 'Error', 'The specified Cemu MLC directory does not exist.')
            return
        return super().accept()

# About Dialog


class AboutDialog(QtWidgets.QDialog, Ui_AboutDialog):

    def __init__(self, *args, **kwargs):
        super(AboutDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)
        logo_path = str(util.get_exec_dir() / 'data' / 'logo-smaller.png')
        self.lblLogo.setPixmap(QtGui.QPixmap(logo_path).scaledToWidth(256))
        self.lblVersion.setText('Version ' + util.get_bcml_version())
        self.btnClose.clicked.connect(self.close)

# Progress Operation Stuff


class ProgressDialog(QtWidgets.QDialog, Ui_dlgProgress):

    def __init__(self, *args, **kwargs):
        super(ProgressDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)


class ProgressThread(threading.Thread):
    def __init__(self, parent, target, *args):
        threading.Thread.__init__(self)
        self._dialog = ProgressDialog(parent)
        self._parent = parent
        self._target = target
        self._args = args
        self._dialog.show()
        self.signal = ThreadSignal()

    def run(self):
        sys.stdout = RedirectText(self._dialog.lblProgress)
        self._target(*self._args)
        self._dialog.close()
        self.signal.sig.emit('Done')


class RedirectText:
    def __init__(self, label: QtWidgets.QLabel):
        self.out = label

    def write(self, text):
        if text != '\n':
            self.out.setText(text)


class ThreadSignal(QtCore.QObject):
    sig = QtCore.Signal(str)

# Main


InstallResult = namedtuple(
    'InstallResult', 'path leave shrink no_packs no_texts no_gamedata no_savedata no_actorinfo deep_merge wait_merge')


def main():
    app = QtWidgets.QApplication([])
    application = MainWindow()
    application.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
