from backend.opencode_adapter import OpenCodeAdapter, parse_opencode_output


def test_opencode_adapter_builds_supported_cli_args_without_legacy_permission_flag():
    adapter = OpenCodeAdapter(
        opencode_bin="/usr/local/bin/opencode",
        model="deepseek/deepseek-chat",
        mode="cli",
    )

    args = adapter.build_args("super-analyst", "测试")

    assert args == [
        "/usr/local/bin/opencode",
        "run",
        "--agent",
        "super-analyst",
        "--model",
        "deepseek/deepseek-chat",
        "--format",
        "json",
        "测试",
    ]
    assert "--permission-mode" not in args


def test_opencode_adapter_can_attach_to_running_server_when_requested():
    adapter = OpenCodeAdapter(
        opencode_bin="/usr/local/bin/opencode",
        model="deepseek/deepseek-chat",
        mode="attach",
        opencode_url="http://127.0.0.1:3001",
    )

    args = adapter.build_args("qa-analyst", "测试")

    assert "--attach" in args
    assert "http://127.0.0.1:3001" in args


def test_parse_opencode_output_extracts_text_and_counts_events():
    stdout = "\n".join([
        '{"type":"step_start","part":{"type":"step-start"}}',
        '{"type":"text","part":{"type":"text","text":"第一段"}}',
        '{"type":"text","part":{"type":"text","text":"第二段"}}',
    ])

    result = parse_opencode_output(stdout)

    assert result.ok is True
    assert result.text == "第一段\n第二段"
    assert result.text_events == 2


def test_parse_opencode_output_marks_step_only_output_as_empty():
    result = parse_opencode_output('{"type":"step_start","part":{"type":"step-start"}}')

    assert result.ok is False
    assert result.text == ""
    assert "未产生文本输出" in result.error
