import io
from enum import IntEnum
from typing import Any, Optional

from pydantic import BaseModel


class State(IntEnum):
    NIL = 0
    NAME = 1
    VALUE = 2
    PARAMETER = 3
    MESSAGE = 4
    COMMENT = 5


ErrInvalidCommand = ValueError("invalid command")
ErrInvalidMessageRole = ValueError("invalid message role")
ErrMissingFrom = ValueError("missing from directive")
ErrUnexpectedEOF = ValueError("unexpected EOF")


class ParserError(Exception):
    def __init__(self, line_number, msg):
        super().__init__(f"line {line_number}: {msg}")
        self.line_number = line_number
        self.msg = msg


class Command:
    def __init__(self):
        self.name = ""
        self.args = ""


class Message(BaseModel):
    role: str
    content: str


class CreateRequest(BaseModel):
    model: Optional[str] = None
    template: Optional[str] = None
    parameters: Optional[dict[str, Any]] = {}


class Modelfile:
    def __init__(self):
        self.commands = []

    def create_request(self) -> Optional["CreateRequest"]:
        req = CreateRequest()

        params: dict[str, Any] = {}

        for c in self.commands:
            if c.name == "model":
                req.model = c.args
            elif c.name == "template":
                req.template = c.args
            else:
                if c.name in params:
                    params[c.name].append(c.args)
                else:
                    params[c.name] = [c.args]

        if params:
            req.parameters = params

        return req


def is_alpha(ch: str) -> bool:
    return ch.isalpha()


def is_number(ch: str) -> bool:
    return ch.isdigit()


def is_space(ch: str) -> bool:
    return ch in (" ", "\t")


def is_newline(ch: str) -> bool:
    return ch in ("\n", "\r")


def is_valid_message_role(role: str) -> bool:
    return role in ("system", "user", "assistant")


def is_valid_command(cmd: str) -> bool:
    return cmd.lower() in (
        "from",
        "license",
        "template",
        "system",
        "adapter",
        "parameter",
        "message",
    )


def quote(s: str) -> str:
    if "\n" in s or s.startswith(" ") or s.endswith(" "):
        if '"' in s:
            return f'"""{s}"""'
        return f'"{s}"'
    return s


def unquote(s: str) -> tuple[str, bool]:
    # TODO: single quotes
    if len(s) >= 3 and s.startswith('"""'):
        if len(s) >= 6 and s.endswith('"""'):
            return s[3:-3], True
        return "", False

    if len(s) >= 1 and s[0] == '"':
        if len(s) >= 2 and s[-1] == '"':
            return s[1:-1], True
        return "", False

    return s, True


def parse_rune_for_state(ch: str, curr: State):
    if curr == State.NIL:
        if ch == "#":
            return State.COMMENT, None, None
        elif is_space(ch) or is_newline(ch):
            return State.NIL, None, None
        else:
            return State.NAME, ch, None
    elif curr == State.NAME:
        if is_alpha(ch):
            return State.NAME, ch, None
        elif is_space(ch):
            return State.VALUE, None, None
        else:
            return State.NIL, None, ErrInvalidCommand
    elif curr == State.VALUE:
        if is_newline(ch) or is_space(ch):
            return State.NIL, ch, None
        else:
            return State.VALUE, ch, None
    elif curr == State.PARAMETER:
        if is_alpha(ch) or is_number(ch) or ch == "_":
            return State.PARAMETER, ch, None
        elif is_space(ch):
            return State.VALUE, None, None
        else:
            return State.NIL, None, ErrUnexpectedEOF
    elif curr == State.MESSAGE:
        if is_alpha(ch):
            return State.MESSAGE, ch, None
        elif is_space(ch):
            return State.VALUE, None, None
        else:
            return State.NIL, None, ErrUnexpectedEOF
    elif curr == State.COMMENT:
        if is_newline(ch):
            return State.NIL, None, None
        return State.COMMENT, None, None
    return State.NIL, None, Exception("invalid state")


def parse_modelfile(content: str, allow_missing_from: bool = False) -> Modelfile:
    cmd = Command()
    curr = State.NIL
    curr_line = 1
    buffer: list[str] = []
    role = ""
    f = Modelfile()
    reader = io.StringIO(content)
    while True:
        ch = reader.read(1)
        if ch == "":
            break  # EOF
        if is_newline(ch):
            curr_line += 1
        next_state, ch2, err = parse_rune_for_state(ch, curr)
        if err is ErrUnexpectedEOF:
            raise ValueError(f"{err}: {''.join(buffer)}")
        elif err:
            raise ParserError(curr_line, err.args[0])

        if next_state != curr:
            content = "".join(buffer).strip()
            if curr == State.NAME:
                if not is_valid_command(content):
                    raise ParserError(curr_line, ErrInvalidCommand.args[0])
                s = content.lower()
                if s == "from":
                    cmd.name = "model"
                elif s == "parameter":
                    next_state = State.PARAMETER
                elif s == "message":
                    next_state = State.MESSAGE
                    cmd.name = s
                else:
                    cmd.name = s
            elif curr == State.PARAMETER:
                cmd.name = content
            elif curr == State.MESSAGE:
                if not is_valid_message_role(content):
                    raise ParserError(curr_line, ErrInvalidMessageRole.args[0])
                role = content
            elif curr == State.VALUE:
                val, ok = unquote(content)
                if not ok or is_space(ch):
                    buffer.append(ch)
                    continue
                if role:
                    val = f"{role}: {val}"
                    role = ""
                cmd.args = val
                f.commands.append(cmd)
                cmd = Command()

            buffer = []
            curr = next_state

        if ch2 and ch2.isprintable():
            buffer.append(ch2)

    # flush buffer at EOF
    content = "".join(buffer).strip()
    if curr in (State.COMMENT, State.NIL):
        pass
    elif curr == State.VALUE:
        val, ok = unquote(content)
        if not ok:
            raise ErrUnexpectedEOF
        if role:
            val = f"{role}: {val}"
        cmd.args = val
        f.commands.append(cmd)
    else:
        raise ErrUnexpectedEOF

    for cmd in f.commands:
        if cmd.name == "model":
            return f
    if allow_missing_from:
        return f
    else:
        raise ErrMissingFrom
