# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'c:\Users\macad\Documents\Git\BCML-2\.vscode\install.ui',
# licensing of 'c:\Users\macad\Documents\Git\BCML-2\.vscode\install.ui' applies.
#
# Created: Wed Aug 14 19:25:58 2019
#      by: pyside2-uic  running on PySide2 5.12.3
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore, QtGui, QtWidgets


class Ui_InstallDialog(object):
    def setupUi(self, InstallDialog):
        InstallDialog.setObjectName("InstallDialog")
        InstallDialog.setWindowModality(QtCore.Qt.WindowModal)
        InstallDialog.resize(587, 267)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            InstallDialog.sizePolicy().hasHeightForWidth())
        InstallDialog.setSizePolicy(sizePolicy)
        InstallDialog.setModal(True)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(InstallDialog)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.label = QtWidgets.QLabel(InstallDialog)
        self.label.setObjectName("label")
        self.verticalLayout_3.addWidget(self.label)
        self.lstQueue = QtWidgets.QListWidget(InstallDialog)
        self.lstQueue.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.lstQueue.setAlternatingRowColors(True)
        self.lstQueue.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        self.lstQueue.setObjectName("lstQueue")
        self.verticalLayout_3.addWidget(self.lstQueue)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.btnAddFile = QtWidgets.QPushButton(InstallDialog)
        self.btnAddFile.setStyleSheet("padding: 4px 8px;")
        self.btnAddFile.setObjectName("btnAddFile")
        self.horizontalLayout_3.addWidget(self.btnAddFile)
        self.btnAddFolder = QtWidgets.QPushButton(InstallDialog)
        self.btnAddFolder.setStyleSheet("padding: 4px 8px;")
        self.btnAddFolder.setObjectName("btnAddFolder")
        self.horizontalLayout_3.addWidget(self.btnAddFolder)
        self.btnRemove = QtWidgets.QPushButton(InstallDialog)
        self.btnRemove.setStyleSheet("padding: 4px 12px;")
        self.btnRemove.setObjectName("btnRemove")
        self.horizontalLayout_3.addWidget(self.btnRemove)
        self.btnClear = QtWidgets.QPushButton(InstallDialog)
        self.btnClear.setStyleSheet("padding: 4px 12px;")
        self.btnClear.setObjectName("btnClear")
        self.horizontalLayout_3.addWidget(self.btnClear)
        self.verticalLayout_3.addLayout(self.horizontalLayout_3)
        self.horizontalLayout_2.addLayout(self.verticalLayout_3)
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.groupBox = QtWidgets.QGroupBox(InstallDialog)
        self.groupBox.setObjectName("groupBox")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setSpacing(4)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.chkRstbShrink = QtWidgets.QCheckBox(self.groupBox)
        self.chkRstbShrink.setObjectName("chkRstbShrink")
        self.verticalLayout_2.addWidget(self.chkRstbShrink)
        self.chkRstbGuess = QtWidgets.QCheckBox(self.groupBox)
        self.chkRstbGuess.setObjectName("chkRstbGuess")
        self.verticalLayout_2.addWidget(self.chkRstbGuess)
        self.chkEnableDeepMerge = QtWidgets.QCheckBox(self.groupBox)
        self.chkEnableDeepMerge.setObjectName("chkEnableDeepMerge")
        self.verticalLayout_2.addWidget(self.chkEnableDeepMerge)
        self.chkRstbLeave = QtWidgets.QCheckBox(self.groupBox)
        self.chkRstbLeave.setObjectName("chkRstbLeave")
        self.verticalLayout_2.addWidget(self.chkRstbLeave)
        self.chkDisablePack = QtWidgets.QCheckBox(self.groupBox)
        self.chkDisablePack.setObjectName("chkDisablePack")
        self.verticalLayout_2.addWidget(self.chkDisablePack)
        self.chkDisableTexts = QtWidgets.QCheckBox(self.groupBox)
        self.chkDisableTexts.setObjectName("chkDisableTexts")
        self.verticalLayout_2.addWidget(self.chkDisableTexts)
        self.chkDisableActorInfo = QtWidgets.QCheckBox(self.groupBox)
        self.chkDisableActorInfo.setObjectName("chkDisableActorInfo")
        self.verticalLayout_2.addWidget(self.chkDisableActorInfo)
        self.chkDisableGamedata = QtWidgets.QCheckBox(self.groupBox)
        self.chkDisableGamedata.setObjectName("chkDisableGamedata")
        self.verticalLayout_2.addWidget(self.chkDisableGamedata)
        self.chkDisableMap = QtWidgets.QCheckBox(self.groupBox)
        self.chkDisableMap.setObjectName("chkDisableMap")
        self.verticalLayout_2.addWidget(self.chkDisableMap)
        self.verticalLayout.addWidget(self.groupBox)
        self.buttonBox = QtWidgets.QDialogButtonBox(InstallDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)
        self.horizontalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(InstallDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(
            "accepted()"), InstallDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(
            "rejected()"), InstallDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(InstallDialog)

    def retranslateUi(self, InstallDialog):
        InstallDialog.setWindowTitle(QtWidgets.QApplication.translate(
            "InstallDialog", "Mod Install", None, -1))
        self.label.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Mod(s) to install ", None, -1))
        self.btnAddFile.setToolTip(QtWidgets.QApplication.translate(
            "InstallDialog", "Browse for a mod", None, -1))
        self.btnAddFile.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Add Mod File...", None, -1))
        self.btnAddFolder.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Add Mod Folder...", None, -1))
        self.btnRemove.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Remove", None, -1))
        self.btnClear.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Clear All", None, -1))
        self.groupBox.setTitle(QtWidgets.QApplication.translate(
            "InstallDialog", "Advanced Install Options", None, -1))
        self.chkRstbShrink.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Shrink RSTB values where possible", None, -1))
        self.chkRstbGuess.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Estimate complex RSTB values", None, -1))
        self.chkEnableDeepMerge.setToolTip(QtWidgets.QApplication.translate(
            "InstallDialog", "Deep merge attempts to merge changes made to individual AAMP files. This can be a powerful tool to resolve conflicts but might cause unexpected bugs or issues. ", None, -1))
        self.chkEnableDeepMerge.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Disable deep merge", None, -1))
        self.chkRstbLeave.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Don\'t remove complex RSTB entries", None, -1))
        self.chkDisablePack.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Don\'t merge pack files", None, -1))
        self.chkDisableTexts.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Don\'t merge game texts", None, -1))
        self.chkDisableActorInfo.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Don\'t merge actor info", None, -1))
        self.chkDisableGamedata.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Don\'t merge game/save data", None, -1))
        self.chkDisableMap.setText(QtWidgets.QApplication.translate(
            "InstallDialog", "Don\'t merge map units", None, -1))
