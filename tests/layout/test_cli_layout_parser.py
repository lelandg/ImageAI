from cli.parser import build_arg_parser


def test_layout_design_flags_parse():
    p = build_arg_parser()
    args = p.parse_args([
        "--layout-design", "a 4-panel comic",
        "--content-kind", "comic",
        "--page-size", "A4",
        "--orientation", "landscape",
        "--dpi", "150",
        "--layout-llm-provider", "anthropic",
        "--layout-llm-model", "some-model",
        "-o", "out.iaiproj.json",
    ])
    assert args.layout_design == "a 4-panel comic"
    assert args.content_kind == "comic"
    assert args.page_size == "A4"
    assert args.orientation == "landscape"
    assert args.dpi == 150
    assert args.layout_llm_provider == "anthropic"
    assert args.layout_llm_model == "some-model"
    assert args.out == "out.iaiproj.json"


def test_layout_export_and_fill_flags_parse():
    p = build_arg_parser()
    a1 = p.parse_args(["--layout-export", "proj.json", "-o", "out.pdf"])
    assert a1.layout_export == "proj.json"
    a2 = p.parse_args(["--layout-fill", "proj.json", "--provider", "google"])
    assert a2.layout_fill == "proj.json"


def test_content_kind_rejects_unknown():
    import pytest
    p = build_arg_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["--layout-design", "x", "--content-kind", "childrens_book"])
