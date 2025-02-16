import pytest
from agentic.tools.rag_tool import RAGTool
from agentic.tools.registry import tool_registry

@pytest.fixture
def rag_tool():
    tool = RAGTool()
    tool_registry.ensure_dependencies(tool, always_install=True)
    return tool
   

@pytest.mark.asyncio
async def test_universal_read_file(rag_tool):
    file_name = "tests/data/agentic_reasoning.pdf"
    result = await rag_tool._universal_read_file(file_name, None)
    assert isinstance(result, tuple)
    assert isinstance(result[0], str)  # Assuming the PDF content is returned as a string
    assert result[1] == "application/pdf"  # Check if the mime type is correct

@pytest.mark.asyncio
async def test_universal_read_file_invalid_file(rag_tool):
    file_name = "invalid_file.txt"
    with pytest.raises(ValueError):
        await rag_tool._universal_read_file(file_name, None)

@pytest.mark.asyncio
async def test_universal_read_file_image(rag_tool):
    file_name = "tests/data/omni.png"
    with pytest.raises(ValueError, match="Enable the Image Analysis & Recognition tool to read image files."):
        await rag_tool._universal_read_file(file_name, None)
