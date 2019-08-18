# pylint: skip-file

from PySide2 import QtCore, QtGui, QtWidgets

class Ui_ProgressDialog(object):
    def setupUi(self, ProgressDialog):
        ProgressDialog.setObjectName("ProgressDialog")
        ProgressDialog.resize(400, 80)
        ProgressDialog.setMinimumSize(QtCore.QSize(400, 80))
        ProgressDialog.setMaximumSize(QtCore.QSize(400, 80))
        self.verticalLayout = QtWidgets.QVBoxLayout(ProgressDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.progressBar = QtWidgets.QProgressBar(ProgressDialog)
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
        self.lblProgress = QtWidgets.QLabel(ProgressDialog)
        self.lblProgress.setObjectName("lblProgress")
        self.verticalLayout.addWidget(self.lblProgress)

        self.retranslateUi(ProgressDialog)
        QtCore.QMetaObject.connectSlotsByName(ProgressDialog)

    def retranslateUi(self, ProgressDialog):
        ProgressDialog.setWindowTitle(QtWidgets.QApplication.translate("ProgressDialog", "BCML Operation in Progress", None, -1))
        self.lblProgress.setText(QtWidgets.QApplication.translate("ProgressDialog", "...", None, -1))

