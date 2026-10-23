class LLMError(Exception):
    """The model could not give a usable answer: every model failed, too many steps, the
    time budget ran out, or an answer stayed invalid. Callers catch it and fall back.

    Never show its text to a client: it can describe the model's answer."""


class ToolError(Exception):
    """Raised by a tool handler when the model asked for something wrong, for example an
    unknown city. Its message is sent back to the model, so it must hold no personal data.
    Any other exception is logged and the model only sees "tool failed"."""
