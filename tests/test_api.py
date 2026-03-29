"""Tests for OpenRouter helper (mocked HTTP)."""

from unittest.mock import MagicMock, patch

from utils import api


def test_generate_text_missing_key_returns_empty(capsys, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    assert api.generate_text("hi") == ""
    err = capsys.readouterr().out
    assert "OPENROUTER_API_KEY" in err


@patch("utils.api.requests.post")
def test_generate_text_success(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "  hello world  "}}],
    }
    mock_post.return_value = mock_resp

    with patch.dict(
        "os.environ",
        {"OPENROUTER_API_KEY": "sk-test", "OPENROUTER_MODEL": "test/model"},
        clear=False,
    ):
        out = api.generate_text("ping", model="other/model")

    assert out == "hello world"
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "other/model"
    assert kwargs["json"]["messages"][0]["content"] == "ping"
    assert kwargs["timeout"] == (api._CONNECT_TIMEOUT, 60.0)
    assert "max_tokens" not in kwargs["json"]


@patch("utils.api.requests.post")
def test_generate_text_passes_max_tokens(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_post.return_value = mock_resp
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "k"}, clear=False):
        api.generate_text("x", max_tokens=500)
    assert mock_post.call_args.kwargs["json"]["max_tokens"] == 500


@patch("utils.api.requests.post")
def test_generate_text_legacy_choice_text(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"text": " legacy "}]}
    mock_post.return_value = mock_resp
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "k"}, clear=False):
        assert api.generate_text("x") == "legacy"


@patch("utils.api.requests.post")
def test_generate_text_reasoning_when_content_empty(mock_post: MagicMock, capsys) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "", "reasoning": "inner"}}],
    }
    mock_post.return_value = mock_resp
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "k"}, clear=False):
        assert api.generate_text("x") == "inner"
    assert "reasoning" in capsys.readouterr().out.lower()


@patch("utils.api.requests.post")
def test_generate_text_http_error(mock_post: MagicMock, capsys) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 402
    mock_resp.json.return_value = {"error": {"message": "pay up"}}
    mock_post.return_value = mock_resp

    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "x"}, clear=False):
        assert api.generate_text("x") == ""
    assert "402" in capsys.readouterr().out
