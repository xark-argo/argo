import logging
import time
from pydantic import BaseModel, Field

class StreamMetrics(BaseModel):
    # init var
    RequestId: str = ""
    FromKafkaTime: float = 0.0
    ArrivalTime: float = Field(default_factory=time.perf_counter)

    # temp inner var
    LastTokenTime: float = 0.0
    TokenCount: int = 0

    # performance metrics var
    TTFT: float = 0.0
    TPOT: float = 0.0
    OutputSpeed: float = 0.0
    InferTotal: float = 0.0
    DeltaStreaming: float = 0.0

    def output_token(self):
        current = time.perf_counter()

        if self.TokenCount == 0:
           self.TTFT = current - self.ArrivalTime
        else:
            self.TPOT = max(self.TPOT, current-self.LastTokenTime)
        self.TokenCount += 1
        self.LastTokenTime = current
        return

    def finish_infer(self, token_len=0):
        current = time.perf_counter()
        if token_len:
            self.TokenCount = token_len

        self.OutputSpeed = self.TokenCount/(current-self.ArrivalTime)
        self.InferTotal = current-self.ArrivalTime
        self.DeltaStreaming = self.InferTotal-self.TTFT

    def format_log(self):
        logging.info(f"{self.TTFT:.3f} {self.TPOT:.3f} {self.OutputSpeed:.3f} {self.InferTotal:.3f} {self.DeltaStreaming:.3f} " \
                    f"tokens:{self.TokenCount} request_id:{self.RequestId}")

    def __str__(self):
        str = f"{self.TTFT:.3f} {self.TPOT:.3f} {self.OutputSpeed:.3f} {self.InferTotal:.3f} {self.DeltaStreaming:.3f} " \
                     f"tokens:{self.TokenCount} request_id:{self.RequestId}"
        return str
