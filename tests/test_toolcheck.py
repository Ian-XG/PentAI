from pentai.toolcheck import COMMON_TOOLS, check_tools

def test_common_tools_includes_nmap():
    assert "nmap" in COMMON_TOOLS

def test_check_tools_uses_injected_which():
    present = {"nmap", "curl"}
    which = lambda name: "/usr/bin/" + name if name in present else None
    results = check_tools(["nmap", "sqlmap", "curl"], which=which)
    assert results == [("nmap", True), ("sqlmap", False), ("curl", True)]

def test_check_tools_defaults_to_common_tools():
    results = check_tools(which=lambda n: None)
    assert [n for n, _ in results] == COMMON_TOOLS
    assert all(avail is False for _, avail in results)
