"""Parser accepts the styles argument group."""
from cli.parser import build_arg_parser


def test_style_flags_parse():
    p = build_arg_parser()
    args = p.parse_args([
        "--style-create", "Water", "--style-images", "a.png", "imgs/",
        "--style-llm-provider", "openai", "--style-llm-model", "m",
    ])
    assert args.style_create == "Water"
    assert args.style_images == ["a.png", "imgs/"]
    assert args.style_llm_provider == "openai"
    assert args.style_llm_model == "m"


def test_style_use_flags_parse():
    p = build_arg_parser()
    args = p.parse_args(["-p", "a fox", "--style", "Water", "--style-smart"])
    assert args.style == "Water" and args.style_smart is True


def test_style_management_flags_parse():
    p = build_arg_parser()
    assert p.parse_args(["--style-list"]).style_list is True
    assert p.parse_args(["--style-show", "w"]).style_show == "w"
    assert p.parse_args(["--style-delete", "w"]).style_delete == "w"
    assert p.parse_args(["--style-export", "w", "-o", "w.zip"]).style_export == "w"
    assert p.parse_args(["--style-import", "w.zip"]).style_import == "w.zip"


def test_style_defaults_are_none_or_false():
    args = build_arg_parser().parse_args(["-p", "x"])
    assert args.style is None and args.style_smart is False
    assert args.style_create is None and args.style_list is False
