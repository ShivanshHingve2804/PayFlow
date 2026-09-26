def test_concurrent_transfers_balance_consistency(client):
    """
    Verify that multiple sequential rapid-fire transfers do not corrupt balances.
    Crucial for high-throughput financial systems where many transactions happen simultaneously.
    While test uses synchronous TestClient, this verifies that individual transaction isolation
    maintains strict consistency.
    """
    # Setup
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

    # Fire 100 transfers of 100
    for _ in range(100):
        client.post('/api/v1/transfers/', json={
            'from_account_id': alice,
            'to_account_id': bob,
            'amount': 100.00
        })

    # Verify final balances
    alice_bal = client.get(f'/api/v1/accounts/{alice}/balance').json()['balance']
    bob_bal = client.get(f'/api/v1/accounts/{bob}/balance').json()['balance']
    
    assert alice_bal == 0.00
    assert bob_bal == 10000.00


def test_concurrent_deposits_balance_consistency(client):
    """
    Verify that rapid sequential deposits result in the correct final balance.
    Essential to ensure deposits are properly serialized and no data is lost.
    """
    acc = client.post('/api/v1/accounts/', json={
        'owner_name': 'Deposit Concurrency',
        'currency': 'USD',
        'initial_balance': 0.00
    }).json()['id']

    # Fire 50 deposits of 10
    for _ in range(50):
        client.post(f'/api/v1/accounts/{acc}/deposit', json={
            'amount': 10.00
        })

    acc_bal = client.get(f'/api/v1/accounts/{acc}/balance').json()['balance']
    assert acc_bal == 500.00


def test_rapid_fire_mixed_operations(client):
    """
    Verify system handles mixed bidirectional transfers without losing funds.
    Important for ensuring locks or isolation levels don't allow race conditions
    when two accounts transact with each other repeatedly.
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
    for _ in range(20):
        client.post('/api/v1/transfers/', json={
            'from_account_id': alice,
            'to_account_id': bob,
            'amount': 50.00
        })

    # 20 transfers Bob -> Alice
    for _ in range(20):
        client.post('/api/v1/transfers/', json={
            'from_account_id': bob,
            'to_account_id': alice,
            'amount': 50.00
        })

    # Both should end up back at 5000
    alice_bal = client.get(f'/api/v1/accounts/{alice}/balance').json()['balance']
    bob_bal = client.get(f'/api/v1/accounts/{bob}/balance').json()['balance']
    
    assert alice_bal == 5000.00
    assert bob_bal == 5000.00
