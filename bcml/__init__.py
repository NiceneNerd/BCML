"""Main BCML application"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=invalid-name,missing-docstring,too-many-lines
import os
import platform
import shutil
import subprocess
import sys
import threading
import traceback
import urllib.error
import urllib.request
from configparser import ConfigParser
from pathlib import Path

from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtCore import Qt
from PySide2.QtCore import QUrl
from PySide2.QtGui import QDesktopServices
from PySide2.QtWidgets import QFileDialog

try:
    from bcml import data, install, merge, pack, rstable, texts, util, mubin, events, mergers
    from bcml.Ui_about import Ui_AboutDialog
    from bcml.Ui_install import Ui_InstallDialog
    from bcml.Ui_main import Ui_MainWindow
    from bcml.Ui_progress import Ui_ProgressDialog
    from bcml.Ui_settings import Ui_SettingsDialog
    from bcml.Ui_package import Ui_PackageDialog
    from bcml.Ui_options import Ui_OptionsDialog
    from bcml.util import BcmlMod
    uhoh = False
except ImportError:
    uhoh = True

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
        self.btnPackage.setToolTip('Create BNP Mod')
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
        self.btnDisableMod.clicked.connect(self.DisableModClicked)
        self.btnEnableMod.clicked.connect(self.EnableModClicked)
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
                                    'Please select the directory where Cemu is installed. You can '
                                    'tell it\'s right if it contains <code>Cemu.exe</code>.')
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
                self, 'Dump Location', 'BCML needs to know the location of your game dump. '
                'Please select the "content" directory in your dumped copy of Breath of the Wild. '
                'Note this is <em>not</em> usually inside Cemu\'s MLC folder. This is where the '
                'base game in installed, not update or DLC data.')
            folder = '/'
            while not (Path(folder).parent / 'code' / 'app.xml').exists():
                folder = QFileDialog.getExistingDirectory(self, 'Select Game Dump Directory')
                if folder:
                    folder = Path(folder)
                    if (folder / 'content').exists():
                        folder = folder / 'content'
                    if not (folder.parent / 'code' / 'app.xml').exists():
                        QtWidgets.QMessageBox.warning(
                            self,
                            'Error',
                            'The chosen directory does not appear to be a valid dump. Please select'
                            'the "content" directory in your dumped copy of Breath of the Wild.'
                        )
                    else:
                        try:
                            util.set_game_dir(folder)
                        except FileNotFoundError:
                            QtWidgets.QMessageBox.information(
                                self,
                                'MLC Location',
                                'BCML could not detect the location of Cemu\'s MLC directory for '
                                'your game. You will need to specify it manually.'
                            )
                            mlc_folder = QFileDialog.getExistingDirectory(
                                self,
                                'Select Cemu MLC Directory'
                            )
                            if mlc_folder:
                                util.set_mlc_dir(Path(mlc_folder))
                                util.set_game_dir(Path(folder))                    
                                util.get_update_dir()
                                try:
                                    util.get_aoc_dir()
                                except FileNotFoundError:
                                    pass
                            else:
                                sys.exit(0)
                else:
                    sys.exit(0)
        try:
            util.get_update_dir()
        except FileNotFoundError:
            QtWidgets.QMessageBox.warning(
                self, 'Dump Location', 'BCML could not locate your game\'s update data. Usually,  '
                'this means that either the game dump folder or the MLC folder is not correctly set'
                '. Please go to your BCML settings and confirm the correct location of both '
                'folders. You will not be able to install any mods until this is corrected')
        if 'lang' not in util.get_settings() or not util.get_settings()['lang']:
            lang, okay = QtWidgets.QInputDialog.getItem(
                self,
                'Select Language',
                'Select the regional language you\nuse to play Breath of the Wild',
                texts.LANGUAGES,
                0,
                False,
                flags=QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint
            )
            if okay and lang:
                util.get_settings()['lang'] = lang
                util.save_settings()
        self.LoadMods()

    def LoadMods(self):
        self.statusBar().showMessage('Loading mods...')
        self.listWidget.clear()
        self._mods = sorted(util.get_installed_mods(disabled=True), key=lambda imod: imod.priority,
                            reverse=not util.get_settings_bool('load_reverse'))
        for mod in self._mods:
            mod_item = QtWidgets.QListWidgetItem()
            mod_item.setText(mod.name)
            mod_item.setData(QtCore.Qt.UserRole, mod)
            if util.is_mod_disabled(mod):
                mod_item.setTextColor(QtGui.QColor(211, 47, 47))
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
            rules = util.RulesParser()
            if util.is_mod_disabled(mod):
                rules.read(str(mod.path / 'rules.txt.disable'))
            else:
                rules.read(str(mod.path / 'rules.txt'))
            font_met = QtGui.QFontMetrics(self.lblModInfo.font())
            path = str(mod.path)
            while font_met.boundingRect(f'Path: {path}.....').width() >= self.lblModInfo.width():
                path = path[:-1]
            changes = []
            for merger in {cls() for cls in mergers.get_mergers()}:
                if merger.is_mod_logged(mod):
                    changes.append(merger.NAME if not merger.NAME == 'rstb' else 'RSTB')
            mod_info = [
                f'<b>Name</b>: {mod.name}',
                f'<b>Priority:</b> {mod.priority}',
                f'<b>Path:</b> {path}...',
                '<b>Description:</b> {}'.format(
                    str(rules["Definition"]["description"]).strip(' "\'')),
                f'<b>Changes:</b> {", ".join(changes)}'
            ]
            if util.is_mod_disabled(mod):
                mod_info.insert(0, '<b><span style="color:#d32f2f">DISABLED</span></b>')
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

        self.lblModInfo.setText(f'<p>{"</p><p>".join(mod_info)}</p>')
        self.lblImage.setFixedSize(
            256, 256 // (preview.width() / preview.height())
        )
        self.lblImage.setPixmap(preview)
        self.lblModInfo.setWordWrap(True)

        if not self.btnUninstall.isEnabled():
            self.btnUninstall.setEnabled(True)
        if not self.btnExplore.isEnabled():
            self.btnExplore.setEnabled(True)
        disabled = util.is_mod_disabled(mod)
        self.btnEnableMod.setVisible(disabled)
        self.btnDisableMod.setVisible(not disabled)
        if not self.btnEnableMod.isEnabled():
            self.btnEnableMod.setEnabled(True)
        if not self.btnDisableMod.isEnabled():
            self.btnDisableMod.setEnabled(True)

    def PerformOperation(self, func, *args, title: str = 'Operation In Progress'):
        self.btnInstall.setEnabled(False)
        self.btnRemerge.setEnabled(False)
        self.btnExport.setEnabled(False)
        self.btnUninstall.setEnabled(False)
        self.btnEnableMod.setEnabled(False)
        self.btnDisableMod.setEnabled(False)
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
        title = self._progress.windowTitle()
        self._progress.close()
        del self._progress
        self.btnInstall.setEnabled(True)
        self.btnRemerge.setEnabled(True)
        self.btnExport.setEnabled(True)
        self.btnRestore.setEnabled(True)
        self.btnCemu.setEnabled(True)
        self.btnOrder.setEnabled(True)
        self.LoadMods()
        msg_done = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Information,
            f'{title} Finished',
            'Operation complete!',
            parent=self
        )
        msg_done.addButton('OK', QtWidgets.QMessageBox.NoRole)
        msg_done.addButton('Launch Game', QtWidgets.QMessageBox.ActionRole)
        result = msg_done.exec_()
        del self._thread
        util.clear_temp_dir()
        if result == 1:
            self.CemuClicked()

    def OperationError(self):
        self.btnInstall.setEnabled(True)
        self.btnRemerge.setEnabled(True)
        self.btnExport.setEnabled(True)
        self.btnRestore.setEnabled(True)
        self.btnCemu.setEnabled(True)
        self.btnOrder.setEnabled(True)
        QtWidgets.QMessageBox.critical(
            self,
            'Error',
            f'BCML has encountered an error while performing an operation. '
            f'Error details:\n\n{self._thread.error}'
        )
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
        def install_all(result: dict):
            mods = []
            for i, mod in enumerate(result['paths']):
                mods.append(install.install_mod(
                    mod,
                    verbose=False,
                    options=result['options'],
                    wait_merge=True,
                    insert_priority=result['insert_priority'] + i
                ))
            all_mergers = [merge_class() for merge_class in mergers.get_mergers()]
            merges = set()
            partials = {}
            for mod in mods:
                for merger in all_mergers:
                    if merger.is_mod_logged(mod):
                        merges.add(merger)
                        if merger.can_partial_remerge():
                            if not merger.NAME in partials:
                                partials[merger.NAME] = set()
                            partials[merger.NAME] |= set(merger.get_mod_affected(mod))
            for merger in mergers.sort_mergers(merges):
                if merger.NAME in result['options']:
                    merger.set_options(result['options'][merger.NAME])
                if merger.NAME in partials:
                    merger.set_options({'only_these': partials[merger.NAME]})
                merger.perform_merge()

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
        def full_rstb():
            rstable.log_merged_files_rstb()
            rstable.generate_master_rstb()
        self.PerformOperation(full_rstb, title='Remerging RSTB')


    def MergePacks_Clicked(self):
        self.PerformOperation(
            pack.merge_installed_packs,
            (False, None, False, True),
            title='Remerging Packs'
        )


    def MergeTexts_Clicked(self):
        def all_texts():
            tm = texts.TextsMerger()
            tm.perform_merge()

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
            all_mergers = [merger() for merger in mergers.get_mergers()]
            remergers = set()
            partials = {}
            mods_to_change = []
            for i in range(self.listWidget.count()):
                mod = self.listWidget.item(i).data(QtCore.Qt.UserRole)
                target_priority = i + 100 if util.get_settings_bool(
                    'load_reverse') else 100 + ((self.listWidget.count() - 1) - i)
                if mod.priority != target_priority:
                    mods_to_change.append(BcmlMod(mod.name, target_priority, mod.path))
                    for merger in all_mergers:
                        if merger.is_mod_logged(mod):
                            remergers.add(merger)
                            if merger.can_partial_remerge():
                                if merger.NAME not in partials:
                                    partials[merger.NAME] = set()
                                partials[merger.NAME] |= set(merger.get_mod_affected(mod))
            for mod in sorted(mods_to_change, key=lambda m: m.priority, reverse=True):
                new_path = util.get_modpack_dir() / util.get_mod_id(mod.name, mod.priority)
                shutil.move(str(mod.path), str(new_path))
                rules_name = 'rules.txt'
                if not Path(str(new_path / rules_name)).exists():
                    rules_name = f'{rules_name}.disable'
                rules = util.RulesParser()
                rules.read(str(new_path / rules_name))
                rules['Definition']['fsPriority'] = str(mod.priority)
                with (new_path / rules_name).open('w', encoding='utf-8') as rf:
                    rules.write(rf)
            for merger in mergers.sort_mergers(remergers):
                if merger.NAME in partials:
                    merger.set_options({'only_these': partials[merger.NAME]})
                merger.perform_merge()
            self.LoadMods()
            install.refresh_cemu_mods()

        self.btnChange.setEnabled(False)
        self.PerformOperation(resort_mods, (self))

    def ExportClicked(self):
        def export(self, output: Path):
            print('Loading files...')
            tmp_dir = util.get_work_dir() / 'tmp_export'
            if tmp_dir.drive != util.get_modpack_dir().drive:
                tmp_dir = Path(util.get_modpack_dir().drive) / 'tmp_bcml_export'
            install.link_master_mod(tmp_dir)
            print('Adding rules.txt...')
            rules_path = tmp_dir / 'rules.txt'
            mods = util.get_installed_mods()
            with rules_path.open('w', encoding='utf-8') as rules:
                rules.writelines([
                    '[Definition]\n',
                    'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n',
                    'name = Exported BCML Mod\n',
                    'path = The Legend of Zelda: Breath of the Wild/Mods/Exported BCML\n',
                    f'description = Exported merge of {", ".join([mod.name for mod in mods])}\n',
                    'version = 4\n'
                ])
            if output.suffix == '.bnp' or output.name.endswith('.bnp.7z'):
                print('Exporting BNP...')
                install.create_bnp_mod(
                    mod=tmp_dir,
                    output=output,
                    options={'rstb':{'guess':True}}
                )
            else:
                print('Exporting as graphic pack mod...')
                x_args = [str(util.get_exec_dir() / 'helpers' / '7z.exe'),
                          'a', str(output), f'{str(tmp_dir / "*")}']
                subprocess.run(x_args, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
            shutil.rmtree(str(tmp_dir))

        file_name = QFileDialog.getSaveFileName(
            self,
            'Save Exported Mod',
            str(Path.home()),
            'BCML Nano Patch Mod (*.bnp; *.bnp.7z);;Graphic Pack Archive (*.zip);;All Files (*)'
        )[0]
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
            all_mergers = [merger() for merger in mergers.get_mergers()]
            remergers = []
            partials = {}
            for mod in mods:
                for merger in all_mergers:
                    if merger.is_mod_logged(mod):
                        if merger not in remergers:
                            remergers.append(merger)
                        if merger.can_partial_remerge():
                            if merger.NAME not in partials:
                                partials[merger.NAME] = set()
                            partials[merger.NAME] |= set(merger.get_mod_affected(mod))
            for mod in sorted(mods, key=lambda m: m.priority, reverse=True):
                install.uninstall_mod(mod, wait_merge=True)
            for merger in mergers.sort_mergers(remergers):
                if merger.NAME in partials:
                    merger.set_options({'only_these': partials[merger.NAME]})
                merger.perform_merge()
            install.refresh_cemu_mods()

        if self.listWidget.selectedItems():
            mods = [item.data(Qt.UserRole)
                    for item in self.listWidget.selectedItems()]
            if QtWidgets.QMessageBox.question(
                self,
                'Confirm Uninstall',
                f'Are you sure you want to uninstall the selected {len(mods)} mod(s)?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            ) == QtWidgets.QMessageBox.Yes:
                self.PerformOperation(uninstall, (mods))

    def DisableModClicked(self):
        def disable(mods):
            all_mergers = [merger() for merger in mergers.get_mergers()]
            remergers = []
            partials = {}
            for mod in mods:
                for merger in all_mergers:
                    if merger.is_mod_logged(mod):
                        if merger not in remergers:
                            remergers.append(merger)
                        if merger.can_partial_remerge():
                            if merger.NAME not in partials:
                                partials[merger.NAME] = set()
                            partials[merger.NAME] |= set(merger.get_mod_affected(mod))
            for mod in mods:
                install.disable_mod(mod, wait_merge=True)
            for merger in mergers.sort_mergers(remergers):
                if merger.NAME in partials:
                    merger.set_options({'only_these': partials[merger.NAME]})
                merger.perform_merge()
            install.refresh_cemu_mods()

        if self.listWidget.selectedItems():
            mods = [item.data(Qt.UserRole)
                    for item in self.listWidget.selectedItems()]
            if QtWidgets.QMessageBox.question(
                self,
                'Confirm Disable',
                f'Are you sure you want to disable the selected {len(mods)} mod(s)?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            ) == QtWidgets.QMessageBox.Yes:
                self.PerformOperation(disable, (mods))

    def EnableModClicked(self):
        def enable(mods):
            all_mergers = [merger() for merger in mergers.get_mergers()]
            remergers = []
            partials = {}
            for mod in mods:
                for merger in all_mergers:
                    if merger.is_mod_logged(mod):
                        if merger not in remergers:
                            remergers.append(merger)
                        if merger.can_partial_remerge():
                            if merger.NAME not in partials:
                                partials[merger.NAME] = set()
                            partials[merger.NAME] |= set(merger.get_mod_affected(mod))
            for mod in mods:
                install.enable_mod(mod, wait_merge=True)
            for merger in mergers.sort_mergers(remergers):
                if merger.NAME in partials:
                    merger.set_options({'only_these': partials[merger.NAME]})
                merger.perform_merge()
            install.refresh_cemu_mods()

        if self.listWidget.selectedItems():
            mods = [item.data(Qt.UserRole)
                    for item in self.listWidget.selectedItems()]
            self.PerformOperation(enable, (mods))

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
                f'path = {{BCML: DON\'T TOUCH}}/{result["name"]}',
                'description = {}'.format(result['description'].replace('\n', ' ')),
                'version = 4'
            ]
            if result['image']:
                rules.append(f'image = {result["image"]}')
            if result['url']:
                rules.append(f'url = {result["url"]}')
            (result['folder'] / 'rules.txt').write_text('\n'.join(rules), encoding='utf-8')
            install.create_bnp_mod(
                mod=result['folder'],
                output=result['output'],
                options=result['options']
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
        self._options = {
            'disable': [],
            'options': {}
        }
        super(InstallDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)
        self.btnAddFile.clicked.connect(self.AddFileClicked)
        self.btnAddFolder.clicked.connect(self.AddFolderClicked)
        self.btnRemove.clicked.connect(self.RemoveClicked)
        self.btnClear.clicked.connect(self.ClearClicked)
        self.btnAdvanced.clicked.connect(self.AdvancedClicked)
        self.spnPriority.setValue(install.get_next_priority())

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

    def AdvancedClicked(self):
        self._options = OptionsDialog(self).get_options()

    def GetResult(self):
        if self.exec_() == QtWidgets.QDialog.Accepted:
            paths = [self.lstQueue.item(i).data(Qt.UserRole)
                     for i in range(self.lstQueue.count())]
            return {
                'paths': paths,
                'insert_priority': self.spnPriority.value(),
                'options': self._options
            }

# Options Dialog


class OptionsDialog(QtWidgets.QDialog, Ui_OptionsDialog):

    def __init__(self, *args, **kwargs):
        super(OptionsDialog, self).__init__()
        self.setupUi(self)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)

    def get_options(self) -> dict:
        if self.exec_():
            options = {
                'disable': []
            }
            for widget in self.checkboxes:
                if hasattr(widget, 'disable_name') and widget.isChecked():
                    options['disable'].append(widget.disable_name)
                if hasattr(widget, 'option_name'):
                    if not widget.merger in options:
                        options[widget.merger] = {}
                    options[widget.merger][widget.option_name] = widget.isChecked()
            return options
        else:
            return {}

# Package Dialog


class PackageDialog(QtWidgets.QDialog, Ui_PackageDialog):

    def __init__(self, *args, **kwargs):
        # pylint: disable=unused-argument
        super(PackageDialog, self).__init__()
        self.setupUi(self)
        self._options = {}
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(str(util.get_exec_dir() / 'data' / 'bcml.ico')))
        self.setWindowIcon(icon)
        self.btnBrowseContent.clicked.connect(self.BrowseContentClicked)
        self.btnBrowseImg.clicked.connect(self.BrowseImgClicked)
        self.btnAdvanced.clicked.connect(self.AdvancedClicked)

    def BrowseContentClicked(self):
        folder = QFileDialog.getExistingDirectory(
            self, 'Select Mod Folder')
        if folder:
            path = Path(folder)
            if path.name == 'content':
                path = path.parent
            self.txtFolder.setText(str(path.resolve()))
            if (path / 'rules.txt').exists():
                rules = util.RulesParser()
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

    def AdvancedClicked(self):
        self._options = OptionsDialog(self).get_options()

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
            output = QFileDialog.getSaveFileName(
                self,
                'Save Your Mod',
                str(Path.home()),
                'Botw Nano Patch Mod (*.bnp);;7-Zip Archive (*.7z);;All Files (*)'
            )[0]
            if not output:
                return None
            return {
                'name': self.txtName.text().strip(),
                'description': self.txtDescript.toPlainText().strip(),
                'image': self.txtImage.text().strip(),
                'url': self.txtUrl.text().strip(),
                'folder': Path(self.txtFolder.text().strip()),
                'options': self._options,
                'output': Path(output)
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
        try:
            self.txtMlc.setText(str(util.get_mlc_dir()))
        except FileNotFoundError:
            self.txtMlc.setText('')
        self.chkDark.setChecked(util.get_settings_bool('dark_theme'))
        self.chkGuessMerge.setChecked(util.get_settings_bool('guess_merge'))
        self.drpLang.addItems(texts.LANGUAGES)
        self.drpLang.setCurrentText(util.get_settings()['lang'])

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
        dark = util.get_settings_bool('dark_theme')
        if dark != self.chkDark.isChecked():
            util.set_settings_bool('dark_theme', self.chkDark.isChecked())
            if self.chkDark.isChecked():
                QtWidgets.QApplication.instance().setStyleSheet(DARK_THEME)
            else:
                QtWidgets.QApplication.instance().setStyleSheet('')
        util.set_settings_bool('guess_merge', self.chkGuessMerge.isChecked())
        util.get_settings()['lang'] = self.drpLang.currentText()
        util.save_settings()
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
            if hasattr(e, 'error_text'):
                self.error = e.error_text # pylint: disable=no-member
            else:
                self.error = traceback.format_exc(limit=-4)
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


DARK_THEME = """
    QMainWindow, QDialog {
        background-color: #2f3136;
    }

    QMainWindow, QLabel, QGroupBox, QCheckBox {
        color: #eeeeee;
    }

    QStatusBar, QStatusBar QLabel {
        color: #7f8186;
    }

    QStatusBar:item {
        border: 0;
    }

    QPushButton, QToolButton {
        background-color: #1584CD;
        color: #e0e0e0;
    }

    QToolButton {
        padding: 0px 2px;
        border-radius: 2px;
    }

    QPushButton {
        border-radius: 2px;
        padding: 4px 6px;
    }

    QPushButton:disabled, QToolButton:disabled {
        background-color: #4f5b62;
        color: #212121;
    }

    QPushButton:hover, QToolButton:hover {
        background-color: #3899D8;
    }

    QPushButton:focus, QToolButton:focus {
        background-color: #0765A3;
    }

    QGroupBox {
        background-color: #212121;
        border: 1px solid #202225;
        border-radius: 4px;
        padding-top: 8px;
        margin-top: 6px;
    }

    QGroupBox:title {
        subcontrol-origin: margin;
        top: 0;
        left: 12px;
        padding: 0 4px;
    }

    QListWidget {
        background-color: #212121;
        border: 1px solid #202225;
        border-radius: 2px;
        color: #fafafa;
        padding: 0 4px;
    }

    QListWidget:item {
        padding: 4px 0;
    }

    QListWidget:item:alternate {
        background-color: #424242;
    }

    QLineEdit, QPlainTextEdit {
        background-color: #484c52;
        border: 0;
        border-radius: 2px;
        color: #fafafa;
        padding: 2px;
    }    

    QScrollBar:vertical {
        background-color: #212121;
        border: 0;
        width: 10px;
        margin: 0;
    }

    QScrollBar::handle:vertical {
        background: #424242;
        min-height: 0;
    }

    QScrollBar::add-line:vertical {
        border: 0;
        background: #32CC99;
        height: 0;
        subcontrol-position: bottom;
        subcontrol-origin: margin;
    }

    QScrollBar::sub-line:vertical {
        border: 0;
        background: #32CC99;
        height: 0;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }

    QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
        border: 0;
        width: 3px;
        height: 0;
        background: white;
    }

    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    QMenu {
        background-color: #212121;
        color: #fafafa;
    }

    QMenu:item:selected {
        background-color: #424242;
    }
"""

# Main

def uri_validator(x):
    from urllib.parse import urlparse
    try:
        result = urlparse(x)
        return all([result.scheme, result.netloc, result.path])
    except Exception: # pylint: disable=broad-except
        return False


def quit_download():
    del process_args.progress
    raise RuntimeError()


def process_args() -> Path:
    try:
        if Path(sys.argv[1]).exists():
            return Path(sys.argv[1])
    except (WindowsError, OSError):
        if sys.argv[1].startswith('bcml:'):
            try_url = sys.argv[1].replace('bcml:', '').replace('\\', '/')
            if uri_validator(try_url) and 'gamebanana.com' in try_url:
                process_args.progress = QtWidgets.QProgressDialog(
                    'Downloading requested mod...', 'Stop', 0, 0, None
                )
                from tempfile import NamedTemporaryFile
                try:
                    with NamedTemporaryFile('wb', prefix='GameBanana_',
                                            suffix='.bnp', delete=False) as tmp:
                        path = Path(tmp.name)
                    process_args.progress.open()
                    process_args.progress.canceled.connect(quit_download)
                    urllib.request.urlretrieve(try_url, path.resolve(), reporthook=download_progress)
                    process_args.progress.canceled.disconnect()
                    process_args.progress.cancel()
                    return Path(tmp.name)
                except RuntimeError:
                    if hasattr(process_args, 'progress') and process_args.progress:
                        process_args.progress.cancel()
                except Exception as e: # pylint: disable=broad-except
                    if hasattr(process_args, 'progress') and process_args.progress:
                        process_args.progress.cancel()
                    QtWidgets.QMessageBox.warning(
                        None,
                        'Error',
                        f'Failed to download mod from <code>{try_url}</code>. '
                        f'Error details:\n\n{str(e)}'
                    )
            else:
                QtWidgets.QMessageBox.warning(
                    None,
                    'Error',
                    f'The request download <code>{try_url}</code> does not appear to be a valid '
                    'GameBanana URL.'
                )
    return None


def download_progress(count, block_size, total_size):
    QtCore.QCoreApplication.instance().processEvents()
    process_args.progress.setMaximum(total_size)
    process_args.progress.setValue(count * block_size)


def main():
    app = QtWidgets.QApplication([])
    if uhoh:
        QtWidgets.QMessageBox.warning(
            None,
            'Error',
            'BCML requires the latest 64 bit Visual C++ redistributable. Download it here: '
            '<a href="https://aka.ms/vs/16/release/vc_redist.x64.exe">'
            'https://aka.ms/vs/16/release/vc_redist.x64.exe</a>'
        )
        sys.exit(0)
    util.clear_temp_dir()
    util.create_schema_handler()
    ver = platform.python_version_tuple()
    if int(ver[0]) < 3 or (int(ver[0]) >= 3 and int(ver[1]) < 7):
        QtWidgets.QMessageBox.warning(
            None,
            'Error',
            f'BCML requires Python 3.7 or higher, but your Python version is {ver[0]}.{ver[1]}'
        )
        sys.exit(0)

    is_64bits = sys.maxsize > 2**32
    if not is_64bits:
        QtWidgets.QMessageBox.warning(
            None,
            'Error',
            'BCML requires 64 bit Python, but it looks like you\'re running 32 bit.'
        )
        sys.exit(0)
    if util.get_settings_bool('dark_theme'):
        app.setStyleSheet(DARK_THEME)
        if 'Roboto Lt' in QtGui.QFontDatabase().families(QtGui.QFontDatabase.Latin):
            app.setFont(QtGui.QFont('Roboto Lt', 10, weight=QtGui.QFont.DemiBold))
    application = MainWindow()
    try:
        application.show()
        application.SetupChecks()
        if len(sys.argv) > 1:
            parg = process_args()
            if parg:
                application.InstallClicked(parg)
        app.exec_()
    except Exception: # pylint: disable=broad-except
        tb = traceback.format_exc(limit=-2)
        e = util.get_work_dir() / 'error.log'
        QtWidgets.QMessageBox.warning(
            None,
            'Error',
            f'An unexpected error has occured:\n\n{tb}\n\nThe error has been logged to:\n'
            f'{e}\n\nBCML will now close.'
        )
        e.write_text(tb, encoding='utf-8')
    finally:
        util.clear_temp_dir()


if __name__ == "__main__":
    main()
