import logging
import os
from datetime import datetime

class Logger:
    def __init__(self, log_dir='logs', log_level=logging.INFO):
        # 创建日志目录
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 日志文件名格式: 年-月-日.log
        self.log_filename = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")

        # 创建logger实例
        self.logger = logging.getLogger('arxiv_auto_logger')
        self.logger.setLevel(log_level)
        self.logger.propagate = False  # 防止日志重复输出

        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 文件处理器
        file_handler = logging.FileHandler(self.log_filename, encoding='utf-8')
        file_handler.setFormatter(formatter)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def get_logger(self):
        return self.logger

# 创建默认日志实例
logger = Logger().get_logger()

# 使用示例:
# logger.debug('调试信息')
# logger.info('普通信息')
# logger.warning('警告信息')
# logger.error('错误信息')
# logger.critical('严重错误信息')