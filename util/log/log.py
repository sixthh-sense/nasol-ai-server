import logging
import os
import inspect
import functools
import time

from datetime import datetime


class Log:
    _logger = None

    @classmethod
    def get_logger(cls):
        if cls._logger is not None:
            return cls._logger

        logger = logging.getLogger("server")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            GREEN = "\033[92m"
            RESET = "\033[0m"

            # 콘솔용: 초록색 levelname
            console_formatter = logging.Formatter(
                f'{GREEN}%(levelname)s{RESET}(%(asctime)s) : %(filename)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # 파일용: 색 없음
            file_formatter = logging.Formatter(
                '%(levelname)s(%(asctime)s) : %(filename)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(console_formatter)

            log_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(log_dir, exist_ok=True)

            date_str = datetime.now().strftime("%Y%m%d")
            log_path = os.path.join(log_dir, f"{date_str}_log.log")

            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(file_formatter)

            logger.addHandler(stream_handler)
            logger.addHandler(file_handler)

        cls._logger = logger
        return logger

    import time

    def logging_decorator(self, func):
        if inspect.iscoroutinefunction(func):  # async 함수 처리
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # args에서 session_id 제거 (클래스/메서드 첫 인자 self 제외)
                filtered_args = tuple(a for a in args if not isinstance(a, str) or a != kwargs.get("session_id"))
                filtered_kwargs = {k: v for k, v in kwargs.items() if k != "session_id"}

                self.get_logger().info(
                    f"{func.__name__} called {datetime.now().strftime('%Y%m%d%H%M%S')} "
                    f"with args={filtered_args}, kwargs={filtered_kwargs}"
                )

                start_time = time.time()
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time

                self.get_logger().info(
                    f"{func.__name__} returned at {datetime.now().strftime('%Y%m%d%H%M%S')} "
                    f"(elapsed {elapsed:.3f}s)"
                )
                return result

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                filtered_args = tuple(a for a in args if not isinstance(a, str) or a != kwargs.get("session_id"))
                filtered_kwargs = {k: v for k, v in kwargs.items() if k != "session_id"}

                self.get_logger().info(
                    f"{func.__name__} called {datetime.now().strftime('%Y%m%d%H%M%S')} "
                    f"with args={filtered_args}, kwargs={filtered_kwargs}"
                )

                start_time = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time

                self.get_logger().info(
                    f"{func.__name__} returned at {datetime.now().strftime('%Y%m%d%H%M%S')} "
                    f"(elapsed {elapsed:.3f}s)"
                )
                return result

            return sync_wrapper
