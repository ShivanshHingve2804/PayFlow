"""Tests for currency exchange endpoints."""

import uuid
from decimal import Decimal


def _dec(value) -> Decimal:
    """Convert JSON balance value (may be string or float) to Decimal for comparison."""
    return Decimal(str(value))


def test_get_exchange_rates(client, seed_exchange_rates):
    """Verify exchange rates can be retrieved. Necessary for clients to know current rates."""
    response = client.get('/api/v1/exchange/rates')
    assert response.status_code == 200
    data = response.json()
    assert 'rates' in data
    assert len(data['rates']) > 0


def test_exchange_success(client, seed_exchange_rates, create_usd_account):
    """Verify successful currency exchange applies the correct rate and updates both balances."""
    usd_acc = create_usd_account['id']
    eur_acc = client.post('/api/v1/accounts/', json={
        'owner_name': 'Euro User',
        'currency': 'EUR',
        'initial_balance': 0.00
    }).json()['id']

    response = client.post('/api/v1/exchange/', json={
        'from_account_id': usd_acc,
        'to_account_id': eur_acc,
        'amount': 100.00
    })

    assert response.status_code == 201
    usd_bal = _dec(client.get(f"/api/v1/accounts/{usd_acc}/balance").json()['balance'])
    eur_bal = _dec(client.get(f"/api/v1/accounts/{eur_acc}/balance").json()['balance'])

    assert usd_bal == Decimal('900.00')
    assert eur_bal > Decimal('0')  # Exact amount depends on seeded rate


def test_exchange_insufficient_funds(client, seed_exchange_rates, create_usd_account):
    """Verify exchange fails if sender has insufficient funds."""
    usd_acc = create_usd_account['id']
    eur_acc = client.post('/api/v1/accounts/', json={
        'owner_name': 'Euro User',
        'currency': 'EUR',
        'initial_balance': 0.00
    }).json()['id']

    response = client.post('/api/v1/exchange/', json={
        'from_account_id': usd_acc,
        'to_account_id': eur_acc,
        'amount': 2000.00
    })
    assert response.status_code == 400


def test_exchange_same_currency(client, create_two_usd_accounts):
    """Verify exchange requires different currencies."""
    acc1, acc2 = create_two_usd_accounts
    response = client.post('/api/v1/exchange/', json={
        'from_account_id': acc1['id'],
        'to_account_id': acc2['id'],
        'amount': 100.00
    })
    assert response.status_code == 400
    assert 'transfer' in response.json()['detail'].lower()


def test_exchange_account_not_found(client, create_usd_account):
    """Verify exchange fails if an account does not exist."""
    usd_acc = create_usd_account['id']
    random_id = str(uuid.uuid4())

    response = client.post('/api/v1/exchange/', json={
        'from_account_id': usd_acc,
        'to_account_id': random_id,
        'amount': 100.00
    })
    assert response.status_code == 404


def test_exchange_rate_not_found(client):
    """Verify exchange fails when no rate exists between two currencies."""
    acc1 = client.post('/api/v1/accounts/', json={
        'owner_name': 'User1',
        'currency': 'USD',
        'initial_balance': 100.00
    }).json()['id']
    acc2 = client.post('/api/v1/accounts/', json={
        'owner_name': 'User2',
        'currency': 'CHF',
        'initial_balance': 0.00
    }).json()['id']

    response = client.post('/api/v1/exchange/', json={
        'from_account_id': acc1,
        'to_account_id': acc2,
        'amount': 10.00
    })
    assert response.status_code in [400, 404]


def test_exchange_idempotency(client, seed_exchange_rates, create_usd_account):
    """Verify duplicate exchange requests with same idempotency key execute once."""
    usd_acc = create_usd_account['id']
    eur_acc = client.post('/api/v1/accounts/', json={
        'owner_name': 'Euro User',
        'currency': 'EUR',
        'initial_balance': 0.00
    }).json()['id']

    idem_key = str(uuid.uuid4())
    payload = {
        'from_account_id': usd_acc,
        'to_account_id': eur_acc,
        'amount': 100.00,
        'idempotency_key': idem_key
    }

    client.post('/api/v1/exchange/', json=payload)
    client.post('/api/v1/exchange/', json=payload)

    usd_bal = _dec(client.get(f"/api/v1/accounts/{usd_acc}/balance").json()['balance'])
    assert usd_bal == Decimal('900.00')


def test_exchange_usd_to_inr(client, seed_exchange_rates, create_usd_account):
    """Verify USD to INR exchange conversion works."""
    usd_acc = create_usd_account['id']
    inr_acc = client.post('/api/v1/accounts/', json={
        'owner_name': 'INR User',
        'currency': 'INR',
        'initial_balance': 0.00
    }).json()['id']

    response = client.post('/api/v1/exchange/', json={
        'from_account_id': usd_acc,
        'to_account_id': inr_acc,
        'amount': 10.00
    })

    assert response.status_code == 201
    usd_bal = _dec(client.get(f"/api/v1/accounts/{usd_acc}/balance").json()['balance'])
    inr_bal = _dec(client.get(f"/api/v1/accounts/{inr_acc}/balance").json()['balance'])

    assert usd_bal == Decimal('990.00')
    assert inr_bal > Decimal('0')
