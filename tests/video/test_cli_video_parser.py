from unittest.mock import patch
from cli.parser import build_arg_parser


def test_video_flags_parse():
    parser = build_arg_parser()
    args = parser.parse_args([
        "--video", "-p", "a fox in snow", "-o", "fox.mp4",
        "--video-provider", "omni", "--aspect", "9:16",
        "--ref-image", "a.png", "--ref-image", "b.png",
        "--last-frame", "end.png", "--extend", "prev.mp4",
        "--video-model", "veo-3.1-fast-generate-001", "--json",
    ])
    assert args.video is True
    assert args.video_provider == "omni"
    assert args.aspect == "9:16"
    assert args.ref_image == ["a.png", "b.png"]
    assert args.last_frame == "end.png"
    assert args.extend == "prev.mp4"
    assert args.video_model == "veo-3.1-fast-generate-001"
    assert args.json is True


def test_video_provider_defaults_to_veo():
    parser = build_arg_parser()
    args = parser.parse_args(["--video", "-p", "x"])
    assert args.video_provider == "veo"


def test_run_cli_routes_to_video_command():
    parser = build_arg_parser()
    args = parser.parse_args(["--video", "-p", "x", "-o", "x.mp4"])
    with patch("cli.commands.video.run_video_cmd", return_value=0) as m:
        from cli.runner import run_cli
        rc = run_cli(args)
    assert rc == 0
    m.assert_called_once()
