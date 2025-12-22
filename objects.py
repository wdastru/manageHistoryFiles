import re

object_pattern = re.compile(
    r"^(.*?client changed object to.*?)?"
    r"(?P<object>\"(?!\/Undefined.*?).*?\")"
    r".*$"
)