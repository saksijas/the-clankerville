import pytest

from office import step_label


def tool(name, input, status="running"):
    return {"type": "tool", "tool": name, "input": input, "status": status}


@pytest.mark.parametrize("name,input,label", [
    ("Read", "/data/apps/x/theme.css", "Reading theme.css"),
    ("Edit", "/a/b/index.jsx", "Editing index.jsx"),
    ("Bash", "ls -la", "Running a command"),
    ("Grep", "pattern", "Searching the code"),
    ("WebSearch", "isometric art", "Searching the web"),
    ("mcp__mobius_control__spawn_agent", "{...}", "Briefing a helper"),
    ("mcp__mobius_control__request_question", "{...}", "Asking you something"),
    ("mcp__mobius_control__apply_app", "{...}", "Shipping an app"),
    ("SomethingNew", "x", "Working"),
])
def test_label_table(name, input, label):
    assert step_label([tool(name, input)]) == label


def test_label_never_leaks():  # Review Focus 2
    for blocks in ([tool("Bash", 'curl -H "Authorization: Bearer sk-live-9f8a7b6c5d4e3f2a1b0c" https://api.x.com/v1')],
                   [tool("WebFetch", "https://example.com/?token=abc123")],
                   [tool("Read", "/secrets/9f8a7b6c5d4e3f2a1b0c9f8a7b6c5d4e.json")]):
        out = step_label(blocks)
        assert "sk-live" not in out and "http" not in out and "9f8a7b6c5d4e" not in out


def test_basename_capped_and_bubble_capped():
    assert step_label([tool("Read", "/x/" + "a" * 60 + ".md")]) == "Reading " + "a" * 19 + "…"  # 28 total


def test_text_and_thinking():
    assert step_label([tool("Read", "/x/a.md", "done"), {"type": "text", "text": "..."}]) == "Writing a reply"
    assert step_label([]) == "Thinking"


# The three tests below pin the setup ruling that tightened the scrub rule.

def test_readable_long_file_name_survives_scrub():
    assert step_label([tool("Edit", "/docs/implementation-plan-for-agent-office-v2.md")]) == "Editing implementation-plan…"


def test_mixed_letter_digit_token_in_file_name_is_scrubbed():
    out = step_label([tool("Read", "/tmp/AbC123dEf456GhI789jKl012MnO345pQ.txt")])
    assert "AbC123" not in out and out == "Reading .txt"


def test_file_name_that_is_all_secret_falls_back():
    assert step_label([tool("Read", "/keys/9f8a7b6c5d4e3f2a1b0c9f8a7b6c5d4e")]) == "Reading a file"


def test_the_tool_file_field_wins_over_other_paths_in_a_summary():
    summary = "new_source=open('/data/x/other.csv'), notebook_path=/data/n/analysis.ipynb, cell_id=3"
    assert step_label([tool("NotebookEdit", summary)]) == "Editing analysis.ipynb"


def test_the_tool_file_field_wins_in_a_structured_input():
    assert step_label([tool("Edit", {"old_string": "see /etc/hosts", "file_path": "/a/b/app.py"})]) == "Editing app.py"


def test_codex_commands_and_patches_have_labels():
    assert step_label([tool("shell", "npm test")]) == "Running a command"
    assert step_label([tool("apply_patch", "*** Begin Patch")]) == "Editing code"
