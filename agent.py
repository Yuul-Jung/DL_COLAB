## 투자 행동을 수행하고 투자금과 보유 주식을 관리하기 위한 에이전트 클래스
import numpy as np

class Agent:
    # 에이전트 상태가 구성하는 값 개수
    STATE_DIM = 2   # 주식보유비율, 포트폴리오가치비율

    # 매매 수수료 및 세금
    TRADING_CHANGE = 0.015  # 거래 수수료
    TRADING_TAX = 0.25  # 중권 거래세

    # 투자 종류
    ACTION_BUY = 0  # 매수
    ACTION_SELL = 1 # 매도
    ACTION_HOLD = 2 # 홀드

    # 투자 행동
    ACTIONS = [ACTION_BUY, ACTION_SELL]     # 인공 신경망에서 확률을 구할 행동들
    NUM_ACTIONS = len(ACTIONS)              # 인공 신경망에서 고려할 출력값의 개수

    def __init__(self, environment, mintrading_unit = 1, maxtrading_unit = 2, delayed_reward_threshold = 0.05):
        # Environment 객체
        self.environment = environment  # 현재 주식 가격을 가져오기 위해 환경 참조

        # 최소 매매 단위, 최대 매매 단위, 지연 보상 임계치
        self.min_trading_unit = mintrading_unit     # 최소 단일 거래 단위
        self.max_trading_unit = maxtrading_unit     # 최대 단일 거래 단위
        self.delayed_reward_threshold = delayed_reward_threshold    # 지연 보상 임계치

        # Agent 클래스의 속성
        self.initial_balance = 0     # 초기 자본금
        self.balance = 0            # 현재 현금 잔고
        self.num_stocks = 0     # 보유 주식수
        self.portfolio_value = 0    # balance + num_stocks * 현재 주식 가격
        self.base_portfolio_value = 0   # 직전 학습 시점의 PV
        self.num_buy = 0    # 매수 횟수
        self.num_sell = 0   # 매도 횟수
        self.num_hold = 0   # 관망 횟수
        self.immediate_reward = 0   # 즉시 보상

        # Agent 클래스의 상태
        self.ratio_hold = 0     # 주식 보유 비율
        self.ratio_portfolio_value = 0      # 포트폴리오 가치 비율

    # Agent의 속성과 상태를 초기화
    # 학습단계에서 한 에포크마다 에이전트의 상태를 초기화
    def reset(self):
        self.balance = self.initial_balance
        self.num_stocks = 0
        self.portfolio_value = self.initial_balance
        self.base_portfolio_value = self.initial_balance
        self.num_buy = 0
        self.num_sell = 0
        self.num_hold = 0
        self.immediate_reward = 0
        # Agent 상태 초기화
        self.ratio_hold = 0
        self.ratio_portfolio_value = 0

    # Agent의 초기 자본금을 설정
    def set_balance(self, balance):
        self.initial_balance = balance

    # Agent의 상태를 반환
    # 주식보유비율, 포트폴리오가치비율
    def get_states(self):
        self.ratio_hold = self.num_stocks / int(self.portfolio_value / self.environment.get_price())
        self.ratio_portfolio_value = self.portfolio_value / self.initial_balance
        return (self.ratio_hold, self.ratio_portfolio_value)

    # 입력으로 들어온 epsilon의 확률로 무작위로 행동을 결정, 그렇지 않으면 신경망을 통해 행동 결정
    def decide_action(self, network, sample, epsilon):
        confidence = 0.
        # 탐험 결정
        if np.random.rand() < epsilon:  # 0과 1 사이의 랜던 값을 생성, epsilon보다 작으면 무작위로 행동 결정
            exploration = True
            action = np.random.randint(self.NUM_ACTIONS)    # 무작위로 행동(매수=0 매도=1) 결정, self.NUM_ACTIONS = 2
        # 탐험하지 않은 경우 신경망을 통해 행동을 결정
        else:
            exploration = False
            probs = network.predict(sample)     # 각 행동(매수와 매도)을 predict에서 가져와서 확률 중 큰 값을 선택하여 행동 결정
            action = np.argmax(probs)   # argmax는 입력으로 들어온 array에서 가장 큰 값의 위치를 반환
            confidence = probs[action]
        return action, confidence, exploration

    def validate_action(self, action):
        validaty = True
        if action == Agent.ACTION_BUY:
            # 적어도 한주를 살 수 있는지 확인
            pass
        elif action == Agent.ACTION_SELL:
            pass
        return validaty





