import sys
import logging
import os
import data_manager

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic
from PyQt5.QAxContainer import *
from PyQt5.QtGui import *

form_class = uic.loadUiType("DL.ui")[0]

########################################################################################################################
# 메인 윈도우, 폼 출력
########################################################################################################################
class MyWindow(QMainWindow, form_class):

    def __init__(self): #생성자 : 클래스 객체가 생성될 때 자동으로 호출되는 함수
        super().__init__()  #클래스 초기화 값 상속
        self.setupUi(self)  # Load the MainFrame(form)

        self.pushButton.clicked.connect(self._pre_process)
        self.pushButton.clicked.connect(self._reinference_learn)

    def _reinference_learn(self):
        pass

    def _pre_process(self):
        chart_data = data_manager.load_chart_data('test.csv')
        print("chart_data:", chart_data.head())

        prep_data = data_manager.preprocess(chart_data)
        print("prep_data:", prep_data)

        training_data = data_manager.build_training_data(prep_data)
        print("training_data:", training_data)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = MyWindow()
    myWindow.show()
    app.exec_()
