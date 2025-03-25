from unittest.mock import Mock, patch, AsyncMock
import pytest
from agentic.tools.oauth_tool import OAuthTool, OAuthConfig
from agentic.events import OAuthFlowResult

@pytest.fixture
def oauth_config():
    return OAuthConfig(
        authorize_url="https://example.com/authorize",
        token_url="https://example.com/token",
        client_id_key="TEST_CLIENT_ID",
        client_secret_key="TEST_CLIENT_SECRET",
        scopes="test_scope",
        tool_name="test_tool"
    )

@pytest.fixture
def mock_run_context():
    context = Mock()
    context.run_id = "test_run_id"
    context.get_oauth_callback_url = Mock(return_value="https://callback.com")
    context.get_oauth_token = Mock(return_value=None)
    context.get_oauth_auth_code = Mock(return_value=None)
    context.set_oauth_token = Mock()
    return context

@pytest.fixture
def oauth_tool(oauth_config):
    return OAuthTool(oauth_config)

@pytest.mark.asyncio
async def test_start_oauth_flow_success(oauth_tool, mock_run_context):
    """Test successful OAuth flow initialization"""
    with patch('os.getenv', return_value='test_client_id'):
        result = await oauth_tool._start_oauth_flow(mock_run_context)
        
        assert isinstance(result, OAuthFlowResult)
        assert 'auth_url' in result.data
        assert 'tool_name' in result.data
        assert result.data['tool_name'] == 'test_tool'
        assert 'client_id=test_client_id' in result.data['auth_url']
        assert 'scope=test_scope' in result.data['auth_url']

@pytest.mark.asyncio
async def test_start_oauth_flow_missing_client_id(oauth_tool, mock_run_context):
    """Test OAuth flow initialization with missing client ID"""
    with patch('os.getenv', return_value=None):
        with pytest.raises(ValueError) as exc_info:
            await oauth_tool._start_oauth_flow(mock_run_context)
        assert "TEST_CLIENT_ID not found in environment variables" in str(exc_info.value)

@pytest.mark.asyncio
async def test_exchange_code_for_token_success(oauth_tool, mock_run_context):
    """Test successful token exchange"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'access_token': 'test_token'}
    
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    
    with patch('os.getenv', side_effect=['test_client_id', 'test_client_secret']), \
         patch('httpx.AsyncClient', return_value=mock_client):
        token = await oauth_tool._exchange_code_for_token('test_code', mock_run_context)
        
        assert token == 'test_token'
        mock_run_context.set_oauth_token.assert_called_once_with('test_tool', 'test_token')

@pytest.mark.asyncio
async def test_exchange_code_for_token_failure(oauth_tool, mock_run_context):
    """Test token exchange failure"""
    mock_response = Mock()
    mock_response.status_code = 400
    
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    
    with patch('os.getenv', side_effect=['test_client_id', 'test_client_secret']), \
         patch('httpx.AsyncClient', return_value=mock_client):
        token = await oauth_tool._exchange_code_for_token('test_code', mock_run_context)
        
        assert token is None
        mock_run_context.set_oauth_token.assert_not_called()

@pytest.mark.asyncio
async def test_authenticate_existing_token(oauth_tool, mock_run_context):
    """Test authentication with existing token"""
    mock_run_context.get_oauth_token.return_value = 'existing_token'
    
    result = await oauth_tool.authenticate(mock_run_context)
    
    assert "Already authenticated" in result
    mock_run_context.get_oauth_token.assert_called_once_with('test_tool')

@pytest.mark.asyncio
async def test_authenticate_with_auth_code(oauth_tool, mock_run_context):
    """Test authentication with authorization code"""
    mock_run_context.get_oauth_auth_code.return_value = 'test_auth_code'
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'access_token': 'new_token'}
    
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    
    with patch('os.getenv', side_effect=['test_client_id', 'test_client_secret']), \
         patch('httpx.AsyncClient', return_value=mock_client):
        result = await oauth_tool.authenticate(mock_run_context)
        
        assert "Successfully authenticated" in result
        mock_run_context.set_oauth_token.assert_called_once_with('test_tool', 'new_token')

@pytest.mark.asyncio
async def test_authenticate_start_new_flow(oauth_tool, mock_run_context):
    """Test starting new authentication flow"""
    with patch('os.getenv', return_value='test_client_id'):
        result = await oauth_tool.authenticate(mock_run_context)
        
        assert isinstance(result, OAuthFlowResult)
        assert 'auth_url' in result.data
        assert result.data['tool_name'] == 'test_tool'
