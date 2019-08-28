"""Main BCML application"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=invalid-name,missing-docstring,too-many-lines
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import traceback
import urllib.error
import urllib.request
import zipfile
#import glob
from collections import namedtuple
from configparser import ConfigParser
from pathlib import Path

from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtCore import Qt
from PySide2.QtCore import QUrl
from PySide2.QtGui import QDesktopServices
from PySide2.QtWidgets import QFileDialog

from bcml import data, install, merge, pack, rstable, texts, util, mubin
from bcml.Ui_about import Ui_AboutDialog
from bcml.Ui_install import Ui_InstallDialog
from bcml.Ui_main import Ui_MainWindow
from bcml.Ui_progress import Ui_ProgressDialog
from bcml.Ui_settings import Ui_SettingsDialog
from bcml.Ui_package import Ui_PackageDialog
from bcml.util import BcmlMod


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        self._mods = []
        self._mod_infos = {}
        self._progress = None
        self._thread = None
        self._cemu_exe = None

        self.setWindowIcon(util.get_icon('bcml.ico'))
        load_reverse = util.get_settings_bool('load_reverse')

        self.menRemerge = QtWidgets.QMenu()
        self.actMergeRstb = QtWidgets.QAction('Remerge RSTB')
        self.actMergePacks = QtWidgets.QAction('Remerge Packs')
        self.actMergeTexts = QtWidgets.QAction('Remerge Texts')
        self.actMergeActors = QtWidgets.QAction('Remerge Actor Info')
        self.actMergeGamedata = QtWidgets.QAction('Remerge Game/Save Data')
        self.actMergeMaps = QtWidgets.QAction('Remerge Maps')
        self.actDeepMerge = QtWidgets.QAction('Refresh Deep Merge')
        self.actMergeRstb.triggered.connect(self.MergeRstb_Clicked)
        self.actMergePacks.triggered.connect(self.MergePacks_Clicked)
        self.actMergeTexts.triggered.connect(self.MergeTexts_Clicked)
        self.actMergeActors.triggered.connect(self.MergeActors_Clicked)
        self.actMergeGamedata.triggered.connect(self.MergeGamedata_Clicked)
        self.actMergeMaps.triggered.connect(self.MergeMaps_Clicked)
        self.actDeepMerge.triggered.connect(self.DeepMerge_Clicked)
        self.menRemerge.addAction(self.actMergeRstb)
        self.menRemerge.addAction(self.actMergePacks)
        self.menRemerge.addAction(self.actMergeTexts)
        self.menRemerge.addAction(self.actMergeActors)
        self.menRemerge.addAction(self.actMergeGamedata)
        self.menRemerge.addAction(self.actMergeMaps)
        self.menRemerge.addAction(self.actDeepMerge)
        self.btnRemerge.setMenu(self.menRemerge)

        self.btnPackage = QtWidgets.QToolButton(self.statusBar())
        self.btnPackage.setIcon(util.get_icon('pack.png'))
        self.btnPackage.setToolTip('Create BCNL Nano Patch Mod')
        self.btnSettings = QtWidgets.QToolButton(self.statusBar())
        self.btnSettings.setIcon(util.get_icon('settings.png'))
        self.btnSettings.setToolTip('Settings')
        self.btnAbout = QtWidgets.QToolButton(self.statusBar())
        self.btnAbout.setIcon(util.get_icon('about.png'))
        self.btnAbout.setToolTip('About')

        self.statusBar().addPermanentWidget(
            QtWidgets.QLabel('Version ' + util.get_bcml_version()))
        self.statusBar().addPermanentWidget(self.btnPackage)
        self.statusBar().addPermanentWidget(self.btnSettings)
        self.statusBar().addPermanentWidget(self.btnAbout)

        logo_path = str(util.get_exec_dir() / 'data' / 'logo-smaller.png')
        self._logo = QtGui.QPixmap(logo_path)
        self.lblImage.setFixedSize(256, 144)
        self._order_icons = {
            False: util.get_icon('up.png'),
            True: util.get_icon('down.png')
        }
        self.btnOrder.setIcon(self._order_icons[load_reverse])

        higher = 'top' if not load_reverse else 'bottom'
        lower = 'bottom' if not load_reverse else 'top'
        self.listWidget.setToolTip(f'Drag and drop to change mod load order. Mods at the {higher}'
                                   f' of the list override mods at the {lower}.')

        # Bind events
        self.listWidget.setDragDropMode(
            QtWidgets.QAbstractItemView.InternalMove)
        self.listWidget.itemSelectionChanged.connect(self.SelectItem)
        self.listWidget.installEventFilter(self)
        self.btnOrder.clicked.connect(self.OrderClicked)
        self.btnInstall.clicked.connect(self.InstallClicked)
        self.btnRemerge.clicked.connect(self.RemergeClicked)
        self.btnChange.clicked.connect(self.ChangeClicked)
        self.btnExport.clicked.connect(self.ExportClicked)
        self.btnBackup.clicked.connect(self.BackupClicked)
        self.btnRestore.clicked.connect(self.RestoreClicked)
        self.btnCemu.clicked.connect(self.CemuClicked)
        self.btnRemoveAll.clicked.connect(self.RemoveAllClicked)
        self.btnUninstall.clicked.connect(self.UninstallClicked)
        self.btnExplore.clicked.connect(self.ExploreClicked)
        self.btnPackage.clicked.connect(self.PackageClicked)
        self.btnSettings.clicked.connect(self.SettingsClicked)
        self.btnAbout.clicked.connect(self.AboutClicked)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.ChildRemoved:
            mods = [self.listWidget.item(i).data(Qt.UserRole)
                    for i in range(self.listWidget.count())]
            if mods != self._mods:
                self.btnChange.setEnabled(True)
            else:
                self.btnChange.setEnabled(False)
        return super(MainWindow, self).eventFilter(watched, event)

    def SetupChecks(self):
        try:
            util.get_cemu_dir()
        except FileNotFoundError:
            QtWidgets.QMessageBox.information(
                self, 'First Time', 'It looks like this may be your first time running BCML.'
                                    'Please select the directory where Cemu is installed.')
            folder = QFileDialog.getExistingDirectory(
                self, 'Select Cemu Directory')
            if folder:
                util.set_cemu_dir(Path(folder))
            else:
                sys.exit(0)
        try:
            util.get_game_dir()
        except FileNotFoundError:
            QtWidgets.QMessageBox.information(
                self, 'First Time', 'BCML needs to know the location of your game dump. '
                'Please select the "content" directory in your dumped copy of Breath of the Wild.')
            folder = '/'
            while not (Path(folder).parent / 'code' / 'app.xml').exists():
                folder = QFileDialog.getExistingDirectory(
                    self, 'Select Game Dump Directory')
                if folder:
                    if (Path(folder) / 'content').exists():
                        folder = str(Path(folder) / 'content')
                    if not (Path(folder).parent / 'code' / 'app.xml').exists():
                        QtWidgets.QMessageBox.warning(
                            self,
                            'Error',
                            'The chosen directory does not appear to be a valid dump. Please select'
                            'the "content" directory in your dumped copy of Breath of the Wild.'
                        )
                    else:
                        try:
                            util.set_game_dir(Path(folder))
                        except FileNotFoundError:
                            QtWidgets.QMessageBox.information(
                                self,
                                'First Time',
                                'BCML could not detect the location of Cemu\'s MLC directory for '
                                'your game. You will need to specify it manually.'
                            )
                            mlc_folder = QFileDialog.getExistingDirectory(
                                self, 'Select Cemu MLC Directory')
                            if mlc_folder:
                                util.set_mlc_dir(Path(mlc_folder))
                                util.set_game_dir(Path(folder))
                            else:
                                sys.exit(0)
                else:
                    sys.exit(0)

        ver = platform.python_version_tuple()
        if int(ver[0]) < 3 or (int(ver[0]) >= 3 and int(ver[1]) < 7):
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'BCML requires Python 3.7 or higher, but your Python version is {ver[0]}.{ver[1]}'
            )
            sys.exit(0)

        is_64bits = sys.maxsize > 2**32
        if not is_64bits:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                'BCML requires 64 bit Python, but it looks like you\'re running 32 bit.'
            )
            sys.exit(0)

        self.LoadMods()

    def LoadMods(self):
        self.statusBar().showMessage('Loading mods...')
        self.listWidget.clear()
        self._mods = sorted(util.get_installed_mods(), key=lambda imod: imod.priority,
                            reverse=not util.get_settings_bool('load_reverse'))
        for mod in self._mods:
            mod_item = QtWidgets.QListWidgetItem()
            mod_item.setText(mod.name)
            mod_item.setData(QtCore.Qt.UserRole, mod)
            self.listWidget.addItem(mod_item)
        self._mod_infos = {}
        self.lblModInfo.linkActivated.connect(self.link)
        self.lblModInfo.setText('No mod selected')
        self.lblImage.setPixmap(self._logo)
        self.lblImage.setFixedSize(256, 144)
        self.statusBar().showMessage(f'{len(self._mods)} mods installed')
        if self._mods:
            self.btnRemerge.setEnabled(True)
            self.btnExport.setEnabled(True)
            self.btnBackup.setEnabled(True)
            self.btnRemoveAll.setEnabled(True)
        else:
            self.btnRemerge.setEnabled(False)
            self.btnExport.setEnabled(False)
            self.btnBackup.setEnabled(False)
            self.btnRemoveAll.setEnabled(False)

    def link(self, linkStr):
        QDesktopServices.openUrl(QUrl(linkStr))

    def SelectItem(self):
        if not self.listWidget.selectedItems():
            return
        mod = self.listWidget.selectedItems()[0].data(QtCore.Qt.UserRole)

        if mod not in self._mod_infos:
            rules = ConfigParser()
            rules.read(str(mod.path / 'rules.txt'))
            font_met = QtGui.QFontMetrics(self.lblModInfo.font())
            path = str(mod.path)
            while font_met.boundingRect(f'Path: {path}.....').width() >= self.lblModInfo.width():
                path = path[:-1]
            changes = []
            if rstable.get_mod_rstb_values(mod):
                changes.append('RSTB')
            if util.is_pack_mod(mod):
                changes.append('packs')
            if texts.get_modded_languages(mod.path):
                changes.append('texts')
                if 'RSTB' not in changes:
                    changes.insert(0, 'RSTB')
            if util.is_gamedata_mod(mod):
                changes.append('game data')
            if util.is_savedata_mod(mod):
                changes.append('save data')
            if util.is_actorinfo_mod(mod):
                changes.append('actor info')
            if util.is_map_mod(mod):
                changes.append('maps')
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
                mod_info.insert(3, util.get_mod_link_meta(rules))
            try:
                preview = util.get_mod_preview(mod, rules)
            except (FileNotFoundError, KeyError, IndexError, UnboundLocalError):
                preview = self._logo
            finally:
                self._mod_infos[mod] = (mod_info, preview)
        else:
            mod_info, preview = self._mod_infos[mod]

        self.lblModInfo.setText('<br><br>'.join(mod_info))
        self.lblImage.setFixedSize(
            256, 256 // (preview.width() / preview.height())
        )
        self.lblImage.setPixmap(preview)
        self.lblModInfo.setWordWrap(True)

        if not self.btnUninstall.isEnabled():
            self.btnUninstall.setEnabled(True)
        if not self.btnExplore.isEnabled():
            self.btnExplore.setEnabled(True)

    def PerformOperation(self, func, *args, title: str = 'Operation In Progress'):
        self.btnInstall.setEnabled(False)
        self.btnRemerge.setEnabled(False)
        self.btnExport.setEnabled(False)
        self.btnUninstall.setEnabled(False)
        self.btnExplore.setEnabled(False)
        self.btnBackup.setEnabled(False)
        self.btnRestore.setEnabled(False)
        self.btnCemu.setEnabled(False)
        self.btnRemoveAll.setEnabled(False)
        self.btnOrder.setEnabled(False)
        self._progress = ProgressDialog(self)
        self._progress.setWindowTitle(title)
        self._progress.setWindowModality(QtCore.Qt.ApplicationModal)
        self._progress.show()
        self._thread = ProgressThread(self._progress.lblProgress, func, *args)
        self._thread.start()
        self._thread.signal.sig.connect(self.OperationFinished)
        self._thread.signal.err.connect(self.OperationError)


    def OperationFinished(self):
        self._progress.close()
        del self._progress
        self.btnInstall.setEnabled(True)
        self.btnRemerge.setEnabled(True)
        self.btnExport.setEnabled(True)
        self.btnRestore.setEnabled(True)
        self.btnCemu.setEnabled(True)
        self.btnOrder.setEnabled(True)
        self.LoadMods()
        QtWidgets.QMessageBox.information(
            self, 'Complete', 'Operation finished!')
        del self._thread
        util.clear_temp_dir()

    def OperationError(self):
        self.btnInstall.setEnabled(True)
        self.btnRemerge.setEnabled(True)
        self.btnExport.setEnabled(True)
        QtWidgets.QMessageBox.critical(
            self, 'Error', f'BCML has encountered an error while performing an operation.'
                           f'Error details:\n\n{self._thread.error}')
        self.LoadMods()
        self._progress.close()
        del self._progress
        del self._thread
        util.clear_temp_dir()

    # Button handlers

    def OrderClicked(self):
        load_reverse = not util.get_settings_bool('load_reverse')
        util.set_settings_bool('load_reverse', load_reverse)
        self.LoadMods()
        self.btnOrder.setIcon(self._order_icons[load_reverse])

        higher = 'top' if not load_reverse else 'bottom'
        lower = 'bottom' if not load_reverse else 'top'
        self.listWidget.setToolTip('Drag and drop to change mod load order. Mods at the'
                                   f'{higher} of the list override mods at the {lower}.')

    def InstallClicked(self, preload_mod: Path = None):
        def install_all(result: InstallResult):
            mods = []
            for i, mod in enumerate(result.paths):
                mods.append(install.install_mod(
                    mod,
                    verbose=False,
                    no_packs=result.no_packs,
                    no_texts=result.no_texts,
                    no_gamedata=result.no_gamedata,
                    no_savedata=result.no_savedata,
                    no_actorinfo=result.no_actorinfo,
                    no_map=result.no_map,
                    leave_rstb=result.leave,
                    shrink_rstb=result.shrink,
                    guess=result.guess,
                    wait_merge=True,
                    deep_merge=result.deep_merge,
                    insert_priority=result.insert_priority + i
                ))
            fix_packs = set()
            fix_gamedata = False
            fix_savedata = False
            fix_actorinfo = False
            fix_map = False
            fix_deepmerge = set()
            fix_texts = []
            for mod in mods:
                for mpack in pack.get_modded_packs_in_mod(mod):
                    fix_packs.add(mpack)
                fix_gamedata = fix_gamedata or util.is_gamedata_mod(
                    mod) or 'content\\Pack\\Bootup.pack' in fix_packs
                fix_savedata = fix_savedata or util.is_savedata_mod(
                    mod) or 'content\\Pack\\Bootup.pack' in fix_packs
                fix_actorinfo = fix_actorinfo or util.is_actorinfo_mod(mod)
                fix_map = fix_map or util.is_map_mod(mod)
                for mfile in merge.get_mod_deepmerge_files(mod):
                    fix_deepmerge.add(mfile)
                for lang in texts.get_modded_languages(mod.path):
                    if lang not in fix_texts:
                        fix_texts.append(lang)
            rstable.generate_master_rstb()
            if fix_packs:
                pack.merge_installed_packs(no_injection=not (
                    fix_gamedata or fix_savedata), only_these=list(fix_packs), even_one=True)
            if fix_gamedata:
                data.merge_gamedata()
            if fix_savedata:
                data.merge_savedata()
            if fix_actorinfo:
                data.merge_actorinfo()
            if fix_map:
                mubin.merge_maps()
            mubin.merge_dungeonstatic()
            for lang in fix_texts:
                texts.merge_texts(lang)
            if fix_deepmerge:
                merge.deep_merge(only_these=list(fix_deepmerge))

        dialog = InstallDialog(self)
        if preload_mod:
            mod_item = QtWidgets.QListWidgetItem()
            mod_item.setText(preload_mod.stem)
            mod_item.setData(Qt.UserRole, preload_mod)
            dialog.lstQueue.addItem(mod_item)
        result = dialog.GetResult()
        if result:
            self.PerformOperation(install_all, result, title='Installing')

    def RemergeClicked(self):
        self.PerformOperation(install.refresh_merges, ())


    def MergeRstb_Clicked(self):
        self.PerformOperation(rstable.generate_master_rstb, title='Remerging RSTB')


    def MergePacks_Clicked(self):
        self.PerformOperation(
            pack.merge_installed_packs,
            (False, None, False, True),
            title='Remerging Packs'
        )


    def MergeTexts_Clicked(self):
        def all_texts():
            for text_mod in util.get_modpack_dir().rglob('**/texts_*.yml'):
                lang = util.get_file_language(text_mod)
                texts.merge_texts(lang)

        self.PerformOperation(all_texts, title='Remerging Texts')


    def MergeActors_Clicked(self):
        self.PerformOperation(data.merge_actorinfo, title='Remerging Actor Info')


    def MergeGamedata_Clicked(self):
        def both_datas():
            data.merge_gamedata()
            data.merge_savedata()
        self.PerformOperation(both_datas, title='Remerging Game/Save Data')


    def MergeMaps_Clicked(self):
        def map_and_rstb():
            mubin.merge_maps()
            rstable.generate_master_rstb()
        self.PerformOperation(map_and_rstb, title='Remerging Maps')


    def DeepMerge_Clicked(self):
        self.PerformOperation(merge.deep_merge, title='Redoing Deep Merge')


    def ChangeClicked(self):
        def resort_mods(self):
            fix_packs = set()
            fix_gamedata = False
            fix_savedata = False
            fix_actorinfo = False
            fix_map = False
            fix_deepmerge = set()
            fix_texts = []
            mods_to_change = []
            for i in range(self.listWidget.count()):
                mod = self.listWidget.item(i).data(QtCore.Qt.UserRole)
                target_priority = i + 100 if util.get_settings_bool(
                    'load_reverse') else 100 + ((self.listWidget.count() - 1) - i)
                if mod.priority != target_priority:
                    for mpack in pack.get_modded_packs_in_mod(mod):
                        fix_packs.add(mpack)
                    fix_gamedata = fix_gamedata or util.is_gamedata_mod(
                        mod) or 'content\\Pack\\Bootup.pack' in fix_packs
                    fix_savedata = fix_savedata or util.is_savedata_mod(
                        mod) or 'content\\Pack\\Bootup.pack' in fix_packs
                    fix_actorinfo = fix_actorinfo or util.is_actorinfo_mod(mod)
                    fix_map = fix_map or util.is_map_mod(mod)
                    for mfile in merge.get_mod_deepmerge_files(mod):
                        fix_deepmerge.add(mfile)
                    for lang in texts.get_modded_languages(mod.path):
                        if lang not in fix_texts:
                            fix_texts.append(lang)
                    mods_to_change.append((mod, target_priority))
            for mod in mods_to_change:
                new_path = util.get_modpack_dir(
                ) / util.get_mod_id(mod[0].name, mod[1])
                shutil.move(str(mod[0].path), str(new_path))
                rules = ConfigParser()
                rules.read(str(new_path / 'rules.txt'))
                rules['Definition']['fsPriority'] = str(mod[1])
                with (new_path / 'rules.txt').open('w', encoding='utf-8') as rf:
                    rules.write(rf)
            rstable.generate_master_rstb()
            if fix_packs:
                pack.merge_installed_packs(no_injection=not (
                    fix_gamedata or fix_savedata), only_these=list(fix_packs))
            if fix_gamedata:
                data.merge_gamedata()
            if fix_savedata:
                data.merge_savedata()
            if fix_actorinfo:
                data.merge_actorinfo()
            if fix_map:
                mubin.merge_maps()
            mubin.merge_dungeonstatic()
            for lang in fix_texts:
                texts.merge_texts(lang)
            if fix_deepmerge:
                merge.deep_merge(only_these=list(fix_deepmerge))
            self.LoadMods()
            install.refresh_cemu_mods()

        self.btnChange.setEnabled(False)
        self.PerformOperation(resort_mods, (self))

    def ExportClicked(self):
        def export(self, output: Path):
            print('Loading files...')
            files = {}
            mods = sorted([self.listWidget.item(i).data(Qt.UserRole) for i in range(
                self.listWidget.count())], key=lambda mod: mod.priority)
            for mod in mods:
                for file in mod.path.rglob('**/*'):
                    rel_path = file.relative_to(mod.path)
                    if rel_path.parts[0] in ['aoc', 'content'] and file.is_file():
                        files[rel_path.as_posix()] = file
            for file in util.get_master_modpack_dir().rglob('**/*'):
                rel_path = file.relative_to(util.get_master_modpack_dir())
                if rel_path.parts[0] in ['aoc', 'content'] and file.is_file():
                    files[rel_path.as_posix()] = file
            print('Creating new ZIP...')
            out = zipfile.ZipFile(str(output), mode='w',
                                  compression=zipfile.ZIP_DEFLATED)
            for file, path in files.items():
                try:
                    out.write(str(path), file)
                except ValueError:
                    os.utime(str(path))
                    out.write(str(path), file)
            print('Adding rules.txt...')
            rules_path = util.get_work_dir() / 'tmprules.txt'
            with rules_path.open('w', encoding='utf-8') as rules:
                rules.writelines([
                    '[Definition]\n',
                    'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n',
                    'name = Exported BCML Mod\n',
                    'path = The Legend of Zelda: Breath of the Wild/Mods/Exported BCML\n',
                    f'description = Exported merge of {", ".join([mod.name for mod in mods])}\n',
                    'version = 4\n'
                ])
            out.write(str(rules_path), 'rules.txt')
            rules_path.unlink()
            out.close()

        file_name = QFileDialog.getSaveFileName(self, 'Save Exported Mod', str(
            Path.home()), 'Mod Archive (*.zip);;All Files (*)')[0]
        if file_name:
            self.PerformOperation(export, self, Path(file_name))

    def BackupClicked(self):
        backup_name, okay = QtWidgets.QInputDialog.getText(
            self,
            'Backup Mod Configuration',
            'Enter a name for your backup (optional)',
            QtWidgets.QLineEdit.Normal,
            '',
            flags=QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint
        )
        if okay:
            self.PerformOperation(install.create_backup, (backup_name), title='Backing Up Mods')

    def RestoreClicked(self):
        backups = [backup.stem for backup in install.get_backups()]
        backup, okay = QtWidgets.QInputDialog.getItem(
            self,
            'Restore Backup',
            'Select the backup to restore',
            backups,
            0,
            False,
            flags=QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint
        )
        if okay and backup:
            self.PerformOperation(install.restore_backup, (backup))

    def CemuClicked(self):
        if not self._cemu_exe:
            for file in util.get_cemu_dir().glob('*.exe'):
                if 'cemu' in file.stem.lower():
                    self._cemu_exe = file
        if not self._cemu_exe:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                'The Cemu executable could not be found.'
            )
        else:
            subprocess.Popen(
                [
                    str(self._cemu_exe),
                    '-g',
                    str(util.get_game_dir().parent / 'code' / 'U-King.rpx')
                ],
                cwd=str(util.get_cemu_dir())
            )

    def RemoveAllClicked(self):
        def uninstall_everything():
            for folder in [item for item in util.get_modpack_dir().glob('*') if item.is_dir()]:
                print(f'Removing {folder.name}...')
                shutil.rmtree(str(folder))
                print('All BCML mods have been uninstalled!')

        if QtWidgets.QMessageBox.question(
                self,
                'Confirm Uninstall',
                'Are you sure you want to uninstall all of your mods?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) == QtWidgets.QMessageBox.Yes:
            self.PerformOperation(uninstall_everything, title='Uninstalling All Mods')

    def UninstallClicked(self):
        def uninstall(mods):
            fix_packs = set()
            fix_gamedata = False
            fix_savedata = False
            fix_actorinfo = False
            fix_map = False
            fix_deepmerge = set()
            fix_texts = []
            for mod in mods:
                for mpack in pack.get_modded_packs_in_mod(mod):
                    fix_packs.add(mpack)
                fix_gamedata = fix_gamedata or util.is_gamedata_mod(
                    mod) or 'content\\Pack\\Bootup.pack' in fix_packs
                fix_savedata = fix_savedata or util.is_savedata_mod(
                    mod) or 'content\\Pack\\Bootup.pack' in fix_packs
                fix_actorinfo = fix_actorinfo or util.is_actorinfo_mod(mod)
                fix_map = fix_map or util.is_map_mod(mod)
                for mfile in merge.get_mod_deepmerge_files(mod):
                    fix_deepmerge.add(mfile)
                for lang in texts.get_modded_languages(mod.path):
                    if lang not in fix_texts:
                        fix_texts.append(lang)
            for mod in mods:
                install.uninstall_mod(mod, wait_merge=True)
            rstable.generate_master_rstb()
            if fix_packs:
                pack.merge_installed_packs(
                    no_injection=not (fix_gamedata or fix_savedata),
                    only_these=list(fix_packs)
                )
            if fix_gamedata:
                data.merge_gamedata()
            if fix_savedata:
                data.merge_savedata()
            if fix_actorinfo:
                data.merge_actorinfo()
            if fix_map:
                mubin.merge_maps()
            mubin.merge_dungeonstatic()
            for lang in fix_texts:
                texts.merge_texts(lang)
            if fix_deepmerge:
                merge.deep_merge(only_these=list(fix_deepmerge))
            install.refresh_cemu_mods()

        if self.listWidget.selectedItems():
            mods = [item.data(Qt.UserRole)
                    for item in self.listWidget.selectedItems()]
            self.PerformOperation(uninstall, (mods))

    def ExploreClicked(self):
        path = self.listWidget.selectedItems()[0].data(QtCore.Qt.UserRole).path
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def PackageClicked(self):
        def create_package(result):
            rules = [
                '[Definition]',
                'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500',
                f'name = {result["name"]}',
                f'path = ι BCML: DON\'T TOUCH/{result["name"]}',
                'description = {}'.format(result['description'].replace('\n', ' ')),
                'version = 4'
            ]
            if result['image']:
                rules.append(f'image = {result["image"]}')
            if result['url']:
                rules.append(f'url = {result["url"]}')
            (result['folder'] / 'rules.txt').write_text('\n'.join(rules))
            install.create_bnp_mod(
                mod=result['folder'],
                output=result['output'],
                no_packs=result['no_packs'],
                no_texts=result['no_texts'],
                no_gamedata=result['no_gamedata'],
                no_savedata=result['no_gamedata'],
                no_actorinfo=result['no_actorinfo'],
                no_map=result['no_map'],
                leave_rstb=result['leave'],
                shrink_rstb=result['shrink'],
                guess=result['guess'],
                deep_merge=result['deep_merge']
            )
        dialog = PackageDialog(self)
        result = dialog.GetResult()
        if result:
            self.PerformOperation(
                create_package,
                (result),
                title=f'Creating BNP package for {result["name"]}'
            )

    def SettingsClicked(self):
        if SettingsDialog(self).exec_() == QtWidgets.QDialog.Accepted:
            self.LoadMods()

    def AboutClicked(self):
        AboutDialog(self).exec_()

# Install Dialog


class InstallDialog(QtWidgets.QDialog, Ui_InstallDialog):

    def __init__(self, *args, **kwargs): # pylint: disable=unused-argument
        super(InstallDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)
        self.btnAddFile.clicked.connect(self.AddFileClicked)
        self.btnAddFolder.clicked.connect(self.AddFolderClicked)
        self.btnRemove.clicked.connect(self.RemoveClicked)
        self.btnClear.clicked.connect(self.ClearClicked)

    def AddFileClicked(self):
        file_names = QFileDialog.getOpenFileNames(
            self,
            'Select a Mod',
            str(Path.home()),
            'Mod Archives (*.zip; *.rar; *.7z; *.bnp);;All Files (*)'
        )[0]
        for file_name in file_names:
            path = Path(file_name)
            if path.exists():
                mod_item = QtWidgets.QListWidgetItem()
                mod_item.setText(path.stem)
                mod_item.setData(Qt.UserRole, path)
                self.lstQueue.addItem(mod_item)

    def AddFolderClicked(self):
        folder = QFileDialog.getExistingDirectory(
            self, 'Select a Mod Folder')
        if folder:
            path = Path(folder)
            if path.exists():
                mod_item = QtWidgets.QListWidgetItem()
                mod_item.setText(path.stem)
                mod_item.setData(Qt.UserRole, path)
                self.lstQueue.addItem(mod_item)

    def RemoveClicked(self):
        for i in self.lstQueue.selectedIndexes():
            self.lstQueue.takeItem(i.row())

    def ClearClicked(self):
        self.lstQueue.clear()

    def GetResult(self):
        if self.exec_() == QtWidgets.QDialog.Accepted:
            paths = [self.lstQueue.item(i).data(Qt.UserRole)
                     for i in range(self.lstQueue.count())]
            return InstallResult(
                paths,
                self.chkRstbLeave.isChecked(),
                self.chkRstbShrink.isChecked(),
                self.chkRstbGuess.isChecked(),
                self.chkDisablePack.isChecked(),
                self.chkDisableTexts.isChecked(),
                self.chkDisableGamedata.isChecked(),
                self.chkDisableGamedata.isChecked(),
                self.chkDisableActorInfo.isChecked(),
                self.chkDisableMap.isChecked(),
                not self.chkEnableDeepMerge.isChecked(),
                self.spnInsertPriority.value()
            )

# Package Dialog


class PackageDialog(QtWidgets.QDialog, Ui_PackageDialog):

    def __init__(self, *args, **kwargs):
        # pylint: disable=unused-argument
        super(PackageDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)
        self.btnBrowseContent.clicked.connect(self.BrowseContentClicked)
        self.btnBrowseImg.clicked.connect(self.BrowseImgClicked)

    def BrowseContentClicked(self):
        folder = QFileDialog.getExistingDirectory(
            self, 'Select Mod Folder')
        if folder:
            path = Path(folder)
            if path.name == 'content':
                path = path.parent
            self.txtFolder.setText(str(path.resolve()))
            if (path / 'rules.txt').exists():
                rules = ConfigParser()
                rules.read(str(path / 'rules.txt'))
                if 'name' in rules['Definition'] and not self.txtName.text():
                    self.txtName.setText(str(rules['Definition']['name']))
                if 'url' in rules['Definition'] and not self.txtUrl.text():
                    self.txtUrl.setText(str(rules['Definition']['url']))
                if 'image' in rules['Definition'] and not self.txtImage.text():
                    self.txtImage.setText(str(rules['Definition']['image']))
                if 'description' in rules['Definition'] and not self.txtDescript.toPlainText():
                    self.txtDescript.setPlainText(str(rules['Definition']['description']))

    def BrowseImgClicked(self):
        file_name = QFileDialog.getOpenFileName(
            self,
            'Select a Preview Image',
            str(Path.home()),
            'Images (*.png; *.jpg; *.bmp);;All Files (*)'
        )[0]
        if file_name:
            self.txtImage.setText(str(Path(file_name).resolve()))

    def accept(self):
        if not self.txtName.text().strip():
            QtWidgets.QMessageBox.warning(
                self, 'Error', 'You must provide a name for your mod.')
            return
        if not self.txtDescript.toPlainText().strip():
            QtWidgets.QMessageBox.warning(
                self, 'Error', 'You must provide a description for your mod.')
            return
        if not self.txtFolder.text().strip() or \
                not Path(self.txtFolder.text().strip()).exists():
            QtWidgets.QMessageBox.warning(
                self, 'Error', 'You must provide a valid folder containing a mod.')
            return
        return super().accept()

    def GetResult(self):
        if self.exec_() == QtWidgets.QDialog.Accepted:
            output = Path(
                QFileDialog.getSaveFileName(
                    self,
                    'Save Your Mod',
                    str(Path.home()),
                    'Botw Nano Patch Mod (*.bnp);;7-Zip Archive (*.7z);;All Files (*)'
                )[0]
            )
            if not output:
                return None
            return {
                'name': self.txtName.text().strip(),
                'description': self.txtDescript.toPlainText().strip(),
                'image': self.txtImage.text().strip(),
                'url': self.txtUrl.text().strip(),
                'folder': Path(self.txtFolder.text().strip()),
                'shrink': self.chkRstbShrink.isChecked(),
                'leave': self.chkRstbLeave.isChecked(),
                'guess': self.chkRstbGuess.isChecked(),
                'deep_merge': not self.chkEnableDeepMerge.isChecked(),
                'no_packs': self.chkDisablePack.isChecked(),
                'no_texts': self.chkDisableTexts.isChecked(),
                'no_actorinfo': self.chkDisableActorInfo.isChecked(),
                'no_gamedata': self.chkDisableGamedata.isChecked(),
                'no_map': self.chkDisableMap.isChecked(),
                'output': output
            }


# Settings Dialog

class SettingsDialog(QtWidgets.QDialog, Ui_SettingsDialog):

    def __init__(self, *args, **kwargs):
        # pylint: disable=unused-argument
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
        folder = QFileDialog.getExistingDirectory(
            self, 'Select Cemu Directory')
        if folder:
            self.txtCemu.setText(folder)

    def BrowseGameClicked(self):
        folder = QFileDialog.getExistingDirectory(
            self, 'Select Game Dump Directory')
        if folder:
            self.txtGameDump.setText(folder)

    def BrowseMlcClicked(self):
        folder = QFileDialog.getExistingDirectory(
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

    def link(self, linkStr):
        QDesktopServices.openUrl(QUrl(linkStr))

    def __init__(self, *args, **kwargs):
        # pylint: disable=unused-argument
        super(AboutDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)
        logo_path = str(util.get_exec_dir() / 'data' / 'logo-smaller.png')
        self.lblLogo.setPixmap(QtGui.QPixmap(logo_path).scaledToWidth(256))
        self.lblVersion.setText('Version ' + util.get_bcml_version())
        self.lblSites.linkActivated.connect(self.link)
        self.btnClose.clicked.connect(self.close)

# Progress Operation Stuff


class ProgressDialog(QtWidgets.QDialog, Ui_ProgressDialog):

    def __init__(self, *args, **kwargs):
        # pylint: disable=unused-argument
        super(ProgressDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(
            str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)
        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint)


class ProgressThread(threading.Thread):
    def __init__(self, output, target, *args):
        threading.Thread.__init__(self)
        self._out = output
        self._target = target
        self._args = args
        self.signal = ThreadSignal()
        self.error = None

    def run(self):
        sys.stdout = RedirectText(self._out)
        try:
            self._target(*self._args)
            self.signal.sig.emit('Done')
        except Exception as e: # pylint: disable=broad-except
            self.error = traceback.format_exc(limit=3)
            self.signal.err.emit(e)


class RedirectText:
    def __init__(self, label: QtWidgets.QLabel):
        self.out = label

    def write(self, text):
        if text != '\n':
            try:
                self.out.setText(text)
            except RuntimeError:
                pass

    def flush(self):
        pass


class ThreadSignal(QtCore.QObject):
    sig = QtCore.Signal(str)
    err = QtCore.Signal(str)


# Main

InstallResult = namedtuple(
    'InstallResult',
    'paths leave shrink guess no_packs no_texts no_gamedata no_savedata no_actorinfo no_map ' + \
    'deep_merge insert_priority'
)


def main():
    util.clear_temp_dir()
    app = QtWidgets.QApplication([])
    application = MainWindow()
    try:
        application.show()
        application.SetupChecks()
        if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
            application.InstallClicked(Path(sys.argv[1]))
        app.exec_()
    except Exception: # pylint: disable=broad-except
        tb = traceback.format_exc(limit=2)
        e = util.get_work_dir() / 'error.log'
        QtWidgets.QMessageBox.warning(
            None,
            'Error',
            f'An unexpected error has occured:\n\n{tb}\nThe error has been logged to:\n'
            f'{e}\n\nBCML will now close.'
        )
        e.write_text(tb)


if __name__ == "__main__":
    main()
