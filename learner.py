import os

from network import Network


class Learner:
    def __init__(self, stock_code, chart_data, training_data):
        # 종목코드
        self.stock_code = stock_code
        # 종목의 차트 데이터
        self.chart_data = chart_data

        # 에이전트 객체

        # 학습 데이터
        self.training_data = training_data
        # 샘플 데이터
        self.sample = None
        # 훈련 데이터의 위치
        self.training_data_idx = -1

        # 신경망 모델
        # (강화학습 모델에서 차별화 된 요인) 학습데이터의 구성 개수 = 주가 및 거래량과 관련된 구성 개수  + 에이전트의 상태 구성 개수
        self.num_factor_learn_data = self.training_data.shape[1]
        # 신경망 모듈
        self.network = Network(input_dim=self.num_factor_learn_data, output_dim=None, lr=None)

    # 에포크 초기화
    def reset(self):
        self.training_data_idx = -1

    # 학습 함수
    def fit(self):
        pass

