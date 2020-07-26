import pandas as pd
import numpy as np

# csv 파일 읽기
def load_chart_data(fpath):
    chart_data = pd.read_csv(fpath, thousands=',')
    return chart_data

# 종가와 거래량의 이동평균 구하기
def preprocess(chart_data):
    prep_data = chart_data
    windows = [5, 10, 20, 60, 120]
    for window in windows:
        # 종가의 이동평균값(5, 10, 20, 60, 120) 구하기
        prep_data['close_ma{}'.format(window)] = prep_data['Close'].rolling(window).mean()
        # 거래량의 이동평균값(5, 10, 20, 60, 120) 구하기
        prep_data['volume_ma{}'.format(window)] = prep_data['Volume'].rolling(window).mean()
    return prep_data

# 주가와 거래량의 비율 구하기
def build_training_data(prep_data):
    training_data = prep_data
    # 시가/전일종가 비율
    training_data['open_lastclose_ratio'] = np.zeros(len(training_data))    # "0" 초기화
    # 현재 종가에서 전일 종가를 빼고 전일 종가로 나누기
    training_data['open_lastclose_ratio'].iloc[1:] = (training_data['Open'][1:].values - training_data['Close'][:-1].values) \
                                                   / training_data['Close'][:-1].values
    return training_data


