import uuid
from decimal import Decimal

def test_create_account_success(client):
    """Verify that a valid account creation request succeeds and returns expected fields. Important for onboarding."""
    response = client.post('/api/v1/accounts/', json={
        'owner_name': 'John Doe',
        'currency': 'USD',
        'initial_balance': 500.00
    })
    assert response.status_code == 201
    data = response.json()
    assert 'id' in data
    assert data['owner_name'] == 'John Doe'
    assert data['currency'] == 'USD'
    assert data['balance'] == 500.00
    assert 'created_at' in data
    assert 'updated_at' in data

def test_create_account_with_initial_balance(client):
    """Verify initial balance is set correctly. Crucial for financial integrity at account opening."""
    response = client.post('/api/v1/accounts/', json={
        'owner_name': 'Jane Doe',
        'currency': 'EUR',
        'initial_balance': 1234.56
    })
    assert response.status_code == 201
    assert response.json()['balance'] == 1234.56

def test_create_account_invalid_currency(client):
    """Ensure invalid currencies are rejected to prevent unsupported transactions."""
    response = client.post('/api/v1/accounts/', json={
        'owner_name': 'User',
        'currency': 'XYZ',
        'initial_balance': 100.00
    })
    assert response.status_code == 422 or response.status_code == 400

def test_create_account_missing_name(client):
    """Verify required fields are enforced. An account must have an owner."""
    response = client.post('/api/v1/accounts/', json={
        'currency': 'USD',
        'initial_balance': 100.00
    })
    assert response.status_code == 422

def test_create_account_negative_balance(client):
    """Ensure negative initial balances are prevented to stop accounts starting in debt."""
    response = client.post('/api/v1/accounts/', json={
        'owner_name': 'User',
        'currency': 'USD',
        'initial_balance': -100.00
    })
    assert response.status_code == 422

def test_get_account_success(client, create_usd_account):
    """Verify retrieving an existing account returns correct details. Necessary for user dashboards."""
    account_id = create_usd_account['id']
    response = client.get(f'/api/v1/accounts/{account_id}')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == account_id
    assert data['owner_name'] == 'Test User'

def test_get_account_not_found(client):
    """Ensure appropriate error is returned for non-existent accounts."""
    random_id = str(uuid.uuid4())
    response = client.get(f'/api/v1/accounts/{random_id}')
    assert response.status_code == 404

def test_get_balance(client, create_usd_account):
    """Verify balance endpoint works. Essential for quick balance checks."""
    account_id = create_usd_account['id']
    response = client.get(f'/api/v1/accounts/{account_id}/balance')
    assert response.status_code == 200
    data = response.json()
    assert data['account_id'] == account_id
    assert data['currency'] == 'USD'
    assert data['balance'] == 1000.00

def test_deposit_success(client, create_usd_account):
    """Verify deposits correctly increase the balance. Core financial operation."""
    account_id = create_usd_account['id']
    response = client.post(f'/api/v1/accounts/{account_id}/deposit', json={
        'amount': 200.00
    })
    assert response.status_code == 200
    
    # Check updated balance
    balance_resp = client.get(f'/api/v1/accounts/{account_id}/balance')
    assert balance_resp.json()['balance'] == 1200.00

def test_deposit_idempotency(client, create_usd_account):
    """Verify duplicate deposit requests with same idempotency key don't double charge. Crucial for network retries."""
    account_id = create_usd_account['id']
    idem_key = str(uuid.uuid4())
    
    # First deposit
    client.post(f'/api/v1/accounts/{account_id}/deposit', json={
        'amount': 200.00,
        'idempotency_key': idem_key
    })
    
    # Second deposit with same key
    client.post(f'/api/v1/accounts/{account_id}/deposit', json={
        'amount': 200.00,
        'idempotency_key': idem_key
    })
    
    # Balance should only increase by 200 once
    balance_resp = client.get(f'/api/v1/accounts/{account_id}/balance')
    assert balance_resp.json()['balance'] == 1200.00

def test_deposit_negative_amount(client, create_usd_account):
    """Verify negative deposits are rejected. Deposit implies addition."""
    account_id = create_usd_account['id']
    response = client.post(f'/api/v1/accounts/{account_id}/deposit', json={
        'amount': -50.00
    })
    assert response.status_code == 422

def test_health_check(client):
    """Verify API health check endpoint. Important for load balancers."""
    response = client.get('/')
    assert response.status_code == 200
    assert 'PayFlow' in response.text or 'PayFlow' in str(response.json())
