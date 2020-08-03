"""
########################################################################################################################
QtDesigner로 만든 UI와 해당 UI의 위젯에서 발생하는 이벤트를 컨트롤하는 클래스
author: Jung.Byung.Woo.
# 2020.1.18 : 전체청산 요청(시장가 매도) 메서드 추가
# 2020.1.21 : 매수방법 교체(realdata 안에서 매수하지 않고 time 이벤트에 의해 매수)
# 2020.1.31 : 버그 수정(조건검색하지 않고 자동매매 클릭 시 문제)
# 2020.2.01 :
    1. api TR조회 제한에 따른 프로그램 정지 문제 (앞으로 해결 해야할 문제)
    2. QlistWidget에 문자열을 추가할 때 일정시간 지나면 프로그램 정지(QlistWidget의 문자열 제한이 있는 듯)
         해결방법 :: 문자열 clear() 추가
    3. 1초 5회 미만, 일 3,000~4,000회 사이 제한 error 발생
# 2020.2.02 : api TR조회 제한에 따른 프로그램 정지 문제 해결을 위해서 OnReceiveChejanData를 활용
    1. 처음 프로그램이 실행되면 잔고현황 조회 :: 1)예수금, 2)주식잔고, 3)매수체결현황, 4)매도체결현황을 조회한 후 보류
    2. OnReceiveChejanData에서 1)매수체결, 2)매도체결이 될 때 타이머 이벤트가 작동하여 잔고(미체결포함) 현황 업데이트
# 2020.2.5 : (실시간 로스컷 매도방법 문제) 실시간 잔고 종목에 대하여 매도할 때 중복 주문이 되어 과도한 주문요청 문제점 발생
# 2020.2.9 :
    0. self.real_account_estimated 전체를 순차적으로 조사하여 매도하는 방식에서 -> OnReceiveRealData에 수신된 실시간
    주문체결 코드를 조사하여 실시간 매도하는 것으로 변경
    1. 실시간 로스컷 매도방법 수정테스트 : 잔고조회 -> 조건확인(부합여부) -> self.busy_sell_stock_list에 코드 플래그 조사
    2. 플래그가 가능하면 해당종목 매도 주문, 해당종목 busy 처리
    3. OnreceiveChejanData에 접수, 체결, 잔고 확인 -> 잔고가 업데이트 되며, 해당종목 self.busy_sell_stock_list의 busy 해제
# 2020.2.18 :
    1. 조건 검색 종목에 대하여 매도 주문하지 않도록 처리
    2.매수주문 dic과 잔고 dic에 코드 있으면, 매입 제한 하고 있으나, 매수 하면, self.real_account_estimated(잔고 딕셔너리)를
    60초에 1회 업데이트 하면 -> *문제점 : 시장가 매입시 잔고dic 업데이트가 되지 않아 사고팚고가 수차례 되풀이 되는 문제 발생
    =====>>> 해결방안 : self.real_account_estimated를 chejan과 연계하여 실시간으로 업데이트가 필요
# 2020.2.26 :
    1. 조건검색 편입 종목이 self.real_condition에 업데이트 되지 않는 것 해결
    2. 중복 매수되는 것 해결
    3. 전체 청산 시 랙 걸리는 문제 발견 ==> 추후 해결책 보완 필요********
# 2020.3.4 :
    1. 60초에 self.busy_sell_stock_list.clear()추가로 매도 안되는 문제 해결
    2. 화면 수정
# 2020.3.16 :
    1. 지정가 매도(익절/손절) 추가, 시장가 매도(손절) 수식 오류 수정
    2. 트레일링 매도 기법 적용을 위한 방법 강구 : self.real_account_estimated에 플래그를 추가
# 2020.3.20 :
    1. 잔고 리스트 플래그 포함하여 불러오기 추가
# 2020.3.21 :
    1. 트레일링 매도 적용
    2. 로그인 시 대기방법 수정
    3. 보유종목 바로 매도 가능토록 추가(클릭 시 매도 창)  ==> 실시간 매도 시 처리 안되는 문제 발생
# 2020.3.30 :
    1. 시장가 매수 시 보유하고 있음에도 매수되는 버그(실시간 잔고가 바로 처리되지 않기때문에 발생)
        :: (개선해야할 사항) 매수체결조회, 매도체결조회, 체잔 등과 상호 비교 및 데이터 업데이트를 통해 현행화
        :: self.busy_buy_stock_code_list = []를 활용하여 보유, 실시간 매수 종목에 대하여 업데이트
# 2020.4.1 :
    1. 다양한 매수방법 case 포함
    2. 15분봉 매수 기법 포함(시간에 따른 매매)
# 2020.4.2 :
    1. def _auto_select_condition(self): 조건식 자동선택 초기화
    2. 매도 시 트레일링 상태 표시 문제 발견

########################################################################################################################
"""

import sys
import sqlite3 as sq
import time
import re
import copy
from pandas import DataFrame
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic
from PyQt5.QAxContainer import *
from PyQt5.QtGui import *
from PyQt5.QtCore import pyqtSlot

form_class = uic.loadUiType("DL.ui")[0]

########################################################################################################################
# 메인 윈도우, 폼 출력
########################################################################################################################
class MyWindow(QMainWindow, form_class):
    # 생성자
    def __init__(self):

        super().__init__()

        self.dict_stock = {}
        self.dict_kospi = {}
        self.dict_kosdaq = {}

        # 시간 초기화
        start = time.time()

        # 금일 매수 종목 수
        # 프로그램을 재실행하더라도 금일 체결한 종목 수 업데이트 필요
        self.today_stock_count = 0

        # trdata event count
        self.count_trdata_event = 0

        # 조건검색 후 실시간 종목 편입 이탈 딕셔너리
        self.condition_search_stock = {}

        # 실시간 주식잔고 딕셔너리
        self.real_account_estimated = {}

        # 매도 종목이 현재 매도 접수하여 진행 중인지 여부 확인 하는 플래그
        self.busy_sell_stock_code_list = []

        # 매수 종목(보유종목, 매수주문종목)인지 여부를 확인하는 플래그(코드리스트 저장)
        # self.real_account_estimated = {}의 잔고 코드, 실시간 CHEJAN의 정보를 실시간으로 업데이트
        self.busy_buy_stock_code_list = []

        # 매수 시 매수금지리스트에 코드를 추가
        # 매수금지리스트 self.forbid_buy_temp는 매수주문 시 코드 추가, 매도 시 코드 삭제, 매수취소주문 시 코드 삭제
        self.forbid_buy_temp = []

        # 실시간 조건식에 따른 종목 편입종목의 코드를 저장
        self.real_insert_stock_list = []

        # 매수 체결 미체결 현황 딕셔너리
        self.buy_and_nobuy = {}
        # 매수 미체결 현황 딕셔너리
        self.no_buy = {}
        # 매수 체결 현황 딕셔너리
        self.end_buy = {}

        # 매도 체결 미체결 현황 딕셔너리
        self.sell_and_nosell = {}

        #실시간 CHEJAN
        self.jumun_chegyul_dic = {}
        self.chejan_dic = {}

        # 주문번호 : OnReceiveTrData 이벤트로 주문번호를 얻고, 주문후 이 이벤트에서 주문번호가 ''공백으로 전달되면, 주문접수 실패
        self.orderNo = ""

        # 홀수 / 짝수 flag  :: 0이면 odd, 1이면 even
        self.odd_even_flag = 0

        # button flag
        self.current_time_compare = "0959"

        # 매수를 위한 종목 수 카운트
        self.count_buy_flag = 0

        # 매도를 위한 종목 수 카운트
        self.count_sell_flag = 0

        self.setupUi(self)                                      # Load the MainFrame(form)
        self.KW_API = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")    # Create Kiwoom instance
        self.KW_API.dynamicCall("CommConnect")                  # Load the Login form

        # 자동매매 조건 설정 초기값 불러오기
        self._init_load_auto_set_data()

        # # 15.0초 -> 1.0초 타이머 이벤트 : 초기 시간 지연 설정
        self.timer_check = QTimer(self)
        # self.timer_check.start(1000*15)
        #
        # # 2.0초 매수 이벤트 : 타이머
        self.timer_buy_sell = QTimer(self)
        #
        # # 60.0초 타이머(60초 마다 이벤트 발생)
        self.timer_60s = QTimer(self)
        # self.timer_60s.start(1000 * 60)

        # self._make_table()

        # Signal & slots(이벤트 핸들러) 타이머
        self.timer_buy_sell.timeout.connect(self._timer_buy_sell)
        self.timer_check.timeout.connect(self._timer_check)
        self.timer_60s.timeout.connect(self._timer_60s)

        # 제일먼저 실행 1번 : CommConnect 요청에 따른 응답 event
        self.KW_API.OnEventConnect.connect(self._event_connect)
        # 종목조회 실시간 응답
        self.KW_API.OnReceiveRealData.connect(self._receive_real_data)
        # 계좌, 종목조회 기타 등등 : CommRqData 함수 호출 -> OnReceiveTrData 응답
        self.KW_API.OnReceiveTrData.connect(self._receive_trdata)       
        # 체결주문/잔고
        self.KW_API.OnReceiveChejanData.connect(self._receiveChejanData)
        # 메시지 이벤트 출력
        self.KW_API.OnReceiveMsg.connect(self._receiveMsg)

        self.pushButton_2.clicked.connect(self._stock_search)           # 종목조회 버튼 클릭
        self.pushButton_4.clicked.connect(self._order_buysell)              # 매수매도 주문하기
        self.pushButton_3.clicked.connect(self._check_buy_order)        # 매수 체결 조회
        self.pushButton_7.clicked.connect(self._check_sell_order)           # 매도 체결 조회
        self.pushButton_10.clicked.connect(self._sell_all_stock)        # 전체 청산 주문
        self.pushButton_8.clicked.connect(self._real_check_balance)         # 실시간 매매
        self.pushButton_11.clicked.connect(self._condition_search_stop)     # 조건식 Stop

        self.KW_API.OnReceiveConditionVer.connect(self._receive_condition_ver)  # 조건식 이름 불러오기
        self.KW_API.OnReceiveTrCondition.connect(self._receive_trcondition)     # 조건식 종목리스트 불러오기
        self.KW_API.OnReceiveRealCondition.connect(self._receive_real_condition) #조건식 실시간 종목리스트

        self.tableWidget_4.cellClicked.connect(self._condition_search)      # 조건식에 부합된 종목들 불러오기
        self.tableWidget_5.cellClicked.connect(self._selected_check_balance)  # 잔고현황 선택 셀  ==> 수동 매도 주문하기

        self.pushButton_6.clicked.connect(self._init_load_auto_set_data)        # 자동주문 설정 값 불러오기
        self.pushButton_5.clicked.connect(self._save_auto_set_data)         # 자동주문 설정 값 저장하기

        self.checkBox_8.stateChanged.connect(self._display_order_set)       # 매매창 호가창 표시

        self.radioButton_7.clicked.connect(self._auto_select_condition)
        self.radioButton_8.clicked.connect(self._auto_select_condition)
        self.radioButton_9.clicked.connect(self._auto_select_condition)
        self.radioButton_10.clicked.connect(self._auto_select_condition)
        self.radioButton_11.clicked.connect(self._auto_select_condition)
        self.checkBox_7.stateChanged.connect(self._auto_select_condition)
        self.checkBox_11.stateChanged.connect(self._auto_select_condition)
        self.checkBox_12.stateChanged.connect(self._auto_select_condition)
        self.checkBox_9.stateChanged.connect(self._auto_select_condition)
        self.checkBox_14.stateChanged.connect(self._auto_select_condition)

    def _timer_60s(self):
        self.timer_check.start(1000)

    # 타이머 OUT : # 초기 20초가 될때까지는 잔고 / 체결 조회하지 않음  // 3초에 한번씩 잔고조회, 매수체결, 매도체결 조회 실시
    def _timer_check(self):

        if not self.checkBox_2.isChecked():
            return

        if self.odd_even_flag == 0:
            self.odd_even_flag = 1
            self.timer_check.stop()
            # 2초 마다 자산 / 잔고 / 매수 / 매도 체결 조회
            self.timer_check.start(2000)
            self.timer_buy_sell.start(1000)

        elif self.odd_even_flag == 1:
            self.odd_even_flag = 2
            # To Do:: 실시간 자산 조회 (업데이트) :: 실시간계좌평가잔고내역요청 opw00018
            # ['총매입금액', '총평가금액', '총평가손익금액', '총수익률(%)', '추정예탁자산']
            self._real_check_account()
            self.listWidget_4.clear()

        elif self.odd_even_flag == 2:
            self.odd_even_flag = 3

            # 변수 초기화
            self.busy_buy_stock_code_list.clear()

            # To Do:: 실시간 잔고 조회 (업데이트) :: <<계좌평가현황요청>>  opw00004
            # ['종목코드', '종목명', '평균단가', '보유수량', '현재가', '매입금액', '손익금액', '손익율']
            # self.real_acount_estimated ={}에 저장
            self._real_check_balance()
            self.busy_sell_stock_code_list.clear()

            # 중복된 매수주문을 금지하기 위하여 이미 잔고 종목을 self.busy_buy_stock_code_list에 저장
            code_list_temp = [key_code for key_code in self.real_account_estimated]
            self.busy_buy_stock_code_list = self.busy_buy_stock_code_list + code_list_temp
            print("self.busy_buy_stock_code_list", self.busy_buy_stock_code_list)
            code_list_temp.clear()

        elif self.odd_even_flag == 3:
            self.odd_even_flag = 4
            # To Do:: 실시간 매수 체결 조회 (업데이트)
            # self.KW_API.dynamicCall("CommRqData(QString, QString, QString, QString)", "실시간매수체결미체결", "opt10075", 0, "7500")
            # ['종목코드', '종목명', '시간', '매매구분', '주문수량', '주문가격', '체결량', '체결가',
            #  '체결누계금액', '현재가', '미체결수량', '주문번호', '주문상태', '주문구분', '원주문번호']
            self._check_buy_order()

            code_list_temp = [key_code for key_code in self.no_buy]
            self.busy_buy_stock_code_list = self.busy_buy_stock_code_list + code_list_temp
            print("self.busy_buy_stock_code_list", self.busy_buy_stock_code_list)
            code_list_temp.clear()

        elif self.odd_even_flag == 4:
            self.odd_even_flag = 5
            # To Do:: 종목조회(업데이트) ::
            # OnReceiveRealData에서 매도 가능한 보유종목이 실시간 조회가 가능하도록 종목 조회
            self._all_balance_search()

        elif self.odd_even_flag == 5:
            self.odd_even_flag = 6
            # To Do:: 당일 실현 손익
            self._today_balance_check()

        else:
            self.odd_even_flag = 1
            # To Do:: 실시간 매도 체결 조회 (업데이트)
            self._check_sell_order()
            self.timer_check.stop()       # 1사이클 타이머 동작 후 타이머 정지

    # 매수 매도 타이머 메서도 호출  :: 매수와 매도가 자동으로 될 수 있도록 일정 시간 마다 이벤트 실행
    def _timer_buy_sell(self):
        self._buy_timer()
        self._sell_timer()
        # self.timer_2.stop()

    # 매도 이벤트 : 타이머
    def _sell_timer(self):

        # 자동매매 설정에 따른 실행 여부
        if not self.checkBox_3.isChecked():
            return

        # 당일 청산 여부 (체크 시 당일 청산)
        if not self.checkBox_6.isChecked():
            return

        # 보유 종목 코드 저장 및 갯수 확인
        code_stock = [key_code for key_code in self.real_account_estimated]
        count = len(code_stock)

        # 보유한 종목이 없으면, 종료
        if count == 0:
            self.count_sell_flag = 0
            return

        # 매도 주문하였으나 미체결 된 종목 코드 리스트 찾기
        keys_nosell = []  # 미체결 종목 코드 저장
        for codename in self.sell_and_nosell.keys():
            all_sell_order = self.sell_and_nosell.get(codename)
            if all_sell_order[10] == "접수":
                keys_nosell.append(codename)

        # 매도 형식 지정
        account_num = self.comboBox.currentText()
        order_type_lookup = {'신규매수': 1, '신규매도': 2, '매수취소': 3, '매도취소': 4}
        hoga_lookup = {'지정가': "00", '시장가': "03"}
        order_type = "신규매도"
        sell_type = "지정가"

        # 청산 요청 시간 범위 안이면, 지정가 청산
        if QTime.currentTime() > self.timeEdit_3.time() and QTime.currentTime() < self.timeEdit_4.time():
            # 보유 잔고 종목 확인 후 지정가 매도
            auto_stock = self.real_account_estimated.get(code_stock[self.count_sell_flag])  # To sell, auto_stock에 데이터 저장
            price = int(float(auto_stock[3]) + float(auto_stock[3]) * float(self.doubleSpinBox_10.value()) / 100)
            # 지정가 매도 접수되어 미체결 된 종목인 경우에는 매도 주문 생략
            if not auto_stock[0] in keys_nosell:
                self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                        ["자동거래매수주문", "5149", account_num, order_type_lookup[order_type],
                                         auto_stock[0], auto_stock[3], price, hoga_lookup[sell_type], ""])
            # 다음 매도 종목 찾기
            self.count_sell_flag += 1

            # 매도 종목 끝이면 플래그 리셋
            if self.count_sell_flag == count:
                self.count_sell_flag = 0

        # 장마감 시간이 가까워 지면 시장가 청산
        elif QTime.currentTime() > self.timeEdit_4.time():
            # 1. 지정가 매도 미체결 종목 취소주문

            # 2. 전체 시장가 매도 주문
            self._sell_all_stock()

    def _current_time_interval(self):

        # 현재 시간 가져오기
        now_time_flag = "0859"
        now_time = QTime.currentTime().toString("hhmmss")

        print("현재시간 : ", now_time)

        ################################################################################################################
        # 시간 세분화 : 15분 단위 flag 지정
        ################################################################################################################
        if now_time < "090000":
            now_time_flag = "0859"

        elif now_time > "090000" and now_time <= "091500":
            now_time_flag = "0900"
        elif now_time > "091500" and now_time <= "093000":
            now_time_flag = "0915"
        elif now_time > "093000" and now_time <= "094500":
            now_time_flag = "0930"
        elif now_time > "094500" and now_time <= "100000":
            now_time_flag = "0945"

        elif now_time > "100000" and now_time <= "101500":
            now_time_flag = "1000"
        elif now_time > "101500" and now_time <= "103000":
            now_time_flag = "1015"
        elif now_time > "103000" and now_time <= "104500":
            now_time_flag = "1030"
        elif now_time > "104500" and now_time <= "110000":
            now_time_flag = "1045"

        elif now_time > "110000" and now_time <= "111500":
            now_time_flag = "1100"
        elif now_time > "111500" and now_time <= "113000":
            now_time_flag = "1115"
        elif now_time > "113000" and now_time <= "114500":
            now_time_flag = "1130"
        elif now_time > "114500" and now_time <= "120000":
            now_time_flag = "1145"

        elif now_time > "120000" and now_time <= "121500":
            now_time_flag = "1200"
        elif now_time > "121500" and now_time <= "123000":
            now_time_flag = "1215"
        elif now_time > "123000" and now_time <= "124500":
            now_time_flag = "1230"
        elif now_time > "124500" and now_time <= "130000":
            now_time_flag = "1245"

        elif now_time > "130000" and now_time <= "131500":
            now_time_flag = "1300"
        elif now_time > "131500" and now_time <= "133000":
            now_time_flag = "1315"
        elif now_time > "133000" and now_time <= "134500":
            now_time_flag = "1330"
        elif now_time > "134500" and now_time <= "140000":
            now_time_flag = "1345"

        elif now_time > "140000" and now_time <= "141500":
            now_time_flag = "1400"
        elif now_time > "141500" and now_time <= "143000":
            now_time_flag = "1415"
        elif now_time > "143000" and now_time <= "144500":
            now_time_flag = "1430"
        elif now_time > "144500" and now_time <= "150000":
            now_time_flag = "1445"

        elif now_time > "150000" and now_time <= "151500":
            now_time_flag = "1500"
        elif now_time > "151500" and now_time <= "152000":
            now_time_flag = "1515"
        elif now_time > "152000" and now_time <= "153000":
            now_time_flag = "1520"
        else:
            now_time_flag = "1530"

        return now_time_flag

    ####################################################################################################################
    # <<매수 이벤트>> : 타이머에 의해서 조건에 따른 매수 주문 발생
    ####################################################################################################################
    def _buy_timer(self):

        # 매수전략 라디오 버튼 초기값
        buy_case_selection = False

        # 계좌번호 지정
        account_num = self.comboBox.currentText()

        # 매수설정
        buy_max_account = self.spinBox_8.value()  # 14 1종목당 매수금액(단위 만원)

        # 조건식 매수 전략 1 ~ 6 변수 할당
        condition_case_1 = self.radioButton_6.isChecked()  # case 1
        condition_case_2 = self.radioButton_7.isChecked()  # case 2
        condition_case_3 = self.radioButton_8.isChecked()  # case 3
        condition_case_4 = self.radioButton_9.isChecked()  # case 4
        condition_case_5 = self.radioButton_10.isChecked()  # case 5
        condition_case_6 = self.radioButton_11.isChecked()  # case 6

        ################################################################################################################
        # 버튼 클릭과 시간 구간 변화 상태의 포지티브 엣지를 검출
        # 현재시간과 조건시간을 비교, 현재시간의 구간 엣지를 검출, 검출되면, 조건검색식에 따른 종목검색 요청
        ################################################################################################################
        if condition_case_4 == True:
            if self.checkBox_7.isChecked():
                if self._current_time_interval() == "0915":
                    if not self.current_time_compare == "0915":
                        self.current_time_compare = "0915"
                        self._auto_select_condition()

            if self.checkBox_11.isChecked():
                if self._current_time_interval() == "0930":
                    if not self.current_time_compare == "0930":
                        self.current_time_compare = "0930"
                        self._auto_select_condition()

            if self.checkBox_12.isChecked():
                if self._current_time_interval() == "0945":
                    if not self.current_time_compare == "0945":
                        self.current_time_compare = "0945"
                        self._auto_select_condition()

        elif condition_case_5 == True:
            if self.checkBox_9.isChecked():
                if self._current_time_interval() == "0915":
                    if not self.current_time_compare == "0915":
                        self.current_time_compare = "0915"
                        self._auto_select_condition()

            if self.checkBox_14.isChecked():
                if self._current_time_interval() == "0930":
                    if not self.current_time_compare == "0930":
                        self.current_time_compare = "0930"
                        self._auto_select_condition()

            if self.checkBox_16.isChecked():
                if self._current_time_interval() == "0945":
                    if not self.current_time_compare == "0945":
                        self.current_time_compare = "0945"
                        self._auto_select_condition()

        ################################################################################################################
        # 매수 형식 지정
        order_type_lookup = {'신규매수': 1, '신규매도': 2, '매수취소': 3, '매도취소': 4}
        hoga_lookup = {'지정가': "00", '시장가': "03"}
        order_type = "신규매수"

        # 자동매매 설정에 따른 실행 여부
        if not self.checkBox_3.isChecked():
            self.listWidget_4.addItem("자동매매 설정이 되지 않아 매수 종료")
            return

        # 프로그램 실행 후 체결 회수 제한
        if self.today_stock_count > self.spinBox_4.value():  # 0 매수체결 회수
            self.listWidget_4.addItem("매수 체결 횟수 제한으로 매수 종료")
            return

        ################################################################################################################
        # 2 설정 시작시간 self.timeEdit.time() 이고
        # 3 설정 끝 시간 self.timeEdit_2.time(): 이내이면 자동 매수
        ################################################################################################################
        if QTime.currentTime() > self.timeEdit.time() and QTime.currentTime() < self.timeEdit_2.time():
            pass
        else:
            self.listWidget_4.addItem("설정 시간 제한으로 매수 종료")
            return

        # 잔고 코드 리스트(임시 저장)
        keys_account = [key_code for key_code in self.real_account_estimated]

        # 매수 주문하였으나 미체결 된 종목 코드 저장
        # self.buy_and_nobuy의 key값은 접수번호
        keys_nobuy = []  # 미체결 종목 접수번호 저장
        keys_nobuy_code = [] # 미체결 종목 코드 저장

        # 미체결 종목 접수번호와 코드를 추출하여 keys_nobuy, keys_nobuy_code에 저장
        for codename in self.buy_and_nobuy.keys():
            all_buy_order = self.buy_and_nobuy.get(codename)  # 매수주문한 모든 정보 조회
            if all_buy_order[12] == "접수":
                print("all_buy_order", all_buy_order)
                keys_nobuy.append(codename)     # 접수번호
                keys_nobuy_code.append(all_buy_order[0])        # 종목 코드
        print("미체결 종목 접수번호와코드 keys_nobuy, keys_nobuy_code", keys_nobuy, keys_nobuy_code)

        ################################################################################################################
        # 5 매수 주문 후 일정시간(t초) 경과 후 자동취소 여부
        ################################################################################################################
        if self.checkBox_4.isChecked():
            num = 0
            while num < len(keys_nobuy):
                print("매수 주문 시간 가져오기")
                # 매수 주문 시간 가져오기
                buy_order_stock = self.buy_and_nobuy.get(keys_nobuy[num])
                buy_order_point = QTime.fromString(buy_order_stock[2], "hhmmss") # QTime(15, 36, 38) 형식 변환

                # 현재 시간 가져오기
                now_time = QTime.currentTime().toString("hhmmss")
                now_time_point = QTime.fromString(now_time, "hhmmss")  # QTime(15, 36, 38) 형식 변환

                # 초로 환산
                now_time_point_sec = now_time_point.hour() * 3600 + now_time_point.minute() * 60 + now_time_point.second()
                buy_order_point_sec = buy_order_point.hour() * 3600 + buy_order_point.minute() * 60 + buy_order_point.second()

                # 현재 시간과 매수 주문 시간의 차를 구함
                nobuy_elapsed_time = now_time_point_sec - buy_order_point_sec
                print("경과된 시간 출력", now_time_point_sec, buy_order_point_sec, nobuy_elapsed_time)

                # 매수 주문 후 t초 경과 후에도 매수되지 않은 경우에 매수취소 주문
                if nobuy_elapsed_time > self.spinBox_6.value():     # 정한 시간 초과이면
                    self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                            ["자동거래매수취소", "1430", account_num, 3,
                                            buy_order_stock[0], buy_order_stock[4], buy_order_stock[5], "00", buy_order_stock[11]])
                    print("매수 취소 주문")

                    # 매수 취소 시 self.forbid_buy_temp (매수금지 list) 에서 삭제
                    if buy_order_stock[0] in self.forbid_buy_temp:
                        self.forbid_buy_temp.remove(buy_order_stock[0])

                    num += 1
                    # 랙 방지용 : 1초 5회 미만
                    if num > 5:
                        break

                # 정한 시간이 경과되지 않아 패스
                else:
                    num += 1
                    print("정한 시간이 경과되지 않아 패스함")

        ################################################################################################################
        # 보유 종목 수 제한 여부
        ################################################################################################################
        basic_stock_count = len(keys_account) + len(keys_nobuy)
        if basic_stock_count > int(self.spinBox_5.value()):  # 1 보유 종목 수(미체결 주문 포함)
            self.listWidget_4.addItem("보유종목 제한 갯수 " + str(self.spinBox_5.value()) + "초과로 자동매매 제한")
            return

        ################################################################################################################
        # 조건식에서 검출된 종목 리스트 저장, 갯수
        ################################################################################################################
        code_stock = [key_code for key_code in self.condition_search_stock]
        count = len(code_stock)
        print("조건검색식 편입 종목의 수 count = ", count)

        ################################################################################################################
        # 조건식 검출 종목이 없음
        ################################################################################################################
        if count == 0:
            self.listWidget_4.addItem("조건검색식 편입 종목이 없습니다. 먼저 조건검색을 확인하세요.")
            return

        print("조건검색식 종목 수 만큼 매수하기 위한 전역변수 self.count_buy_flag", self.count_buy_flag)

        try:
            # 조건검색식으로 편입된 종목에 대한 현재가 찾기, 매수해야 할 수량 계산
            if code_stock[self.count_buy_flag] in self.condition_search_stock:
                # To buy, auto_stock에 데이터 저장
                auto_stock = self.condition_search_stock.get(code_stock[self.count_buy_flag])
                print("오토스톡", auto_stock)
            else:
                print("오토스톡 예외처리")
        except:
            print("=========================exceptexceptexceptexceptexceptexceptexcept================================")
            self.listWidget_4.addItem("조건검색식 편입 현재가 찾기와 수량 계산에서 오류 발생")
            self.count_buy_flag = 0     # 오류 발생 시 플래그를 초기화
            return

        ################################################################################################################
        # 매수 case 1 : 매수전략이 없는 매수 방법  :: (지정가/시장가 지정)
        ################################################################################################################
        if condition_case_1 == True:
            print("condition_case_1 매수형태 지정")
            buy_type = self.comboBox_6.currentText()  # 12 매수 형태(지정가, 시장가)
            buy_nomal_type_hoga = self.doubleSpinBox_11.value()  # 13 지정가이면 호가

            # 매수형태 = 지정가
            if buy_type == "지정가":
                # print("현재가:", float(auto_stock[1]))
                price = int(float(auto_stock[1]) + float(auto_stock[1]) * float(buy_nomal_type_hoga) / 100)
                quantity = int(float(buy_max_account * 10000) / price)
            # 매수형태 = 시장가
            elif buy_type == "시장가":
                price = 0
                quantity = int(float(buy_max_account * 10000) / int(auto_stock[1]))
            # 그외는 오류
            else:
                buy_case_selection = False

            buy_case_selection = True

        ################################################################################################################
        # 매수 case 2 : 갭상승 매수 전략 1
        ################################################################################################################
        elif condition_case_2 == True:

            buy_type = "지정가"

            high_val = float(auto_stock[6].lstrip(' -+'))
            low_val = float(auto_stock[7].lstrip(' -+'))

            price = int(high_val * (1 - (high_val / low_val - 1) / 1.764 / 2))
            quantity = int(float(buy_max_account * 10000) / price)
            print(auto_stock[0], " = price : ", price)

            buy_case_selection = True

        ################################################################################################################
        # 매수 case 3 : 갭상승 매수 전략 2
        ################################################################################################################
        elif condition_case_3 == True:
            if self._current_time_interval() == "1530":
                print("time 테스트")
                high_val = float(auto_stock[6].lstrip(' -+'))
                low_val = float(auto_stock[7].lstrip(' -+'))

                price = int(high_val * (1 - (high_val / low_val - 1) / 1.764 / 2))
                quantity = int(float(buy_max_account * 10000) / price)
                print(auto_stock[0], " = price : ", price)

                buy_case_selection = True
            else:
                print("time 미스")

        ################################################################################################################
        # 매수 case 4 : 15분봉 매수 전략 1
        ################################################################################################################
        elif condition_case_4 == True:
            ############################################################################################################
            # 15분봉 매매 전략
            # auto_stock[0]= 종목명, *[1]= 현재가, [2]= 전일대비, [3]= 등락률,
            # auto_stokc[4]= 거래량, *[5]= 시가, *[6]= 고가, *[7]= 저가, [8]= 체결강도
            # (1)저점대비 고점 상승률 = 고가 / 저가 /100 (%), (2)피보나치 상수값 나누기 = (1) / 1.764
            # (3)고점대비 피보나치 값 = 고가 - 고가*(2), (4) 매수값 = {고가 + (3)} / 2
            ############################################################################################################

            # 매수 case 4 - 1 :: 15분봉 1봉, 9시 15분 매수
            if self.checkBox_7.isChecked():

                # 현재시간과 조건시간을 비교
                if self._current_time_interval() == "0915":
                    print("9시 15분 초과 9시 30분 이하이다.")

                    # 매수 형태 = 지정가
                    buy_type = "지정가"

                    # 조건식에서 검출된 종목에 대하여 고가, 저가를 저장
                    high_val = float(auto_stock[6].lstrip(' -+'))  # 고가
                    low_val = float(auto_stock[7].lstrip(' -+'))  # 저가

                    # 매수 가격 : price, 매수 수량 : quantity 각각 계산
                    price = int(high_val * (1 - (high_val / low_val - 1) / 1.764 / 2))
                    quantity = int(float(buy_max_account * 10000) / price)
                    print(auto_stock[0], " = price : ", price)

                    buy_case_selection = True

                # 기타 시간
                else:
                    print("9시 15분 ~ 9시 30분 이하가 아니다.")
                    buy_case_selection = False
                    return

            # 매수 case 4 - 2 :: 15분봉 2봉, 9시 30분 매수
            if self.checkBox_11.isChecked():

                # 현재시간과 조건시간을 비교
                if self._current_time_interval() == "0930":
                    print("9시 30분 초과 9시 45분 이하이다.")

                    # 매수 형태 = 지정가
                    buy_type = "지정가"

                    # 조건식에서 검출된 종목에 대하여 고가, 저가를 저장
                    high_val = float(auto_stock[6].lstrip(' -+'))  # 고가
                    low_val = float(auto_stock[7].lstrip(' -+'))  # 저가

                    # 매수 가격 : price, 매수 수량 : quantity 각각 계산
                    price = int(high_val * (1 - (high_val / low_val - 1) / 1.764 / 2))
                    quantity = int(float(buy_max_account * 10000) / price)
                    print(auto_stock[0], " = price : ", price)

                    buy_case_selection = True

                # 기타 시간
                else:
                    print("9시 15분 ~ 9시 30분 이하가 아니다.")
                    buy_case_selection = False
                    return

            # 매수 case 4 - 3 :: 15분봉 3봉, 9시 45분 매수
            if self.checkBox_12.isChecked():

                # 현재시간과 조건시간을 비교
                if self._current_time_interval() == "0945":
                    print("9시 45분 ~ 10시 00분 이하가 아니다.")

                    # 매수 형태 = 지정가
                    buy_type = "지정가"

                    # 조건식에서 검출된 종목에 대하여 고가, 저가를 저장
                    high_val = float(auto_stock[6].lstrip(' -+'))  # 고가
                    low_val = float(auto_stock[7].lstrip(' -+'))  # 저가

                    # 매수 가격 : price, 매수 수량 : quantity 각각 계산
                    price = int(high_val * (1 - (high_val / low_val - 1) / 1.764 / 2))
                    quantity = int(float(buy_max_account * 10000) / price)
                    print(auto_stock[0], " = price : ", price)

                    buy_case_selection = True

                # 기타 시간
                else:
                    print("9시 45분 ~ 10시 00분 이하가 아니다.")
                    buy_case_selection = False
                    return

        ################################################################################################################
        # 매수 case 5 : 15분봉 매수 전략 2 ::
        # 기존 15분봉 매수기법에 매수와 매도 타점을 조정
        ################################################################################################################
        elif condition_case_5 == True:
            # 매수 case 5 - 1 :: 15분봉 1봉
            if self.checkBox_9.isChecked():

                # 현재시간과 조건시간을 비교
                if self._current_time_interval() == "0915":
                    print("9시 15분 초과 9시 30분 이하이다.")

                    # 매수 형태 = 지정가
                    buy_type = "지정가"

                    # 조건식에서 검출된 종목에 대하여 고가, 저가를 저장
                    high_val = float(auto_stock[6].lstrip(' -+'))  # 고가
                    low_val = float(auto_stock[7].lstrip(' -+'))  # 저가

                    # 매수 가격 : price, 매수 수량 : quantity 각각 계산
                    price = int(high_val * (1 - (high_val / low_val - 1) / 1.764 / 2))
                    quantity = int(float(buy_max_account * 10000) / price)
                    print(auto_stock[0], " = price : ", price)

                    buy_case_selection = True

                # 기타 시간
                else:
                    print("9시 15분 ~ 9시 30분 이하가 아니다.")
                    buy_case_selection = False
                    return

            # 매수 case 5 - 2 :: 15분봉 2봉
            elif self.checkBox_14.isChecked():
                # 현재시간과 조건시간을 비교
                if self._current_time_interval() == "0930":
                    print("9시 30분 초과 9시 45분 이하이다.")

                    # 매수 형태 = 지정가
                    buy_type = "지정가"

                    # 조건식에서 검출된 종목에 대하여 고가, 저가를 저장
                    high_val = float(auto_stock[6].lstrip(' -+'))  # 고가
                    low_val = float(auto_stock[7].lstrip(' -+'))  # 저가

                    # 매수 가격 : price, 매수 수량 : quantity 각각 계산
                    price = int(high_val * (1 - (high_val / low_val - 1) / 1.764 / 2))
                    quantity = int(float(buy_max_account * 10000) / price)
                    print(auto_stock[0], " = price : ", price)

                    buy_case_selection = True

                # 기타 시간
                else:
                    print("9시 15분 ~ 9시 30분 이하가 아니다.")
                    buy_case_selection = False
                    return

            # 매수 case 5 - 3 :: 15분봉 3봉, 9시 45분 매수
            if self.checkBox_16.isChecked():

                # 현재시간과 조건시간을 비교
                if self._current_time_interval() == "0945":
                    print("9시 45분 ~ 10시 00분 이하가 아니다.")

                    # 매수 형태 = 지정가
                    buy_type = "지정가"

                    # 조건식에서 검출된 종목에 대하여 고가, 저가를 저장
                    high_val = float(auto_stock[6].lstrip(' -+'))  # 고가
                    low_val = float(auto_stock[7].lstrip(' -+'))  # 저가

                    # 매수 가격 : price, 매수 수량 : quantity 각각 계산
                    price = int(high_val * (1 - (high_val / low_val - 1) / 1.764 / 2))
                    quantity = int(float(buy_max_account * 10000) / price)
                    print(auto_stock[0], " = price : ", price)

                    buy_case_selection = True

                # 기타 시간
                else:
                    print("9시 45분 ~ 10시 00분 이하가 아니다.")
                    buy_case_selection = False
                    return


        ################################################################################################################
        # 매수 case 6 : To Do
        ################################################################################################################
        elif condition_case_6 == True:
            buy_case_selection = False

        # 그 외
        else:
            buy_case_selection = False

        # 매수 방법이 지정되지 않은 경우 종료
        if not buy_case_selection == True:
            return

        ################################################################################################################
        # 매수 주문
        # 보유잔고 종목을 조회해서 보유한 종목이거나 매수 미체결인 경우에 추가 매수하지 않음(2020.3.31 수정)
        # auto_stock[0] : code, # auto_stock[1] : 현재가, # auto_stock[2] : 전일대비,
        # auto_stock[3] : 등락률, # auto_stock[4] : 거래량, # auto_stock[5] : 시가,
        # auto_stock[6] : 고가, # auto_stock[7] : 저가, # auto_stock[8] : 체결강도
        ################################################################################################################
        if not auto_stock[0] in self.busy_buy_stock_code_list:
            print("보유종목이 아님:: 오토스톡[0], 잔고코드리스트", auto_stock[0], self.busy_buy_stock_code_list)
            if not auto_stock[0] in self.forbid_buy_temp:
                self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                        ["자동거래매수주문", "5149", account_num, order_type_lookup[order_type],
                                        auto_stock[0], quantity, price, hoga_lookup[buy_type], ""])
                print("자동거래매수주문")
                # 매수 주문 후 반복 매수되지 않도록 self.busy_buy_stock_code_list에 종목코드 추가
                self.busy_buy_stock_code_list.append(auto_stock[0])
                self.forbid_buy_temp.append(auto_stock[0])

        else:
            self.listWidget_4.addItem("보유한 잔고 종목 또는 매수주문되어 있어 매수하지 않음 " + str(auto_stock))
            print("=============================== 보유한 잔고 종목 또는 매수주문되어 있어 매수하지 않음 ", str(auto_stock))

        print("forbid_buy_temp", self.forbid_buy_temp)
        self.count_buy_flag += 1

        if self.count_buy_flag == count:
            self.count_buy_flag = 0

        # self.listWidget_4.addItem("매수 종목 수는 " + str(self.count_buy_flag) + "개 입니다.")
        print("매수 종목 수는 ", str(self.count_buy_flag), "개 입니다.")

    ####################################################################################################################
    # 조건식 멈추기
    ####################################################################################################################
    def _condition_search_stop(self):
        condition_code = self.lineEdit_18.text()
        condition_name = self.lineEdit_19.text()
        print("test 선택한 셀의 내용: ", condition_code, condition_name)
        # print(scrNo, conditionName, conditionIndex)
        self.KW_API.dynamicCall("SendConditionStop(QString, QString, int)", "0009", condition_name, condition_code)
        self.condition_search_stock.clear()
        self.qtable_3_display()

    ####################################################################################################################
    # 보유 종목 조회(잔고조회 종목에 대하여 실시간 조회)
    # # OnReceiveRealData에서 매도 가능한 보유종목이 실시간 조회가 가능하도록 종목 조회
    ####################################################################################################################
    def _all_balance_search(self):
        balance_code_list = [key_code for key_code in self.real_account_estimated]
        balance_count = len(balance_code_list)
        balance_code_string = ';'.join(balance_code_list)
        # 매도해야 할 종목이 없으면
        if balance_code_string == "":
            self.listWidget_4.addItem("매도 해야 할 종목이 없습니다.")
        # 매도해야 할 종목이 있으면
        else:
            self.KW_API.dynamicCall("CommKwRqData(QString, QBoolean, int, int, QString, QString)",
                                      balance_code_string, "0", balance_count, "0", "종목연속조회", "0130")
            print(balance_code_string, balance_code_string)

    ####################################################################################################################
    # 프로그램 진행상태 메시지 출력
    ####################################################################################################################
    def _receiveMsg(self, sScrNo, sRQName, sTrCode, sMsg):
        print("테스트 시작")
        self.listWidget_4.addItem("< Msg > : " + sScrNo + " " + sRQName + " " + sTrCode + " " + sMsg)
        print("끝")

    ####################################################################################################################
    # TR 조회를 통해서 실시간계좌평가잔고내역요청
    # ['총매입금액', '총평가금액', '총평가손익금액', '총수익률(%)', '추정예탁자산']
    ####################################################################################################################
    def _real_check_account(self):
        Account_num = self.comboBox.currentText()
        if len(Account_num) > 0:
            self.KW_API.dynamicCall("SetInputValue(QString, QString)", "계좌번호", Account_num)
            self.KW_API.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
            self.KW_API.dynamicCall("SetInputValue(QString, QString)", "조회구분", "1")  # 1: 합산, 2: 개별
            self.KW_API.dynamicCall("CommRqData(QString, QString, int, QString)", "실시간계좌평가잔고내역요청", "opw00018", 0, "8110")  #8100 + 10

    ####################################################################################################################
    # TR 조회를 통해서 계좌평가현황요청
    # ['종목코드', '종목명', '평균단가', '보유수량', '현재가', '매입금액', '손익금액', '손익율']
    ####################################################################################################################
    def _real_check_balance(self):
        Account_num = self.comboBox.currentText()
        if len(Account_num) > 0:
            self.KW_API.dynamicCall("SetInputValue(QString, QString)", "계좌번호", Account_num)
            self.KW_API.dynamicCall("SetInputValue(QString, QString)", "상장폐지조회구분", "0")
            self.KW_API.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
            self.KW_API.dynamicCall("CommRqData(QString, QString, int, QString)", "계좌평가현황요청", "opw00004", 0, "4010")     #4000 + 10


    ####################################################################################################################
    # TR 조회를 통해서 당일실현 손익 확인
    #
    ####################################################################################################################
    def _today_balance_check(self):
        Account_num = self.comboBox.currentText()
        if len(Account_num) > 0:
            pass

    ####################################################################################################################
    # 보유종목 중 해당 셀을 선택하면 종목의 매도 주문 창 연결
    # 수동 매도가 가능하도록 매수종목 클릭
    ####################################################################################################################
    def _selected_check_balance(self):
        index = self.tableWidget_5.currentRow()
        balance_code = self.tableWidget_5.item(index, 0)    # 선택한 종목명 저장
        balance_name = self.tableWidget_5.item(index, 1)    # 선택한 종목코드 저장
        balance_price = self.tableWidget_5.item(index, 4)    # 선택한 현재가 저장
        balance_cnt = self.tableWidget_5.item(index, 3)  # 선택한 셀 보유수량 저장

        balance_code = balance_code.text()
        balance_name = balance_name.text()
        balance_price = balance_price.text()
        balance_cnt = balance_cnt.text()

        self.listWidget_4.addItem("선택한 셀은 " + balance_name + balance_code + "입니다.")

        self.lineEdit_11.setText(balance_name)
        self.lineEdit_12.setText(balance_name)
        self.lineEdit_13.setText(balance_code)
        self.lineEdit_14.setText(balance_price)
        self.spinBox.setValue(int(balance_cnt))
        self.spinBox_2.setValue(int(balance_price))

        # To Do : 시장가 또는 지정가 매도 주문

    ####################################################################################################################
    # 보유종목 일괄 매도(시장가)
    ####################################################################################################################
    def _sell_all_stock(self):
        #
        self.listWidget_4.addItem("보유 종목 전체청산 준비 중입니다....... 잠시 기다리세요.")
        order_type_lookup ={'신규매수': 1, '신규매도': 2, '매수취소': 3, '매도취소': 4}
        hoga_lookup = {'지정가': "00", '시장가': "03"}
        account_num = self.comboBox.currentText()
        order_type = "신규매도"
        hoga = "시장가"
        price = 0

        for codename in self.real_account_estimated.keys():
            display = self.real_account_estimated.get(codename)
            code = codename
            quantity = display[3]
            if len(account_num) > 0:
                print("code:", code, "quantity:", quantity)
                self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                ["전체청산주문", "0999", account_num, order_type_lookup[order_type], code, quantity, price, hoga_lookup[hoga], ""])
            time.sleep(0.5)    # 1초 5회 미만으로 요청
        self.listWidget_4.addItem("보유 종목 전체청산 주문이 완료되었습니다.")

    ####################################################################################################################
    # 보유종목 추가 옵션
    # To Do : # DISPLAY 체크여부 확인
    ####################################################################################################################
    def _display_order_set(self):
        if self.checkBox_8.isChecked():
            self.isDisplayOrder = True
            self._insert_tabs("DISPLAY", "1", 3)
        else:
            self.isDisplayOrder = False
            self.tabWidget.removeTab(4)

    ####################################################################################################################
    # Tab Widget 생성 메서드, Tab Widget 내에 Table Widget 생성
    # 당일 보유 종목에 대한 모니터링(10개로 제한)
    ####################################################################################################################
    def _insert_tabs(self, txt, index, codes):
        self.txt = QWidget()
        self.tabWidget.addTab(self.txt, txt)

        self.tableWidget1 = QTableWidget(20, 5)
        self.tableWidget1.verticalHeader().setVisible(False)
        self.tableWidget1.setHorizontalHeaderLabels(["호가", "단가", "잔량", "시간", "체결량"])
        self.tableWidget1.resizeColumnsToContents()
        self.tableWidget1.resizeRowsToContents()

        tableWidget2 = QTableWidget(4, 4)
        tableWidget2.setHorizontalHeaderLabels(["", "종목코드", "종목명", "현재가"])
        tableWidget2.resizeColumnsToContents()
        tableWidget2.resizeRowsToContents()

        tableWidget3 = QTableWidget(4, 4)
        tableWidget3.setHorizontalHeaderLabels(["", "종목코드", "종목명", "현재가"])
        tableWidget3.resizeColumnsToContents()
        tableWidget3.resizeRowsToContents()

        tableWidget4 = QTableWidget(4, 4)
        tableWidget4.setHorizontalHeaderLabels(["", "종목코드", "종목명", "현재가"])
        tableWidget4.resizeColumnsToContents()
        tableWidget4.resizeRowsToContents()

        tableWidget5 = QTableWidget(20, 4)
        tableWidget5.setHorizontalHeaderLabels(["", "종목코드", "종목명", "현재가"])
        tableWidget5.resizeColumnsToContents()
        tableWidget5.resizeRowsToContents()

        tableWidget6 = QTableWidget(4, 4)
        tableWidget6.setHorizontalHeaderLabels(["", "종목코드", "종목명", "현재가"])
        tableWidget6.resizeColumnsToContents()
        tableWidget6.resizeRowsToContents()

        tableWidget7 = QTableWidget(4, 4)
        tableWidget7.setHorizontalHeaderLabels(["", "종목코드", "종목명", "현재가"])
        tableWidget7.resizeColumnsToContents()
        tableWidget7.resizeRowsToContents()

        tableWidget8 = QTableWidget(4, 4)
        tableWidget8.setHorizontalHeaderLabels(["", "종목코드", "종목명", "현재가"])
        tableWidget8.resizeColumnsToContents()
        tableWidget8.resizeRowsToContents()

        tableWidget9 = QTableWidget(4, 4)
        tableWidget9.setHorizontalHeaderLabels(["", "종목코드", "종목명", "현재가"])
        tableWidget9.resizeColumnsToContents()
        tableWidget9.resizeRowsToContents()

        tableWidget10 = QTableWidget(20, 4)
        tableWidget10.setHorizontalHeaderLabels(["", "종목코드", "종목명", "현재가"])
        tableWidget10.resizeColumnsToContents()
        tableWidget10.resizeRowsToContents()

        layout = QGridLayout()

        layout.addWidget(self.tableWidget1, 0, 0)
        layout.addWidget(tableWidget2, 0, 1)
        layout.addWidget(tableWidget3, 0, 2)
        layout.addWidget(tableWidget4, 0, 3)
        layout.addWidget(tableWidget5, 0, 4)
        layout.addWidget(tableWidget6, 1, 0)
        layout.addWidget(tableWidget7, 1, 1)
        layout.addWidget(tableWidget8, 1, 2)
        layout.addWidget(tableWidget9, 1, 3)
        layout.addWidget(tableWidget10, 1, 4)

        hoga_count = 10
        for i in range(10):
            self.tableWidget1.setItem(i, 0, QTableWidgetItem("+" + str(hoga_count)))
            self.tableWidget1.setItem(i + 10, 0, QTableWidgetItem("-" + str(i + 1)))
            hoga_count = hoga_count - 1

        self.txt.setLayout(layout)  # 마지막에 입력되어야 정상 출력

    ####################################################################################################################
    # 테이블 자동 생성
    # _insert_tabs과 연동
    ####################################################################################################################
    def _make_table(self):
        self.tableWidget_5.setRowCount(10)
        self.tableWidget_5.setColumnCount(15)
        self.tableWidget_5.setAlternatingRowColors(True)  # 열의 색깔 교차 변경
        self.tableWidget_5.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_5.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_5.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.tableWidget_5.setFocusPolicy(Qt.StrongFocus)

#        self.tableWidget_5.setColumnWidth(2, 300)
        ckbox = QCheckBox('매도')
        self.tableWidget_5.setCellWidget(0, 12, ckbox)

        mycom = QComboBox()
        mycom.addItems(["시장가", "지정가"])
        self.tableWidget_5.setCellWidget(0, 10, mycom)

        mycom.currentTextChanged.connect(self._mycom_text_changed)

        #출처: https: // freeprog.tistory.com / 취미로 하는 프로그래밍 !!!]

    ####################################################################################################################
    # 테이블 내 콤보박스 생성
    #
    ####################################################################################################################
    def _mycom_text_changed(self, txt):
        if txt == "지정가":
            mycom_2 = QComboBox()
            mycom_2.addItems(["+5호가", "+4호가", "+3호가","+2호가","+1호가","","-1호가","-2호가","-3호가","-4호가","-5호가"])
            self.tableWidget_5.setCellWidget(0, 11, mycom_2)

        else:
            self.tableWidget_5.removeCellWidget(0, 11)

    ####################################################################################################################
    # 조건 검색식에 따른 실시간 종목편입과 종목이탈을 string으로 전달)
        # param : code string 종목코드
        # param : event string 이벤트 종류("I": 종목편입, "D": 종목이탈)
        # param : conditionName string 조건식 이름
        # param : conditionIndex string 조건식 인덱스(여기서만 인덱
    ####################################################################################################################
    def _receive_real_condition(self, code, event, conditionName, conditionIndex):

        # 종목 편입
        if event == "I":
            print("종목편입 이벤트:", code)
            if code not in self.condition_search_stock:
                self.real_insert_stock_list.append(code)
                # 0 : 해당종목만, 1 : 기존 종목을 포함하여, 해당종목 추가
                self.KW_API.dynamicCall("SetRealReg(QString, QString, QString, QString)",
                                        7777, code, "302;10;11;12;13;16;17;18;228", "1")

        # 종목 이탈
        elif event == "D":
            if code in self.condition_search_stock:
                 del self.condition_search_stock[code]
                 self.KW_API.dynamicCall("SetRealReg(QString, QString)", 7777, code)

        print("code 와 종목명 출력: ", conditionName, conditionIndex, len(self.condition_search_stock))

    ####################################################################################################################
    # 설정 초기화 값 자동 로딩
    ####################################################################################################################
    def _init_load_auto_set_data(self):
        f = open("set_list.txt",'r', encoding = 'utf8')
        set_list = f.readlines()

        if len(set_list) != 29:
            return

        self.spinBox_4.setValue(int(set_list[0]))
        self.spinBox_5.setValue(int(set_list[1]))

        time_char_split = re.findall("\d+", set_list[2]+"a0")
        self.timeEdit.setTime(QTime(int(time_char_split[1]), int(time_char_split[2]), int(time_char_split[3])))

        time_char_split = re.findall("\d+", set_list[3]+"a0")
        self.timeEdit_2.setTime(QTime(int(time_char_split[1]), int(time_char_split[2]), int(time_char_split[3])))

        self.spinBox_6.setValue(int(set_list[4]))
        if set_list[5].strip('\n') == "True":
            self.checkBox_4.setChecked(True)
        else:
            self.checkBox_4.setChecked(False)

        self.spinBox_7.setValue(int(set_list[6]))

        if set_list[7].strip('\n') == "True":
            self.checkBox_5.setChecked(True)
        else:
            self.checkBox_5.setChecked(False)

        if set_list[8].strip('\n') == "True":
            self.checkBox_6.setChecked(True)
        else:
            self.checkBox_6.setChecked(False)

        # 검색 문자열에서 패턴과 매칭되는 모든 경우를 찾아 리스트로 반환
        # 출처 : https://devanix.tistory.com/296
        time_char_split = re.findall("\d+", set_list[9]+"a0")
        self.timeEdit_3.setTime(QTime(int(time_char_split[1]), int(time_char_split[2]), int(time_char_split[3])))

        self.doubleSpinBox_10.setValue(float(set_list[10]))

        time_char_split = re.findall("\d+", set_list[11]+"a0")
        self.timeEdit_4.setTime(QTime(int(time_char_split[1]), int(time_char_split[2]), int(time_char_split[3])))

        self.comboBox_6.setCurrentIndex(int(set_list[12]))
        self.doubleSpinBox_11.setValue(float(set_list[13]))
        self.spinBox_8.setValue(int(set_list[14]))

        if set_list[15].strip('\n') == "True":
            self.radioButton.setChecked(True)
        elif set_list[16].strip('\n') == "True":
            self.radioButton_2.setChecked(True)
        elif set_list[17].strip('\n') == "True":
            self.radioButton_3.setChecked(True)
        else:
            self.radioButton.setChecked(False)
            self.radioButton_2.setChecked(False)
            self.radioButton_3.setChecked(False)

        self.doubleSpinBox.setValue(float(set_list[18]))
        self.doubleSpinBox_2.setValue(float(set_list[19]))
        self.doubleSpinBox_3.setValue(float(set_list[20]))
        self.doubleSpinBox_4.setValue(float(set_list[21]))
        self.doubleSpinBox_5.setValue(float(set_list[22]))
        self.doubleSpinBox_6.setValue(float(set_list[23]))
        self.radioButton_4.setChecked(bool(set_list[24]))
        self.radioButton_5.setChecked(bool(set_list[25]))

        if set_list[24].strip('\n') == "True":
            self.radioButton_4.setChecked(True)
        elif set_list[25].strip('\n') == "True":
            self.radioButton_5.setChecked(True)
        else:
            self.radioButton.setChecked(False)
            self.radioButton_2.setChecked(False)

        self.doubleSpinBox_7.setValue(float(set_list[26]))
        self.doubleSpinBox_12.setValue(float(set_list[27]))
        self.doubleSpinBox_8.setValue(float(set_list[28]))
        # self.doubleSpinBox_9.setValue(float(set_list[29]))
        # self.doubleSpinBox_13.setValue(float(set_list[30]))
        
        f.close()

    ####################################################################################################################
    # 설정 초기화 값 저장
    ####################################################################################################################
    def _save_auto_set_data(self):
        f = open("set_list.txt", 'wt', encoding = 'utf8')

        f.write(str(self.spinBox_4.value()))   #0
        f.write('\n')
        f.write(str(self.spinBox_5.value()))    #1
        f.write('\n')
        f.write(str(self.timeEdit.time()))      #2
        f.write('\n')
        f.write(str(self.timeEdit_2.time()))    #3
        f.write('\n')
        f.write(str(self.spinBox_6.value()))    #4
        f.write('\n')
        f.write(str(self.checkBox_4.isChecked()))   #5
        f.write('\n')
        f.write(str(self.spinBox_7.value()))    #6
        f.write('\n')
        f.write(str(self.checkBox_5.isChecked()))   #7
        f.write('\n')
        f.write(str(self.checkBox_6.isChecked()))   #8
        f.write('\n')
        f.write(str(self.timeEdit_3.time()))    #9
        f.write('\n')
        f.write(str(self.doubleSpinBox_10.value()))   #10
        f.write('\n')
        f.write(str(self.timeEdit_4.time()))    #11
        f.write('\n')
        f.write(str(self.comboBox_6.currentIndex()))    #12
        f.write('\n')
        f.write(str(self.doubleSpinBox_11.value()))    #13
        f.write('\n')
        f.write(str(self.spinBox_8.value()))    #14
        f.write('\n')
        f.write(str(self.radioButton.isChecked()))  #15
        f.write('\n')
        f.write(str(self.radioButton_2.isChecked()))    #16
        f.write('\n')
        f.write(str(self.radioButton_3.isChecked()))    #17
        f.write('\n')
        f.write(str(self.doubleSpinBox.value()))    #18
        f.write('\n')
        f.write(str(self.doubleSpinBox_2.value()))  #19
        f.write('\n')
        f.write(str(self.doubleSpinBox_3.value()))  #20
        f.write('\n')
        f.write(str(self.doubleSpinBox_4.value()))  #21
        f.write('\n')
        f.write(str(self.doubleSpinBox_5.value()))  #22
        f.write('\n')
        f.write(str(self.doubleSpinBox_6.value()))  #23
        f.write('\n')
        f.write(str(self.radioButton_4.isChecked()))    #24
        f.write('\n')
        f.write(str(self.radioButton_5.isChecked()))    #25
        f.write('\n')
        f.write(str(self.doubleSpinBox_7.value()))  #26
        f.write('\n')
        f.write(str(self.doubleSpinBox_12.value()))    #27
        f.write('\n')
        f.write(str(self.doubleSpinBox_8.value()))  #28
        f.write('\n')
        f.write(str(self.radioButton_6.isChecked()))  # 29
        f.write(str(self.radioButton_7.isChecked()))  # 30
        f.write(str(self.radioButton_8.isChecked()))  # 31
        f.write(str(self.radioButton_9.isChecked()))  # 32
        f.write(str(self.radioButton_10.isChecked()))  # 33
        f.write(str(self.radioButton_11.isChecked()))  # 34

        f.close()

    ####################################################################################################################
    # 조건식이 조회 됨에 따른 조건검색 종목 조회(100종목 까지)
    ####################################################################################################################
    def _receive_trcondition(self, sScrNo, CodeList, conditinName, index, next):
        #
        # CodeList에 코드가 ;로 구분하여 연속한 문자열로 들어오면 각각 분리하여 stockCodeList에 저장
        print("trcontest::", sScrNo, CodeList, conditinName, index, next)

        if len(CodeList) > 0:
            stockCodeList = CodeList
            CodeList = CodeList.split(';')
            count = len(CodeList)
            code = CodeList

            if count <= 100:
                # receiveTrdata에서 조건검색종목의 값을 count 만큼 반복하여 결과를 받음
                self.KW_API.dynamicCall("CommKwRqData(QString, Bool, int, int, QString, QString)",
                                        stockCodeList, 0, count, 0, "조건검색종목", "1100")
            else:
                QMessageBox.about(self, "Message", " 종목이 너무 많습니다. !!! 조건검색식을 조정하세요... ")

        elif len(CodeList) == 0:
            QMessageBox.about(self, "Message", " 조건에 맞는 종목이 없습니다.   ")


    ####################################################################################################################
    # 조건식 리스트에서 클릭하면 클릭된 검색식을 선택하여 표시
    #
    #  [SendCondition() 함수]
    #           SendCondition(
    #           BSTR strScrNo,    // 화면번호
    #           BSTR strConditionName,  // 조건식 이름
    #           int nIndex,     // 조건명 인덱스
    #           int nSearch   // 조회구분, 0:조건검색, 1:실시간 조건검색
    #           )
    # 서버에 조건검색을 요청하는 함수로 맨 마지막 인자값으로
    # 조건검색만 할것인지 실시간 조건검색도 할 것인지를 지정할 수 있습니다.
    # 여기서 조건식 인덱스는 GetConditionNameList()함수가 조건식 이름과 함께 전달한
    # 조건명 인덱스를 그대로 사용해야 합니다.
    # 리턴값 1이면 성공이며, 0이면 실패입니다.
    # 요청한 조건식이 없거나 조건명 인덱스와 조건식이 서로 안맞거나 조회횟수를 초과하는 경우 실패하게 됩니다.
    # --------------------------------------------------------------------------------------------------------
    # [조건검색 사용예시]
    # GetConditionNameList()함수로 얻은 조건식 목록이 "0^조건식1;3^조건식1;8^조건식3;23^조건식5"일때 조건식3을 검색
    # long lRet = SendCondition("0156", "조건식3", 8, 1);
    # --------------------------------------------------------------------------------------------------------
    ####################################################################################################################
    def _condition_search(self):
        index = self.tableWidget_4.currentRow()
        condition_code = self.tableWidget_4.item(index, 0)
        condition_name = self.tableWidget_4.item(index, 1)
        condition_code = condition_code.text()
        condition_name = condition_name.text()
        print("선택한 셀의 내용: ", condition_code, condition_name)
        #
        self.lineEdit_18.setText(condition_code)
        self.lineEdit_19.setText(condition_name)
        #
        self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition_name, condition_code, 1)
        self.condition_search_stock.clear()

        self.qtable_3_display()

    ####################################################################################################################
    # 조건식 자동 선택 :: 매수 전략과 매칭되도록 선택
    # 시간의 흐름에 따라 자동으로 조건식이 선택
    ####################################################################################################################
    def _auto_select_condition(self):

        if not self.checkBox_15.isChecked():
            return

        self.condition_search_stock.clear()

        conditionList = self.KW_API.GetConditionNameList()
        count_condition_gubun = conditionList.count('^')   # '^' 갯수 찾기
        conditionArray = conditionList.split(';')

        condition = [[0] * 2 for i in range(count_condition_gubun)]

        for i in range(count_condition_gubun):
            con_list = conditionArray[i].split('^')
            for j in range(2):
                condition[i][j] = con_list[j]


        # 조건식 매수 전략 1 ~ 6 변수 할당
        condition_case_1 = self.radioButton_6.isChecked()  # case 1
        condition_case_2 = self.radioButton_7.isChecked()  # case 2
        condition_case_3 = self.radioButton_8.isChecked()  # case 3
        condition_case_4 = self.radioButton_9.isChecked()  # case 4
        condition_case_5 = self.radioButton_10.isChecked()  # case 5
        condition_case_6 = self.radioButton_11.isChecked()  # case 6

        try:
            if condition_case_2 == True:    # 1
                self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[0][1],
                                        condition[0][0], 1)
                self.lineEdit_18.setText(condition[0][0])
                self.lineEdit_19.setText(condition[0][1])
            elif condition_case_3 == True:  # 2
                self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[1][1],
                                        condition[1][0], 1)
                self.lineEdit_18.setText(condition[1][0])
                self.lineEdit_19.setText(condition[1][1])

            elif condition_case_4 == True:
                # 매수 case 4 - 1 :: 15분봉 1개봉, 9시 15분 매수
                if self.checkBox_7.isChecked():
                    self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[2][1],
                                            condition[2][0], 1)
                    self.lineEdit_18.setText(condition[2][0])
                    self.lineEdit_19.setText(condition[2][1])

                # 매수 case 4 - 2 :: 15분봉 2봉, 9시 30분 매수
                if self.checkBox_11.isChecked():
                    self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[3][1],
                                            condition[3][0], 1)
                    self.lineEdit_18.setText(condition[3][0])
                    self.lineEdit_19.setText(condition[3][1])

                # 매수 case 4 - 3 :: 15분봉 3봉, 9시 45분 매수
                if self.checkBox_12.isChecked():

                    self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[4][1],
                                            condition[4][0], 1)
                    self.lineEdit_18.setText(condition[4][0])
                    self.lineEdit_19.setText(condition[4][1])

                # 시간과 무관하게 요청
                if not (self.checkBox_7.isChecked() and self.checkBox_11.isChecked() and self.checkBox_12.isChecked()):  # 4
                    self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[3][1],
                                            condition[3][0], 1)
                    self.lineEdit_18.setText(condition[3][0])
                    self.lineEdit_19.setText(condition[3][1])

            elif condition_case_5 == True:

                # 매수 case 5 - 1 :: 15분봉 1봉
                if self.checkBox_9.isChecked():     # 6
                    self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[5][1],
                                            condition[5][0], 1)
                    self.lineEdit_18.setText(condition[5][0])
                    self.lineEdit_19.setText(condition[5][1])

                # 매수 case 5 - 2 :: 15분봉 2봉
                if self.checkBox_14.isChecked():    # 7
                    self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[6][1],
                                            condition[6][0], 1)
                    self.lineEdit_18.setText(condition[6][0])
                    self.lineEdit_19.setText(condition[6][1])

                # 매수 case 5 - 3 :: 15분봉 3봉
                if self.checkBox_16.isChecked():    # 8
                    self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[7][1],
                                            condition[7][0], 1)
                    self.lineEdit_18.setText(condition[7][0])
                    self.lineEdit_19.setText(condition[7][1])

                # 시간과 무관
                if not (self.checkBox_9.isChecked() and self.checkBox_14.isChecked() and self.checkBox_16.isChecked()):  # 7
                    self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[6][1],
                                            condition[6][0], 1)
                    self.lineEdit_18.setText(condition[6][0])
                    self.lineEdit_19.setText(condition[6][1])

            elif condition_case_6 == True:  # 9
                self.KW_API.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition[8][1],
                                        condition[8][0], 1)
                self.lineEdit_18.setText(condition[8][0])
                self.lineEdit_19.setText(condition[8][1])

            else:
                pass

        except:
            print("조건식 자동선택 예외 처리")
            return


    ###################################################################################################################
    # 조건식을 문자열로 받아 토큰하고 테이블에 출력
    ####################################################################################################################
    def _receive_condition_ver(self, receive, msg):
        if not receive:
            return
        conditionList = self.KW_API.GetConditionNameList()
        count_condition_gubun = conditionList.count('^')   # '^' 갯수 찾기
        conditionArray = conditionList.split(';')
        count = len(conditionArray)
        self.tableWidget_4.setRowCount(count-1)
        self.tableWidget_4.setAlternatingRowColors(True)  # 열의 색깔 교차 변경
        #self.tableWidget_4.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_4.setColumnWidth(0, 55)  # 열의 넓이 지정
        self.tableWidget_4.setColumnWidth(1, 220)
        self.tableWidget_4.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.tableWidget_4.setFocusPolicy(Qt.StrongFocus)

        for i in range(count_condition_gubun):
            condition = conditionArray[i].split('^')
            condition_num = QTableWidgetItem(condition[0])
            condition_name = QTableWidgetItem(condition[1])

            self.tableWidget_4.setItem(i, 0, condition_num)
            self.tableWidget_4.setItem(i, 1, condition_name)

    ####################################################################################################################
    # 매수 체결 조회
    ####################################################################################################################
    def _check_buy_order(self):
        account_num = self.comboBox.currentText()
        # 매수 체결
        self.KW_API.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_num)
        self.KW_API.dynamicCall("SetInputValue(QString, QString)", "체결구분", "0")  # 0: 전체, 1: 미체결, 2: 체결
        self.KW_API.dynamicCall("SetInputValue(QString, QString)", "매매구분", "2")  # 0: 전체, 1: 매도, 2: 매수
        self.KW_API.dynamicCall("CommRqData(QString, QString, QString, QString)", "실시간매수체결미체결", "opt10075", 0, "7500")

    ####################################################################################################################
    # 매도 체결 조회
    ####################################################################################################################
    def _check_sell_order(self):
        account_num = self.comboBox.currentText()
        # 매도 체결
        self.KW_API.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_num)
        self.KW_API.dynamicCall("SetInputValue(QString, QString)", "체결구분", "0")  # 0: 전체, 1: 미체결, 2: 체결
        self.KW_API.dynamicCall("SetInputValue(QString, QString)", "매도수구분", "1")  # 0: 전체, 1: 매도, 2: 매수
        self.KW_API.dynamicCall("CommRqData(QString, QString, QString, QString)", "실시간매도체결미체결", "opt10076", 0, "7600")

    ####################################################################################################################
    # 종목 매수 매도 주문
    ####################################################################################################################
    def _order_buysell(self):
        order_type_lookup ={'신규매수': 1, '신규매도': 2, '매수취소': 3, '매도취소': 4}
        hoga_lookup = {'지정가': "00", '시장가': "03"}

        account_num = self.comboBox.currentText()
        order_type = self.comboBox_3.currentText()
        code = self.lineEdit_13.text()
        hoga = self.comboBox_2.currentText()
        quantity = self.spinBox.value()
        price = self.spinBox_2.value()

        if len(account_num) > 0:
            self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                         ["send_order_req", "0101", account_num, order_type_lookup[order_type], code, quantity, price, hoga_lookup[hoga], ""])


    ####################################################################################################################
    # 실시간 데이터 수신
    # 실시간 조건검색 종목 체결현황, 실시간 매도 구현
    #
    # ------------------------------------------------------------------------------------------------------------------
    # 실시간 데이터를 받는 곳으로 주식시장이 열려있는 동안에만 발동 됨.
    # 가격이나 거래량, 호가상태 등이 변동 할 때 이벤트가 발생(setrealreg이용)
    #  getCommRealData() 메서드를 이용해서 실시간 데이터를 얻을 수 있음
    # ------------------------------------------------------------------------------------------------------------------
    # code : string - 종목코드
    # realType : string - 실시간 타입(KOA의 실시간 목록 참조)
    # realData : string - 실시간 데이터 전문
    ####################################################################################################################
    def _receive_real_data(self, code, realType, realData):      #
        # print("code:",code, "realType:", realType, "realData:", realData )

        # 리얼타입이 아니면 종료
        if realType not in RealType.REALTYPE:
            return

        # 실시간으로 입력되는 종목의 realType fid를 저장하기 위한 리스트
        chegyul_data = []

        # 매도용 데이터 임시 리스트 : self.real_account_estimated의 value를 저장
        auto_stock = []

        # 추가 변수
        current_time = QTime.currentTime()

        # 기본설정(매수) 값
        basic_buy_max_count = self.spinBox_4.value()    #0 매수체결 회수
        basic_stock_count = self.spinBox_5.value()  #1 보유 종목 수(미체결 주문 포함)
        stock_start_time = self.timeEdit.time()     #2 특정시간대 시작 시간
        stock_end_time = self.timeEdit_2.time()     #3 특정시간대 끝 시간
        after_buyorder_elapsed_time = self.spinBox_6.value()    #4 매수주문 후 경과시간 설정
        cancel_buyorder_check = self.checkBox_4.isChecked()     #5 매수 자동취소 여부

        # 기본설정(매도) 값
        after_sellorder_elapsed_time = self.spinBox_7.value()   #6 매도주문 후 경과시간 설정
        cancel_sellorder_check = self.checkBox_5.isChecked()    #7 매도 자동최소 여부
        theday_sellorder_check = self.checkBox_6.isChecked()    #8 당일 청산 여부
        theday_nomal_sellorder_time = self.timeEdit_3.time()    #9 청산 요청 시간
        theday_nomal_sellorder_hoga = self.doubleSpinBox_10.value()    #10 청산 호가
        theday_first_sellorder_time = self.timeEdit_4.time()            #11 시장가 청산 시간

        # 매수 설정
        buy_type = self.comboBox_6.currentText()               #12 매수 형태(지정가, 시장가)
        buy_nomal_type_hoga = self.doubleSpinBox_11.value()    #13 지정가이면 호가
        buy_max_account = self.spinBox_8.value()              #14 1종목당 매수금액(단위 만원)

        # 매도설정(이익실현)
        sell_stoploss_check = self.radioButton.isChecked()         #15 매도방법 선택(1.스톱-시장가)
        sell_stoploss_sethoga_check = self.radioButton_2.isChecked()   #16 매도방법 선택(2.스톱-지정가)
        sell_trailing_check = self.radioButton_3.isChecked()    #17 매도방법 선택(3.트레일링)

        # 매도설정(손절)
        sell_limit_loss_check = self.radioButton_4.isChecked()  #24 매도(손실제한) 시장가 선택
        sell_limit_sethoga_check = self.radioButton_5.isChecked()  #25 매도(손실제한) 지정가 선택

        # 기본 설정
        order_type_lookup ={'신규매수': 1, '신규매도': 2, '매수취소': 3, '매도취소': 4}
        hoga_lookup = {'지정가': "00", '시장가': "03"}

        account_num = self.comboBox.currentText()
        order_type = "신규매도"
        hoga = "시장가"
        hoga_set = "지정가"

        if realType == "주식체결":     # 주식체결
            # print("주식체결")
            if code != "":
                chegyul_data.append(code)
                codeOrNot = code
            else:
                codeOrNot = realType

            # 주식체결되어 들어오는 해당 종목을 chegyul_data list에 저장
            for fid in (RealType.REALTYPE[realType].keys()):
                if fid == 10:  # 10 : 현재가를 조사
                    value = self.getCommRealData(codeOrNot, fid)
                    value = value.lstrip(' -+0')
                else:
                    value = self.getCommRealData(codeOrNot, fid)
                    value = value.strip()
                chegyul_data.append(value)

            # 실시간 편입 이탈 종목에 대한 코드 목록 리스트에 저장
            condition_search_stock_list = [key_code for key_code in self.condition_search_stock]

            # 실시간 조건검색 종목에 대하여 종목이 편입되면, 편입된 종목을 self.condition_search_stock에 추가
            if chegyul_data[0] in self.real_insert_stock_list:
                self.condition_search_stock[chegyul_data[0]] = chegyul_data
                self.real_insert_stock_list.remove(chegyul_data[0])

            # 실시간 편입 이탈 종목에 대한 코드 목록이 저장된 리스트와 비교하여 같은 코드 딕셔너리를 찾아 변경된 정보를 업데이트
            if chegyul_data[0] in condition_search_stock_list:
                self.condition_search_stock[chegyul_data[0]] = chegyul_data     # 업데이트 종목(편입된 종목)

            # 이하 실시간 잔고의 현재가를 업데이트 하기 위함
            if chegyul_data[0] in self.real_account_estimated:
                update_account = self.real_account_estimated.get(chegyul_data[0])
                update_account[4] = chegyul_data[1]

                # update_account[6] = float(update_account[4].strip()) * 100
                # update_account[7] = float(update_account[6]) / float(update_account[5])
                self.real_account_estimated[chegyul_data[0]] = update_account

            self.qtable_5_display()

            #자동매매 실행여부
            if not self.checkBox_3.isChecked():
                return

            #자동매도 설정
            if len(self.real_account_estimated) > 0:
                pass
            else:
                return

            # 예외 처리
            try:
                # 현재 리얼 데이터와 self.real_account_estimated의 key값으로 value를 얻어 auto_stock에 저장
                if chegyul_data[0] in self.real_account_estimated:
                    auto_stock = self.real_account_estimated.get(chegyul_data[0])
                else:
                    return

                self.qtable_5_display()

                # 리얼 데이터 종목의 잔고 매입 평균단가 : auto_stock[2]
                # 리얼 데이터 종목의 현재가 : chegyul_data[1]

                # 해당 종목 이익 구간
                if float(chegyul_data[1]) > float(auto_stock[2]):
                    # print("이익 구간")
                    ####################################################################################################
                    # <<이익구간 : 시장가 매도>>    스톱로스 이익실현 선택 (sell_stoploss_check)
                    ####################################################################################################
                    if sell_stoploss_check == True:
                        # print("스톱로스 이익실현 선택")
                        # 스톱로스 "이익실현률"을 적용하여 계산
                        stock_data_0 = float(float(auto_stock[2]) + float(auto_stock[2]) * float(self.doubleSpinBox.value()) / 100)
                        # print("이익실현률 적용 값", stock_data_0)
                        # 이익실현률 적용 값 범위에 들어온 경우 : 현재가 > 목표가
                        if float(chegyul_data[1]) > stock_data_0:
                            # 이미 매도하여 플래그가 있는 경우 패스
                            if chegyul_data[0] in self.busy_sell_stock_code_list:
                                print("이미 매도하여 패스:", chegyul_data[0])
                                pass
                            # 매도한 적이 없어 처음 매도하는 경우
                            else:
                                # print("이익 실현 매도")
                                self.listWidget_4.addItem(auto_stock[0] + auto_stock[1] + "종목을 스톱로스(이익실현) 하였습니다.")
                                # 종목코드: auto_stock[0], 보유수량: auto_stock[3]
                                self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                                        ["이익실현시장가매도", "0777", account_num, order_type_lookup[order_type], auto_stock[0],
                                                         auto_stock[3], 0, hoga_lookup[hoga], ""])
                                # 매도가 반복되어 허 매도 되지 않도록 플래그 추가
                                self.busy_sell_stock_code_list.append(chegyul_data[0])
                                print("self.busy_sell_stock_code_list", self.busy_sell_stock_code_list)
                        # 이익실현률에 못 미치는 경우 패스
                        else:
                            pass
                            # print("이익실현률에 미치지 못해 매도하지 않음")

                    ####################################################################################################
                    # <<이익구간 : 지정가 매도>> 스톱로스 이익실현 선택 (sell_stoploss_check)
                    ####################################################################################################
                    elif sell_stoploss_sethoga_check == True:
                        stock_data_0 = float(float(auto_stock[2]) + float(auto_stock[2]) * float(self.doubleSpinBox_2.value()) / 100)
                        # print("이익실현률 적용 값", stock_data_0)
                        # 이익실현률 적용 값인 경우
                        if float(chegyul_data[1]) > stock_data_0:
                            # 이미 매도하여 플래그가 있는 경우 패스
                            if chegyul_data[0] in self.busy_sell_stock_code_list:
                                print("이미 매도하여 패스:", chegyul_data[0])
                                pass
                            # 매도한 적이 없어 처음 매도하는 경우
                            else:
                                # print("이익 실현 매도")
                                madohoga = int(float(chegyul_data[1]) + float(chegyul_data[1]) * float(self.doubleSpinBox_3.value()) / 100)
                                self.listWidget_4.addItem(auto_stock[0] + auto_stock[1] + "종목을 스톱로스(이익실현) 하였습니다.")
                                # 종목코드: auto_stock[0], 보유수량: auto_stock[3]
                                self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                                        ["이익실현지정가매도", "0888", account_num, order_type_lookup[order_type], auto_stock[0],
                                                         auto_stock[3], madohoga, hoga_lookup[hoga_set], ""])
                                # 매도가 반복되어 허 매도 되지 않도록 플래그 추가
                                self.busy_sell_stock_code_list.append(chegyul_data[0])
                                print("self.busy_sell_stock_code_list", self.busy_sell_stock_code_list)
                        # 이익실현률에 못 미치는 경우 패스
                        else:
                            pass
                            # print("이익실현률에 미치지 못해 매도하지 않음")
                    ####################################################################################################
                    # <<이익구간 : 트레일링 매도>> 트레일링 매도 적용하여 +알파를 지속적 업데이트로 이익 극대화, -알파 이탈 시 매도
                    ####################################################################################################
                    elif sell_trailing_check == True:
                        # stock_data_0 = 기본목표 값
                        # trailing_plus = plus 목표 값
                        # trailing_minus = minus 이탈 값
                        # update_stock[] = self.real_account_estimated 잔고를 업데이트 하기 위한 리스트
                        update_stock = copy.deepcopy(auto_stock)
                        stock_data_0 = float(float(auto_stock[2]) + float(auto_stock[2]) * float(self.doubleSpinBox_4.value()) / 100)


                        # 기본목표 달성 시 : 트레일링 작동
                        if float(chegyul_data[1]) > stock_data_0:

                            # 이미 매도하여 플래그가 있는 경우 패스
                            if chegyul_data[0] in self.busy_sell_stock_code_list:
                                print("이미 매도하여 패스:", chegyul_data[0])
                                pass
                            # 매도한 적이 없는 경우
                            else:
                                # 트레일링 시작
                                if auto_stock[9] == '':
                                    update_stock[8] = int(stock_data_0)     # type 에러 여부 확인 필요
                                    update_stock[9] = 'Tr'
                                    if auto_stock[0] in self.real_account_estimated:
                                        self.real_account_estimated[auto_stock[0]] = update_stock

                                else:
                                    stock_data_plus = float(float(auto_stock[8]) + float(auto_stock[8]) * float(self.doubleSpinBox_5.value()) / 100)
                                    stock_data_minus = float(float(auto_stock[8]) + float(auto_stock[8]) * float(self.doubleSpinBox_6.value()) / 100)

                                    # 트레일링 plus 달성으로 목표값 업데이트
                                    if float(chegyul_data[1]) > stock_data_plus:
                                        update_stock[8] = int(stock_data_plus) # type 에러 여부 확인 필요
                                        update_stock[9] = update_stock[9] + '+'
                                        if auto_stock[0] in self.real_account_estimated:
                                            self.real_account_estimated[auto_stock[0]] = update_stock

                                    # 트레일링 minus 설정 값 이탈로 매도
                                    elif float(chegyul_data[1]) < stock_data_minus:
                                        # print("이익 실현 트레일링 매도")
                                        self.listWidget_4.addItem(auto_stock[0] + auto_stock[1] + "종목을 트레일링 매도 하였습니다.")
                                        # 종목코드: auto_stock[0], 보유수량: auto_stock[3]
                                        self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                            ["트레일링시장가매도", "0999", account_num, order_type_lookup[order_type],
                                             auto_stock[0], auto_stock[3], 0, hoga_lookup[hoga], ""])
                                        # 매도가 반복되어 허 매도 되지 않도록 플래그 추가
                                        self.busy_sell_stock_code_list.append(chegyul_data[0])
                                        print("self.busy_sell_stock_code_list", self.busy_sell_stock_code_list)

                                    else:
                                        pass

                        # 이익실현률에 못 미치는 경우 패스
                        else:
                            pass

                    # To Do : <<이익 구간 : 기타 방법 추가>
                    else:
                        pass

                # 리얼 데이터 종목의 잔고 매입 평균단가 : auto_stock[2]
                # 리얼 데이터 종목의 현재가 : chegyul_data[1]

                # 해당 종목 손실 구간
                elif float(chegyul_data[1]) < float(auto_stock[2]):
                    # print("손실 구간")
                    ####################################################################################################
                    # <<손실구간 : 시장가 매도>> 스톱로스 손실 제한 선택 (sell_limit_loss_check)
                    ####################################################################################################
                    if sell_limit_loss_check == True:
                        # print("스톱로스 손실제한 선택")
                        # 스톱로스 "손실제한률"을 적용하여 계산
                        stock_data_1 = float(float(auto_stock[2]) + float(auto_stock[2]) * float(self.doubleSpinBox_7.value()) / 100)
                        # 손실제한률 적용 값인 경우
                        if float(chegyul_data[1]) < stock_data_1:
                            # 이미 매도하여 플래그가 있는 경우 패스
                            if chegyul_data[0] in self.busy_sell_stock_code_list:
                                pass
                            # 매도한 적이 없어 처음 매도하는 경우
                            else:
                                # print("손실 제한 매도")
                                self.listWidget_4.addItem(auto_stock[0] + auto_stock[1] + "종목을 스톱로스(손실제한) 하였습니다.")
                                # 종목코드: auto_stock[0], 보유수량: auto_stock[3]
                                self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                                        ["손실제한매도", "0999", account_num, order_type_lookup[order_type], auto_stock[0],
                                                        auto_stock[3], 0, hoga_lookup[hoga], ""])
                                # 매도가 반복되어 허매도(이미 매도주문 하였으나 중복 매도) 되지 않도록 플래그 추가
                                self.busy_sell_stock_code_list.append(chegyul_data[0])
                                print("self.busy_sell_stock_code_list", self.busy_sell_stock_code_list)

                        # 손실제한률에 못 미치는 경우 패스
                        else:
                            pass
                            # print("손실제한률에 미치지 못해 매도하지 않음")

                    ####################################################################################################
                    # <<손실 구간 : 지정가 매도>> 스톱로스 손실 제한 선택 (sell_limit_loss_check)
                    ####################################################################################################
                    elif sell_limit_sethoga_check == True:
                        stock_data_1 = float(float(auto_stock[2]) + float(auto_stock[2]) * float(self.doubleSpinBox_8.value()) / 100)
                        # 손실제한률 적용 값인 경우
                        if float(chegyul_data[1]) < stock_data_1:
                            # 이미 매도하여 플래그가 있는 경우 패스
                            if chegyul_data[0] in self.busy_sell_stock_code_list:
                                pass
                            # 매도한 적이 없어 처음 매도하는 경우
                            else:
                                # print("손실 제한 매도")
                                madohoga = int(float(chegyul_data[1]) + float(chegyul_data[1]) * float(self.doubleSpinBox_12.value()) / 100)
                                self.listWidget_4.addItem(auto_stock[0] + auto_stock[1] + "종목을 스톱로스(손실제한) 하였습니다.")
                                # 종목코드: auto_stock[0], 보유수량: auto_stock[3]
                                self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                    ["손실제한매도", "0999", account_num, order_type_lookup[order_type], auto_stock[0],
                                     auto_stock[3], madohoga, hoga_lookup[hoga_set], ""])
                                # 매도가 반복되어 허매도(이미 매도주문 하였으나 중복 매도) 되지 않도록 플래그 추가
                                self.busy_sell_stock_code_list.append(chegyul_data[0])
                                print("self.busy_sell_stock_code_list", self.busy_sell_stock_code_list)

                    # To Do : <<손실 구간 : 기타 방법 추가>
                    else:
                        pass

                else:
                    pass

            except:
                print("실시간 매도에서 에러 검출")
                self.listWidget_4.addItem("실시간 매도에서 에러 검출")
                return

        # 조건검색식 화면에 정보 출력
        self.qtable_3_display()
        self.qtable_5_display()

    # 주문 접수/확인 수신시 이벤트, 주문요청후 주문접수, 체결통보, 잔고통보를 수신할 때 마다 호출
    def _receiveChejanData(self, gubun, itemCnt, fidList):
        """
        :param gubun: string - 체결구분('0': 주문접수/주문체결, '1': 잔고통보, '3': 특이신호)
        :param itemCnt: int - fid의 갯수
        :param fidList: string - fidList 구분은 ;(세미콜론) 이다.
        """
        print("gubun: ", gubun, "itemCnt: ", itemCnt, "fidList: ", fidList)

        try:
            # 주문 접수, 체결 결과를 임시로 저장
            jumun_chejan_data = []

            # 주문 접수, 주문 체결 시 실시간 데이터 처리
            if gubun == "0":
                realType = "주문체결"

                # 주문체결 여부를 실시간으로 처리
                for fid in (RealType.REALTYPE[realType].keys()):
                    value = self.getChejanData(fid)
                    value = value.lstrip(' A')
                    jumun_chejan_data.append(value)

                # 주문번호(딕셔너리의 키 값)에 따른 주문 접수 --> 주문 체결로 업데이트
                # self.jumun_chegyul_dic ={...}는 매수와 매도 주문정보를 함께 보유
                self.jumun_chegyul_dic[jumun_chejan_data[11]] = jumun_chejan_data

                # 매수와 매도를 구분하여 저장
                if jumun_chejan_data[13] == "+매수":
                    self.buy_and_nobuy[jumun_chejan_data[11]] = jumun_chejan_data
                    if jumun_chejan_data[12] =="체결":
                        # 에러 방지
                        if jumun_chejan_data[0] in self.busy_buy_stock_code_list:
                            self.busy_buy_stock_code_list.remove(jumun_chejan_data[0])

                elif jumun_chejan_data[13] == "-매도":
                    self.sell_and_nosell[jumun_chejan_data[11]] = jumun_chejan_data
                    if jumun_chejan_data[12] =="체결":
                        # 리스트.remove 실행 시 에러 방지
                        if jumun_chejan_data[0] in self.busy_sell_stock_code_list:
                            self.busy_sell_stock_code_list.remove(jumun_chejan_data[0])
                            self.forbid_buy_temp.remove(jumun_chejan_data[0])
                            print("jumun_chejan_data[0] 값", jumun_chejan_data[0])
                else:
                    pass


                print("self.forbid_buy_temp 확인", self.forbid_buy_temp)
                print("chejandata 주문체결:", self.jumun_chegyul_dic)

                self.qtable_6_display()
                self.qtable_7_display()
                self.qtable_9_display()

            # 주문 체결 후 잔고 전달
            elif gubun == "1":
                realType = "잔고"
                for fid in (RealType.REALTYPE[realType].keys()):
                    value = self.getChejanData(fid)
                    value = value.lstrip(' A')
                    jumun_chejan_data.append(value)

                if jumun_chejan_data[0] in self.real_account_estimated:
                    update_account = self.real_account_estimated.get(jumun_chejan_data[0])
                    for i in range(8):
                        update_account[i] = jumun_chejan_data[i]
                        # print("i", i, "up_acc", update_account[i])

                    # update_account[6] = float(update_account[4].strip()) * 100
                    # update_account[7] = float(update_account[6]) / float(update_account[5])

                    self.chejan_dic[jumun_chejan_data[0]] = jumun_chejan_data
                    self.real_account_estimated[jumun_chejan_data[0]] = update_account
                    print("chejandata 잔고:", self.chejan_dic)

                # 잔고 전달을 확인하여 매도 체결이 되면 self.busy_sell_stock_code_list 플래그 해제
                # 순서 확인 필요
                if jumun_chejan_data[8] == "1":  # 매도 인 경우
                    if jumun_chejan_data[0] in self.busy_sell_stock_code_list:
                        # list.remove 실행 시 에러방지(list.remove 실행 시 코드 없으면 에러 발생)
                        if jumun_chejan_data[0] in self.busy_sell_stock_code_list:
                            self.busy_sell_stock_code_list.remove(jumun_chejan_data[0])
                            print("jumun_chejan_data[0]", jumun_chejan_data[0])

                elif jumun_chejan_data[8] == "2":   #매수 인 경우
                    print("jumun_chejan_data[8]", jumun_chejan_data[8])

                else:
                    print("기타")

                print("END,busy_sell_stock_code_list ", self.busy_sell_stock_code_list)


                self.qtable_10_display()
                self.qtable_5_display()

            else:
                pass

            print("최잔에서 self.busy_sell_stock_code_list", self.busy_sell_stock_code_list)


        except:
            print("체잔 에러")

    ####################################################################################################################
    # 종목 조회 버튼 클릭 시 처리
    ####################################################################################################################
    def _stock_search(self):
        searchStock = self.lineEdit_11.text()
        if searchStock == "":
            QMessageBox.about(self, "Message", "해당 종목이 없습니다.!! 다시 입력하세요.!!   ")
        else:
            have_in_dict = searchStock in self.dict_stock.keys()
            if have_in_dict == True:
                search_code = self.dict_stock.get(searchStock)
                # stockName = self.KW_API.dynamicCall("GetMasterCodeName(QString)", code)
                self.lineEdit_12.setText(searchStock)
                self.lineEdit_13.setText(search_code)

                self.KW_API.dynamicCall("SetInputValue(QString, QString)", "종목코드", search_code)
                self.KW_API.dynamicCall("CommRqData(QString, QString, int, QString)", "종목정보요청", "opt10001", 0, "5000")

                self.KW_API.dynamicCall("SetInputValue(QString, QString)", "종목코드", search_code)
                self.KW_API.dynamicCall("CommRqData(QString, QString, int, QString)", "주식호가", "opt10004", 0, "5001")

            else:
                QMessageBox.about(self, "Message", "해당 종목이 없습니다.!! 다시 입력하세요.!!   ")

    ####################################################################################################################
    #qtableWidget에 데이터 출력
    ####################################################################################################################
    def qtable_9_display(self):
        count = len(self.sell_and_nosell)
        keylist = ['종목코드', '종목명', '주문시간', '매매구분', '주문수량', '주문가격', '체결량', '체결가', '체결누계금액',
                   '현재가', '미체결수량',  '주문번호', '주문상태', '주문구분', '원주문번호']
        count_keylist = len(keylist)

        # qtablewidget 초기설정
        self.tableWidget_9.clearContents()
        self.tableWidget_9.setColumnCount(count_keylist)
        self.tableWidget_9.setRowCount(count)
        self.tableWidget_9.setHorizontalHeaderLabels(keylist)
        self.tableWidget_9.setAlternatingRowColors(True)  # 열의 색깔 교차 변경
        self.tableWidget_9.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_9.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.tableWidget_9.setFocusPolicy(Qt.StrongFocus)
        # qtablewidget 출력
        j = 0
        display = []
        for codename in self.sell_and_nosell.keys():
            display = self.sell_and_nosell.get(codename)
            for i in range(0, count_keylist):
                table_cell = display[i]
                table_cell = QTableWidgetItem(table_cell)
                table_cell.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.tableWidget_9.setItem(j, i, table_cell)
            j += 1
        return 0

    ####################################################################################################################
    #qtableWidget 7 에 데이터 출력
    ####################################################################################################################
    def qtable_7_display(self):
        count = len(self.buy_and_nobuy)
        # 금일 매수 주문한 종목 수 저장
        self.today_stock_count = len(self.buy_and_nobuy)

        keylist = ['종목코드', '종목명', '시간', '매매구분', '주문수량', '주문가격', '체결량', '체결가',
                   '체결누계금액', '현재가', '미체결수량', '주문번호', '주문상태', '주문구분', '원주문번호']
        count_keylist = len(keylist)

        # qtablewidget 초기설정
        self.tableWidget_7.clearContents()
        self.tableWidget_7.setColumnCount(count_keylist)
        self.tableWidget_7.setRowCount(count)
        self.tableWidget_7.setHorizontalHeaderLabels(keylist)
        self.tableWidget_7.setAlternatingRowColors(True)  # 열의 색깔 교차 변경
        self.tableWidget_7.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_7.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.tableWidget_7.setFocusPolicy(Qt.StrongFocus)
        # qtablewidget 출력
        j = 0
        display = []
        for codename in self.buy_and_nobuy.keys():
            display = self.buy_and_nobuy.get(codename)
            for i in range(0, count_keylist):
                table_cell = display[i]
                table_cell = QTableWidgetItem(table_cell)
                table_cell.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.tableWidget_7.setItem(j, i, table_cell)
            j += 1
        return 0

    ####################################################################################################################
    # qtableWidget 6 에 데이터 출력
    # 주문체결 매수와 매도에 대한 정보 출력
    ####################################################################################################################
    def qtable_6_display(self):
        count = len(self.jumun_chegyul_dic)
        keylist = ['종목코드', '종목명', '주문시간', '매매구분', '주문수량', '주문가격', '체결량', '체결가', '체결누계금액',
                   '현재가', '미체결수량',  '주문번호', '주문상태', '주문구분', '원주문번호']
        count_keylist = len(keylist)

        # qtablewidget 초기설정
        self.tableWidget_6.clearContents()
        self.tableWidget_6.setColumnCount(count_keylist)
        self.tableWidget_6.setRowCount(count)
        self.tableWidget_6.setHorizontalHeaderLabels(keylist)
        self.tableWidget_6.setAlternatingRowColors(True)  # 열의 색깔 교차 변경
        self.tableWidget_6.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_6.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.tableWidget_6.setFocusPolicy(Qt.StrongFocus)
        # qtablewidget 출력
        j = 0
        display = []
        for codename in self.jumun_chegyul_dic.keys():
            display = self.jumun_chegyul_dic.get(codename)
            for i in range(0, count_keylist):
                table_cell = display[i]
                table_cell = QTableWidgetItem(table_cell)
                table_cell.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.tableWidget_6.setItem(j, i, table_cell)
            j += 1
        return 0

    ####################################################################################################################
    # qtableWidget 5 에 데이터 출력
    # 보유 종목 잔고 출력
    ####################################################################################################################
    def qtable_5_display(self):
        count = len(self.real_account_estimated)
        keylist = ['종목코드', '종목명', '평균단가', '보유수량', '현재가', '매입금액', '손익금액', '손익율', '목표가', '도달상태', '강매방법', '강매호가', '강매실행']
        count_keylist = len(keylist)

        # qtablewidget 초기설정
        self.tableWidget_5.clearContents()
        self.tableWidget_5.setColumnCount(count_keylist)
        self.tableWidget_5.setRowCount(count)
        self.tableWidget_5.setHorizontalHeaderLabels(keylist)
        self.tableWidget_5.setAlternatingRowColors(True)  # 열의 색깔 교차 변경
        self.tableWidget_5.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_5.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.tableWidget_5.setFocusPolicy(Qt.StrongFocus)
        # qtablewidget 출력
        j = 0
        display = []
        for codename in self.real_account_estimated.keys():
            display = self.real_account_estimated.get(codename)
            for i in range(0, count_keylist):             # 강제매도 방법 추가하면, -3 해야, 다운 방지
                table_cell = display[i]
                table_cell = QTableWidgetItem(table_cell)
                table_cell.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.tableWidget_5.setItem(j, i, table_cell)
            j += 1
        return 0

    #qtableWidget에 데이터 출력
    def qtable_10_display(self):
        count = len(self.chejan_dic)
        keylist = ['종목코드', '종목명', '평균단가', '보유수량', '현재가', '매입금액', '손익금액', '손익율', '목표가', '도달상태', '강매방법', '강매호가', '강매실행']
        count_keylist = len(keylist)

        # qtablewidget 초기설정
        self.tableWidget_10.clearContents()
        self.tableWidget_10.setColumnCount(count_keylist)
        self.tableWidget_10.setRowCount(count)
        self.tableWidget_10.setHorizontalHeaderLabels(keylist)
        self.tableWidget_10.setAlternatingRowColors(True)  # 열의 색깔 교차 변경
        self.tableWidget_10.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_10.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.tableWidget_10.setFocusPolicy(Qt.StrongFocus)
        # qtablewidget 출력
        j = 0
        display = []
        for codename in self.chejan_dic.keys():
            display = self.chejan_dic.get(codename)
            for i in range(0, count_keylist):             # 강제매도 방법 추가하면, -3 해야, 다운 방지
                table_cell = display[i]
                table_cell = QTableWidgetItem(table_cell)
                table_cell.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.tableWidget_10.setItem(j, i, table_cell)
            j += 1
        return 0

    #qtableWidget_3에 데이터 출력
    def qtable_3_display(self):
        count = len(self.condition_search_stock)
        # qtablewidget_3 초기설정
        self.tableWidget_3.clearContents()
        self.tableWidget_3.setRowCount(count)
        self.tableWidget_3.setAlternatingRowColors(True)  # 열의 색깔 교차 변경
        self.tableWidget_3.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_3.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.tableWidget_3.setFocusPolicy(Qt.StrongFocus)
        # qtablewidget_3 출력
        j = 0
        display = []
        for codename in self.condition_search_stock.keys():
            display = self.condition_search_stock.get(codename)
            for i in range(0, 9):
                if i == 0:
                    table_cell = self.KW_API.dynamicCall("GetMasterCodeName(QString)", codename).strip() #종목코드 -> 종목명 표시
                else:
                    table_cell = display[i]
                table_cell = QTableWidgetItem(table_cell)
                table_cell.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.tableWidget_3.setItem(j, i, table_cell)
            j += 1
        return 0

    ####################################################################################################################
    # 종목조회 등등 : CommRqData 함수 호출 -> OnReceiveTrData 응답
    # 종목조회
    # 조건검색 종목
    # 주식호가 조회
    # 계좌평가잔고내역요청
    # 계좌평가현황요청
    # 종목정보요청
    ####################################################################################################################
    def _receive_trdata(self, sScrNo, sRQName, sTrCode, SRecodeName, sPrevNext, nDataLength, sErrorCode, sMessage, sSplmMsg):
        #
        data = []
        pop_data = []
        
        # TEST :: 이 값이 3,500 ~ 4,000 사이에서 프로그램 정지(키움 정책)
        self.count_trdata_event += 1
        print("self.count_trdata_event", self.count_trdata_event)

        # 주문번호와 주문루프
        self.orderNo = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "주문번호")

        # _receive tr condition에서, self.KW_API.dynamicCall("CommKwRqData(QString, Bool, int, int, QString, QString)",
        # stockCodeList, 0, count, 0, "조건검색종목", "1100") 요청에 따른 값을 읽어옴옴
        if sRQName == "조건검색종목":
            count = self.KW_API.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)
            for i in range(count):
                stockCode = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목코드")
                currentPrice = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재가")
                netChange = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "전일대비")
                upDownRate = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "등락율")
                volume = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "거래량")
                startPrice = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "시가")
                highPrice = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "고가")
                low_Price = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "저가")
                density = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "체결강도")
                #
                data.append(stockCode.strip())
                data.append(currentPrice.lstrip(' -+0'))
                data.append(netChange.strip())
                data.append(upDownRate.strip())
                data.append(volume.strip())
                data.append(startPrice.strip())
                data.append(highPrice.strip())
                data.append(low_Price.strip())
                data.append(density.strip())
                #
                self.condition_search_stock[stockCode.strip()] = data
                data = []

            self.qtable_3_display()

        if sRQName == "주식호가":
            self.listWidget_2.clear()
            self.listWidget_3.clear()

            for i in range(9):
                maedo_hoga = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매도"+str(10 - i)+"차선호가")
                maedo_hoga = self.change_format(maedo_hoga, 0)
                self.listWidget_2.addItem(maedo_hoga)

                if i == 4:
                    maedo_remain = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매도"+str(10 - i)+"우선잔량")
                    maedo_remain = self.change_format(maedo_remain, 0)
                    self.listWidget_3.addItem(maedo_remain)
                else:
                    maedo_remain = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매도"+str(10 - i)+"차선잔량")
                    maedo_remain = self.change_format(maedo_remain, 0)
                    self.listWidget_3.addItem(maedo_remain)

            maedo_first_hoga = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매도최우선호가")
            maedo_first_hoga = self.change_format(maedo_first_hoga, 0)
            self.listWidget_2.addItem(maedo_first_hoga)

            maedo_first_remain = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매도최우선잔량")
            maedo_first_remain = self.change_format(maedo_first_remain, 0)
            self.listWidget_3.addItem(maedo_first_remain)

            maesu_first_hoga = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매수최우선호가")
            maesu_first_hoga = self.change_format(maesu_first_hoga, 3)
            self.listWidget_2.addItem(maesu_first_hoga)

            maesu_first_remain = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매수최우선잔량")
            maesu_first_remain = self.change_format(maesu_first_remain, 3)
            self.listWidget_3.addItem(maesu_first_remain)

            for i in range(9):
                if i == 4:
                    maesu_hoga = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매수" + str(2 + i) + "우선호가")
                    maesu_hoga = self.change_format(maesu_hoga, 3)
                    self.listWidget_2.addItem(maesu_hoga)

                    maesu_remain = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매수" + str(2 + i) + "우선잔량")
                    maesu_remain = self.change_format(maesu_remain, 3)
                    self.listWidget_3.addItem(maesu_remain)

                else:
                    maesu_hoga = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매수" + str(2 + i) + "차선호가")
                    maesu_hoga = self.change_format(maesu_hoga, 3)
                    self.listWidget_2.addItem(maesu_hoga)

                    maesu_remain = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                         sRQName, 0, "매수" + str(2 + i) + "차선잔량")
                    maesu_remain = self.change_format(maesu_remain, 3)
                    self.listWidget_3.addItem(maesu_remain)

        if sRQName == "계좌평가잔고내역요청":
            totalPurchase = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총매입금액")
            totalPurchase = self.change_format(totalPurchase, 0)
            self.lineEdit_6.setText(totalPurchase)

            totalEstimate = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총평가금액")
            totalEstimate = self.change_format(totalEstimate, 0)
            self.lineEdit_7.setText(totalEstimate)

            totalProfitLoss = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총평가손익금액")
            totalProfitLoss = self.change_format(totalProfitLoss, 0)
            self.lineEdit_8.setText(totalProfitLoss)

            totalProfitRate = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총수익률(%)")
            totalProfitRate = self.change_format(totalProfitRate, 2)
            self.lineEdit_9.setText(totalProfitRate)

            Estimate_Money = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "추정예탁자산")
            Estimate_Money = self.change_format(Estimate_Money, 0)
            self.lineEdit_10.setText(Estimate_Money)



        if sRQName == "실시간계좌평가잔고내역요청":
            keylist = ['총매입금액', '총평가금액', '총평가손익금액', '총수익률(%)', '추정예탁자산']
            for key in keylist:
                temp = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, key)
                data.append(temp)

            self.lineEdit_22.setText(self.change_format(data[0], 0))
            self.lineEdit_24.setText(self.change_format(data[1], 0))
            self.lineEdit_25.setText(self.change_format(data[2], 0))
            self.lineEdit_20.setText(self.change_format(data[3], 2))
            self.lineEdit_21.setText(self.change_format(data[4], 0))

        # opw00004 이벤트에 따른 처리
        if sRQName == "계좌평가현황요청":
            deposit = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "D+2추정예수금")
            self.lineEdit_23.setText(self.change_format(deposit, 0))

            real_account_estimated_temp = copy.deepcopy(self.real_account_estimated)
            self.real_account_estimated = {}

            count = self.KW_API.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)
            keylist = ['종목코드', '종목명', '평균단가', '보유수량', '현재가', '매입금액', '손익금액', '손익율', '시가', '저가', '시가', '저가', '저가']

            for i in range(count):
                for key in keylist:
                    temp = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, key)
                    data.append(temp)

                for j in range(0, 10):
                    # 0 : 부호있는 int
                    # 1 : 100으로 나눈 float
                    # 2 : 부호있는 float
                    # 3 : 부호 없는 int
                    # 4 : 'A'문자 제거
                    # 그 외 : 패싱
                    if j == 0:
                        data[j] = self.change_format(data[j], 4)    #0
                    elif j == 1:
                        data[j] = self.change_format(data[j], 5)    #1
                    elif j == 2:
                        data[j] = self.change_format(data[j], 99)    #2
                    elif j == 3:
                        data[j] = self.change_format(data[j], 3)    #3
                    elif j == 4:
                        data[j] = self.change_format(data[j], 99)  # 4
                    elif j == 5:
                        data[j] = self.change_format(data[j], 3)  # 5
                    elif j == 6:
                        data[j] = self.change_format(data[j], 0)    #6
                    elif j == 7:
                        data[j] = self.change_format(data[j], 2)    #7
                    else:
                        data[j] = self.change_format(data[j], 99)

                if data[0] in real_account_estimated_temp:
                    pop_data = real_account_estimated_temp[data[0]]
                    data[8] = str(pop_data[8])
                    data[9] = str(pop_data[9])
                    data[10] = str(pop_data[10])
                    data[11] = str(pop_data[11])
                    data[12] = str(pop_data[12])
                print("pop_data", pop_data)

                self.real_account_estimated[data[0]] = data
                data = []

            self.qtable_5_display()

        # 매수주문에 따른 실시간 매수체결 현황
        # To Do : 실시간 체결미체결은 최대값 count = 100이므로 해당 코드 수정 필요
        if sRQName == "실시간매수체결미체결":
            self.buy_and_nobuy = {}
            self.no_buy = {}
            self.end_buy = {}

            count = self.KW_API.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)
            print("매수카운트", count)
            keylist = ['종목코드', '종목명', '시간', '매매구분', '주문수량', '주문가격', '체결량', '체결가',
                       '체결누계금액', '현재가', '미체결수량', '주문번호', '주문상태', '주문구분', '원주문번호']

            for i in range(count):
                for key in keylist:
                    temp = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, key)
                    data.append(self.change_format(temp, 5))
                self.buy_and_nobuy[self.change_format(data[11], 5)] = data
                data = []

            # self.buy_and_nobuy(매수 체결과 미체결 저장 정보) ==> self.no_buy(매수 미체결), self.end_buy(매수 체결)에 저장
            for codename in self.buy_and_nobuy.keys():
                all_buy_order = self.buy_and_nobuy.get(codename)  # 매수주문한 모든 정보 조회
                if all_buy_order[12] == "접수":
                    self.no_buy[all_buy_order[0]] = all_buy_order  # 코드
                else:
                    self.end_buy[all_buy_order[0]] = all_buy_order  # 코드

            print("매수 체결 :", self.no_buy, "매수 미체결", self.end_buy)

            self.qtable_7_display()

        # 주문에 따른 실시간 체결 현황
        # To Do : 실시간 체결미체결은 최대값 count = 100이므로 해당 코드 수정 필요
        if sRQName == "실시간매도체결미체결":
            self.sell_and_nosell = {}
            count = self.KW_API.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)
            keylist = ['종목코드', '종목명', '주문시간', '매매구분', '주문수량', '주문가격', '체결량', '체결가', '체결누계금액',
                       '현재가', '미체결수량',  '주문번호', '주문상태', '주문구분', '원주문번호']

            for i in range(count):
                for key in keylist:
                    temp = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, key)
                    data.append(self.change_format(temp, 5))
                self.sell_and_nosell[self.change_format(data[11], 5)] = data
                data = []

            # print(keylist)
            print("sell_and_nosell:", self.sell_and_nosell)

            self.qtable_9_display()

        if sRQName == "종목정보요청":
            stockPrice = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "현재가")
            spinPrice = stockPrice
            stockPrice = self.change_format(stockPrice, 3)
            self.lineEdit_14.setText(stockPrice)
            self.spinBox_2.setValue(int(spinPrice))

            upDown = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "전일대비")
            upDown = self.change_format(upDown, 0)
            self.lineEdit_15.setText(upDown)

            volumeToday = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "거래량")
            volumeToday = self.change_format(volumeToday, 0)
            self.lineEdit_16.setText(volumeToday)

            upDownRate = self.KW_API.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "등락율")
            upDownRate = self.change_format(upDownRate, 2)
            self.lineEdit_17.setText(upDownRate)

    # 0 : 부호있는 int
    # 1 : 100으로 나눈 float
    # 2 : 부호있는 float
    # 3 : 부호 없는 int
    # 4 : 'A'문자 제거
    # 그 외 : 패싱
    def change_format(self, data, index):   # 금액을 천단위 콤마(",")를 추가하여 반환하는 함수

        if index == 99:
            form = data.lstrip(' -+0')
            return form

        is_minus = False    # 마이너스 표기를 False
        data = data.strip(' ')
        if data.startswith('-'):    # 입력된 금액의 앞자리가 - 일 경우
            is_minus = True # 마이너스 표기를 참으로 지정

        strip_str = data.lstrip('-')   # 입력된 금액의 앞자리에 - 기호 삭제

        if index == 0:   # 퍼센트 구분 기호가 0이라면
            strip_data = int(strip_str) # 입력값을 int로 변환 후
            form = strip_data
            form = format(strip_data, ',d') # 정수형으로 만듬
        elif index == 1:    # 퍼센트 구분 기호가 1이라면
            strip_data = int(strip_str) # 입력값을 int로 변환 후
            strip_data = strip_data / 100   # 100으로 나눠주고
            form = format(strip_data, ',.2f')   # 소수점 2자리까지 자름
        elif index == 2:  # 퍼센트 구분 기호가 2이라면
            strip_data = float(strip_str)   # 입력값을 float로 변환 후
            form = format(strip_data, ',.2f')   # 소수점 2자리까지 자름
        elif index == 3: # 강제로 부호를 제거
            strip_data = int(strip_str) # 입력값을 int로 변환 후
            form = format(strip_data, ',d') # 정수형으로 만듬
            is_minus = False
        elif index == 4:
            form = strip_str.lstrip('A')
        else:
            form = strip_str

        if form.startswith('.'):    # 변환된 금액의 앞자리가 . 으로 시작한다면
            form = '0' + form   # 변환된 금액에 앞에 0을 붙여줌

        if is_minus:    # 입력된 금액이 마이너스 였다면
            form = '-' + form   # 변환된 금액에 앞에 - 기호를 붙여줌

        return form # 변환됨 금액을 반환함

    # CommConnect 함수가 OnEventConnect 함수를 호출(로그인요청: CommConnect함수호출 -> 로인인 요청결과: OnEventConnect 함수 호출)
    # 사용자는 CommConnect 일반함수를 호출해서 로그인 화면을 띄움. 그리고 로그인을 진행
    # 사용자가 키움서버로 보낸 요청의 결과로 이벤트 함수를 호출. 사용자는 아래 이벤트 함수에서 요청의 결과를 입력변수에 전달.
    def _event_connect(self, err_code):
        if err_code == 0:
            accouns_num = int(self.KW_API.dynamicCall("GetLoginInfo(QString)", "ACCOUNT_CNT"))  # 계좌 수
            accounts = self.KW_API.dynamicCall("GetLoginInfo(QString)", "ACCNO")  # 계좌번호
            accounts_list = accounts.split(';')[0:accouns_num]
            self.comboBox.addItems(accounts_list)

            name = self.KW_API.dynamicCall("GetLoginInfo(QString)", "USER_NAME")  #유저 이름
            user_id = self.KW_API.dynamicCall("GetLoginInfo(QString)", "USER_ID") # 유저 id
            server_gubun = self.KW_API.dynamicCall("GetLoginInfo(QString)", "GetServerGubun")  # 모의 / 실제 여부

            self.lineEdit.setText(name)
            self.lineEdit_2.setText(user_id)
            if server_gubun == '1':
                self.lineEdit_3.setText("모의투자")
            else:
                self.lineEdit_3.setText("실제투자")

            # 코스피와 코스탁 종목코드 가져오기
            stock_Kospi = self.KW_API.dynamicCall("GetCodeListByMarKet(QString)","0")
            stock_Kospi = stock_Kospi.split(';')
            stock_Kosdaq = self.KW_API.dynamicCall("GetCodeListByMarKet(QString)","10")
            stock_Kosdaq = stock_Kosdaq.split(';')

            # 코스피와 코스탁 종목코드에 대응된 종목명을 "딕셔너리 변수" dict_kospi, dict_kosdaq에 각각 저장 후 dict_stock에 업데이트
            for i in range(len(stock_Kospi)):
                list = self.KW_API.dynamicCall("GetMasterCodeName(QString)", stock_Kospi[i])
                self.dict_kospi.setdefault(list, stock_Kospi[i])
            # kosdaq
            for i in range(len(stock_Kosdaq)):
                list2 = self.KW_API.dynamicCall("GetMasterCodeName(QString)", stock_Kosdaq[i])
                self.dict_kosdaq.setdefault(list2, stock_Kosdaq[i])

            # self.dict_stock에 합치기(코스피와 코스닥 정보)
            self.dict_stock.update(self.dict_kospi)
            self.dict_stock.update(self.dict_kosdaq)

            # 조건식 로드  : getconditionload 함수는 onReceiveConditionVer함수를 호출 -> 사용자 조건식을 요청하고 화면에 바인딩
            self.KW_API.dynamicCall("GetConditionLoad()")

        self.timer_check.start(1000*15)

        # 2.0초 매수 이벤트 : 타이머
        # self.timer_buy_sell = QTimer(self)

        # 60.0초 타이머(60초 마다 이벤트 발생)
        self.timer_60s.start(1000 * 60)

    # 참고자료 참조
    # ###############################################################
    # 메서드 정의: 주문과 잔고처리 관련 메서드                      #
    # 1초에 5회까지 주문 허용                                      #
    ###############################################################

    def sendOrder(self, requestName, screenNo, accountNo, orderType, code, qty, price, hogaType, originOrderNo):

        """
        주식 주문 메서드

        sendOrder() 메소드 실행시,
        OnReceiveMsg, OnReceiveTrData, OnReceiveChejanData 이벤트가 발생한다.
        이 중, 주문에 대한 결과 데이터를 얻기 위해서는 OnReceiveChejanData 이벤트를 통해서 처리한다.
        OnReceiveTrData 이벤트를 통해서는 주문번호를 얻을 수 있는데, 주문후 이 이벤트에서 주문번호가 ''공백으로 전달되면,
        주문접수 실패를 의미한다.

        :param requestName: string - 주문 요청명(사용자 정의)
        :param screenNo: string - 화면번호(4자리)
        :param accountNo: string - 계좌번호(10자리)
        :param orderType: int - 주문유형(1: 신규매수, 2: 신규매도, 3: 매수취소, 4: 매도취소, 5: 매수정정, 6: 매도정정)
        :param code: string - 종목코드
        :param qty: int - 주문수량
        :param price: int - 주문단가
        :param hogaType: string - 거래구분(00: 지정가, 03: 시장가, 05: 조건부지정가, 06: 최유리지정가, 그외에는 api 문서참조)
        :param originOrderNo: string - 원주문번호(신규주문에는 공백, 정정및 취소주문시 원주문번호르 입력합니다.)
        """

        if not self.getConnectState():
            raise KiwoomConnectError()

        if not (isinstance(requestName, str)
                and isinstance(screenNo, str)
                and isinstance(accountNo, str)
                and isinstance(orderType, int)
                and isinstance(code, str)
                and isinstance(qty, int)
                and isinstance(price, int)
                and isinstance(hogaType, str)
                and isinstance(originOrderNo, str)):

            raise ParameterTypeError()

        returnCode = self.KW_API.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                      [requestName, screenNo, accountNo, orderType, code, qty, price, hogaType, originOrderNo])

        if returnCode != ReturnCode.OP_ERR_NONE:
            raise KiwoomProcessingError("sendOrder(): " + ReturnCode.CAUSE[returnCode])

        # receiveTrData() 에서 루프종료
        self.orderLoop = QEventLoop()
        self.orderLoop.exec_()

    def getChejanData(self, fid):
        """
        주문접수, 주문체결, 잔고정보를 얻어오는 메서드

        이 메서드는 receiveChejanData() 이벤트 메서드가 호출될 때 그 안에서 사용해야 합니다.

        :param fid: int
        :return: string
        """

        if not isinstance(fid, int):
            raise ParameterTypeError()

        cmd = 'GetChejanData("%s")' % fid
        data = self.KW_API.dynamicCall(cmd)
        return data

    ###############################################################
    # 기타 메서드 정의                                                #
    ###############################################################

    def getCodeListByMarket(self, market):
        """
        시장 구분에 따른 종목코드의 목록을 List로 반환한다.

        market에 올 수 있는 값은 아래와 같다.
        '0': 장내, '3': ELW, '4': 뮤추얼펀드, '5': 신주인수권, '6': 리츠, '8': ETF, '9': 하이일드펀드, '10': 코스닥, '30': 제3시장

        :param market: string
        :return: List
        """

        if not self.getConnectState():
            raise KiwoomConnectError()

        if not isinstance(market, str):
            raise ParameterTypeError()

        if market not in ['0', '3', '4', '5', '6', '8', '9', '10', '30']:
            raise ParameterValueError()

        cmd = 'GetCodeListByMarket("%s")' % market
        codeList = self.KW_API.dynamicCall(cmd)
        return codeList.split(';')

    def getCodeList(self, *market):
        """
        여러 시장의 종목코드를 List 형태로 반환하는 헬퍼 메서드.

        :param market: Tuple - 여러 개의 문자열을 매개변수로 받아 Tuple로 처리한다.
        :return: List
        """

        codeList = []

        for m in market:
            tmpList = self.getCodeListByMarket(m)
            codeList += tmpList

        return codeList

    def getMasterCodeName(self, code):
        """
        종목코드의 한글명을 반환한다.

        :param code: string - 종목코드
        :return: string - 종목코드의 한글명
        """

        if not self.getConnectState():
            raise KiwoomConnectError()

        if not isinstance(code, str):
            raise ParameterTypeError()

        cmd = 'GetMasterCodeName("%s")' % code
        name = self.KW_API.dynamicCall(cmd)
        return name

    def opwDataReset(self):
        """ 잔고 및 보유종목 데이터 초기화 """
        self.opw00001Data = 0
        self.opw00018Data = {'accountEvaluation': [], 'stocks': []}

    def getCommRealData(self, code, fid):
        """
        실시간 데이터 획득 메서드
        이 메서드는 반드시 receiveRealData() 이벤트 메서드가 호출될 때, 그 안에서 사용해야 합니다.
        :param code: string - 종목코드
        :param fid: - 실시간 타입에 포함된 fid
        :return: string - fid에 해당하는 데이터
        """

        if not (isinstance(code, str) and isinstance(fid, int)):
            raise ParameterTypeError()

        value = self.KW_API.dynamicCall("GetCommRealData(QString, int)", code, fid)

        return value

class ParameterTypeError(Exception):
    """ 파라미터 타입이 일치하지 않을 경우 발생하는 예외 """

    def __init__(self, msg="파라미터 타입이 일치하지 않습니다."):
        self.msg = msg

    def __str__(self):
        return self.msg

class ParameterValueError(Exception):
    """ 파라미터로 사용할 수 없는 값을 사용할 경우 발생하는 예외 """

    def __init__(self, msg="파라미터로 사용할 수 없는 값 입니다."):
        self.msg = msg

    def __str__(self):
        return self.msg

class KiwoomProcessingError(Exception):
    """ 키움에서 처리실패에 관련된 리턴코드를 받았을 경우 발생하는 예외 """

    def __init__(self, msg="처리 실패"):
        self.msg = msg

    def __str__(self):
        return self.msg

    def __repr__(self):
        return self.msg

class KiwoomConnectError(Exception):
    """ 키움서버에 로그인 상태가 아닐 경우 발생하는 예외 """

    def __init__(self, msg="로그인 여부를 확인하십시오"):
        self.msg = msg

    def __str__(self):
        return self.msg

class ReturnCode(object):
    """ 키움 OpenApi+ 함수들이 반환하는 값 """

    OP_ERR_NONE = 0 # 정상처리
    OP_ERR_FAIL = -10   # 실패
    OP_ERR_LOGIN = -100 # 사용자정보교환실패
    OP_ERR_CONNECT = -101   # 서버접속실패
    OP_ERR_VERSION = -102   # 버전처리실패
    OP_ERR_FIREWALL = -103  # 개인방화벽실패
    OP_ERR_MEMORY = -104    # 메모리보호실패
    OP_ERR_INPUT = -105 # 함수입력값오류
    OP_ERR_SOCKET_CLOSED = -106 # 통신연결종료
    OP_ERR_SISE_OVERFLOW = -200 # 시세조회과부하
    OP_ERR_RQ_STRUCT_FAIL = -201    # 전문작성초기화실패
    OP_ERR_RQ_STRING_FAIL = -202    # 전문작성입력값오류
    OP_ERR_NO_DATA = -203   # 데이터없음
    OP_ERR_OVER_MAX_DATA = -204 # 조회가능한종목수초과
    OP_ERR_DATA_RCV_FAIL = -205 # 데이터수신실패
    OP_ERR_OVER_MAX_FID = -206  # 조회가능한FID수초과
    OP_ERR_REAL_CANCEL = -207   # 실시간해제오류
    OP_ERR_ORD_WRONG_INPUT = -300   # 입력값오류
    OP_ERR_ORD_WRONG_ACCTNO = -301  # 계좌비밀번호없음
    OP_ERR_OTHER_ACC_USE = -302 # 타인계좌사용오류
    OP_ERR_MIS_2BILL_EXC = -303 # 주문가격이20억원을초과
    OP_ERR_MIS_5BILL_EXC = -304 # 주문가격이50억원을초과
    OP_ERR_MIS_1PER_EXC = -305  # 주문수량이총발행주수의1%초과오류
    OP_ERR_MIS_3PER_EXC = -306  # 주문수량이총발행주수의3%초과오류
    OP_ERR_SEND_FAIL = -307 # 주문전송실패
    OP_ERR_ORD_OVERFLOW = -308  # 주문전송과부하
    OP_ERR_MIS_300CNT_EXC = -309    # 주문수량300계약초과
    OP_ERR_MIS_500CNT_EXC = -310    # 주문수량500계약초과
    OP_ERR_ORD_WRONG_ACCTINFO = -340    # 계좌정보없음
    OP_ERR_ORD_SYMCODE_EMPTY = -500 # 종목코드없음

    CAUSE = {
        0: '정상처리',
        -10: '실패',
        -100: '사용자정보교환실패',
        -102: '버전처리실패',
        -103: '개인방화벽실패',
        -104: '메모리보호실패',
        -105: '함수입력값오류',
        -106: '통신연결종료',
        -200: '시세조회과부하',
        -201: '전문작성초기화실패',
        -202: '전문작성입력값오류',
        -203: '데이터없음',
        -204: '조회가능한종목수초과',
        -205: '데이터수신실패',
        -206: '조회가능한FID수초과',
        -207: '실시간해제오류',
        -300: '입력값오류',
        -301: '계좌비밀번호없음',
        -302: '타인계좌사용오류',
        -303: '주문가격이20억원을초과',
        -304: '주문가격이50억원을초과',
        -305: '주문수량이총발행주수의1%초과오류',
        -306: '주문수량이총발행주수의3%초과오류',
        -307: '주문전송실패',
        -308: '주문전송과부하',
        -309: '주문수량300계약초과',
        -310: '주문수량500계약초과',
        -340: '계좌정보없음',
        -500: '종목코드없음'
    }

class FidList(object):
    """ receiveChejanData() 이벤트 메서드로 전달되는 FID 목록 """

    CHEJAN = {
        9201: '계좌번호',
        9203: '주문번호',
        9205: '관리자사번',
        9001: '종목코드',
        912: '주문업무분류',
        913: '주문상태',
        302: '종목명',
        900: '주문수량',
        901: '주문가격',
        902: '미체결수량',
        903: '체결누계금액',
        904: '원주문번호',
        905: '주문구분',
        906: '매매구분',
        907: '매도수구분',
        908: '주문/체결시간',
        909: '체결번호',
        910: '체결가',
        911: '체결량',
        10: '현재가',
        27: '(최우선)매도호가',
        28: '(최우선)매수호가',
        914: '단위체결가',
        915: '단위체결량',
        938: '당일매매수수료',
        939: '당일매매세금',
        919: '거부사유',
        920: '화면번호',
        921: '921',
        922: '922',
        923: '923',
        949: '949',
        10010: '10010',
        917: '신용구분',
        916: '대출일',
        930: '보유수량',
        931: '매입단가',
        932: '총매입가',
        933: '주문가능수량',
        945: '당일순매수수량',
        946: '매도/매수구분',
        950: '당일총매도손일',
        951: '예수금',
        307: '기준가',
        8019: '손익율',
        957: '신용금액',
        958: '신용이자',
        959: '담보대출수량',
        924: '924',
        918: '만기일',
        990: '당일실현손익(유가)',
        991: '당일신현손익률(유가)',
        992: '당일실현손익(신용)',
        993: '당일실현손익률(신용)',
        397: '파생상품거래단위',
        305: '상한가',
        306: '하한가'
    }

class RealType(object):

    REALTYPE = {
        '주식시세': {
            10: '현재가',
            11: '전일대비',
            12: '등락율',
            27: '최우선매도호가',
            # 28: '최우선매수호가',
            13: '누적거래량',
            # 14: '누적거래대금',
            16: '시가',
            17: '고가',
            18: '저가',
            # 25: '전일대비기호',
            # 26: '전일거래량대비',
            # 29: '거래대금증감',
            # 30: '거일거래량대비',
            31: '거래회전율',
            # 32: '거래비용',
            # 311: '시가총액(억)'
        },

        '주식체결': {
            # 20: '체결시간(HHMMSS)',
            10: '체결가',
            11: '전일대비',
            12: '등락율',
            # 27: '최우선매도호가',
            # 28: '최우선매수호가',
            # 15: '체결량',
            13: '누적체결량',
            # 14: '누적거래대금',
            16: '시가',
            17: '고가',
            18: '저가',
            # 25: '전일대비기호',
            # 26: '전일거래량대비',
            # 29: '거래대금증감',
            # 30: '전일거래량대비',
            # 31: '거래회전율',
            # 32: '거래비용',
            228: '체결강도',
            # 311: '시가총액(억)',
            # 290: '장구분',
            # 691: 'KO접근도'
        },

        '주식호가잔량': {
            21: '호가시간',
            41: '매도호가1',
            61: '매도호가수량1',
            81: '매도호가직전대비1',
            51: '매수호가1',
            71: '매수호가수량1',
            91: '매수호가직전대비1',
            42: '매도호가2',
            62: '매도호가수량2',
            82: '매도호가직전대비2',
            52: '매수호가2',
            72: '매수호가수량2',
            92: '매수호가직전대비2',
            43: '매도호가3',
            63: '매도호가수량3',
            83: '매도호가직전대비3',
            53: '매수호가3',
            73: '매수호가수량3',
            93: '매수호가직전대비3',
            44: '매도호가4',
            64: '매도호가수량4',
            84: '매도호가직전대비4',
            54: '매수호가4',
            74: '매수호가수량4',
            94: '매수호가직전대비4',
            45: '매도호가5',
            65: '매도호가수량5',
            85: '매도호가직전대비5',
            55: '매수호가5',
            75: '매수호가수량5',
            95: '매수호가직전대비5',
            46: '매도호가6',
            66: '매도호가수량6',
            86: '매도호가직전대비6',
            56: '매수호가6',
            76: '매수호가수량6',
            96: '매수호가직전대비6',
            47: '매도호가7',
            67: '매도호가수량7',
            87: '매도호가직전대비7',
            57: '매수호가7',
            77: '매수호가수량7',
            97: '매수호가직전대비7',
            48: '매도호가8',
            68: '매도호가수량8',
            88: '매도호가직전대비8',
            58: '매수호가8',
            78: '매수호가수량8',
            98: '매수호가직전대비8',
            49: '매도호가9',
            69: '매도호가수량9',
            89: '매도호가직전대비9',
            59: '매수호가9',
            79: '매수호가수량9',
            99: '매수호가직전대비9',
            50: '매도호가10',
            70: '매도호가수량10',
            90: '매도호가직전대비10',
            60: '매수호가10',
            80: '매수호가수량10',
            100: '매수호가직전대비10',
            121: '매도호가총잔량',
            122: '매도호가총잔량직전대비',
            125: '매수호가총잔량',
            126: '매수호가총잔량직전대비',
            23: '예상체결가',
            24: '예상체결수량',
            128: '순매수잔량(총매수잔량-총매도잔량)',
            129: '매수비율',
            138: '순매도잔량(총매도잔량-총매수잔량)',
            139: '매도비율',
            200: '예상체결가전일종가대비',
            201: '예상체결가전일종가대비등락율',
            238: '예상체결가전일종가대비기호',
            291: '예상체결가',
            292: '예상체결량',
            293: '예상체결가전일대비기호',
            294: '예상체결가전일대비',
            295: '예상체결가전일대비등락율',
            13: '누적거래량',
            299: '전일거래량대비예상체결률',
            215: '장운영구분'
        },

        '장시작시간': {
            215: '장운영구분(0:장시작전, 2:장종료전, 3:장시작, 4,8:장종료, 9:장마감)',
            20: '시간(HHMMSS)',
            214: '장시작예상잔여시간'
        },

        '업종지수': {
            20: '체결시간',
            10: '현재가',
            11: '전일대비',
            12: '등락율',
            15: '거래량',
            13: '누적거래량',
            14: '누적거래대금',
            16: '시가',
            17: '고가',
            18: '저가',
            25: '전일대비기호',
            26: '전일거래량대비(계약,주)'
        },

        '업종등락': {
            20: '체결시간',
            252: '상승종목수',
            251: '상한종목수',
            253: '보합종목수',
            255: '하락종목수',
            254: '하한종목수',
            13: '누적거래량',
            14: '누적거래대금',
            10: '현재가',
            11: '전일대비',
            12: '등락율',
            256: '거래형성종목수',
            257: '거래형성비율',
            25: '전일대비기호'
        },

        '주문체결': {
            # 9201: '계좌번호',
            # 9205: '관리자사번',
            9001: '종목코드',  # 0
            302: '종목명',  # 1
            908: '체결시간(HHMMSS)',  # 2
            906: '매매구분(보통, 시장가등)',  # 3
            # 912: '주문분류(jj:주식주문)',
            900: '주문수량',    #4
            901: '주문가격',    #5
            911: '체결량',  # 6
            910: '체결가',  # 7
            903: '체결누계금액',  # 8
            10: '체결가',  # 9
            902: '미체결수량',   #10
            9203: '주문번호',  # 11
            913: '주문상태(10:원주문, 11:정정주문, 12:취소주문, 20:주문확인, 21:정정확인, 22:취소확인, 90,92:주문거부)',  # 12
            # 907: '매도수구분(1:매도, 2:매수)',   #13
            905: '주문구분(+:현금매수, -:현금매도)', #13
            904: '원주문번호',   #14
            # 909: '체결번호',
            # 27: '최우선매도호가',
            # 28: '최우선매수호가',
            # 914: '단위체결가',
            # 915: '단위체결량',
            # 938: '당일매매수수료',
            # 939: '당일매매세금'
        },

        '잔고': {

            # 9201: '계좌번호',
            9001: '종목코드',       #0
            302: '종목명',     #1
            931: '매입단가',   #2
            930: '보유수량',    #3
            10: '현재가',      #4
            932: '총매입가',    #5
            950: '당일총매도손익', #6
            8019: '손익율',    #7
            946: '매도매수구분'   #8
            #
            # 930: '보유수량',
            # 931: '매입단가',
            # 932: '총매입가',
            # 933: '주문가능수량',
            # 945: '당일순매수량',
            # 946: '매도매수구분',
            # 950: '당일총매도손익',
            # 951: '예수금',
            # # 27: '최우선매도호가',
            # # 28: '최우선매수호가',
            # # 307: '기준가',
            # 8019: '손익율'
        },

        '주식시간외호가': {
            21: '호가시간(HHMMSS)',
            131: '시간외매도호가총잔량',
            132: '시간외매도호가총잔량직전대비',
            135: '시간외매수호가총잔량',
            136: '시간외매수호가총잔량직전대비'
        }
    }

if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = MyWindow()
    myWindow.show()
    app.exec_()
