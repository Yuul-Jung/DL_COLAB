class Environment:
    Price_index = 4     # 종가의 위치

    def __init__(self, chart_data=None):
        self.chart_data = chart_data    # 주식 종목의 차트 데이터
        self.observation = None         # 현재 관측치
        self.index_data = -1            # 차트 데이터의 현재 위치

    # index_data와 observation을 초기화
    def reset(self):
        self.observation = None
        self.index_data = -1

    # index_data를 다음 위치로 이동하고 observation을 업데이트
    def observe(self):
        if len(self.chart_data) > self.index_data + 1:
            # len()함수는 파이썬 내장함수이며 문자열, 리스트 등의 길이를 반환
            self.index_data += 1
            self.observation = self.chart_data.iloc(self.index_data)
            # iloc()함수는 DataFrame함수이며 특정 행의 데이터를 가져옴
            return self.observation
        return None

    # 현재 observation에서 종가를 획득
    def get_price(self):
        if self.observation is not None:
            return self.observation(self.Price_index)
        return None


