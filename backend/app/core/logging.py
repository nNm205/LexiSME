import logging

def get_logger(name: str):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler("pipeline.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(name)