"""Tests for money transfer endpoints."""

import uuid
from decimal import Decimal


def _dec(value) -> Decimal:
    """Convert JSON balance value (may be string or float) to Decimal for comparison."""
    return Decimal(str(value))


def test_transfer_success(client, create_two_usd_accounts):
    """Verify valid transfer correctly updates both balances. Core money movement."""
    alice, bob = create_two_usd_accounts

    response = client.post('/api/v1/transfers/', json={
        'from_account_id': alice['id'],
        'to_account_id': bob['id'],
        'amount': 200.00
    })
    assert response.status_code == 201
    data = response.json()
    assert data['status'] == 'COMPLETED'
    assert _dec(data['amount']) == Decimal('200.00')

    alice_bal = _dec(client.get(f"/api/v1/accounts/{alice['id']}/balance").json()['balance'])
    bob_bal = _dec(client.get(f"/api/v1/accounts/{bob['id']}/balance").json()['balance'])
    assert alice_bal == Decimal('800.00')
    assert bob_bal == Decimal('1200.00')


def test_transfer_insufficient_funds(client, create_two_usd_accounts):
    """Verify transfer fails if sender has insufficient funds."""
    alice, bob = create_two_usd_accounts
    response = client.post('/api/v1/transfers/', json={
        'from_account_id': alice['id'],
        'to_account_id': bob['id'],
        'amount': 2000.00
    })
    assert response.status_code == 400


def test_transfer_to_self(client, create_usd_account):
    """Verify transferring to the same account is prevented."""
    acc_id = create_usd_account['id']
    response = client.post('/api/v1/transfers/', json={
        'from_account_id': acc_id,
        'to_account_id': acc_id,
        'amount': 100.00
    })
    assert response.status_code == 400


def test_transfer_account_not_found(client, create_usd_account):
    """Verify transfer fails if destination account doesn't exist."""
    acc_id = create_usd_account['id']
    random_id = str(uuid.uuid4())
    response = client.post('/api/v1/transfers/', json={
        'from_account_id': acc_id,
        'to_account_id': random_id,
        'amount': 100.00
    })
    assert response.status_code == 404


def test_transfer_currency_mismatch(client, create_usd_account):
    """Verify standard transfers enforce same-currency rule."""
    usd_acc = create_usd_account['id']
    eur_acc = client.post('/api/v1/accounts/', json={
        'owner_name': 'Euro User',
        'currency': 'EUR',
        'initial_balance': 1000.00
    }).json()['id']

    response = client.post('/api/v1/transfers/', json={
        'from_account_id': usd_acc,
        'to_account_id': eur_acc,
        'amount': 100.00
    })
    assert response.status_code == 400
    assert 'exchange' in response.json()['detail'].lower()


def test_transfer_idempotency(client, create_two_usd_accounts):
    """Verify duplicate transfers with same idempotency key don't execute twice."""
    alice, bob = create_two_usd_accounts
    idem_key = str(uuid.uuid4())

    payload = {
        'from_account_id': alice['id'],
        'to_account_id': bob['id'],
        'amount': 200.00,
        'idempotency_key': idem_key
    }

    res1 = client.post('/api/v1/transfers/', json=payload)
    res2 = client.post('/api/v1/transfers/', json=payload)

    assert res1.status_code == 201
    assert res2.status_code == 201

    alice_bal = _dec(client.get(f"/api/v1/accounts/{alice['id']}/balance").json()['balance'])
    assert alice_bal == Decimal('800.00')


def test_transfer_zero_amount(client, create_two_usd_accounts):
    """Verify zero amount transfers are rejected."""
    alice, bob = create_two_usd_accounts
    response = client.post('/api/v1/transfers/', json={
        'from_account_id': alice['id'],
        'to_account_id': bob['id'],
        'amount': 0.00
    })
    assert response.status_code == 422


def test_transfer_negative_amount(client, create_two_usd_accounts):
    """Verify negative amount transfers are rejected."""
    alice, bob = create_two_usd_accounts
    response = client.post('/api/v1/transfers/', json={
        'from_account_id': alice['id'],
        'to_account_id': bob['id'],
        'amount': -100.00
    })
    assert response.status_code == 422


def test_get_transfer_success(client, create_two_usd_accounts):
    """Verify retrieving a transfer by ID works."""
    alice, bob = create_two_usd_accounts
    transfer = client.post('/api/v1/transfers/', json={
        'from_account_id': alice['id'],
        'to_account_id': bob['id'],
        'amount': 200.00
    }).json()

    transfer_id = transfer['id']
    response = client.get(f'/api/v1/transfers/{transfer_id}')
    assert response.status_code == 200
    assert response.json()['id'] == transfer_id


def test_get_transfer_not_found(client):
    """Verify retrieving a non-existent transfer returns 404."""
    random_id = str(uuid.uuid4())
    response = client.get(f'/api/v1/transfers/{random_id}')
    assert response.status_code == 404


def test_multiple_transfers(client, create_two_usd_accounts):
    """Verify multiple subsequent transfers accumulate correctly."""
    alice, bob = create_two_usd_accounts
    for _ in range(3):
        client.post('/api/v1/transfers/', json={
            'from_account_id': alice['id'],
            'to_account_id': bob['id'],
            'amount': 100.00
        })

    alice_bal = _dec(client.get(f"/api/v1/accounts/{alice['id']}/balance").json()['balance'])
    bob_bal = _dec(client.get(f"/api/v1/accounts/{bob['id']}/balance").json()['balance'])

    assert alice_bal == Decimal('700.00')
    assert bob_bal == Decimal('1300.00')
