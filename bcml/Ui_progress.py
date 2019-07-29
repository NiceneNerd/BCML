# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'c:\Users\macad\Documents\Git\BCML-2\.vscode\progress.ui',
# licensing of 'c:\Users\macad\Documents\Git\BCML-2\.vscode\progress.ui' applies.
#
# Created: Fri Jul 26 21:54:50 2019
#      by: pyside2-uic  running on PySide2 5.12.3
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore, QtGui, QtWidgets

class Ui_dlgProgress(object):
    def setupUi(self, dlgProgress):
        dlgProgress.setObjectName("dlgProgress")
        dlgProgress.setWindowModality(QtCore.Qt.WindowModal)
        dlgProgress.resize(400, 80)
        dlgProgress.setMinimumSize(QtCore.QSize(400, 80))
        dlgProgress.setMaximumSize(QtCore.QSize(400, 80))
        dlgProgress.setModal(True)
        self.verticalLayout = QtWidgets.QVBoxLayout(dlgProgress)
        self.verticalLayout.setObjectName("verticalLayout")
        self.progressBar = QtWidgets.QProgressBar(dlgProgress)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.progressBar.sizePolicy().hasHeightForWidth())
        self.progressBar.setSizePolicy(sizePolicy)
        self.progressBar.setMaximum(0)
        self.progressBar.setProperty("value", -1)
        self.progressBar.setTextVisible(False)
        self.progressBar.setObjectName("progressBar")
        self.verticalLayout.addWidget(self.progressBar)
        self.lblProgress = QtWidgets.QLabel(dlgProgress)
        self.lblProgress.setObjectName("lblProgress")
        self.verticalLayout.addWidget(self.lblProgress)

        self.retranslateUi(dlgProgress)
        QtCore.QMetaObject.connectSlotsByName(dlgProgress)

    def retranslateUi(self, dlgProgress):
        dlgProgress.setWindowTitle(QtWidgets.QApplication.translate("dlgProgress", "BCML Operation in Progress", None, -1))
        self.lblProgress.setText(QtWidgets.QApplication.translate("dlgProgress", "...", None, -1))

