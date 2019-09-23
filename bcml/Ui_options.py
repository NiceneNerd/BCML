# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'c:\Users\macad\Documents\Git\BCML-2\.vscode\options.ui',
# licensing of 'c:\Users\macad\Documents\Git\BCML-2\.vscode\options.ui' applies.
#
# Created: Thu Sep 12 14:31:57 2019
#      by: pyside2-uic  running on PySide2 5.13.0
#
# WARNING! All changes made in this file will be lost!

from bcml import mergers
from PySide2 import QtCore, QtGui, QtWidgets

class Ui_OptionsDialog(object):
    def setupUi(self, OptionsDialog):
        OptionsDialog.setObjectName("OptionsDialog")
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(OptionsDialog.sizePolicy().hasHeightForWidth())
        OptionsDialog.setSizePolicy(sizePolicy)
        self.verticalLayout = QtWidgets.QVBoxLayout(OptionsDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(OptionsDialog)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.checkboxes = []
        for merger_class in mergers.get_mergers():
            merger = merger_class()
            chkMerger = QtWidgets.QCheckBox(OptionsDialog)
            chkMerger.setObjectName('chkDisable' + merger.NAME)
            chkMerger.setText('Disable ' + merger.friendly_name())
            setattr(chkMerger, 'disable_name', merger.NAME)
            self.verticalLayout.addWidget(chkMerger)
            self.checkboxes.append(chkMerger)
            for option in merger.get_checkbox_options():
                chkOption = QtWidgets.QCheckBox(OptionsDialog)
                chkOption.setObjectName('chk' + merger.NAME + option[0])
                setattr(chkOption, 'option_name', option[0])
                setattr(chkOption, 'merger', merger.NAME)
                chkOption.setText(option[1])
                self.verticalLayout.addWidget(chkOption)
                self.checkboxes.append(chkOption)
        self.buttonBox = QtWidgets.QDialogButtonBox(OptionsDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(OptionsDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), OptionsDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), OptionsDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(OptionsDialog)

    def retranslateUi(self, OptionsDialog):
        OptionsDialog.setWindowTitle(QtWidgets.QApplication.translate("OptionsDialog", "Advanced Options", None, -1))
        self.label.setText(QtWidgets.QApplication.translate("OptionsDialog", "Select Advanced Mod Options", None, -1))

