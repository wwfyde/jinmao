import logging
from logging.handlers import RotatingFileHandler

from crawler.config import settings


def get_logger():
    logger = logging.getLogger("target_logger")
    logger.setLevel(logging.DEBUG)  # 设置日志级别

    log_file = settings.log_file_path.joinpath("target.log")
    handler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=3)
    handler.setLevel(logging.WARNING)  # 设置处理器的日志级别
    formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s [in %(pathname)s:%(lineno)d]")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # 创建标准输出处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # 设置处理器的日志级别
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


log = get_logger()

if __name__ == "__main__":
    # 示例日志记录
    log.debug("这是一个调试日志")
    log.info("这是一个信息日志")
    log.warning("这是一个警告日志")
    log.error("这是一个错误日志")
    log.critical("这是一个严重错误日志")
