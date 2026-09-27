"""Tests for balance consistency under rapid sequential operations.

These tests verify that the system maintains strict financial integrity
when processing many transactions in sequence. While using a synchronous
TestClient (not true concurrency), these validate that each individual
transaction correctly reads, modifies, and persists balances without
data loss — the foundation of any reliable payment system.
"""

from decimal import Decimal


def _dec(value) -> Decimal:
    """Convert JSON balance value (may be string or float) to Decimal for comparison."""
    return Decimal(str(value))


def test_concurrent_transfers_balance_consistency(client):
    """
    Verify that 100 sequential transfers of $100 correctly drain one account
    and fill another. Total money in the system must be conserved.

    In a real payment system, this pattern would be concurrent — here we verify
    the serial invariant holds, which is the baseline for correctness.
    """
    alice = client.post('/api/v1/accounts/', json={
        'owner_name': 'Alice Concurrency',
        'currency': 'USD',
        'initial_balance': 10000.00
    }).json()['id']
    bob = client.post('/api/v1/accounts/', json={
        'owner_name': 'Bob Concurrency',
        'currency': 'USD',
        'initial_balance': 0.00
    }).json()['id']

    # Fire 100 transfers of $100 each
    for i in range(100):
        resp = client.post('/api/v1/transfers/', json={
            'from_account_id': alice,
            'to_account_id': bob,
            'amount': 100.00
        })
        assert resp.status_code == 201, f"Transfer {i} failed: {resp.json()}"

    # Verify final balances
    alice_bal = _dec(client.get(f'/api/v1/accounts/{alice}/balance').json()['balance'])
    bob_bal = _dec(client.get(f'/api/v1/accounts/{bob}/balance').json()['balance'])

    assert alice_bal == Decimal('0.00'), f"Alice should be 0, got {alice_bal}"
    assert bob_bal == Decimal('10000.00'), f"Bob should be 10000, got {bob_bal}"
    # Conservation of money
    assert alice_bal + bob_bal == Decimal('10000.00')


def test_concurrent_deposits_balance_consistency(client):
    """
    Verify that 50 sequential deposits of $10 result in exactly $500.
    Ensures no deposit is lost or double-counted.
    """
    acc = client.post('/api/v1/accounts/', json={
        'owner_name': 'Deposit Concurrency',
        'currency': 'USD',
        'initial_balance': 0.00
    }).json()['id']

    # Fire 50 deposits of $10 each
    for i in range(50):
        resp = client.post(f'/api/v1/accounts/{acc}/deposit', json={
            'amount': 10.00
        })
        assert resp.status_code == 201, f"Deposit {i} failed: {resp.json()}"

    acc_bal = _dec(client.get(f'/api/v1/accounts/{acc}/balance').json()['balance'])
    assert acc_bal == Decimal('500.00'), f"Expected 500, got {acc_bal}"


def test_rapid_fire_mixed_operations(client):
    """
    Verify system handles mixed bidirectional transfers without losing funds.

    20 transfers Alice→Bob of $50, then 20 transfers Bob→Alice of $50.
    Net effect should be zero — both should end with their original $5000.
    """
    alice = client.post('/api/v1/accounts/', json={
        'owner_name': 'Alice Mixed',
        'currency': 'USD',
        'initial_balance': 5000.00
    }).json()['id']
    bob = client.post('/api/v1/accounts/', json={
        'owner_name': 'Bob Mixed',
        'currency': 'USD',
        'initial_balance': 5000.00
    }).json()['id']

    # 20 transfers Alice -> Bob
    for i in range(20):
        resp = client.post('/api/v1/transfers/', json={
            'from_account_id': alice,
            'to_account_id': bob,
            'amount': 50.00
        })
        assert resp.status_code == 201, f"A->B transfer {i} failed: {resp.json()}"

    # 20 transfers Bob -> Alice
    for i in range(20):
        resp = client.post('/api/v1/transfers/', json={
            'from_account_id': bob,
            'to_account_id': alice,
            'amount': 50.00
        })
        assert resp.status_code == 201, f"B->A transfer {i} failed: {resp.json()}"

    # Both should end up back at 5000
    alice_bal = _dec(client.get(f'/api/v1/accounts/{alice}/balance').json()['balance'])
    bob_bal = _dec(client.get(f'/api/v1/accounts/{bob}/balance').json()['balance'])

    assert alice_bal == Decimal('5000.00'), f"Alice should be 5000, got {alice_bal}"
    assert bob_bal == Decimal('5000.00'), f"Bob should be 5000, got {bob_bal}"
    # Conservation of money
    assert alice_bal + bob_bal == Decimal('10000.00')
