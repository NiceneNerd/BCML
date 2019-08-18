# pylint: skip-file

from PySide2 import QtCore, QtGui, QtWidgets

class Ui_PackageDialog(object):
    def setupUi(self, PackageDialog):
        PackageDialog.setObjectName("PackageDialog")
        PackageDialog.setWindowModality(QtCore.Qt.WindowModal)
        PackageDialog.resize(562, 283)
        PackageDialog.setModal(False)
        self.verticalLayout = QtWidgets.QVBoxLayout(PackageDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.groupBox = QtWidgets.QGroupBox(PackageDialog)
        self.groupBox.setObjectName("groupBox")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.formLayout = QtWidgets.QFormLayout()
        self.formLayout.setObjectName("formLayout")
        self.label = QtWidgets.QLabel(self.groupBox)
        self.label.setObjectName("label")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label)
        self.txtName = QtWidgets.QLineEdit(self.groupBox)
        self.txtName.setObjectName("txtName")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.txtName)
        self.label1 = QtWidgets.QLabel(self.groupBox)
        self.label1.setObjectName("label1")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label1)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.txtFolder = QtWidgets.QLineEdit(self.groupBox)
        self.txtFolder.setObjectName("txtFolder")
        self.horizontalLayout_3.addWidget(self.txtFolder)
        self.btnBrowseContent = QtWidgets.QPushButton(self.groupBox)
        self.btnBrowseContent.setStyleSheet("padding: 3px 6px;")
        self.btnBrowseContent.setObjectName("btnBrowseContent")
        self.horizontalLayout_3.addWidget(self.btnBrowseContent)
        self.formLayout.setLayout(2, QtWidgets.QFormLayout.FieldRole, self.horizontalLayout_3)
        self.label_2 = QtWidgets.QLabel(self.groupBox)
        self.label_2.setObjectName("label_2")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.label_2)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.txtImage = QtWidgets.QLineEdit(self.groupBox)
        self.txtImage.setObjectName("txtImage")
        self.horizontalLayout_2.addWidget(self.txtImage)
        self.btnBrowseImg = QtWidgets.QPushButton(self.groupBox)
        self.btnBrowseImg.setStyleSheet("padding: 3px 6px;")
        self.btnBrowseImg.setObjectName("btnBrowseImg")
        self.horizontalLayout_2.addWidget(self.btnBrowseImg)
        self.formLayout.setLayout(3, QtWidgets.QFormLayout.FieldRole, self.horizontalLayout_2)
        self.label_3 = QtWidgets.QLabel(self.groupBox)
        self.label_3.setObjectName("label_3")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.LabelRole, self.label_3)
        self.txtUrl = QtWidgets.QLineEdit(self.groupBox)
        self.txtUrl.setObjectName("txtUrl")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.FieldRole, self.txtUrl)
        self.label_4 = QtWidgets.QLabel(self.groupBox)
        self.label_4.setObjectName("label_4")
        self.formLayout.setWidget(5, QtWidgets.QFormLayout.LabelRole, self.label_4)
        self.txtDescript = QtWidgets.QPlainTextEdit(self.groupBox)
        self.txtDescript.setObjectName("txtDescript")
        self.formLayout.setWidget(6, QtWidgets.QFormLayout.SpanningRole, self.txtDescript)
        self.verticalLayout_2.addLayout(self.formLayout)
        self.horizontalLayout.addWidget(self.groupBox)
        self.groupBox_2 = QtWidgets.QGroupBox(PackageDialog)
        self.groupBox_2.setObjectName("groupBox_2")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.groupBox_2)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.chkRstbShrink = QtWidgets.QCheckBox(self.groupBox_2)
        self.chkRstbShrink.setObjectName("chkRstbShrink")
        self.verticalLayout_3.addWidget(self.chkRstbShrink)
        self.chkRstbGuess = QtWidgets.QCheckBox(self.groupBox_2)
        self.chkRstbGuess.setObjectName("chkRstbGuess")
        self.verticalLayout_3.addWidget(self.chkRstbGuess)
        self.chkEnableDeepMerge = QtWidgets.QCheckBox(self.groupBox_2)
        self.chkEnableDeepMerge.setObjectName("chkEnableDeepMerge")
        self.verticalLayout_3.addWidget(self.chkEnableDeepMerge)
        self.chkRstbLeave = QtWidgets.QCheckBox(self.groupBox_2)
        self.chkRstbLeave.setObjectName("chkRstbLeave")
        self.verticalLayout_3.addWidget(self.chkRstbLeave)
        self.chkDisablePack = QtWidgets.QCheckBox(self.groupBox_2)
        self.chkDisablePack.setObjectName("chkDisablePack")
        self.verticalLayout_3.addWidget(self.chkDisablePack)
        self.chkDisableTexts = QtWidgets.QCheckBox(self.groupBox_2)
        self.chkDisableTexts.setObjectName("chkDisableTexts")
        self.verticalLayout_3.addWidget(self.chkDisableTexts)
        self.chkDisableActorInfo = QtWidgets.QCheckBox(self.groupBox_2)
        self.chkDisableActorInfo.setObjectName("chkDisableActorInfo")
        self.verticalLayout_3.addWidget(self.chkDisableActorInfo)
        self.chkDisableGamedata = QtWidgets.QCheckBox(self.groupBox_2)
        self.chkDisableGamedata.setObjectName("chkDisableGamedata")
        self.verticalLayout_3.addWidget(self.chkDisableGamedata)
        self.chkDisableMap = QtWidgets.QCheckBox(self.groupBox_2)
        self.chkDisableMap.setObjectName("chkDisableMap")
        self.verticalLayout_3.addWidget(self.chkDisableMap)
        self.horizontalLayout.addWidget(self.groupBox_2)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.buttonBox = QtWidgets.QDialogButtonBox(PackageDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(PackageDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), PackageDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), PackageDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(PackageDialog)

    def retranslateUi(self, PackageDialog):
        PackageDialog.setWindowTitle(QtWidgets.QApplication.translate("PackageDialog", "Create Nano Patch Mod Package", None, -1))
        self.groupBox.setTitle(QtWidgets.QApplication.translate("PackageDialog", "Mod Info", None, -1))
        self.label.setText(QtWidgets.QApplication.translate("PackageDialog", "Name:", None, -1))
        self.label1.setText(QtWidgets.QApplication.translate("PackageDialog", "Mod folder:", None, -1))
        self.btnBrowseContent.setText(QtWidgets.QApplication.translate("PackageDialog", "Browse...", None, -1))
        self.label_2.setText(QtWidgets.QApplication.translate("PackageDialog", "Image (optional):", None, -1))
        self.btnBrowseImg.setText(QtWidgets.QApplication.translate("PackageDialog", "Browse...", None, -1))
        self.label_3.setText(QtWidgets.QApplication.translate("PackageDialog", "URL (optional):", None, -1))
        self.label_4.setText(QtWidgets.QApplication.translate("PackageDialog", "Description:", None, -1))
        self.groupBox_2.setTitle(QtWidgets.QApplication.translate("PackageDialog", "Advanced Options", None, -1))
        self.chkRstbShrink.setText(QtWidgets.QApplication.translate("PackageDialog", "Shrink RSTB values where possible", None, -1))
        self.chkRstbGuess.setText(QtWidgets.QApplication.translate("PackageDialog", "Estimate complex RSTB values", None, -1))
        self.chkEnableDeepMerge.setToolTip(QtWidgets.QApplication.translate("PackageDialog", "Deep merge attempts to merge changes made to individual AAMP files. This can be a powerful tool to resolve conflicts but might cause unexpected bugs or issues. ", None, -1))
        self.chkEnableDeepMerge.setText(QtWidgets.QApplication.translate("PackageDialog", "Disable deep merge", None, -1))
        self.chkRstbLeave.setText(QtWidgets.QApplication.translate("PackageDialog", "Don\'t remove complex RSTB entries", None, -1))
        self.chkDisablePack.setText(QtWidgets.QApplication.translate("PackageDialog", "Don\'t merge pack files", None, -1))
        self.chkDisableTexts.setText(QtWidgets.QApplication.translate("PackageDialog", "Don\'t merge game texts", None, -1))
        self.chkDisableActorInfo.setText(QtWidgets.QApplication.translate("PackageDialog", "Don\'t merge actor info", None, -1))
        self.chkDisableGamedata.setText(QtWidgets.QApplication.translate("PackageDialog", "Don\'t merge game/save data", None, -1))
        self.chkDisableMap.setText(QtWidgets.QApplication.translate("PackageDialog", "Don\'t merge map units", None, -1))
