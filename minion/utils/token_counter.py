import tiktoken


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613"):
    """计算消息列表的token数量"""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    num_tokens = 0
    for message in messages:
        num_tokens += 4  # 每条消息的基础token数
        for key, value in message.items():
            num_tokens += len(encoding.encode(str(value)))
            if key == "name":
                num_tokens += -1  # 如果有name字段，减去1个token
    num_tokens += 2  # 对话的开始和结束token
    return num_tokens
