from jinja2 import Environment, BaseLoader

def render_template_with_variables(template_str: str, **kwargs) -> str:
    """使用 Jinja2 渲染模板字符串

    Args:
        template_str (str): 模板字符串
        **kwargs: 传递给模板的变量字典

    Returns:
        str: 渲染后的字符串
    """
    env = Environment(loader=BaseLoader())
    template = env.from_string(template_str)
    return template.render(**kwargs) 