import pytest
from unittest.mock import MagicMock
from plugins.premium import parse_add_premium_args, parse_expiry_time, get_user_id
from plugins.admin import _resolve_target


def test_parse_add_premium_args_explicit():
    msg = MagicMock()
    msg.command = ["add_premium", "123456", "gold", "1d"]
    msg.reply_to_message = None

    user_id, rank, expiry_str = parse_add_premium_args(msg)
    assert user_id == 123456
    assert rank == "gold"
    assert expiry_str == "1d"


def test_parse_add_premium_args_reply():
    msg = MagicMock()
    msg.command = ["add_premium", "gold", "2w"]
    msg.reply_to_message = MagicMock()
    msg.reply_to_message.from_user = MagicMock(id=987654)
    msg.reply_to_message.sender_chat = None

    user_id, rank, expiry_str = parse_add_premium_args(msg)
    assert user_id == 987654
    assert rank == "gold"
    assert expiry_str == "2w"


def test_parse_add_premium_args_reply_default_rank():
    msg = MagicMock()
    msg.command = ["add_premium"]
    msg.reply_to_message = MagicMock()
    msg.reply_to_message.from_user = MagicMock(id=555111)
    msg.reply_to_message.sender_chat = None

    user_id, rank, expiry_str = parse_add_premium_args(msg)
    assert user_id == 555111
    assert rank == "bronze"
    assert expiry_str is None


def test_parse_expiry_time():
    assert parse_expiry_time("1d") is not None
    assert parse_expiry_time("12h") is not None
    assert parse_expiry_time("30min") is not None
    assert parse_expiry_time("1w") is not None
    assert parse_expiry_time("1m") is not None
    assert parse_expiry_time(None) is None
    assert parse_expiry_time("invalid") is None


def test_get_user_id_explicit_and_reply():
    msg1 = MagicMock()
    msg1.command = ["remove_premium", "112233"]
    msg1.reply_to_message = None
    assert get_user_id(msg1) == 112233

    msg2 = MagicMock()
    msg2.command = ["remove_premium"]
    msg2.reply_to_message = MagicMock()
    msg2.reply_to_message.from_user = MagicMock(id=445566)
    assert get_user_id(msg2) == 445566


def test_resolve_target_group_and_user():
    msg1 = MagicMock()
    msg1.reply_to_message = None
    msg1.command = ["authorize", "-100123456789"]
    msg1.chat = MagicMock(id=-100123456789, type="supergroup")
    assert _resolve_target(msg1) == -100123456789

    msg2 = MagicMock()
    msg2.reply_to_message = None
    msg2.command = ["authorize"]
    msg2.chat = MagicMock(id=-100999999999, type="supergroup")
    assert _resolve_target(msg2) == -100999999999

    msg3 = MagicMock()
    msg3.reply_to_message = MagicMock()
    msg3.reply_to_message.from_user = MagicMock(id=777888)
    msg3.command = ["authorize"]
    msg3.chat = MagicMock(id=-100999999999, type="supergroup")
    assert _resolve_target(msg3) == 777888
